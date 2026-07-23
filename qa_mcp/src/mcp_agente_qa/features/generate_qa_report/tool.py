from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from ...core.auth import extract_bearer_token_from_context

from .models import GenerateQaReportInput
from .service import GenerateQaReportService


def register_generate_qa_report(mcp: FastMCP) -> None:
    service = GenerateQaReportService()

    @mcp.tool(
        name="generate_qa_report",
        description=(
            "Generates the final QA Word (.docx) report for an Azure DevOps Test Plan. It collects "
            "the plan data (User Story, suites, cases, results, execution summary and evidence) and "
            "builds the formatted report using the corporate template, entirely server-side. Returns "
            "the document as base64 (field 'ContentBase64') plus 'FileName' and a summary. The client "
            "should decode 'ContentBase64' and save it as 'FileName'. No local commands are required."
        ),
    )
    def generate_qa_report(
        project: str,
        test_plan_id: int,
        user_email: str | None = None,
        access_token: str | None = None,
        include_evidence: bool = True,
        report_date: str | None = None,
        ctx: Context | None = None,
    ) -> dict:
        context_access_token = extract_bearer_token_from_context(ctx)
        payload = GenerateQaReportInput(
            user_email=user_email,
            access_token=access_token,
            project=project,
            test_plan_id=test_plan_id,
            include_evidence=include_evidence,
            report_date=report_date,
        )
        return service.execute(payload, context_access_token=context_access_token)
