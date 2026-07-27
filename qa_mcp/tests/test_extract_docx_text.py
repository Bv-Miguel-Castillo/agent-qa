from pathlib import Path
from zipfile import ZipFile

from features.extract_docx_text.models import ExtractDocxTextInput
from features.extract_docx_text.service import ExtractDocxTextService


def test_extract_docx_text_success(tmp_path: Path) -> None:
    docx_path = tmp_path / "sample.docx"
    with ZipFile(docx_path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
            "<w:body><w:p><w:r><w:t>Hola QA</w:t></w:r></w:p></w:body></w:document>",
        )

    service = ExtractDocxTextService()
    result = service.execute(ExtractDocxTextInput(file_path=str(docx_path)))

    assert result["success"] is True
    assert "Hola QA" in result["text"]


def test_extract_docx_text_failure(tmp_path: Path) -> None:
    service = ExtractDocxTextService()
    result = service.execute(ExtractDocxTextInput(file_path=str(tmp_path / "missing.docx")))
    assert result["success"] is False
