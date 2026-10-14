"""Reusable multi-format exports for saved ConceptFlow learning work."""

from __future__ import annotations

from io import BytesIO
import json
import re
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from fastapi import Response


EXPORT_FORMATS = {"md", "txt", "pdf", "docx", "json"}


def clean_export_text(value: object) -> str:
    """Turn model-flavoured Markdown/LaTeX into calm reader-facing text."""
    text = str(value).replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "")
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1) / (\2)", text)
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", text)
    text = re.sub(r"\\binom\{([^{}]+)\}\{([^{}]+)\}", r"C(\1, \2)", text)
    text = re.sub(r"\\(?:text|mathrm|mathbf)\{([^{}]+)\}", r"\1", text)
    text = text.replace(r"\left", "").replace(r"\right", "")
    for command, symbol in {
        r"\times": "x", r"\cdot": "·", r"\div": "/", r"\pm": "+/-",
        r"\leq": "<=", r"\geq": ">=", r"\neq": "!=", r"\approx": "approximately",
        r"\pi": "pi", r"\theta": "theta", r"\rightarrow": "->",
        r"\sum": "Σ", r"\mu": "μ", r"\sigma": "σ", r"\cap": "∩",
        r"\le": "≤", r"\ge": "≥", r"\ldots": "…",
    }.items():
        text = text.replace(command, symbol)
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    text = re.sub(r"\$\$?(.*?)\$\$?", r"\1", text, flags=re.S)
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
    """Typeset study paragraphs, headings, lists and tables without a Word installation."""
    def make_paragraph(
        text: str, *, style: str = "Normal", bold: bool = False,
        shade: str | None = None, indent: int = 0,
    ) -> str:
        properties = [f'<w:pStyle w:val="{style}"/>', '<w:spacing w:after="110" w:line="300" w:lineRule="auto"/>']
        if shade:
            properties.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
        if indent:
            properties.append(f'<w:ind w:left="{indent}"/>')
        run_properties = "<w:rPr><w:b/></w:rPr>" if bold else ""
        return f'<w:p><w:pPr>{"".join(properties)}</w:pPr><w:r>{run_properties}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'

    body = [make_paragraph(title, style="Title"), make_paragraph("ConceptFlow study edition", style="Subtitle")]
    from xml.etree import ElementTree as ET
    for heading, section_paragraphs in sections:
        body.append(make_paragraph(clean_export_text(heading), style="Heading1"))
        for content in section_paragraphs:
            root = ET.fromstring("<body>" + study_html_blocks(str(content)) + "</body>")
            for block in root:
                text = "".join(block.itertext())
                if block.get("class") == "source":
                    body.append(make_paragraph(text, style="SourceNote"))
                elif re.fullmatch(r"h[1-6]", block.tag):
                    level = min(4, max(2, int(block.tag[1:]) - 1))
                    body.append(make_paragraph(text, style=f"Heading{level}"))
                elif block.tag == "table":
                    rows = list(block)
                    columns = max((len(row) for row in rows), default=1)
                    width = 9936 // columns
                    borders = "".join(f'<w:{side} w:val="single" w:sz="4" w:color="D9D9D9"/>'
                                      for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
                    table = [f'<w:tbl><w:tblPr><w:tblW w:w="9936" w:type="dxa"/><w:tblBorders>{borders}</w:tblBorders>'
                             '<w:tblCellMar><w:top w:w="100" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
                             '<w:bottom w:w="100" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar></w:tblPr>'
                             '<w:tblGrid>' + f'<w:gridCol w:w="{width}"/>' * columns + '</w:tblGrid>']
                    for row_index, row in enumerate(rows):
                        table.append('<w:tr>' + ('<w:trPr><w:tblHeader/></w:trPr>' if row_index == 0 else ''))
                        cells = list(row)
                        for index in range(columns):
                            value = "".join(cells[index].itertext()) if index < len(cells) else ""
                            shade = '<w:shd w:fill="E8EEF5"/>' if row_index == 0 else ''
                            table.append(f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/><w:vAlign w:val="center"/>{shade}</w:tcPr>'
                                         + make_paragraph(value, bold=row_index == 0) + '</w:tc>')
                        table.append('</w:tr>')
                    table.append('</w:tbl>')
                    body.extend(table)
                    body.append(make_paragraph(""))
                elif block.tag == "pre":
                    for line in text.splitlines():
                        body.append(make_paragraph(line, style="Code"))
                elif text.startswith("• "):
                    paragraph = make_paragraph(text[2:], style="ListParagraph", indent=360)
                    body.append(paragraph.replace("</w:pPr>", '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'))
                elif re.match(r"^\d+[.)]\s", text):
                    body.append(make_paragraph(text, style="ListParagraph", indent=360))
                elif block.get("class") == "source" or text.lower().startswith(("source:", "citation:", "evidence:")):
                    body.append(make_paragraph(text, style="SourceNote"))
                elif block.tag != "hr":
                    body.append(make_paragraph(text))
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
<w:style w:type="paragraph" w:styleId="SourceNote"><w:name w:val="Source Note"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="16"/><w:color w:val="64748B"/></w:rPr></w:style>
</w:styles>"""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>""")
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""")
        archive.writestr("word/document.xml", document_xml)
        for level, size in ((2, 26), (3, 24), (4, 22)):
            style = f'<w:style w:type="paragraph" w:styleId="Heading{level}"><w:name w:val="heading {level}"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="180" w:after="90"/><w:outlineLvl w:val="{level - 1}"/></w:pPr><w:rPr><w:b/><w:color w:val="000000"/><w:sz w:val="{size}"/></w:rPr></w:style>'
            styles_xml = styles_xml.replace('</w:styles>', style + '</w:styles>')
        styles_xml = styles_xml.replace('3F3563', '000000').replace('718096', '000000')
        styles_xml = styles_xml.replace('</w:styles>', '<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr></w:style></w:styles>')
        ET.register_namespace("w", "http://schemas.openxmlformats.org/wordprocessingml/2006/main")
        style_tree = ET.fromstring(styles_xml)
        for style_node in style_tree:
            paragraph_properties = style_node.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr")
            run_properties = style_node.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr")
            if paragraph_properties is not None and run_properties is not None:
                style_node.remove(paragraph_properties)
                style_node.insert(list(style_node).index(run_properties), paragraph_properties)
        styles_xml = ET.tostring(style_tree, encoding="unicode")
        archive.writestr("word/styles.xml", styles_xml)
        archive.writestr("word/_rels/document.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="styles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="numbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>')
        archive.writestr("word/numbering.xml", '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
    return buffer.getvalue()


def study_html_blocks(content: str) -> str:
    """Render a safe Markdown subset; never trust model/user HTML."""
    content = str(content).replace("\r\n", "\n")
    blocks = []
    lines = content.splitlines()
    index = 0
    source_section = False
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line:
            continue
        if line.startswith("```"):
            code = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            blocks.append("<pre>" + escape("\n".join(code)) + "</pre>")
        elif re.match(r"^#{1,6}\s+", line):
            level = min(4, len(line) - len(line.lstrip("#")) + 1)
            heading = clean_export_text(re.sub(r"^#+\s+", "", line))
            source_section = heading.casefold().startswith(("sources", "source references", "citations", "references"))
            blocks.append("<p class='source'>" + escape(heading) + "</p>" if source_section else f"<h{level}>" + escape(heading) + f"</h{level}>")
        elif re.fullmatch(r"[-*_]{3,}", line):
            blocks.append("<hr/>")
        elif line.startswith("|") and index < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[index]):
            rows = [line]
            index += 1
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(lines[index].strip())
                index += 1
            table = []
            for row_index, row in enumerate(rows):
                tag = "th" if row_index == 0 else "td"
                cells = "".join(f"<{tag}>{escape(clean_export_text(cell.strip()))}</{tag}>"
                                for cell in row.strip("|").split("|"))
                table.append("<tr>" + cells + "</tr>")
            blocks.append("<table>" + "".join(table) + "</table>")
        else:
            bullet = re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)(.*)", line)
            text = clean_export_text(line)
            citation_text = clean_export_text(bullet.group(1)) if bullet else text
            if source_section or citation_text.casefold().startswith(("source:", "citation:", "evidence:")):
                blocks.append("<p class='source'>" + escape(citation_text) + "</p>")
            elif bullet:
                text = clean_export_text(bullet.group(1))
                prefix = re.match(r"^\d+[.)]\s+", line)
                blocks.append("<p class='item'>" + (escape(prefix.group(0)) if prefix else "• ") + escape(text) + "</p>")
            elif line.startswith(">"):
                blocks.append("<p class='source'>" + escape(clean_export_text(line.lstrip("> "))) + "</p>")
            else:
                # Preserve logical paragraphs/newlines instead of collapsing an entire lesson.
                blocks.append("<p>" + escape(text) + "</p>")
    return "\n".join(blocks)


def pdf_document(title: str, sections: list[tuple[str, list[str]]]) -> bytes:
    """Typeset real headings, tables and Unicode with the installed ingestion renderer."""
    try:
        import pymupdf
    except ImportError as error:
        raise RuntimeError("PDF downloads require PyMuPDF. Install the ingestion dependencies.") from error
    body = ["<h1>" + escape(clean_export_text(title)) + "</h1>",
            "<p class='subtitle'>ConceptFlow · Study notes</p>"]
    for heading, paragraphs in sections:
        body.append("<h2>" + escape(clean_export_text(heading)) + "</h2>")
        for paragraph in paragraphs:
            body.append(study_html_blocks(str(paragraph)))
    css = """
    body {font-family: sans-serif; font-size: 10.5pt; line-height: 1.5; color: #334155;}
    h1 {font-size: 22pt; color: #43365f; margin-bottom: 8pt;}
    h2 {font-size: 15pt; color: #43365f; margin-top: 20pt; margin-bottom: 8pt;}
    h3 {font-size: 13pt; color: #43365f; margin-top: 16pt; margin-bottom: 6pt;}
    h4 {font-size: 11pt; color: #426a62; margin-top: 12pt; margin-bottom: 5pt;}
    p {margin-top: 0; margin-bottom: 8pt;}
    .subtitle {color: #718096; font-size: 9pt;}
    .item {margin-left: 12pt; margin-bottom: 5pt;}
    .source {color: #64748b; font-size: 8pt; line-height: 1.3; margin-top: 0; margin-bottom: 3pt;}
    table {border-collapse: collapse; width: 100%; margin-top: 8pt; margin-bottom: 12pt;}
    th, td {padding: 6pt; font-size: 9pt;}
    th {color: #43365f; font-weight: bold;}
    pre {font-family: monospace; font-size: 8pt; padding: 8pt; white-space: pre-wrap;}
    """
    story = pymupdf.Story(html="<html><body>" + "\n".join(body) + "</body></html>", user_css=css)
    document = story.write_with_links(
        lambda number, filled: (pymupdf.Rect(0, 0, 595, 842), pymupdf.Rect(48, 48, 547, 790), None)
    )
    for number, page in enumerate(document, 1):
        page.insert_text((48, 819), f"ConceptFlow  |  Page {number} of {len(document)}",
                         fontsize=8, color=(0.45, 0.5, 0.58))
    result = document.tobytes(garbage=4, deflate=True)
    document.close()
    return result


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
