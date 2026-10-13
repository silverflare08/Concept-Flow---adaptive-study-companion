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


def safe_filename(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return clean[:80] or "conceptflow-export"


def markdown_document(title: str, sections: list[tuple[str, list[str]]]) -> str:
    lines = [f"# {title}", ""]
    for heading, paragraphs in sections:
        lines.extend([f"## {heading}", ""])
        for paragraph in paragraphs:
            lines.extend([str(paragraph), ""])
    return "\n".join(lines).strip() + "\n"


def plain_text_document(title: str, sections: list[tuple[str, list[str]]]) -> str:
    lines = [title, "=" * len(title), ""]
    for heading, paragraphs in sections:
        lines.extend([heading, "-" * len(heading)])
        lines.extend(str(paragraph).replace("**", "") for paragraph in paragraphs)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def docx_document(title: str, sections: list[tuple[str, list[str]]]) -> bytes:
    """Create a small standards-compliant .docx without requiring local Word libraries."""
    def make_paragraph(text: str, *, style: str | None = None, bold: bool = False) -> str:
        style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        run_properties = "<w:rPr><w:b/></w:rPr>" if bold else ""
        return f'<w:p>{style_xml}<w:r>{run_properties}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'

    body = [make_paragraph(title, style="Title")]
    for heading, section_paragraphs in sections:
        body.append(make_paragraph(heading, style="Heading1"))
        for content_line in section_paragraphs:
            text = str(content_line)
            if text.startswith("- "):
                body.append(make_paragraph(f"- {text[2:]}", style="Normal"))
            elif re.match(r"^\d+\. ", text):
                body.append(make_paragraph(text, style="Normal"))
            else:
                body.append(make_paragraph(text.replace("**", ""), style="Normal"))
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>""" + "".join(body) + """<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>
<w:pgMar w:top="1008" w:right="1152" w:bottom="1008" w:left="1152"/></w:sectPr></w:body></w:document>"""
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/><w:sz w:val="21"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="36"/><w:color w:val="000000"/></w:rPr><w:pPr><w:spacing w:after="240"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="26"/><w:color w:val="000000"/></w:rPr><w:pPr><w:spacing w:before="180" w:after="90"/></w:pPr></w:style>
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
            text = str(paragraph).replace("**", "")
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
    for page, page_id, content_id in zip(pages, page_ids, content_ids):
        commands = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
        for text, kind in page:
            if kind == "title":
                commands.extend(["/F2 18 Tf", f"({pdf_escape(text.encode('ascii', 'replace').decode())}) Tj", "0 -22 Td", "/F1 11 Tf"])
            elif kind == "heading":
                commands.extend(["0 -8 Td", "/F2 13 Tf", f"({pdf_escape(text.encode('ascii', 'replace').decode())}) Tj", "0 -17 Td", "/F1 11 Tf"])
            else:
                commands.extend([f"({pdf_escape(text.encode('ascii', 'replace').decode())}) Tj", "0 -14 Td"])
        commands.append("ET")
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
