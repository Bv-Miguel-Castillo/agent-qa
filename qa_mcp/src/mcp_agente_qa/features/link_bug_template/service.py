from __future__ import annotations

from ...core.auth import token_validator
from ...integrations.azure_devops.client import AzureDevOpsClient
from .models import LinkBugTemplateInput


class LinkBugTemplateService:
    def execute(self, payload: LinkBugTemplateInput, context_access_token: str | None = None) -> dict:
        session = token_validator.build_authenticated_session(
            payload.access_token,
            context_access_token=context_access_token,
            expected_email=payload.user_email,
        )
        token_validator.authorize_tool("link_bug_template", session.identity)
        client = AzureDevOpsClient(
            session.access_token,
            user_email=payload.user_email or session.identity.email,
        )
        project = client.encode_project(payload.project)

        action = payload.action.lower().strip()
        if action not in {"link", "create", "update", "create_or_update"}:
            raise ValueError("action must be one of: link, create, update, create_or_update")

        effective_bug_id = payload.bug_id
        if action in {"create", "create_or_update"} and not effective_bug_id:
            effective_bug_id = self._create_bug(client, project, payload)

        if action in {"update", "create_or_update"} and effective_bug_id:
            self._update_bug(client, project, int(effective_bug_id), payload)

        if action == "link":
            if not effective_bug_id:
                raise ValueError("bug_id is required for action=link")

        result = {
            "bug_id": int(effective_bug_id) if effective_bug_id else None,
            "action": action,
            "linked_to_hu": False,
            "linked_to_test_case": False,
        }

        if effective_bug_id and payload.hu_id:
            self._link_bug_to_hu(client, project, int(effective_bug_id), int(payload.hu_id), payload.test_plan_id)
            result["linked_to_hu"] = True

        if effective_bug_id and payload.test_case_id:
            self._link_bug_to_test_case(client, project, int(effective_bug_id), int(payload.test_case_id))
            result["linked_to_test_case"] = True

        return result

    @staticmethod
    def _create_bug(client: AzureDevOpsClient, project: str, payload: LinkBugTemplateInput) -> int:
        patch = [
            {"op": "add", "path": "/fields/System.Title", "value": payload.title or "Bug sin titulo"},
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.TCM.ReproSteps",
                "value": payload.repro_steps_html or "<p>Sin pasos de reproduccion.</p>",
            },
        ]
        if payload.area_path:
            patch.append({"op": "add", "path": "/fields/System.AreaPath", "value": payload.area_path})
        if payload.iteration_path:
            patch.append(
                {"op": "add", "path": "/fields/System.IterationPath", "value": payload.iteration_path}
            )
        if payload.assigned_to:
            patch.append({"op": "add", "path": "/fields/System.AssignedTo", "value": payload.assigned_to})
        if payload.tags:
            patch.append({"op": "add", "path": "/fields/System.Tags", "value": payload.tags})
        if payload.effort is not None:
            patch.append({"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.Effort", "value": payload.effort})

        created = client.post_json(
            client.with_api_version(f"{project}/_apis/wit/workitems/$Bug"),
            patch,
            content_type="application/json-patch+json",
        )
        return int(created["id"])

    @staticmethod
    def _update_bug(client: AzureDevOpsClient, project: str, bug_id: int, payload: LinkBugTemplateInput) -> None:
        patch = []
        if payload.title:
            patch.append({"op": "add", "path": "/fields/System.Title", "value": payload.title})
        if payload.repro_steps_html:
            patch.append(
                {
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.TCM.ReproSteps",
                    "value": payload.repro_steps_html,
                }
            )
        if payload.area_path:
            patch.append({"op": "add", "path": "/fields/System.AreaPath", "value": payload.area_path})
        if payload.iteration_path:
            patch.append(
                {"op": "add", "path": "/fields/System.IterationPath", "value": payload.iteration_path}
            )
        if payload.assigned_to:
            patch.append({"op": "add", "path": "/fields/System.AssignedTo", "value": payload.assigned_to})
        if payload.tags:
            patch.append({"op": "add", "path": "/fields/System.Tags", "value": payload.tags})
        if payload.effort is not None:
            patch.append({"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.Effort", "value": payload.effort})
        if not patch:
            return

        client.patch_json(
            client.with_api_version(f"{project}/_apis/wit/workItems/{bug_id}"),
            patch,
            content_type="application/json-patch+json",
        )

    @staticmethod
    def _link_bug_to_hu(
        client: AzureDevOpsClient, project: str, bug_id: int, hu_id: int, test_plan_id: int | None
    ) -> None:
        project_meta = client.get(client.with_api_version(f"_apis/projects/{project}"))
        project_id = project_meta.get("id")
        comment = "Bug generated from failed test case"
        if test_plan_id:
            comment += f" in plan {test_plan_id}"

        relation_patch = [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": f"https://dev.azure.com/{client._base_url.rstrip('/').rsplit('/', 1)[-1]}/{project_id}/_apis/wit/workItems/{hu_id}",
                    "attributes": {"comment": comment},
                },
            }
        ]
        client.patch_json(
            client.with_api_version(f"{project}/_apis/wit/workItems/{bug_id}"),
            relation_patch,
            content_type="application/json-patch+json",
        )

    @staticmethod
    def _link_bug_to_test_case(client: AzureDevOpsClient, project: str, bug_id: int, test_case_id: int) -> None:
        relation_patch = [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Related",
                    "url": f"{client._base_url}/{project}/_apis/wit/workItems/{test_case_id}",
                    "attributes": {"comment": "Linked from MCP Agente QA"},
                },
            }
        ]
        client.patch_json(
            client.with_api_version(f"{project}/_apis/wit/workItems/{bug_id}"),
            relation_patch,
            content_type="application/json-patch+json",
        )
