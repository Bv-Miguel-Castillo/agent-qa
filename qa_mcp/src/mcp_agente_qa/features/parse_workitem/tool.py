from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .models import ParseWorkitemInput
from .service import ParseWorkitemService


def register_parse_workitem(mcp: FastMCP) -> None:
    service = ParseWorkitemService()

    @mcp.tool(
        name="parse_workitem",
        description="Parses a local Azure DevOps work item JSON file and returns a flat object with cleaned Description/AcceptanceCriteria and extracted attachments.",
    )
    def parse_workitem(file_path: str) -> dict:
        payload = ParseWorkitemInput(file_path=file_path)
        return service.execute(payload)
