from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .models import CollectPlanDataInput
from .service import CollectPlanDataService


def register_collect_plan_data(mcp: FastMCP) -> None:
    service = CollectPlanDataService()

    @mcp.tool(
        name="collect_plan_data",
        description="Retrieves failed test case information from an Azure DevOps Test Plan, including related User Story details, test steps, execution comments, linked bugs, and optional evidence attachments. Use this tool to analyze test failures, prepare defect reports, and generate QA documentation from failed executions.",
    )
    async def collect_plan_data(
        project: str,
        test_plan_id: int,
        user_email: str | None = None,
        include_evidence_upload: bool = True,
        evidence_dir: str | None = None,
    ) -> dict:
        payload = CollectPlanDataInput(
            user_email=user_email,
            project=project,
            test_plan_id=test_plan_id,
            include_evidence_upload=include_evidence_upload,
            evidence_dir=evidence_dir,
        )
        return await service.execute(payload)
