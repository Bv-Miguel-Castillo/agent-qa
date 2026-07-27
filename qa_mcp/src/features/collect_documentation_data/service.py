from __future__ import annotations

import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import quote

from ...core.auth import token_validator
from ...integrations.azure_devops.client import AzureDevOpsClient
from ...utils import clean_html, safe_file_slug
from .models import CollectDocumentationDataInput


class CollectDocumentationDataService:
    async def execute(self, payload: CollectDocumentationDataInput) -> dict:
        session = await token_validator.build_authenticated_session(expected_email=payload.user_email)
        token_validator.authorize_tool("collect_documentation_data", session.identity)
        client = AzureDevOpsClient(
            session.access_token,
            user_email=payload.user_email or session.identity.email,
        )
        project = client.encode_project(payload.project)
        plan_id = payload.test_plan_id

        evidence_dir = payload.evidence_dir or tempfile.mkdtemp(prefix="evidencias_doc_")
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
        suite_values = suites_resp.get("value", []) or []

        # Phase 2 — resolve the User Story and collect all suites/cases in parallel
        # (two independent I/O chains).
        with ThreadPoolExecutor(max_workers=2) as executor:
            hu_future = executor.submit(self._resolve_hu_full, client, project, plan_name)
            suites_future = executor.submit(
                self._collect_suites,
                client,
                project,
                plan_id,
                suite_values,
                payload.include_evidence,
                evidence_dir,
            )
            hu = hu_future.result()
            suites, counts = suites_future.result()

        result = {
            "PlanId": plan_id,
            "PlanName": plan_name,
            "GeneratedDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "Hu": hu,
            "Summary": counts,
            "Suites": suites,
        }

        # Persist the collected data to a temp JSON so the Word builder can consume it directly,
        # without the agent having to re-serialize the whole payload in a shell command.
        data_json_path = os.path.join(tempfile.gettempdir(), f"plan_{plan_id}_data.json")
        with open(data_json_path, "w", encoding="utf-8") as data_file:
            json.dump(result, data_file, ensure_ascii=False, indent=2)
        result["DataJsonPath"] = data_json_path

        return result

    def _resolve_hu_full(
        self, client: AzureDevOpsClient, project: str, plan_name: str
    ) -> dict | None:
        hu_id = self._resolve_hu_id(client, project, plan_name)
        return self._resolve_hu(client, project, hu_id)

    def _collect_suites(
        self,
        client: AzureDevOpsClient,
        project: str,
        plan_id: int,
        suite_values: list,
        include_evidence: bool,
        evidence_dir: str,
    ) -> tuple[list, dict]:
        suites: list = []
        counts = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "notApplicable": 0,
            "unspecified": 0,
        }

        # 1) Fetch every suite's test points concurrently (I/O-bound REST calls).
        def _fetch_suite_points(suite: dict) -> tuple[dict, list]:
            suite_id = suite.get("id")
            points_resp = client.get(
                client.with_api_version(
                    f"{project}/_apis/testplan/Plans/{plan_id}/Suites/{suite_id}/TestPoint"
                    "?includePointDetails=true"
                )
            )
            return suite, (points_resp.get("value", []) or [])

        if suite_values:
            with ThreadPoolExecutor(max_workers=min(8, len(suite_values))) as executor:
                suite_points = list(executor.map(_fetch_suite_points, suite_values))
        else:
            suite_points = []

        # 2) Fetch result info (comment + evidence) for every executed point concurrently.
        result_targets: dict[tuple[int, int], str] = {}
        for _suite, points in suite_points:
            for point in points:
                results = point.get("results") or {}
                run_id = results.get("lastTestRunId")
                result_id = results.get("lastResultId")
                if run_id and result_id:
                    result_targets[(run_id, result_id)] = (
                        (point.get("testCaseReference") or {}).get("name") or ""
                    )

        def _fetch_result_info(job: tuple[int, int, str]):
            run_id, result_id, case_name = job
            info = self._get_result_info(
                client=client,
                project=project,
                run_id=run_id,
                result_id=result_id,
                case_name=case_name,
                include_evidence=include_evidence,
                evidence_dir=evidence_dir,
            )
            return (run_id, result_id), info

        result_info_map: dict[tuple[int, int], tuple[str, list]] = {}
        if result_targets:
            jobs = [(rid, resid, name) for (rid, resid), name in result_targets.items()]
            with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as executor:
                for key, info in executor.map(_fetch_result_info, jobs):
                    result_info_map[key] = info

        # 3) Build suites + counts (pure in-memory work, no I/O).
        for suite, points in suite_points:
            cases = []
            for point in points:
                results = point.get("results") or {}
                outcome = (results.get("outcome") or "").lower()
                counts["total"] += 1
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

                run_id = results.get("lastTestRunId")
                result_id = results.get("lastResultId")
                comment, evidence_paths = "", []
                if run_id and result_id:
                    comment, evidence_paths = result_info_map.get((run_id, result_id), ("", []))

                cases.append(
                    {
                        "TcId": (point.get("testCaseReference") or {}).get("id"),
                        "TcName": ((point.get("testCaseReference") or {}).get("name") or ""),
                        "Outcome": results.get("outcome"),
                        "Comment": comment,
                        "EvidencePaths": evidence_paths,
                    }
                )

            suites.append(
                {
                    "SuiteId": suite.get("id"),
                    "SuiteName": suite.get("name"),
                    "Cases": cases,
                }
            )

        pass_rate = round((counts["passed"] / counts["total"]) * 100, 1) if counts["total"] else 0.0
        counts["passRate"] = pass_rate
        return suites, counts

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
        if not items:
            return None
        return str(items[0].get("id"))

    @staticmethod
    def _resolve_hu(client: AzureDevOpsClient, project: str, hu_id: str | None) -> dict | None:
        if not hu_id:
            return None
        work_item = client.get(client.with_api_version(f"{project}/_apis/wit/workItems/{hu_id}"))
        fields = work_item.get("fields") or {}
        assigned = fields.get("System.AssignedTo") or {}
        assigned_to = assigned.get("displayName") or assigned.get("uniqueName")
        return {
            "Id": hu_id,
            "Title": fields.get("System.Title"),
            "Description": clean_html(fields.get("System.Description")),
            "AcceptanceCriteria": clean_html(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria")),
            "AreaPath": fields.get("System.AreaPath"),
            "IterationPath": fields.get("System.IterationPath"),
            "AssignedTo": assigned_to,
        }

    def _get_result_info(
        self,
        *,
        client: AzureDevOpsClient,
        project: str,
        run_id: int,
        result_id: int,
        case_name: str,
        include_evidence: bool,
        evidence_dir: str,
    ) -> tuple[str, list[str]]:
        response = client.get(
            client.with_api_version(
                f"{project}/_apis/test/Runs/{run_id}/Results/{result_id}?detailsToInclude=Iterations"
            )
        )
        comment = ""
        for iteration in response.get("iterationDetails") or []:
            if iteration.get("comment"):
                comment = iteration.get("comment")
                break
        if not comment:
            comment = response.get("comment") or ""

        if not include_evidence:
            return comment, []

        attachments = []
        for iteration in response.get("iterationDetails") or []:
            attachments.extend(iteration.get("attachments") or [])

        allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
        downloaded: list[str] = []
        for attachment in attachments:
            name = attachment.get("fileName") or attachment.get("name") or "evidence"
            ext = os.path.splitext(name)[1].lower()
            if ext not in allowed_ext:
                continue

            local_name = f"{result_id}_{attachment.get('id')}_{safe_file_slug(case_name)}{ext}"
            local_path = os.path.join(evidence_dir, local_name)
            blob = client.download(
                client.with_api_version(
                    f"{project}/_apis/test/Runs/{run_id}/Results/{result_id}/attachments/{attachment.get('id')}"
                )
            )
            with open(local_path, "wb") as file_obj:
                file_obj.write(blob)
            downloaded.append(local_path)

        return comment, downloaded

