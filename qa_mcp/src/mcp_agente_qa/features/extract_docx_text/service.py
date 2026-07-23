from __future__ import annotations

import re
import zipfile

from .models import ExtractDocxTextInput


class ExtractDocxTextService:
    def execute(self, payload: ExtractDocxTextInput) -> dict:
        try:
            with zipfile.ZipFile(payload.file_path, "r") as archive:
                xml_raw = archive.read("word/document.xml").decode("utf-8", errors="ignore")
            text = re.sub(r"<[^>]+>", " ", xml_raw)
            text = re.sub(r"\\s{2,}", " ", text).strip()
            return {"text": text, "success": True}
        except Exception:
            return {"text": "No se pudo extraer texto del archivo Word.", "success": False}
