from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from ...core.auth import extract_bearer_token_from_context

from .models import CollectPlanDataInput
from .service import CollectPlanDataService


def register_collect_plan_data(mcp: FastMCP) -> None:
    service = CollectPlanDataService()

    @mcp.tool(name="collect_plan_data",
              description="Retrieves failed test case information from an Azure DevOps Test Plan, including related User Story details, test steps, execution comments, linked bugs, and optional evidence attachments. Use this tool to analyze test failures, prepare defect reports, and generate QA documentation from failed executions."
            )
    
    def collect_plan_data(
        project: str,
        test_plan_id: int,
        user_email: str | None = None,
        access_token: str | None = None,
        include_evidence_upload: bool = True,
        evidence_dir: str | None = None,
        ctx: Context | None = None,
    ) -> dict:
        context_access_token = extract_bearer_token_from_context(ctx)
        payload = CollectPlanDataInput(
            user_email=user_email,
            access_token=access_token,
            project=project,
            test_plan_id=test_plan_id,
            include_evidence_upload=include_evidence_upload,
            evidence_dir=evidence_dir,
        )
        return service.execute(payload, context_access_token=context_access_token)
