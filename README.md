# ConceptFlow

ConceptFlow turns your notes, books, slides and recordings into a source-grounded study workspace. Learn with cited explanations, revise with maps and flashcards, and track your understanding through assessments.

It keeps your learning connected and organised, so you can focus on understanding rather than searching through scattered files.

## Features

- **Study material**
  - Upload documents, images, handwritten notes and audio/video recordings.
  - Capture notes with the camera or import supported public links.
  - Organise subjects into workspaces and add material notes.

- **Source-grounded tutoring**
  - Ask questions or generate lessons from selected material.
  - Open citations at the original page, slide or recording timestamp.
  - Use English by default, with experimental Hindi and Romanised Hinglish options and typeset maths.

- **Revision and assessment**
  - Generate learning flows, revision maps and flashcards.
  - Create quizzes and customised assessments with worked feedback.
  - Review weak topics, mastery estimates and daily progress.

- **Audio and planning**
  - Read timestamped lecture transcripts and listen to browser-narrated lessons.
  - Save study plans, calendar events and in-app reminders.

- **History and downloads**
  - Revisit saved chats, assessments, reports and study guides.
  - Export PDF, DOCX, Markdown, TXT or JSON where supported.

- **Personal accounts**
  - Sign up with a unique username and email.
  - Keep account-specific uploads, workspaces and history.
  - Choose an avatar, theme, text size and study defaults.

See the [supported file formats](docs/supported-formats.md).

## Screenshots

Application screenshots are added in [docs/images](docs/images). It include the welcome page, study dashboard, cited tutor responses, revision maps and assessment reports.

## Tech stack

| Layer | Technologies |
| --- | --- |
| Frontend | React, JavaScript, Vite, Tailwind CSS, Lucide, KaTeX |
| Backend | Python, FastAPI, Pydantic |
| Storage | SQLite, SQLAlchemy, local files |
| Material extraction | PyMuPDF, pypdf, Pillow, python-pptx, Calamine |
| Speech and links | faster-whisper, PyAV, yt-dlp |
| AI and personalisation | Ollama, BM25 retrieval, Bayesian Knowledge Tracing |

## Models used

| Model | Purpose |
| --- | --- |
| Qwen2.5 3B Instruct (`qwen2.5:3b-instruct`) | Explanations, study guides, assessment drafting and answer checks |
| Qwen3-VL 2B Instruct (`qwen3-vl:2b-instruct`) | Reading images, scanned pages and handwritten notes |
| Whisper Base (`base`) | Transcribing audio/video speech through faster-whisper |
| Bayesian Knowledge Tracing | Estimating per-topic learner mastery |

Text and vision models run locally through Ollama. Whisper defaults to CPU with `int8`. The project uses pretrained models for inference, not fine-tuning. Model settings can be changed in `.env`.

## System architecture

```text
React + Tailwind interface
          |
      FastAPI + account sessions
          |
          +-- Material readers --> Source-linked text --> BM25 index
          +-- Tutor --> Retrieved passages --> Ollama --> Cited explanation
          +-- Selected evidence --> Learning flows, revision maps and flashcards
          +-- Assessments --> Answer checks --> Feedback --> Topic mastery (BKT)
          |
          +-- Per-account SQLite: workspaces, chats, reports and learning events
          +-- Private local files: original uploads and reusable model results
```

**RAG:** BM25 retrieves relevant passages for a question. Ollama uses those passages and learner context to explain the answer. Page, slide and timestamp citations come from the application, not invented model locations. Full-material lessons and maps use selected evidence in source order.

**Multimodal reading:** document readers extract text, the vision model reads images and scanned pages, and faster-whisper transcribes audio/video speech with timestamps.

**Personalisation:** assessment outcomes and learning events update topic mastery estimates. Stored reports support weak-topic revision and progress views. This uses a learner model alongside inference, not fine-tuning.

See [architecture documentation](docs/architecture.md) for details.

## Setup

### Prerequisites

- **[Python 3.11](https://www.python.org/downloads/release/python-3119/)** — on Windows, use the 64-bit installer and enable **Add Python to PATH**.
- **[Node.js 24 LTS](https://nodejs.org/en/download)** — includes npm for frontend dependencies.
- **[Git](https://git-scm.com/downloads/)** — needed to clone the repository.
- **[Ollama](https://ollama.com/download)** — open it and keep it running during setup and study sessions.
- **Windows only:** install the x64 [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) if it is not already installed; the speech-processing runtime needs it.

For broader audio/video and public-link compatibility, also install **[FFmpeg](https://ffmpeg.org/download.html)** and add its executable folder to PATH. Local speech decoding uses PyAV's bundled libraries; external FFmpeg helps with media conversion and downloads.

Initial setup requires internet access and several GB of free disk space. Use Python **3.11.x**; on Windows, `py -3.11` selects that version explicitly. On macOS/Linux, use `python3.11` if needed.

### Installation

```bash
git clone https://github.com/silverflare08/Concept-Flow---adaptive-study-companion.git
cd Concept-Flow---adaptive-study-companion
python scripts/setup.py
python scripts/start.py
```

`setup.py` installs project dependencies, downloads the models and validates the environment. Tested on Windows with Python 3.11.9 and Node.js 24.18.0.

### Running the application

Open **http://127.0.0.1:5173**. Sample material is available in [samples/](samples/README.md).

Keep Ollama running and launch subsequent sessions with `python scripts/start.py` from the repository root. The launcher starts both servers; **Ctrl+C** stops them.

On macOS/Linux, use `python3.11` if needed. On Windows, if your global Python command is unavailable but the existing environment works, run `.\.venv311\Scripts\python.exe scripts/start.py`. The launcher supports both `.venv` and `.venv311`.

## Using ConceptFlow

1. Sign in and create a workspace in **Materials**.
2. Upload your material, then open **Learn** for explanations.
3. Generate revision maps, learning flows or flashcards.
4. Take an assessment and check **Progress**.
5. Revisit or download saved work in **History**.
6. Open your profile icon to personalise settings.

English is the default explanation language. Hindi and Romanised Hinglish are labelled **Experimental** in the language selector and profile settings. Output quality varies with the material and local model; source excerpts and transcripts retain their original language. Use English if a requested language cannot be generated reliably.

## Configuration

Defaults work without a configuration file. Copy [.env.example](.env.example) to `.env` only if you need overrides, then restart the server. Never commit credentials.

- Text model: `qwen2.5:3b-instruct`
- Vision model: `qwen3-vl:2b-instruct`
- Speech model: Whisper `base`, CPU with `int8`
- API: port `8000`; frontend: port `5173`

If a port is unavailable:

```bash
python scripts/start.py --api-port 8011 --web-port 5174
```

## Development

From the repository root, using the project's Python environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix web test
npm --prefix web run build
```

Use `.venv311` if that is your active environment, or `.venv/bin/python` on macOS/Linux. Frontend versions are locked in `web/package-lock.json`; setup applies tested Windows/Python 3.11 constraints automatically.

## Project scope

ConceptFlow focuses on material-grounded learning: multimodal ingestion, cited tutoring, revision tools and learner-aware practice. Its modular architecture separates extraction, retrieval, generation and learner modelling, supporting further development of study workflows.
