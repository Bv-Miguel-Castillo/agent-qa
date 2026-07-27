from __future__ import annotations

import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

from ...core.auth import token_validator
from ...integrations.azure_devops.client import AzureDevOpsClient
from ...utils import parse_steps_xml
from .models import CollectPlanDataInput


class CollectPlanDataService:
    def execute(self, payload: CollectPlanDataInput) -> dict:
        session = token_validator.build_authenticated_session(expected_email=payload.user_email)
        token_validator.authorize_tool("collect_plan_data", session.identity)
        client = AzureDevOpsClient(
            session.access_token,
            user_email=payload.user_email or session.identity.email,
        )
        project = client.encode_project(payload.project)
        plan_id = payload.test_plan_id
        evidence_dir = payload.evidence_dir or tempfile.mkdtemp(prefix="evidencias_bug_")
        os.makedirs(evidence_dir, exist_ok=True)

        # Phase 1 — plan details and suite list in parallel (both depend only on plan_id).
        with ThreadPoolExecutor(max_workers=2) as executor:
            plan_future = executor.submit(
                client.get,
                client.with_api_version(f"{project}/_apis/testplan/plans/{plan_id}"),
            )
            suites_future = executor.submit(
                client.get,
                client.with_api_version(f"{project}/_apis/testplan/Plans/{plan_id}/Suites"),
            )
            plan = plan_future.result()
            suites_resp = suites_future.result()

        plan_name = plan.get("name", "")
        hu_id = self._resolve_hu_id(client, project, plan_name)
        suite_ids = [suite.get("id") for suite in suites_resp.get("value", []) or []]

        counts = {
            "failed": 0,
            "passed": 0,
            "blocked": 0,
            "notApplicable": 0,
            "unspecified": 0,
        }

        # Phase 2 — fetch every suite's test points concurrently.
        def _fetch_suite_points(suite_id):
            points_resp = client.get(
                client.with_api_version(
                    f"{project}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestPoint"
                    "?includePointDetails=true"
                )
            )
            return suite_id, (points_resp.get("value", []) or [])

        if suite_ids:
            with ThreadPoolExecutor(max_workers=min(8, len(suite_ids))) as executor:
                suite_points = list(executor.map(_fetch_suite_points, suite_ids))
        else:
            suite_points = []

        # Phase 3 — count every point and gather the failed ones (no I/O).
        failed_points: list[tuple] = []
        for suite_id, points in suite_points:
            for point in points:
                outcome = ((point.get("results") or {}).get("outcome") or "").lower()
                if outcome.startswith("fail"):
                    counts["failed"] += 1
                elif outcome == "passed":
                    counts["passed"] += 1
                elif outcome.startswith("block"):
                    counts["blocked"] += 1
                elif outcome == "notapplicable":
                    counts["notApplicable"] += 1
                else:
                    counts["unspecified"] += 1
                if outcome.startswith("fail"):
                    failed_points.append((suite_id, point))

        # Phase 4 — build each failed case. The four detail calls per case run concurrently,
        # and the failed cases themselves are processed concurrently too.
        def _build_failed_case(job: tuple) -> dict:
            suite_id, point = job
            results = point.get("results") or {}
            run_id = results.get("lastTestRunId")
            result_id = results.get("lastResultId")
            tc_ref = point.get("testCaseReference") or {}
            tc_id = tc_ref.get("id")
            tc_name = tc_ref.get("name")

            with ThreadPoolExecutor(max_workers=4) as executor:
                tc_item_future = executor.submit(
                    client.get, client.with_api_version(f"{project}/_apis/wit/workItems/{tc_id}")
                )
                comment_future = executor.submit(
                    self._get_result_comment, client, project, run_id, result_id
                )
                bug_future = executor.submit(
                    self._get_existing_bug_id, client, project, tc_id
                )
                evidence_future = (
                    executor.submit(
                        self._get_evidence_urls, client, project, run_id, result_id, evidence_dir
                    )
                    if payload.include_evidence_upload
                    else None
                )
                tc_item = tc_item_future.result()
                comment = comment_future.result()
                existing_bug_id = bug_future.result()
                evidence_urls = evidence_future.result() if evidence_future else []

            tc_fields = tc_item.get("fields") or {}
            tc_name = tc_fields.get("System.Title") or tc_name
            steps = parse_steps_xml(tc_fields.get("Microsoft.VSTS.TCM.Steps"))
            return {
                "Suite": suite_id,
                "TcId": tc_id,
                "TcName": tc_name,
                "RunId": run_id,
                "ResultId": result_id,
                "Comment": comment,
                "ExistingBugId": existing_bug_id,
                "Steps": steps,
                "EvidenceUrls": evidence_urls,
            }

        if failed_points:
            with ThreadPoolExecutor(max_workers=min(6, len(failed_points))) as executor:
                failed_cases = list(executor.map(_build_failed_case, failed_points))
        else:
            failed_cases = []

        if not hu_id and failed_cases:
            hu_id = self._resolve_hu_id_from_tc_relations(client, project, failed_cases[0]["TcId"])
        hu = self._resolve_hu(client, project, hu_id)

        return {
            "PlanId": plan_id,
            "PlanName": plan_name,
            "Hu": hu,
            "Summary": counts,
            "FailedCases": failed_cases,
        }

    @staticmethod
    def _resolve_hu_id(client: AzureDevOpsClient, project: str, plan_name: str) -> str | None:
        match = re.search(r"#(\\d{4,})", plan_name or "")
        if match:
            return match.group(1)

        if not plan_name:
            return None

        search_title = plan_name
        title_match = re.search(r"\|\s*(.+)$", search_title)
        if title_match:
            search_title = title_match.group(1).strip()
        safe_title = (search_title or "").replace("'", "''")
        wiql = {
            "query": (
                "SELECT [System.Id] FROM WorkItems "
                "WHERE [System.WorkItemType] = 'User Story' "
                f"AND [System.Title] CONTAINS '{safe_title}'"
            )
        }
        result = client.post_json(client.with_api_version(f"{project}/_apis/wit/wiql"), wiql)
        items = result.get("workItems") or []
        return str(items[0].get("id")) if items else None

    @staticmethod
    def _resolve_hu_id_from_tc_relations(
        client: AzureDevOpsClient, project: str, test_case_id: int
    ) -> str | None:
        tc = client.get(
            client.with_api_version(f"{project}/_apis/wit/workItems/{test_case_id}?$expand=Relations")
        )
        for relation in tc.get("relations") or []:
            url = relation.get("url") or ""
            if "/workItems/" not in url:
                continue
            work_item_id = url.rsplit("/", 1)[-1]
            linked = client.get(client.with_api_version(f"{project}/_apis/wit/workItems/{work_item_id}"))
            work_item_type = ((linked.get("fields") or {}).get("System.WorkItemType") or "").lower()
            if work_item_type in {"user story", "product backlog item", "requirement"}:
                return str(work_item_id)
        return None

    @staticmethod
    def _resolve_hu(client: AzureDevOpsClient, project: str, hu_id: str | None) -> dict | None:
        if not hu_id:
            return None
        hu = client.get(client.with_api_version(f"{project}/_apis/wit/workItems/{hu_id}"))
        fields = hu.get("fields") or {}
        assigned = fields.get("System.AssignedTo") or {}
        assigned_to = assigned.get("uniqueName") or assigned.get("displayName")
        return {
            "Id": hu_id,
            "Title": fields.get("System.Title"),
            "AreaPath": fields.get("System.AreaPath"),
            "IterationPath": fields.get("System.IterationPath"),
            "AssignedTo": assigned_to,
        }

    @staticmethod
    def _get_result_comment(
        client: AzureDevOpsClient, project: str, run_id: int | None, result_id: int | None
    ) -> str:
        if not run_id or not result_id:
            return ""
        result = client.get(
            client.with_api_version(
                f"{project}/_apis/test/Runs/{run_id}/Results/{result_id}?detailsToInclude=Iterations"
            )
        )
        for iteration in result.get("iterationDetails") or []:
            comment = iteration.get("comment")
            if comment:
                return comment
        return result.get("comment") or ""

    def _get_evidence_urls(
        self,
        client: AzureDevOpsClient,
        project: str,
        run_id: int | None,
        result_id: int | None,
        evidence_dir: str,
    ) -> list[str]:
        if not run_id or not result_id:
            return []

        result_with_iterations = client.get(
            client.with_api_version(
                f"{project}/_apis/test/Runs/{run_id}/Results/{result_id}?detailsToInclude=Iterations"
            )
        )
        attachments = []
        for iteration in result_with_iterations.get("iterationDetails") or []:
            attachments.extend(iteration.get("attachments") or [])

        listed = client.get(
            client.with_api_version(
                f"{project}/_apis/test/Runs/{run_id}/Results/{result_id}/attachments"
            )
        )
        attachments.extend(listed.get("value") or [])

        urls = []
        allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

        for attachment in attachments:
            file_name = attachment.get("fileName") or attachment.get("name") or "evidence"
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in allowed_ext:
                continue
            attachment_id = attachment.get("id")
            if not attachment_id:
                continue

            blob = client.download(
                client.with_api_version(
                    f"{project}/_apis/test/Runs/{run_id}/Results/{result_id}/attachments/{attachment_id}"
                )
            )
            local_path = os.path.join(evidence_dir, file_name)
            with open(local_path, "wb") as file_obj:
                file_obj.write(blob)

            encoded_name = quote(file_name)
            uploaded = client.post_binary(
                client.with_api_version(f"{project}/_apis/wit/attachments?fileName={encoded_name}"),
                blob,
            )
            if uploaded.get("url"):
                urls.append(uploaded["url"])

        return urls

    @staticmethod
    def _get_existing_bug_id(client: AzureDevOpsClient, project: str, test_case_id: int) -> str | None:
        tc = client.get(
            client.with_api_version(f"{project}/_apis/wit/workItems/{test_case_id}?$expand=Relations")
        )
        for relation in tc.get("relations") or []:
            url = relation.get("url") or ""
            rel = relation.get("rel") or ""
            if rel != "System.LinkTypes.Related" or "/workItems/" not in url:
                continue
            bug_id = url.rsplit("/", 1)[-1]
            bug = client.get(client.with_api_version(f"{project}/_apis/wit/workItems/{bug_id}"))
            work_item_type = ((bug.get("fields") or {}).get("System.WorkItemType") or "").lower()
            if work_item_type == "bug":
                return str(bug_id)
        return None
