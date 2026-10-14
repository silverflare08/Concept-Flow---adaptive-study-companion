import json
import sqlite3
from zipfile import ZipFile
import pytest
from studybuddy.ingestion.router import parse_study_file, SUPPORTED_FILE_TYPES

def read(path):
    return parse_study_file(path, source_id='source', source_name=path.name, source_uri='/api/sources/source').segments

@pytest.mark.parametrize('extension,text', [
    ('.py','def derivative(x):\n    return 2*x'),('.c','int x = 2;'),('.cpp','class Vector {};'),
    ('.java','class Notes {}'),('.js','const x = 2;'),('.ts','let x: number = 2;'),
    ('.sql','SELECT topic FROM notes;'),('.json','{"topic":"Calculus"}'),('.xml','<topic>Calculus</topic>'),
    ('.yaml','topic: Calculus'),('.tex',r'\section{Calculus}'),('.rmd','# Calculus'),
    ('.step',"ISO-10303-21;\n#1=CARTESIAN_POINT('',(1.,2.,3.));\nEND-ISO-10303-21;"),
    ('.geojson','{"type":"Point","coordinates":[1,2]}'),
])
def test_technical_text_is_retrievable_without_execution(tmp_path, extension, text):
    path=tmp_path/f'notes{extension}'; path.write_text(text,encoding='utf-8')
    segments=read(path)
    assert segments and segments[0].citation.section.startswith('lines 1')
    assert segments[0].citation.source_id=='source'

def test_notebook_html_subtitles_and_vectors(tmp_path):
    samples={
        '.ipynb':json.dumps({'cells':[{'cell_type':'markdown','source':['Derivative means rate of change.']}]}),
        '.html':'<h1>Calculus</h1><p>Derivative means rate of change.</p><script>ignore()</script>',
        '.srt':'1\n00:00:01,000 --> 00:00:03,000\nDerivative means rate of change.\n',
        '.vtt':'WEBVTT\n\n00:01.000 --> 00:03.000\nDerivative means rate of change.\n',
        '.svg':'<svg xmlns="http://www.w3.org/2000/svg"><text>Derivative</text><circle r="5"/></svg>',
        '.drawio':'<mxfile><diagram name="Calculus"><mxGraphModel><root><mxCell id="1" value="Derivative"/><mxCell id="2" edge="1" source="1" target="3"/></root></mxGraphModel></diagram></mxfile>',
        '.stl':'solid triangle\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid',
    }
    for extension,text in samples.items():
        path=tmp_path/f'notes{extension}'; path.write_text(text,encoding='utf-8')
        assert read(path)
    assert read(tmp_path/'notes.srt')[0].citation.start_seconds==1

def test_xlsx_uses_sheet_and_row_citations(tmp_path):
    path=tmp_path/'notes.xlsx'
    with ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Marks" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="A2" t="inlineStr"><is><t>Algebra</t></is></c><c r="B2"><v>80</v></c></row></sheetData></worksheet>')
    segments=read(path)
    assert segments[0].citation.section=='sheet Marks, row 2'
    assert 'Algebra' in segments[0].text and 'B2: 80' in segments[0].text

def test_database_is_read_only_and_rows_have_locations(tmp_path):
    path=tmp_path/'notes.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE notes(topic TEXT)'); db.execute("INSERT INTO notes VALUES ('Calculus')")
    before=path.read_bytes()
    segments=read(path)
    assert 'Calculus' in segments[1].text
    assert segments[1].citation.section=='table notes, row 1'
    assert before==path.read_bytes()

def test_archive_member_is_cited_and_not_executed(tmp_path):
    path=tmp_path/'notes.zip'
    with ZipFile(path,'w') as z: z.writestr('../../lesson.py','raise RuntimeError("never execute")')
    assert '../../lesson.py' in read(path)[0].citation.source_name
    assert not (tmp_path.parent/'lesson.py').exists()

