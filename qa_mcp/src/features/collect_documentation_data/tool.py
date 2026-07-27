from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .models import CollectDocumentationDataInput
from .service import CollectDocumentationDataService


def register_collect_documentation_data(mcp: FastMCP) -> None:
    service = CollectDocumentationDataService()

    @mcp.tool(name="collect_documentation_data",
              description="Collects comprehensive documentation data from an Azure DevOps Test Plan. Retrieves the associated User Story, including its title, description, acceptance criteria, assignment, and metadata, then gathers all test suites, test cases, execution results, comments, execution summary metrics, and optionally downloads image-based test evidence. Returns a structured JSON object suitable for generating QA reports, release documentation, traceability artifacts, or other test documentation."
              )
    
    def collect_documentation_data(
        project: str,
        test_plan_id: int,
        user_email: str | None = None,
        include_evidence: bool = True,
        evidence_dir: str | None = None,
    ) -> dict:
        payload = CollectDocumentationDataInput(
            user_email=user_email,
            project=project,
            test_plan_id=test_plan_id,
            include_evidence=include_evidence,
            evidence_dir=evidence_dir,
        )
        return service.execute(payload)
