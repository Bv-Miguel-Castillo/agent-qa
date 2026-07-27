from tool_mapping import TOOL_MAPPING


def test_mapping_is_one_to_one() -> None:
    # Each source script maps to a distinct MCP tool (1:1). The original .ps1 files were
    # removed once their logic was ported to the MCP tools, so this no longer checks the disk.
    assert len(set(TOOL_MAPPING.values())) == len(TOOL_MAPPING)


def test_expected_tools_are_present() -> None:
    expected = {
        "collect_documentation_data",
        "regenerate_base_template",
        "collect_plan_data",
        "link_bug_template",
        "extract_docx_text",
        "parse_workitem",
    }
    assert set(TOOL_MAPPING.values()) == expected


def test_parse_workitem_script_mapping() -> None:
    assert (
        TOOL_MAPPING[".github/skills/read-user-story/assets/parse_workitem.ps1"]
        == "parse_workitem"
    )
