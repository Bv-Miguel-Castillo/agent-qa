from __future__ import annotations

import os
import shutil
import tempfile
import xml.etree.ElementTree as et
import zipfile

from .models import RegenerateBaseTemplateInput


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


class RegenerateBaseTemplateService:
    def execute(self, payload: RegenerateBaseTemplateInput) -> dict:
        if not os.path.exists(payload.source_docx):
            raise FileNotFoundError(f"Source docx not found: {payload.source_docx}")

        os.makedirs(os.path.dirname(payload.output_docx) or ".", exist_ok=True)
        shutil.copyfile(payload.source_docx, payload.output_docx)

        with zipfile.ZipFile(payload.output_docx, "r") as zip_read:
            document_xml = zip_read.read("word/document.xml")

        root = et.fromstring(document_xml)
        body = root.find("w:body", NS)
        if body is None:
            return {"output_docx": payload.output_docx, "removed": 0, "cut_index": -1}

        children = list(body)
        cut_index = -1
        for idx, node in enumerate(children):
            if node.tag != f"{{{W_NS}}}p":
                continue
            style = node.find(".//w:pStyle", NS)
            all_text = "".join(text_node.text or "" for text_node in node.findall(".//w:t", NS))
            style_val = style.attrib.get(f"{{{W_NS}}}val", "") if style is not None else ""
            if style_val.startswith("Ttulo") and all_text.strip():
                cut_index = idx
                break

        final_sect_pr = body.find("w:sectPr", NS)
        removed = 0
        if cut_index >= 0:
            for idx in range(len(children) - 1, cut_index - 1, -1):
                node = children[idx]
                if final_sect_pr is not None and node is final_sect_pr:
                    continue
                body.remove(node)
                removed += 1

        new_xml = et.tostring(root, encoding="utf-8", xml_declaration=True)

        temp_fd, temp_path = tempfile.mkstemp(suffix=".docx")
        os.close(temp_fd)
        try:
            with zipfile.ZipFile(payload.output_docx, "r") as source_zip:
                with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as target_zip:
                    for item in source_zip.infolist():
                        if item.filename == "word/document.xml":
                            target_zip.writestr(item, new_xml)
                        else:
                            target_zip.writestr(item, source_zip.read(item.filename))
            shutil.move(temp_path, payload.output_docx)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return {
            "output_docx": payload.output_docx,
            "removed": removed,
            "cut_index": cut_index,
        }
