from pathlib import Path
from zipfile import ZipFile

from mcp_agente_qa.features.regenerate_base_template.models import RegenerateBaseTemplateInput
from mcp_agente_qa.features.regenerate_base_template.service import RegenerateBaseTemplateService


def _make_minimal_docx(path: Path) -> None:
    content_types = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>
  <Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>
  <Default Extension='xml' ContentType='application/xml'/>
  <Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>
</Types>"""
    rels = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
  <Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/>
</Relationships>"""
    document = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
  <w:body>
    <w:p><w:pPr><w:pStyle w:val='Normal'/></w:pPr><w:r><w:t>Keep</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val='Ttulo1'/></w:pPr><w:r><w:t>Cut here</w:t></w:r></w:p>
    <w:p><w:r><w:t>Remove me</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>"""
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)


def test_regenerate_base_template_removes_body_after_title(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    output = tmp_path / "output.docx"
    _make_minimal_docx(source)

    service = RegenerateBaseTemplateService()
    result = service.execute(RegenerateBaseTemplateInput(source_docx=str(source), output_docx=str(output)))

    assert output.exists()
    assert result["removed"] >= 1
