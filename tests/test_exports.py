from io import BytesIO
from zipfile import ZipFile

from studybuddy.exports import export_response, markdown_document, plain_text_document


def test_plain_exports_keep_all_sections_and_use_safe_filename() -> None:
    sections = [("Cells", ["A cell is a basic unit.", "- Review the labelled diagram."])]

    markdown = markdown_document("Cell biology", sections)
    text = plain_text_document("Cell biology", sections)
    response = export_response(title="Cell biology", sections=sections, format="txt")

    assert "## Cells" in markdown
    assert "Cells\n-----" in text
    assert response.headers["content-disposition"].endswith('filename="cell-biology.txt"')
    assert b"Review the labelled diagram" in response.body


def test_json_export_keeps_structured_payload() -> None:
    response = export_response(
        title="Quiz", sections=[], format="json", structured={"questions": 5},
    )

    assert response.media_type == "application/json"
    assert b'"questions": 5' in response.body


def test_pdf_and_word_exports_are_real_downloadable_file_formats() -> None:
    sections = [("Cells", ["Cells contain organised structures."])]
    pdf = export_response(title="Biology", sections=sections, format="pdf")
    word = export_response(title="Biology", sections=sections, format="docx")

    assert pdf.body.startswith(b"%PDF-")
    assert pdf.headers["content-disposition"].endswith('filename="biology.pdf"')
    with ZipFile(BytesIO(word.body)) as archive:
        assert "word/document.xml" in archive.namelist()
        document = archive.read("word/document.xml")
        assert b"Biology" in document
        assert b"ConceptFlow study edition" in document
        styles = archive.read("word/styles.xml")
        assert b"Heading1" in styles
        assert b"SourceNote" in styles


def test_pdf_preserves_headings_tables_unicode_and_page_bounds() -> None:
    import pymupdf
    from studybuddy.exports import pdf_document
    content = "## Probability\n\n### Definition\nP(X ≤ 2) = 0.7\n\n| x | p(x) |\n|---|---|\n| 0 | 0.3 |\n| 1 | 0.7 |\n\n" + "\n\n".join(
        f"### Topic {i}\nA short explanation about probability and its applications." for i in range(60)
    )
    document = pymupdf.open(stream=pdf_document("Revision notes", [("Lesson", [content])]), filetype="pdf")
    text = "".join(page.get_text() for page in document)
    assert "###" not in text and "|---|" not in text
    assert "≤" in text and "Topic 59" in text
    assert len(document) > 1
    for page in document:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    assert span["bbox"][0] >= 40
                    assert span["bbox"][2] <= 555
                    assert span["bbox"][3] <= 835


def test_math_cleanup_does_not_leave_common_latex_commands() -> None:
    from studybuddy.exports import clean_export_text, study_html_blocks
    result = clean_export_text(r"$\binom{3}{1}\left(\frac{1}{2}\right)^3$; \sum x \cdot p(x)")
    assert "C(3, 1)" in result
    assert "left" not in result and "right" not in result and "$" not in result
    assert "Σ" in result
    assert "&lt;script&gt;" in study_html_blocks("<script>alert(1)</script>")
