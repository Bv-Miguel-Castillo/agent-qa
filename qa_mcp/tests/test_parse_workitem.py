import json
from pathlib import Path

from features.parse_workitem.models import ParseWorkitemInput
from features.parse_workitem.service import ParseWorkitemService


def test_parse_workitem_success(tmp_path: Path) -> None:
    work_item = {
        "fields": {
            "System.Id": 12345,
            "System.Title": "HU - Validar login",
            "System.State": "Active",
            "System.AssignedTo": {"displayName": "Ana QA"},
            "System.AreaPath": "Proyecto\\Area",
            "System.IterationPath": "Proyecto\\Sprint 1",
            "System.WorkItemType": "User Story",
            "System.Description": "<div>Linea 1<br>Linea 2</div><ul><li>Uno</li><li>Dos</li></ul>",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "<p>Criterio&nbsp;A</p><p>Criterio B</p>",
        },
        "relations": [
            {
                "rel": "AttachedFile",
                "url": "https://dev.azure.com/org/proj/_apis/wit/attachments/ATTACH-001",
                "attributes": {"name": "evidencia.png", "resourceSize": 2048},
            },
            {
                "rel": "System.LinkTypes.Related",
                "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/10",
                "attributes": {"name": "No adjunto", "resourceSize": 10},
            },
        ],
    }

    json_path = tmp_path / "workitem.json"
    json_path.write_text(json.dumps(work_item), encoding="utf-8")

    service = ParseWorkitemService()
    result = service.execute(ParseWorkitemInput(file_path=str(json_path)))

    assert result["Id"] == 12345
    assert result["Title"] == "HU - Validar login"
    assert result["AssignedTo"] == "Ana QA"
    assert result["Description"] == "Linea 1\nLinea 2\n- Uno\n- Dos"
    assert result["AcceptanceCriteria"] == "Criterio A\nCriterio B"
    assert result["Attachments"] == [
        {"Name": "evidencia.png", "SizeKB": 2.0, "Id": "ATTACH-001"}
    ]


def test_parse_workitem_optional_assigned_to_and_missing_fields(tmp_path: Path) -> None:
    work_item = {
        "fields": {
            "System.Id": "54321",
            "System.Title": "HU sin asignado",
            "System.State": "New",
            "System.AssignedTo": {"uniqueName": "qa@contoso.com"},
            "System.Description": None,
            "Microsoft.VSTS.Common.AcceptanceCriteria": "",
        },
        "relations": [
            {
                "rel": "AttachedFile",
                "url": "https://example/attachments/ABC",
                "attributes": {"name": "archivo.bin"},
            }
        ],
    }

    json_path = tmp_path / "workitem_optional.json"
    json_path.write_text(json.dumps(work_item), encoding="utf-8")

    service = ParseWorkitemService()
    result = service.execute(ParseWorkitemInput(file_path=str(json_path)))

    assert result["Id"] == 54321
    assert result["AssignedTo"] == "qa@contoso.com"
    assert result["AreaPath"] == ""
    assert result["IterationPath"] == ""
    assert result["WorkItemType"] == ""
    assert result["Description"] == ""
    assert result["AcceptanceCriteria"] == ""
    assert result["Attachments"] == [{"Name": "archivo.bin", "SizeKB": 0.0, "Id": "ABC"}]
