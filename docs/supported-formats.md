# Study material formats

All extracted content enters the same source-cited retrieval, tutoring, map and assessment pipeline. A supported extension does not guarantee readable content: damaged, encrypted, empty or blurry sources can still fail. Uploaded code is never executed.

| Group | Formats | Evidence available |
| --- | --- | --- |
| Documents | PDF, DOCX, PPTX, TXT, MD, MARKDOWN, HTML, ODT, RTF | Text with page, slide, paragraph or heading references. Scanned PDFs and PDF/PPTX figures use local vision. |
| Images | PNG, JPG, JPEG, WEBP, BMP, TIFF | Local vision transcription of text, handwriting and diagrams. Requires Ollama and the vision model. |
| Spreadsheets | XLSX, XLSM, XLS, XLSB, ODS, CSV, TSV | Sheet/row/cell content. XLSX/XLSM formulas and stored cached values are preserved; formulas are not recalculated. XLS/XLSB/ODS use Calamine for stored values. Macros are never executed. Formatting, charts and embedded pictures are not yet interpreted. |
| Code and structured notes | PY, PYW, C, H, CPP, HPP, JAVA, JS, JSX, TS, TSX, R, GO, RS, SQL, JSON, JSONL, TOML, XML, YAML, TEX, RMD, GeoJSON | Source text with line ranges; JSONL has individual line locations and TSV has row locations. JSON, JSONL and TOML are validated before indexing. No program execution, LaTeX compilation or map rendering. |
| Notebooks | IPYNB | Markdown/code cells and saved textual outputs; embedded plots are not yet interpreted. |
| Archives | ZIP | Supported member files, with member names in citations. No code execution or extraction to user-provided paths. Maximum 500 entries, 50 MB uncompressed, and two nested levels. Unsupported members cause an explicit error. |
| Audio/video | MP3, WAV, M4A, MP4, MOV, WEBM, AAC, FLAC, OGG, MKV, AVI | Speech transcription with timestamps. Visual video frames are not yet analysed. |
| Subtitles | SRT, VTT | Cue text with source times. Subtitle citations refer to the subtitle file, not an inferred companion video. |
| Ebooks | EPUB | Chapters in reading/spine order, with HTML heading references. Images are not yet interpreted. |
| OpenDocument slides | ODP | Slide text and slide-number references; figures are not yet interpreted. |
| Datasets | Parquet, SQLite | Schema and rows with locations. SQLite is opened read-only. Parquet requires the specialist dependency extra. |
| Diagrams | SVG, draw.io (.drawio) | SVG labels and vector records; draw.io node labels and graph connections, including compressed diagrams. Visual semantics are not yet inferred. |
| CAD | STEP, STL | STEP entity text with line references; STL triangle count and coordinate bounds. No CAD rendering, dimensional reasoning, units inference or engineering-purpose inference. |

Install the standard application/ingestion dependencies and, for Parquet, the optional specialist extra:

```powershell
pip install -e ".[app,ingestion,specialist]"
```

For unsupported specialist visuals, export annotated pages to PDF or clear images alongside the original file. Maps and quizzes should only cover the evidence actually extracted. No parser can promise correct generated answers for arbitrary uploaded content; answer verification and evaluation remain necessary.
