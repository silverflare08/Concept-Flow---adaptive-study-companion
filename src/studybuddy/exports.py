"""Reusable multi-format exports for saved ConceptFlow learning work."""

from __future__ import annotations

from io import BytesIO
import json
import re
from textwrap import wrap
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from fastapi import Response


EXPORT_FORMATS = {"md", "txt", "pdf", "docx", "json"}


def clean_export_text(value: object) -> str:
    """Turn model-flavoured Markdown/LaTeX into calm reader-facing text."""
    text = str(value).replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "")
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1) / (\2)", text)
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", text)
    for command, symbol in {
        r"\times": "x", r"\cdot": "·", r"\div": "/", r"\pm": "+/-",
        r"\leq": "<=", r"\geq": ">=", r"\neq": "!=", r"\approx": "approximately",
        r"\pi": "pi", r"\theta": "theta", r"\rightarrow": "->",
    }.items():
        text = text.replace(command, symbol)
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    return text.replace("**", "").replace("__", "").strip()


def safe_filename(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return clean[:80] or "conceptflow-export"


def markdown_document(title: str, sections: list[tuple[str, list[str]]]) -> str:
    lines = [f"# {title}", ""]
    for heading, paragraphs in sections:
        lines.extend([f"## {heading}", ""])
        for paragraph in paragraphs:
            lines.extend([clean_export_text(paragraph), ""])
    return "\n".join(lines).strip() + "\n"


def plain_text_document(title: str, sections: list[tuple[str, list[str]]]) -> str:
    lines = [title, "=" * len(title), ""]
    for heading, paragraphs in sections:
        lines.extend([heading, "-" * len(heading)])
        lines.extend(clean_export_text(paragraph) for paragraph in paragraphs)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def docx_document(title: str, sections: list[tuple[str, list[str]]]) -> bytes:
    """Create a small standards-compliant .docx without requiring local Word libraries."""
    def make_paragraph(
        text: str, *, style: str = "Normal", bold: bool = False,
        shade: str | None = None, indent: int = 0,
    ) -> str:
        properties = [f'<w:pStyle w:val="{style}"/>', '<w:spacing w:after="110" w:line="300" w:lineRule="auto"/>']
        if shade:
            properties.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
        if indent:
            properties.append(f'<w:ind w:left="{indent}"/>')
        run_properties = "<w:rPr><w:b/><w:color w:val=\"3F3563\"/></w:rPr>" if bold else ""
        return f'<w:p><w:pPr>{"".join(properties)}</w:pPr><w:r>{run_properties}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'

    body = [make_paragraph(title, style="Title"), make_paragraph("ConceptFlow study edition", style="Subtitle")]
    for heading, section_paragraphs in sections:
        body.append(make_paragraph(clean_export_text(heading), style="Heading1", shade="F1EDFA"))
        for content_line in section_paragraphs:
            text = clean_export_text(content_line)
            if text.startswith("- "):
                body.append(make_paragraph(f"•  {text[2:]}", style="ListParagraph", indent=360))
            elif re.match(r"^\d+\. ", text):
                body.append(make_paragraph(text, style="ListParagraph", indent=360))
            elif text.lower().startswith(("source:", "citation:", "evidence:")):
                body.append(make_paragraph(text, style="SourceNote", shade="EEF7F4", indent=240))
            elif re.match(r"^[^:]{2,35}:\s", text):
                body.append(make_paragraph(text, style="Normal", bold=True, shade="F7F9FC"))
            else:
                body.append(make_paragraph(text, style="Normal"))
    body.append(make_paragraph("Generated from your source-grounded ConceptFlow workspace.", style="SourceNote"))
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>""" + "".join(body) + """<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>
<w:pgMar w:top="1008" w:right="1152" w:bottom="1008" w:left="1152"/></w:sectPr></w:body></w:document>"""
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="Nirmala UI" w:cs="Nirmala UI"/><w:sz w:val="22"/><w:color w:val="334155"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="42"/><w:color w:val="3F3563"/></w:rPr><w:pPr><w:spacing w:after="80"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:rPr><w:i/><w:sz w:val="19"/><w:color w:val="718096"/></w:rPr><w:pPr><w:spacing w:after="280"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="3F3563"/></w:rPr><w:pPr><w:spacing w:before="240" w:after="120"/><w:keepNext/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="360"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="SourceNote"><w:name w:val="Source Note"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="19"/><w:color w:val="426A62"/></w:rPr></w:style>
</w:styles>"""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>""")
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""")
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", styles_xml)
    return buffer.getvalue()


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_document(title: str, sections: list[tuple[str, list[str]]]) -> bytes:
    """Create a readable paginated PDF without requiring reportlab on the student's device."""
    lines = [(title, "title")]
    for heading, paragraphs in sections:
        lines.append((heading, "heading"))
        for paragraph in paragraphs:
            text = clean_export_text(paragraph)
            prefix = "- " if text.startswith("- ") else ""
            if prefix:
                text = text[2:]
            wrapped = wrap(text, width=92, break_long_words=False) or [""]
            lines.extend(((prefix if index == 0 else "") + line, "body") for index, line in enumerate(wrapped))

    pages = [lines[index:index + 46] for index in range(0, len(lines), 46)] or [[("ConceptFlow export", "title")]]
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    page_ids = []
    content_ids = []
    for _ in pages:
        page_ids.append(len(objects) + 1)
        objects.append("")
        content_ids.append(len(objects) + 1)
        objects.append("")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>"
    for page_number, (page, page_id, content_id) in enumerate(zip(pages, page_ids, content_ids), start=1):
        commands = ["q", "0.247 0.208 0.388 rg", "0 800 595 42 re f", "Q", "BT", "0.18 0.23 0.30 rg", "/F1 11 Tf", "50 780 Td", "15 TL"]
        for text, kind in page:
            safe_text = pdf_escape(clean_export_text(text).encode("ascii", "replace").decode())
            if kind == "title":
                commands.extend(["0.247 0.208 0.388 rg", "/F2 20 Tf", f"({safe_text}) Tj", "0 -26 Td", "0.18 0.23 0.30 rg", "/F1 11 Tf"])
            elif kind == "heading":
                commands.extend(["0 -9 Td", "0.29 0.25 0.45 rg", "/F2 14 Tf", f"({safe_text}) Tj", "0 -19 Td", "0.18 0.23 0.30 rg", "/F1 11 Tf"])
            else:
                commands.extend([f"({safe_text}) Tj", "0 -15 Td"])
        commands.extend(["ET", "BT", "0.45 0.50 0.58 rg", "/F1 9 Tf", "260 24 Td", f"(ConceptFlow  |  Page {page_number} of {len(pages)}) Tj", "ET"])
        stream = "\n".join(commands)
        objects[page_id - 1] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> /F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> >> >> /Contents {content_id} 0 R >>"
        objects[content_id - 1] = f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream"
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, object_body in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n{object_body}\nendobj\n".encode("latin-1"))
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.write("".join(f"{offset:010d} 00000 n \n" for offset in offsets[1:]).encode())
    output.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return output.getvalue()


def export_response(
    *, title: str, sections: list[tuple[str, list[str]]], format: str,
    structured: object | None = None,
) -> Response:
    if format not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported download format: {format}")
    filename = safe_filename(title)
    if format == "json":
        body = json.dumps(structured if structured is not None else {"title": title, "sections": sections}, indent=2, ensure_ascii=False).encode("utf-8")
        media_type = "application/json"
    elif format == "docx":
        body = docx_document(title, sections)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif format == "pdf":
        body = pdf_document(title, sections)
        media_type = "application/pdf"
    elif format == "txt":
        body = plain_text_document(title, sections).encode("utf-8")
        media_type = "text/plain; charset=utf-8"
    else:
        body = markdown_document(title, sections).encode("utf-8")
        media_type = "text/markdown; charset=utf-8"
    return Response(body, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}.{format}"',
    })
