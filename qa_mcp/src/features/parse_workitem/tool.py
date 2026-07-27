from __future__ import annotations
from typing import Any

from mcp.server.fastmcp import FastMCP

from .models import ParseWorkitemInput
from .service import ParseWorkitemService


def register_parse_workitem(mcp: FastMCP) -> None:
    service = ParseWorkitemService()

    @mcp.tool(
        name="parse_workitem",
        description="Parses an Azure DevOps work item JSON and returns a flat object with cleaned Description, Acceptance Criteria and extracted attachments.",
    )
    def parse_workitem(work_item: dict[str, Any]) -> dict:
        payload = ParseWorkitemInput(work_item=work_item)
        return service.execute(payload)
 