# ConceptFlow

**Your course material, turned into a clearer way to study.**

ConceptFlow brings notes, textbooks, slides and recordings into one workspace. Ask for a cited explanation, follow a learning flow, revise with a mind map, or test your understanding with an adaptive quiz. It runs locally with free AI models.

## What you can do

- Upload documents, spreadsheets, code, images, handwritten notes and lecture recordings—or import public links.
- Take a photo of your notes and learn from the extracted text.
- Chat with a source-grounded tutor in English, Hindi or Hinglish.
- Generate learning flows, revision maps, flashcards and practice assessments.
- Review worked feedback, weak topics and progress over time.
- Save chats, material notes, study plans and reminders.
- Listen to browser-narrated explanations and slide lessons.
- Download study content as PDF, DOCX, Markdown, TXT or JSON where available.

[Supported formats and reading limits](docs/supported-formats.md)

## Get started

Install **Python 3.11**, **Node.js 24 LTS** and **[Ollama](https://ollama.com/download)**. Keep Ollama running. Internet is needed for initial dependency/model downloads and public-link imports; no paid API key is required.

Clone the repository and open its root folder:

```bash
git clone https://github.com/silverflare08/Concept-Flow---adaptive-study-companion.git
cd Concept-Flow---adaptive-study-companion
```

Then run:

```bash
python scripts/setup.py
python scripts/start.py
```

On macOS/Linux, use `python3.11` if `python` is unavailable. Open **http://127.0.0.1:5173**. Keep the terminal open; **Ctrl+C stops both servers**.

Setup creates `.venv`, installs Python/frontend dependencies, downloads the text, vision and speech models, and checks the installation. Existing downloads are reused. The two Ollama models occupy roughly 4 GB in total; allow additional space for packages and Whisper. A GPU is optional; CPU inference is slower. Python 3.11.9 and Node 24.18.0 were tested on Windows.

### Try it

Create a workspace in **Materials**, then upload [samples/graph-basics.md](samples/graph-basics.md).

Ask **“Why does BFS use a queue?”**, open its citation, generate a revision map and take a short quiz. [More sample activities](samples/README.md) are included.

## Manual setup

Use this if you prefer to run each step yourself.

**Windows PowerShell**, from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -c requirements-windows-py311.txt -e ".[dev,app,ingestion,specialist]"
cd web
npm ci
cd ..
ollama pull qwen2.5:3b-instruct
ollama pull qwen3-vl:2b-instruct
.\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
.\.venv\Scripts\python.exe scripts/check_setup.py --models
python scripts/start.py
```

**macOS/Linux:**

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev,app,ingestion,specialist]"
cd web
npm ci
cd ..
ollama pull qwen2.5:3b-instruct
ollama pull qwen3-vl:2b-instruct
.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
.venv/bin/python scripts/check_setup.py --models
python3.11 scripts/start.py
```

The Python constraints file records tested Windows/Python 3.11 versions; other platforms use the dependency groups in `pyproject.toml`. Frontend versions are locked by `web/package-lock.json`. FFmpeg on PATH can help with some media providers; local speech decoding uses PyAV's bundled FFmpeg libraries. Tesseract is not required for handwriting.

## Configuration

Defaults work without configuration. To override them, copy `.env.example` to `.env` and edit it; the launcher loads it automatically.

| Setting | Default |
| --- | --- |
| `OLLAMA_URL` | `http://127.0.0.1:11434/api/chat` |
| `OLLAMA_MODEL` | `qwen2.5:3b-instruct` |
| `OLLAMA_VISION_MODEL` | `qwen3-vl:2b-instruct` |
| `WHISPER_MODEL` | `base` |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` | `cpu` / `int8` |
| `CONCEPTFLOW_CACHE_DIR` | `data/cache` |

Use the vision **instruct** model for image transcription. If you change the speech model, download it before using recordings. GPU speech settings require a compatible CUDA installation.

For unavailable ports:

```bash
python scripts/start.py --api-port 8011 --web-port 5174
```

The launcher connects the frontend to the selected API port. API documentation is available at `http://127.0.0.1:8000/docs` with the default ports.

## Performance and local data

The first image reading or lesson requires model inference and can take tens of seconds or longer, depending on hardware and content. Successful image transcriptions and full-lesson responses are cached locally. Repeating the same input can reuse that result; changed input, prompts or model settings create a different cache entry. This does not make an uncached long lecture instantaneous.

Workspaces and progress live in `data/conceptflow.db`; source files in `data/uploads/`; private cached responses in `data/cache/`. Back up these folders if you want to preserve your work.

User files, databases, caches, `.env`, virtual environments and `node_modules` are excluded from Git. Downloaded AI models live outside the repository. Publishing the repository does not publish these files.

## Tech stack

| Layer | Technology |
| --- | --- |
| Interface | React, JavaScript, Vite, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| Storage | SQLite, SQLAlchemy, local source files |
| Material readers | pypdf, PyMuPDF, Pillow, python-pptx, Calamine |
| Speech and links | faster-whisper, PyAV, yt-dlp |
| Retrieval and generation | BM25, source citations, local Ollama models |
| Personalization | Bayesian Knowledge Tracing |

[Architecture](docs/architecture.md)

## Development

On Windows:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_samples.py
.\.venv\Scripts\python.exe -m pytest -q
cd web
npm run build
```

On macOS/Linux, use `.venv/bin/python` in place of the Windows Python path. The sample smoke check needs no running AI service.

```text
src/studybuddy/  Backend, material readers, retrieval and tutoring
web/            React frontend
tests/          Automated tests
scripts/        Setup, launch and environment checks
samples/        Original sample study material
docs/           Architecture and format reference
configs/        Topic fixtures used by tests
```

## Troubleshooting

- **Setup stops:** read the last error, resolve it and rerun setup. Run `scripts/check_setup.py --models` with the environment's Python to check installed dependencies and models.
- **Ollama unavailable:** open Ollama or run `ollama serve` if no service is running. Confirm both required tags with `ollama list`.
- **Failed to fetch:** keep both servers running. Restart them after backend changes.
- **Handwriting is inaccurate:** use a sharp, well-lit photo of the whole page and compare the response with the original.
- **Camera won't open:** grant camera permission. Localhost is supported; a hosted site needs HTTPS.
- **Audio mentions `metadata_errors`:** the declared dependencies require PyAV below 19. Reinstall the ingestion extra or run `python -m pip install "av>=11,<19"` using the project's environment.
- **YouTube import fails:** provider restrictions may block downloads; upload a local recording instead.

## Current scope

ConceptFlow is a local application. Authentication, per-user isolation and public deployment are still pending. The backend currently has one active workspace shared by its clients.

Video reading transcribes speech; it does not analyse every frame. Specialist formats have the limits listed in the format reference. Browser speech availability varies, and narrated slides are not downloadable generated videos. Reminders appear while using or reopening the app; closed-browser push notifications are not implemented.

AI answers, handwriting transcription and question verification can contain errors. Dense/hybrid retrieval benchmarks, formal RAG evaluation and simulated-learner measurements remain planned work. The current Tailwind 3 build dependencies also have reported npm advisories that need review before public deployment.
