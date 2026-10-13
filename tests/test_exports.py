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

    assert pdf.body.startswith(b"%PDF-1.4")
    assert pdf.headers["content-disposition"].endswith('filename="biology.pdf"')
    with ZipFile(BytesIO(word.body)) as archive:
        assert "word/document.xml" in archive.namelist()
        assert b"Biology" in archive.read("word/document.xml")
