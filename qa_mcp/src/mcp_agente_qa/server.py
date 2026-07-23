from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .core.config import settings
from .features.collect_documentation_data.tool import register_collect_documentation_data
from .features.collect_plan_data.tool import register_collect_plan_data
from .features.extract_docx_text.tool import register_extract_docx_text
from .features.generate_qa_report.tool import register_generate_qa_report
from .features.link_bug_template.tool import register_link_bug_template
from .features.parse_workitem.tool import register_parse_workitem
from .features.regenerate_base_template.tool import register_regenerate_base_template


def create_server() -> FastMCP:
    mcp = FastMCP(
        "MCP Agente QA",
        host="0.0.0.0",
        port=8000,
        mount_path="/",
        streamable_http_path="/mcp",
    )

    register_collect_documentation_data(mcp)
    register_regenerate_base_template(mcp)
    register_collect_plan_data(mcp)
    register_link_bug_template(mcp)
    register_extract_docx_text(mcp)
    register_generate_qa_report(mcp)
    register_parse_workitem(mcp)
    return mcp


def main() -> None:
    server = create_server()
    server.run(transport=settings.transport)


if __name__ == "__main__":
    main()
