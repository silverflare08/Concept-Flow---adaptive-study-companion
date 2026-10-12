# ConceptFlow

ConceptFlow is a source-grounded adaptive learning platform. It brings lecture
videos, PDFs, slides, diagrams, and figures into one searchable course space,
then provides cited answers, evidence-backed assessments, and personalized study
support based on concept-level mastery.

Built for the Multimodal AI Hackathon 2026 - Track D: Personalized Tutoring &
Adaptive Learning.

## Features

- Upload and index lecture videos, PDFs, and PowerPoint slides without manual
  transcription or copy-pasting.
- Search prose, OCR, diagrams, and figure descriptions as separate source
  evidence types.
- Ask questions and open the exact page, slide, or timestamp supporting an
  answer.
- Generate source-tagged MCQs, short-answer questions, and numerical problems.
- Verify generated questions against their evidence and prevent repeated items.
- Start new learners with a diagnostic quiz and update concept mastery after
  every answer using Bayesian Knowledge Tracing.
- View weak concepts, prerequisites, progress, and targeted revision tasks in a
  clear dashboard.

## Architecture

```text
PDF / slides / video
        |
multimodal ingestion (text + OCR + figures + transcript timestamps)
        |
source-cited chunks + concept and prerequisite graph
        |
BM25 + dense retrieval -> hybrid ranking -> grounded tutor / assessment engine
        |
student answers -> mastery update -> next-best learning activity
```

## Demo course

The first end-to-end demo uses **MIT 6.006 Graph Algorithms**:

`graph representations -> BFS / DFS -> cycle detection / topological sort -> weighted graphs -> Dijkstra`

This narrow scope supports meaningful diagrams, exact source citations,
multiple assessment formats, and a defensible prerequisite graph. See
[the course-fixture rationale](docs/m0-course-fixture.md).

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | Streamlit |
| Backend | Python, FastAPI, Pydantic |
| Document ingestion | PyPDF, PyMuPDF, python-pptx |
| Video transcription | faster-whisper |
| Visual extraction | Pillow, OCR, multimodal vision adapter |
| Retrieval | BM25, BGE embeddings, Chroma, BGE reranker |
| Generation | OpenAI-compatible LLM adapter |
| Learner model | SQLite, Bayesian Knowledge Tracing |
| Evaluation | pytest, RAGAS |

## Run locally

```powershell
cd studybuddy
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Optional capabilities are installed only when needed:

```powershell
pip install -e ".[ingestion,retrieval,app,evaluation]"
```

## Try the current foundation

Until the web dashboard is built, run the small terminal demo to see the course
map, citation-preserving retrieval, refusal of off-topic questions, and learner
mastery update working together:

```powershell
python -m studybuddy.demo
python -m studybuddy.demo --question "Explain quantum entanglement"
```

## Run the interactive prototype

Install the app dependencies, then launch the pastel Streamlit workspace:

```powershell
pip install -e ".[app]"
streamlit run src/studybuddy/app.py
```

The prototype supports PDF/PPTX parsing and cited keyword search within a local
course workspace. Video transcription, generated answers, automated concept
maps, and generated assessments are upcoming work.

## Run the React frontend

The professional frontend is built with React, JavaScript, Vite, and Tailwind
CSS. It is the interface we will connect to the Python AI backend.

```powershell
cd web
npm install
npm run dev
```

Open the local URL shown by Vite, normally `http://localhost:5173`.

The React frontend talks to the local Python API. Start it in a second terminal:

```powershell
cd C:\Users\PALAKM\Downloads\polyglot-shorthand2\studybuddy
.\.venv\Scripts\Activate.ps1
uvicorn studybuddy.api:app --reload --port 8000
```

## Project structure

```text
studybuddy/
├── configs/          # course fixtures and topic maps
├── docs/             # architecture, evaluation, and design notes
├── src/studybuddy/
│   ├── ingestion/    # PDF, slides, video, and chunking pipelines
│   ├── retrieval/    # BM25, dense, hybrid, and reranking logic
│   └── tutor/        # learner model and recommendation policy
├── tests/            # unit and integration tests
└── pyproject.toml
```

## Documentation

- [Architecture decisions](docs/architecture.md)
- [Track D requirements and acceptance criteria](docs/requirements-traceability.md)
- [Demo-course decision](docs/m0-course-fixture.md)

## Roadmap

- [x] Citation-preserving multimodal ingestion foundation
- [x] Concept graph, BKT baseline, and lexical retrieval
- [ ] Dense and hybrid retrieval benchmark
- [ ] Grounded tutor with citations and abstention
- [ ] Verified adaptive assessment engine
- [ ] Dashboard, learner simulations, RAGAS evaluation, and demo video
