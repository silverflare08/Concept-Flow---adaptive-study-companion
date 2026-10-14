from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from studybuddy.exports import docx_document

def test_word_export_preserves_structured_study_content():
    content = "## Probability\n\n### Definition\nP(X ≤ 2) = 0.7\n\n- Recall the formula.\n1. Find the probability.\n2. Check the result.\n\n| x | p(x) |\n|---|---|\n| 0 | 0.3 |\n| 1 | 0.7 |\n\nSource: Notes, PDF page 2\n\n```python\nx = 1\nprint(x)\n```"
    with ZipFile(BytesIO(docx_document("Probability revision", [("Study lesson", [content])]))) as archive:
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        root = ET.fromstring(archive.read("word/document.xml"))
        text = " ".join(root.itertext())
        assert "##" not in text and "|---|" not in text and "```" not in text
        assert "≤" in text and "PDF page 2" in text
        assert "1. Find" in text and "2. Check" in text
        assert len(root.findall(".//w:tbl", ns)) == 1
        assert len(root.findall(".//w:tbl/w:tr", ns)) == 3
        assert root.find(".//w:tblHeader", ns) is not None
        assert root.find(".//w:numPr", ns) is not None
        styles = [node.attrib['{' + ns['w'] + '}val'] for node in root.findall('.//w:pStyle', ns)]
        assert "Heading2" in styles and "Heading3" in styles and "Code" in styles
        assert "word/_rels/document.xml.rels" in archive.namelist()


def test_downloaded_citations_use_smaller_style_without_losing_labels():
    from studybuddy.exports import study_html_blocks
    content = "## Topic\nMain learning text.\n### Sources for this section\n- Notes.pdf, PDF page 7\n- Lecture, Timestamp 01:20"
    html = study_html_blocks(content)
    assert "<p class='source'>Notes.pdf, PDF page 7</p>" in html
    with ZipFile(BytesIO(docx_document("Revision", [("Lesson", [content])]))) as archive:
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        styles = ET.fromstring(archive.read("word/styles.xml"))
        source = styles.find("w:style[@w:styleId='SourceNote']", ns)
        assert source.find("w:rPr/w:sz", ns).get('{' + ns['w'] + '}val') == "16"
        document = ET.fromstring(archive.read("word/document.xml"))
        for paragraph in document.findall(".//w:p", ns):
            if "Notes.pdf, PDF page 7" in "".join(paragraph.itertext()):
                assert paragraph.find("w:pPr/w:pStyle", ns).get('{' + ns['w'] + '}val') == "SourceNote"
