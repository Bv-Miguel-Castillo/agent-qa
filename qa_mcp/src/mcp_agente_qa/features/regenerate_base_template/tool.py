from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .models import RegenerateBaseTemplateInput
from .service import RegenerateBaseTemplateService


def register_regenerate_base_template(mcp: FastMCP) -> None:
    service = RegenerateBaseTemplateService()

    @mcp.tool(name="regenerate_base_template",
              description="Creates a clean DOCX base template by removing previously generated sections while preserving the document structure and formatting. Use this tool when you need to reset a Word document template before generating new content."
            )
    
    def regenerate_base_template(source_docx: str, output_docx: str) -> dict:
        payload = RegenerateBaseTemplateInput(source_docx=source_docx, output_docx=output_docx)
        return service.execute(payload)
