from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .models import ExtractDocxTextInput
from .service import ExtractDocxTextService


def register_extract_docx_text(mcp: FastMCP) -> None:
    service = ExtractDocxTextService()

    @mcp.tool(name="extract_docx_text",
              description="Extracts clean text from DOCX files and returns it in a structured format. Use this tool when you need to process, analyze, summarize, or retrieve the content of a Microsoft Word document."
            )
    
    def extract_docx_text(file_path: str) -> dict:
        payload = ExtractDocxTextInput(file_path=file_path)
        return service.execute(payload)
