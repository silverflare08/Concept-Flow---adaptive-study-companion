"""ConceptFlow's interactive Streamlit prototype.

Run with:
    streamlit run src/studybuddy/app.py
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import streamlit as st

from studybuddy.ingestion.chunker import chunk_segments
from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType
from studybuddy.ingestion.pdf import ingest_pdf
from studybuddy.ingestion.slides import ingest_slides
from studybuddy.retrieval.bm25 import BM25Index, RetrievedChunk
from studybuddy.tutor.bkt import BKTParameters, update_mastery


st.set_page_config(page_title="ConceptFlow", page_icon="🌿", layout="wide")


def apply_theme() -> None:
    st.markdown(
        """
        <style>
          :root { --ink: #2e3d4a; --lavender: #eee9ff; --mint: #e1f3ed; --peach: #fff0e7; }
          .stApp { background: linear-gradient(135deg, #fcfbff 0%, #f5fbf8 55%, #fff9f4 100%); color: var(--ink); }
          [data-testid="stSidebar"] { background: #f5f0ff; }
          h1, h2, h3 { color: #34465a; }
          .stTextInput input { background: #ffffff !important; color: #34465a !important; border: 1px solid #dcd5ea !important; }
          .stTextInput input::placeholder { color: #718096 !important; }
          [data-testid="stRadio"] label, [data-testid="stRadio"] label p { color: #34465a !important; }
          button[data-baseweb="tab"] p { color: #52606d !important; }
          div[data-testid="stMetric"] { background: rgba(255,255,255,.72); border: 1px solid #e7e2f1; border-radius: 16px; padding: 12px; }
          .soft-card { background: rgba(255,255,255,.78); border: 1px solid #ebe7f2; border-radius: 18px; padding: 1rem 1.2rem; margin: .4rem 0; }
          .concept-card { background: var(--mint); border-radius: 14px; padding: .75rem; min-height: 70px; text-align: center; }
          .stButton > button { background: #7065a8; color: white; border: 0; border-radius: 10px; padding: .5rem 1rem; }
          .stButton > button:hover { background: #5e548e; color: white; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def default_chunks() -> list[KnowledgeChunk]:
    """Small honest demo corpus used until the learner uploads course material."""
    entries = [
        ("bfs", "Breadth-first search uses a queue and discovers vertices in graph layers.", 4, ["bfs"]),
        ("dfs", "Depth-first search uses recursion or an explicit stack before backtracking.", 8, ["dfs"]),
        (
            "topological-sort",
            "Topological sorting uses DFS finishing order on a directed acyclic graph.",
            12,
            ["dfs", "topological-sort"],
        ),
        (
            "dijkstra",
            "Dijkstra's algorithm finds shortest paths when edge weights are non-negative.",
            18,
            ["weighted-graphs", "dijkstra"],
        ),
    ]
    return [
        KnowledgeChunk(
            chunk_id=chunk_id,
            text=text,
            token_count=len(text.split()),
            concepts=concepts,
            citation=CitationAnchor(
                source_id="graph-demo",
                source_name="Graph Algorithms demo notes",
                source_type=SourceType.PDF,
                source_uri="https://example.edu/graph-algorithms-notes.pdf",
                page=page,
            ),
        )
        for chunk_id, text, page, concepts in entries
    ]


def initialise_state() -> None:
    if "chunks" not in st.session_state:
        st.session_state.chunks = default_chunks()
        st.session_state.course_name = "Graph Algorithms demo"
        st.session_state.sources = ["Graph Algorithms demo notes"]
    if "mastery" not in st.session_state:
        st.session_state.mastery = {
            "graph-representations": 0.45,
            "bfs": 0.35,
            "dfs": 0.30,
            "topological-sort": 0.20,
            "weighted-graphs": 0.25,
            "dijkstra": 0.15,
        }


def ingest_uploads(files: list[object]) -> tuple[int, list[str]]:
    """Persist an upload locally and add its page/slide-cited chunks to this session."""
    upload_root = Path("data/uploads")
    upload_root.mkdir(parents=True, exist_ok=True)
    new_chunks: list[KnowledgeChunk] = []
    messages: list[str] = []

    for file in files:
        suffix = Path(file.name).suffix.lower()
        stored_path = upload_root / f"{uuid4().hex}-{Path(file.name).name}"
        stored_path.write_bytes(file.getvalue())
        source_id = f"upload-{uuid4().hex[:10]}"
        try:
            if suffix == ".pdf":
                result = ingest_pdf(stored_path, source_id=source_id, source_name=file.name)
                new_chunks.extend(chunk_segments(result.segments))
                messages.append(f"{file.name}: {len(result.segments)} page/figure evidence units found.")
            elif suffix == ".pptx":
                result = ingest_slides(stored_path, source_id=source_id, source_name=file.name)
                new_chunks.extend(chunk_segments(result.segments))
                messages.append(f"{file.name}: {len(result.segments)} slide/figure evidence units found.")
            else:
                messages.append(f"{file.name}: video saved; transcription UI will be connected in the next milestone.")
        except Exception as error:  # UI boundary: preserve the app instead of hiding parsing errors.
            messages.append(f"{file.name}: could not be processed ({error}).")

    if new_chunks:
        st.session_state.chunks.extend(new_chunks)
        st.session_state.sources.extend(file.name for file in files if Path(file.name).suffix.lower() in {".pdf", ".pptx"})
    return len(new_chunks), messages


def show_evidence(result: RetrievedChunk) -> None:
    citation = result.chunk.citation
    st.markdown('<div class="soft-card">', unsafe_allow_html=True)
    st.markdown(f"**Source-backed evidence**  \\n+{result.chunk.text}")
    st.caption(f"{citation.label()} · BM25 score {result.score:.2f}")
    if citation.target_uri():
        st.link_button("Open source location", citation.target_uri())
    else:
        st.caption("This is a local upload. Source-location opening will be added with the course workspace.")
    st.markdown("</div>", unsafe_allow_html=True)


def app() -> None:
    apply_theme()
    initialise_state()

    with st.sidebar:
        st.markdown("## 🌿 ConceptFlow")
        st.caption("A calm, evidence-first study space")
        st.divider()
        st.markdown("### Study materials")
        uploads = st.file_uploader(
            "Add PDFs, PPTX, or a lecture video",
            type=["pdf", "pptx", "mp4", "mov", "mkv"],
            accept_multiple_files=True,
            help="PDF and PPTX parsing work now. Video transcription is the next ingestion milestone.",
        )
        if st.button("Analyse materials", use_container_width=True, disabled=not uploads):
            count, messages = ingest_uploads(uploads or [])
            for message in messages:
                st.info(message)
            if count:
                st.success(f"Added {count} searchable, cited chunks to this session.")
        st.divider()
        st.caption("Current course")
        st.write(st.session_state.course_name)
        st.caption("Sources in this session")
        for source in dict.fromkeys(st.session_state.sources):
            st.write(f"• {source}")

    st.title("Your study space")
    st.caption("Explore with confidence, practise with purpose, and build mastery gently.")
    learn_tab, practise_tab, progress_tab, course_tab = st.tabs(
        ["📖 Learn", "✍️ Practise", "🌱 Progress", "🗂️ Course map"]
    )

    with learn_tab:
        st.subheader("Ask about your course")
        question = st.text_input(
            "What would you like to understand?",
            placeholder="For example: Which traversal uses a queue?",
        )
        if st.button("Find evidence", type="primary"):
            results = BM25Index(st.session_state.chunks).search(question)
            if not question.strip():
                st.warning("Write a question first.")
            elif not results:
                st.warning("Not covered by the material currently indexed in this study space.")
                st.caption("This is intentional: ConceptFlow should not invent course knowledge.")
            else:
                st.success("Found course-backed evidence")
                show_evidence(results[0])
                if len(results) > 1:
                    with st.expander("More matching evidence"):
                        for result in results[1:]:
                            show_evidence(result)
        st.info("The current screen shows retrieval evidence. Full LLM tutor explanations are the next AI milestone.")

    with practise_tab:
        st.subheader("Quick diagnostic")
        st.write("Which graph traversal primarily uses a queue?")
        answer = st.radio("Choose one answer", ["Depth-first search", "Breadth-first search", "Dijkstra's algorithm"], index=None)
        if st.button("Check answer"):
            if answer is None:
                st.warning("Choose an answer before checking it.")
            else:
                correct = answer == "Breadth-first search"
                before = st.session_state.mastery["bfs"]
                st.session_state.mastery["bfs"] = update_mastery(
                    before, correct=correct, parameters=BKTParameters(learn=0.1)
                )
                if correct:
                    st.success("Correct. BFS explores graph layers using a queue.")
                else:
                    st.error("Not quite. BFS uses a queue; DFS uses a stack or recursion.")
                st.caption(
                    f"BFS mastery updated from {before:.0%} to {st.session_state.mastery['bfs']:.0%}."
                )
                st.info("Feedback is currently rule-based for this diagnostic. Source-validated generated assessments come next.")

    with progress_tab:
        st.subheader("Your concept mastery")
        ordered = sorted(st.session_state.mastery.items(), key=lambda item: item[1])
        left, right = st.columns(2)
        for index, (concept, value) in enumerate(ordered):
            target = left if index % 2 == 0 else right
            with target:
                st.markdown(f"**{concept.replace('-', ' ').title()}**")
                st.progress(value, text=f"{value:.0%} mastery")
        weakest = ordered[0][0].replace("-", " ").title()
        st.markdown(f'<div class="soft-card">Next gentle focus: <b>{weakest}</b></div>', unsafe_allow_html=True)

    with course_tab:
        st.subheader("Graph Algorithms learning flow")
        st.caption("This is the current demo-course map. A generated map for uploaded courses will be added later.")
        row_one = st.columns(3)
        row_one[0].markdown('<div class="concept-card">Graph representations</div>', unsafe_allow_html=True)
        row_one[1].markdown('<div class="concept-card">BFS</div>', unsafe_allow_html=True)
        row_one[2].markdown('<div class="concept-card">DFS</div>', unsafe_allow_html=True)
        st.markdown("<center>↓</center>", unsafe_allow_html=True)
        row_two = st.columns(3)
        row_two[0].markdown('<div class="concept-card">Cycle detection</div>', unsafe_allow_html=True)
        row_two[1].markdown('<div class="concept-card">Topological sort</div>', unsafe_allow_html=True)
        row_two[2].markdown('<div class="concept-card">Weighted graphs → Dijkstra</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    app()
