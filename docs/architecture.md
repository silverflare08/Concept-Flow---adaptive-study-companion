# Architecture

ConceptFlow runs a React frontend and a local FastAPI backend. SQLite stores course records, extracted content, chats, generated artifacts, assessment results and learning events. Original uploads remain in local file storage.

## Material ingestion

Readers produce source segments containing text and a citation. PDF pages, slide numbers, audio timestamps, spreadsheet rows and code line ranges are preserved. The chunker splits long segments while keeping each source location intact.

Scanned PDFs and images use the local instruction vision model. Audio/video use faster-whisper. Blocking readers run in a worker thread so the API can still accept other requests.

## Retrieval and teaching

BM25 retrieves relevant study sections. Ollama receives their evidence plus the learner context and generates an explanation. Citations are built from stored source metadata. Full-material lessons process batches of evidence in source order.

Successful vision readings, full-lesson drafts and timestamped transcripts use a private disk cache. Cache keys include source content or prompt and model identity; cancelled or failed responses are not stored. Cached transcripts get fresh source citations for each upload. A single loaded speech model is reused, with serialized inference to avoid CPU contention.

Full lessons reject truncated or repetitive drafts, then use a separate source-comparison model call before acceptance. A failed check yields labelled excerpts, not a verified lesson. This is a heuristic check using the same local model, not independent cross-model or formal maths verification. PDF exports render safe HTML structure through PyMuPDF with Unicode font support and automatic pagination.

Mind maps and learning flows reuse validated guide results and individual validated batches. Approved lesson-comparison results have a separate cache keyed by evidence, lesson, prompt and model configuration. Cache entries are revalidated on reading; an offline fallback is not cached as a completed AI guide. Exact adjacent chunk overlap at the same citation is compacted in model context only, retaining every evidence ID. Source changes or model configuration changes invalidate reuse. Chat, question drafting and grading remain separate from these static caches.

## Explanation languages

English is the default. A shared frontend selector labels Hindi and Romanised Hinglish as experimental, including the saved profile preference. Generation prompts request the selected language, and language checks can trigger a retry or a visible failure notice. These checks do not guarantee translation quality. Source-excerpt fallbacks and audio/video transcripts preserve the original source language rather than presenting them as translated lessons.

## Assessments and personalization

Questions are drafted and checked against cited evidence. Stored fingerprints help avoid repeated questions. Answers and reports persist, and Bayesian Knowledge Tracing updates topic mastery from assessment answers and grounded learning activity.

Progress charts distinguish fixed test scores from changing mastery estimates. Calendar plans and reminders are stored separately from recorded learning activity.

## Background work

Map and full-lesson jobs expose progress through polling. Cancellation is checked between model calls and before persistence. An inference call already running can finish before a cancellation checkpoint.

## Boundaries

Accounts use salted password hashes and revocable HTTP-only cookie sessions. Request-local context routes study operations to each account's SQLite database, upload folder and cache; background jobs inherit the same context. Legacy data stays preserved and unassigned. Email verification, recovery and additional public-hosting hardening remain outstanding. Optional SMTP welcome emails run in the background and do not verify email ownership. Uploaded code is read without execution. SQLite inputs are read-only, and archives have size/depth limits.

Video frames, full CAD reasoning and some embedded specialist visuals are outside the current extraction scope. See [supported formats](supported-formats.md). Formal RAG and personalization benchmarks remain future work.
