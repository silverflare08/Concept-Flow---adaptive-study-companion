"""Readers for technical notes, tables, ebooks and specialist study sources.

Uploaded code is read as evidence, never executed. Archives are bounded and
members are staged under application-owned temporary names.
"""
from __future__ import annotations
import base64
import csv
import io
import json
import re
import sqlite3
import struct
import tempfile
import tomllib
import zlib
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .models import CitationAnchor, SourceSegment, SourceType, EvidenceKind
from studybuddy.cancellation import check_cancelled

TEXT_TYPES = {'.py', '.c', '.cpp', '.java', '.js', '.ts', '.sql', '.json', '.xml', '.yaml', '.yml', '.tex', '.rmd', '.step', '.stp', '.geojson'}
TEXT_TYPES |= {'.pyw', '.h', '.hpp', '.jsx', '.tsx', '.r', '.go', '.rs', '.toml'}
EXTENDED_TYPES = TEXT_TYPES | {'.html', '.htm', '.xlsx', '.ipynb', '.zip', '.srt', '.vtt', '.svg', '.epub', '.odp', '.parquet', '.sqlite', '.sqlite3', '.db', '.drawio', '.stl'}
EXTENDED_TYPES |= {'.tsv', '.jsonl', '.xls', '.xlsm', '.xlsb', '.ods'}
MAX_BYTES = 50 * 1024 * 1024

def segment(text, section, source_id, source_name, source_uri, **location):
    return SourceSegment(text=str(text), citation=CitationAnchor(
        source_id=source_id, source_name=source_name, source_uri=source_uri,
        source_type=SourceType.DOCUMENT, section=section, **location))

def checked_archive(path):
    archive = ZipFile(path)
    members = archive.infolist()
    if len(members) > 500 or sum(m.file_size for m in members) > MAX_BYTES:
        archive.close()
        raise ValueError('Archive exceeds 500 entries or 50 MB uncompressed. Split it into smaller uploads.')
    if any(m.flag_bits & 1 for m in members):
        archive.close()
        raise ValueError('Password-protected archives are unsupported. Upload an unlocked copy.')
    return archive

