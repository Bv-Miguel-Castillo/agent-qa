from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .models import LinkBugTemplateInput
from .service import LinkBugTemplateService


def register_link_bug_template(mcp: FastMCP) -> None:
    service = LinkBugTemplateService()

    @mcp.tool(name="link_bug_template",
              description="Manages Azure DevOps Bug work items by creating, updating, and linking defects to User Stories and Test Cases. Use this tool to register test failures as bugs, maintain defect information, and establish QA traceability relationships."
            )
    
    def link_bug_template(
        project: str,
        user_email: str | None = None,
        action: str = "link",
        bug_id: int | None = None,
        hu_id: int | None = None,
        test_plan_id: int | None = None,
        title: str | None = None,
        repro_steps_html: str | None = None,
        area_path: str | None = None,
        iteration_path: str | None = None,
        assigned_to: str | None = None,
        tags: str | None = None,
        effort: float | int | None = None,
        test_case_id: int | None = None,
    ) -> dict:
        payload = LinkBugTemplateInput(
            user_email=user_email,
            project=project,
            action=action,
            bug_id=bug_id,
            hu_id=hu_id,
            test_plan_id=test_plan_id,
            title=title,
            repro_steps_html=repro_steps_html,
            area_path=area_path,
            iteration_path=iteration_path,
            assigned_to=assigned_to,
            tags=tags,
            effort=effort,
            test_case_id=test_case_id,
        )
        return service.execute(payload)