def test_epub_spine_and_odp_slides(tmp_path):
    path=tmp_path/'notes.epub'
    with ZipFile(path,'w') as z:
        z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>')
        z.writestr('book.opf','<package xmlns="http://www.idpf.org/2007/opf"><manifest><item id="ch1" href="chapter.html"/></manifest><spine><itemref idref="ch1"/></spine></package>')
        z.writestr('chapter.html','<h1>Calculus</h1><p>Derivative</p>')
    assert 'chapter.html' in read(path)[0].citation.section
    path=tmp_path/'notes.odp'
    with ZipFile(path,'w') as z:
        z.writestr('content.xml','<office:document xmlns:office="urn:o" xmlns:draw="urn:d" xmlns:text="urn:t"><draw:page><text:p>Derivative</text:p></draw:page></office:document>')
    assert read(path)[0].citation.section=='slide 1'

def test_parquet_rows_and_schema(tmp_path):
    pa=pytest.importorskip('pyarrow'); pq=pytest.importorskip('pyarrow.parquet')
    path=tmp_path/'notes.parquet'; pq.write_table(pa.table({'topic':['Calculus']}),path)
    assert 'Calculus' in read(path)[1].text

def test_all_requested_extensions_are_registered():
    requested='pdf docx pptx xlsx csv txt md html png jpg jpeg py ipynb c cpp java js ts sql json xml yaml zip mp3 wav m4a mp4 mov webm srt vtt svg epub odt odp parquet sqlite tex rmd drawio step stl geojson'.split()
    assert {'.'+name for name in requested} <= SUPPORTED_FILE_TYPES


@pytest.mark.parametrize('extension', ['.markdown', '.h', '.hpp', '.pyw', '.jsx', '.tsx', '.r', '.go', '.rs'])
def test_new_text_aliases_retain_content(tmp_path, extension):
    path = tmp_path / f'notes{extension}'
    path.write_text('Study note: probability and random variables.', encoding='utf-8')
    assert 'random variables' in read(path)[0].text


def test_tsv_jsonl_and_toml_preserve_locations(tmp_path):
    path = tmp_path / 'notes.tsv'
    path.write_text('Topic\tScore\nAlgebra\t0', encoding='utf-8')
    assert read(path)[1].citation.section == 'row 2'
    assert 'column 2: 0' in read(path)[1].text
    path = tmp_path / 'notes.jsonl'
    path.write_text('{"topic":"Algebra"}\n\n{"score":80}', encoding='utf-8')
    assert read(path)[1].citation.section == 'line 3'
    path.write_text('{"topic":', encoding='utf-8')
    with pytest.raises(ValueError, match='line 1'):
        read(path)
    path = tmp_path / 'notes.toml'
    path.write_text('[course]\nname="Algebra"', encoding='utf-8')
    assert 'Algebra' in read(path)[0].text


def test_real_legacy_excel_has_sheet_row_and_zero_values(tmp_path):
    import xlwt
    path = tmp_path / 'notes.xls'
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet('Marks')
    sheet.write(2, 1, 'Algebra'); sheet.write(2, 2, 0)
    workbook.save(str(path))
    result = read(path)
    assert result[0].citation.section == 'sheet Marks, row 3'
    assert 'column 2: Algebra' in result[0].text
    assert 'column 3: 0' in result[0].text


def test_macro_enabled_excel_uses_existing_xml_reader(tmp_path):
    path = tmp_path / 'notes.xlsm'
    with ZipFile(path, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Marks" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><v>42</v></c></row></sheetData></worksheet>')
        z.writestr('xl/vbaProject.bin', b'not executable by the reader')
    assert 'A1: 42' in read(path)[0].text


def test_opendocument_spreadsheet_reads_cells(tmp_path):
    path = tmp_path / 'notes.ods'
    with ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/vnd.oasis.opendocument.spreadsheet')
        z.writestr('META-INF/manifest.xml', '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>')
        z.writestr('content.xml', '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:spreadsheet><table:table table:name="Marks"><table:table-row><table:table-cell office:value-type="string"><text:p>Algebra</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="80"><text:p>80</text:p></table:table-cell></table:table-row></table:table></office:spreadsheet></office:body></office:document-content>')
    result = read(path)
    assert 'Algebra' in result[0].text
    assert result[0].citation.section == 'sheet Marks, row 1'


def test_new_extensions_are_registered():
    assert {'.markdown', '.tsv', '.jsonl', '.toml', '.h', '.jsx', '.tsx', '.xls', '.xlsm', '.xlsb', '.ods'} <= SUPPORTED_FILE_TYPES