def read_extended(path, *, source_id, source_name, source_uri=None, depth=0):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('This reader supports files up to 50 MB. Split the source first.')
    suffix = path.suffix.lower()
    make = lambda text, section: segment(text, section, source_id, source_name, source_uri)
    if suffix in TEXT_TYPES:
        text = path.read_text(encoding='utf-8-sig', errors='strict')
        if suffix in {'.json', '.geojson'}:
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        elif suffix in {'.xml'}:
            ET.fromstring(text)
        elif suffix == '.toml':
            tomllib.loads(text)
        lines = text.splitlines()
        return [make('\n'.join(lines[i:i+60]), f'lines {i+1}–{min(i+60,len(lines))}') for i in range(0,len(lines),60) if '\n'.join(lines[i:i+60]).strip()]
    if suffix == '.jsonl':
        result = []
        for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            check_cancelled()
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f'Invalid JSON on line {number}: {error.msg}') from error
            result.append(make(json.dumps(value, ensure_ascii=False, indent=2), f'line {number}'))
        return result
    if suffix == '.tsv':
        result = []
        with path.open(encoding='utf-8-sig', newline='') as handle:
            for number, row in enumerate(csv.reader(handle, delimiter='\t'), 1):
                check_cancelled()
                if any(row):
                    result.append(make('; '.join(f'column {i}: {value}' for i,value in enumerate(row, 1)), f'row {number}'))
        return result
    if suffix in {'.xls', '.xlsb', '.ods'}:
        try:
            from python_calamine import CalamineWorkbook
        except ImportError as error:
            raise RuntimeError('Spreadsheet support needs python-calamine. Run pip install -e ".[ingestion]".') from error
        # This reader only reads stored cell values. It never runs VBA/macros.
        result = []
        workbook = CalamineWorkbook.from_path(path)
        try:
            for name in workbook.sheet_names:
                sheet = workbook.get_sheet_by_name(name)
                column_offset = sheet.start[1] if sheet.start else 0
                for row_number,row in enumerate(sheet.iter_rows(), 1):
                    check_cancelled()
                    cells = [f'column {i}: {value}' for i,value in enumerate(row, column_offset + 1) if value is not None and value != '']
                    if cells:
                        result.append(make('; '.join(cells), f'sheet {name}, row {row_number}'))
        finally:
            workbook.close()
        return result
    if suffix in {'.html', '.htm'}:
        from .web import _StudyHTMLParser
        parser = _StudyHTMLParser()
        parser.feed(path.read_text(encoding='utf-8-sig'))
        return [make(text, section) for section,text in parser.blocks if text.strip()]
    if suffix == '.ipynb':
        notebook = json.loads(path.read_text(encoding='utf-8'))
        result = []
        for i, cell in enumerate(notebook.get('cells', []), 1):
            content = ''.join(cell.get('source', []))
            for output in cell.get('outputs', []):
                content += '\n' + ''.join(output.get('text', []))
                plain = output.get('data', {}).get('text/plain', [])
                content += '\n' + (plain if isinstance(plain,str) else ''.join(plain))
            if content.strip(): result.append(make(content, f'cell {i} ({cell.get("cell_type", "unknown")})'))
        return result
    if suffix in {'.srt', '.vtt'}:
        text = path.read_text(encoding='utf-8-sig')
        result = []
        def seconds(value):
            parts = value.replace(',', '.').split(':')
            return sum(float(p) * 60 ** i for i,p in enumerate(reversed(parts)))
        for block in re.split(r'\n\s*\n', text.replace('\r','')):
            match = re.search(r'([\d:]+[.,]\d+)\s*-->\s*([\d:]+[.,]\d+)[^\n]*\n(.*)', block, re.S)
            if match:
                body = re.sub('<[^>]+>', '', match[3]).strip()
                if body:
                    result.append(make(body, f'subtitle {match[1]}–{match[2]}'))
                    result[-1].citation.start_seconds = seconds(match[1])
                    result[-1].citation.end_seconds = seconds(match[2])
                    result[-1].evidence_kind = EvidenceKind.TRANSCRIPT
        return result
    if suffix in {'.xlsx', '.xlsm'}:
        result = []
        with checked_archive(path) as archive:
            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                strings = [''.join(n.itertext()) for n in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',ns)]
            workbook = ET.fromstring(archive.read('xl/workbook.xml'))
            rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
            for sheet in workbook.findall('s:sheets/s:sheet', ns):
                target = rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
                target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
                root = ET.fromstring(archive.read(target))
                for row in root.findall('s:sheetData/s:row', ns):
                    values = []
                    for cell in row.findall('s:c',ns):
                        value = cell.findtext('s:v', default='', namespaces=ns)
                        if cell.get('t') == 's': value = strings[int(value)]
                        elif cell.get('t') == 'inlineStr': value = ''.join(cell.find('s:is',ns).itertext())
                        formula = cell.findtext('s:f', namespaces=ns)
                        if formula: value = f'formula ={formula}; cached value {value or "not stored"}'
                        if value: values.append(f'{cell.get("r")}: {value}')
                    if values: result.append(make('; '.join(values), f'sheet {sheet.get("name")}, row {row.get("r")}'))
        return result
    if suffix == '.odp':
        result = []
        with checked_archive(path) as archive:
            root = ET.fromstring(archive.read('content.xml'))
            pages = [n for n in root.iter() if n.tag.endswith('}page')]
            for i,page in enumerate(pages,1):
                text = '\n'.join(''.join(n.itertext()) for n in page.iter() if n.tag.endswith(('}p','}h')))
                if text.strip(): result.append(make(text, f'slide {i}'))
        return result
    if suffix == '.epub':
        from .web import _StudyHTMLParser
        result = []
        with checked_archive(path) as archive:
            container = ET.fromstring(archive.read('META-INF/container.xml'))
            opf_name = next(n.get('full-path') for n in container.iter() if n.tag.endswith('rootfile'))
            opf = ET.fromstring(archive.read(opf_name))
            manifest = {n.get('id'): n.get('href') for n in opf.iter() if n.tag.endswith('}item')}
            for item in opf.iter():
                if not item.tag.endswith('}itemref'): continue
                member = str(Path(opf_name).parent / unquote(manifest[item.get('idref')])).replace('\\','/')
                parser = _StudyHTMLParser()
                parser.feed(archive.read(member).decode('utf-8'))
                result.extend(make(text, f'{member}: {section}') for section,text in parser.blocks if text.strip())
        return result
    if suffix == '.drawio':
        root = ET.fromstring(path.read_bytes())
        result = []
        diagrams = root.findall('diagram') if root.tag == 'mxfile' else [root]
        for diagram in diagrams:
            model = diagram.find('mxGraphModel')
            if model is None and diagram.tag == 'mxGraphModel': model = diagram
            if model is None:
                model = ET.fromstring(unquote(zlib.decompress(base64.b64decode(diagram.text or ''), -15).decode()))
            for node in model.iter('mxCell'):
                label = re.sub('<[^>]*>',' ',node.get('value','')).strip()
                edge = f'Connection: {node.get("source")} -> {node.get("target")}' if node.get('edge') == '1' else ''
                if label or edge: result.append(make(f'{label}\n{edge}'.strip(), f'diagram {diagram.get("name", "1")}, node {node.get("id")}'))
        return result
    if suffix == '.svg':
        root = ET.fromstring(path.read_bytes())
        labels = [''.join(n.itertext()).strip() for n in root.iter() if n.tag.split('}')[-1] in {'text','title','desc'}]
        geometry = [ET.tostring(n,encoding='unicode') for n in root.iter() if n.tag.split('}')[-1] in {'path','rect','circle','line','polygon'}]
        return [make('\n'.join(labels) + '\nVector geometry (not an inferred explanation):\n' + '\n'.join(geometry), 'SVG labels and geometry')]
    if suffix == '.parquet':
        import pyarrow.parquet as pq
        result = []
        with pq.ParquetFile(path) as reader:
            result.append(make(f'Schema: {reader.schema}\nRows: {reader.metadata.num_rows}', 'Parquet schema'))
            for batch in reader.iter_batches(batch_size=100):
                check_cancelled()
                for row in batch.to_pylist(): result.append(make(json.dumps(row,default=str), f'row {len(result)}'))
        return result
    if suffix in {'.sqlite', '.sqlite3', '.db'}:
        result = []
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as connection:
            connection.execute('PRAGMA query_only=ON')
            connection.enable_load_extension(False)
            for name, schema in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                result.append(make(schema or name, f'table {name}, schema'))
                quoted = '"' + name.replace('"','""') + '"'
                cursor = connection.execute(f'SELECT * FROM {quoted}')
                columns = [col[0] for col in cursor.description]
                for i,row in enumerate(cursor,1):
                    check_cancelled()
                    result.append(make(json.dumps(dict(zip(columns,row)),default=str), f'table {name}, row {i}'))
        return result
    if suffix == '.stl':
        raw = path.read_bytes()
        if len(raw)>=84 and len(raw) == 84 + struct.unpack_from('<I',raw,80)[0]*50:
            count = struct.unpack_from('<I',raw,80)[0]
            vertices = [struct.unpack_from('<fff',raw,84+i*50+12+j*12) for i in range(count) for j in range(3)]
        else:
            vertices = [tuple(map(float,m)) for m in re.findall(rb'vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)',raw)]
            count = len(vertices)//3
        if not vertices: raise ValueError('No valid STL triangles found.')
        bounds = [(min(v[a] for v in vertices),max(v[a] for v in vertices)) for a in range(3)]
        return [make(f'Mesh triangles: {count}\nXYZ coordinate bounds: {bounds}\nSTL does not specify units or engineering purpose. Only geometry is available.', 'STL geometry summary')]
    if suffix == '.zip':
        if depth >= 2: raise ValueError('Nested archives exceed the supported depth of two.')
        from .router import parse_study_file, SUPPORTED_FILE_TYPES
        result = []
        with checked_archive(path) as archive, tempfile.TemporaryDirectory(prefix='study-archive-', dir=path.parent) as temporary:
            for i, member in enumerate(archive.infolist()):
                check_cancelled()
                if member.is_dir(): continue
                extension = Path(member.filename).suffix.lower()
                if extension not in SUPPORTED_FILE_TYPES:
                    raise ValueError(f'Archive member {member.filename} is unsupported. Remove it or upload study files separately.')
                staged = Path(temporary) / f'member-{i}{extension}'
                staged.write_bytes(archive.read(member))
                parsed = parse_study_file(staged, source_id=source_id, source_name=f'{source_name} / {member.filename}', source_uri=source_uri, archive_depth=depth+1)
                result.extend(parsed.segments)
        return result
    raise ValueError(f'No reader for {suffix}')
