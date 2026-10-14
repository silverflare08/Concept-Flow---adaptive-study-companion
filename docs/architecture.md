# Architecture

ConceptFlow runs a React frontend and a local FastAPI backend. SQLite stores course records, extracted content, chats, generated artifacts, assessment results and learning events. Original uploads remain in local file storage.

## Material ingestion

Readers produce source segments containing text and a citation. PDF pages, slide numbers, audio timestamps, spreadsheet rows and code line ranges are preserved. The chunker splits long segments while keeping each source location intact.

Scanned PDFs and images use the local instruction vision model. Audio/video use faster-whisper. Blocking readers run in a worker thread so the API can still accept other requests.

## Retrieval and teaching

BM25 retrieves relevant study sections. Ollama receives their evidence plus the learner context and generates an explanation. Citations are built from stored source metadata. Full-material lessons process batches of evidence in source order.

Successful vision readings and full-lesson model responses use a private disk cache. Cache keys include source content or prompt and model identity; cancelled or failed responses are not stored.

## Assessments and personalization

Questions are drafted and checked against cited evidence. Stored fingerprints help avoid repeated questions. Answers and reports persist, and Bayesian Knowledge Tracing updates topic mastery from assessment answers and grounded learning activity.

Progress charts distinguish fixed test scores from changing mastery estimates. Calendar plans and reminders are stored separately from recorded learning activity.

## Background work

Map and full-lesson jobs expose progress through polling. Cancellation is checked between model calls and before persistence. An inference call already running can finish before a cancellation checkpoint.

## Boundaries

The backend currently holds one active workspace for all connected clients. Authentication and user isolation are needed before shared hosting. Uploaded code is read without execution. SQLite inputs are read-only, and archives have size/depth limits.

Video frames, full CAD reasoning and some embedded specialist visuals are outside the current extraction scope. See [supported formats](supported-formats.md). Formal RAG and personalization benchmarks remain future work.
