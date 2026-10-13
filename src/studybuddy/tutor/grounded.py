"""Source-grounded tutor orchestration.

This module owns the RAG boundary: retrieve course evidence first, then ask an
LLM to teach from that evidence only. It deliberately returns citations from
our retrieval layer rather than trusting an LLM to invent page numbers.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

from studybuddy.ingestion.models import KnowledgeChunk
from studybuddy.retrieval.bm25 import BM25Index


DEFAULT_MODEL = "qwen2.5:3b-instruct"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


def ollama_available() -> bool:
    """Quickly check the local Ollama service before starting a long generation job."""
    endpoint = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    tags_endpoint = endpoint.rsplit("/api/", 1)[0] + "/api/tags"
    try:
        with urlopen(tags_endpoint, timeout=2) as response:  # nosec B310 - local configurable endpoint
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError):
        return False
    configured = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    return any(model.get("name") == configured or model.get("model") == configured for model in payload.get("models", []))


@dataclass(frozen=True)
class TutorReply:
    answer: str
    citations: list[dict[str, object]]
    follow_up: str
    coverage: str


def citation_for_chunk(chunk: KnowledgeChunk) -> dict[str, object]:
    return {
        "label": chunk.citation.label(),
        "source_name": chunk.citation.source_name,
        "page": chunk.citation.page,
        "slide": chunk.citation.slide,
        "start_seconds": chunk.citation.start_seconds,
        "section": chunk.citation.section,
        "evidence_kind": chunk.evidence_kind.value,
        "target_uri": chunk.citation.target_uri(),
        "excerpt": chunk.text[:280].strip(),
    }


def build_tutor_prompt(question: str, evidence: Iterable[KnowledgeChunk], language: str = "english") -> str:
    """Build a constrained prompt from cited course evidence."""
    passages = []
    for number, chunk in enumerate(evidence, start=1):
        passages.append(f"[{number}] {chunk.citation.label()}\n{chunk.text[:1400]}")
    context = "\n\n".join(passages)
    language_instruction = {
        "english": "Explain in clear, natural English.",
        "hindi": "Explain in natural Hindi using Devanagari script, while retaining necessary technical terms in English.",
        "hinglish": "Explain in natural conversational Hinglish: Hindi in Devanagari mixed with familiar English technical terms.",
    }.get(language, "Explain in clear, natural English.")
    return f"""You are ConceptFlow, a patient and accurate study tutor.

Treat the course evidence as a closed book. Every claim in your answer must be
directly supported by those passages. Do not add generic background knowledge.
Do not define terminology that the passages do not define. Do not invent
examples, formulas, consequences, citations, or page numbers. If the passages
do not contain enough information for a useful explanation, say exactly:
"I can't find that in your uploaded material." Keep the response concise: at
most two short paragraphs, then one brief check-understanding question. Do not
include a Sources section because the application shows verified citations
separately.
{language_instruction}
Make mathematical expressions human-readable. Prefer Unicode symbols and plainly written equations,
for example “x² + y² = r²” and “(a + b) / c”. Never output raw LaTeX delimiters such as \\( \\),
\\[ \\], dollar-sign math blocks, or unexplained backslash commands.

COURSE EVIDENCE:
{context}

STUDENT QUESTION: {question}
"""


def call_ollama(prompt: str) -> str:
    """Ask the configured local Ollama model for a non-streaming response."""
    endpoint = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    payload = json.dumps(
        {
            "model": model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0, "num_predict": 260},
        }
    ).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=120) as response:  # nosec B310 - local configurable endpoint
            body = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError) as error:
        raise RuntimeError("Local tutor model is unavailable. Start Ollama and try again.") from error
    answer = body.get("message", {}).get("content", "").strip()
    if not answer:
        raise RuntimeError("The local tutor model returned an empty answer.")
    return answer


def call_ollama_json(prompt: str) -> str:
    """Ask local Ollama for a JSON-only response used by structured features."""
    endpoint = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    payload = json.dumps(
        {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 2400},
        }
    ).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=180) as response:  # nosec B310 - local configurable endpoint
            body = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError) as error:
        raise RuntimeError("The local model did not finish in time. Try fewer sources or restart Ollama.") from error
    answer = body.get("message", {}).get("content", "").strip()
    if not answer:
        raise RuntimeError("The local tutor model returned an empty map draft.")
    return answer


def call_ollama_long(prompt: str) -> str:
    """Generate a longer grounded lesson while keeping the model local and deterministic."""
    endpoint = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    payload = json.dumps({
        "model": model, "stream": False,
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 1100},
    }).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=180) as response:  # nosec B310 - local configurable endpoint
            body = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError) as error:
        raise RuntimeError("The local model did not finish the lesson. Try one material at a time.") from error
    answer = body.get("message", {}).get("content", "").strip()
    if not answer:
        raise RuntimeError("The local tutor model returned an empty lesson.")
    return answer


def tutor_answer(
    question: str,
    chunks: list[KnowledgeChunk],
    *,
    generate: Callable[[str], str] = call_ollama,
    language: str = "english",
) -> TutorReply:
    """Retrieve evidence and generate a grounded teaching response."""
    results = BM25Index(chunks).search(question, limit=4)
    evidence = [result.chunk for result in results]
    if not evidence:
        return TutorReply(
            answer="I can't find that in your uploaded material.",
            citations=[],
            follow_up="Try asking about a topic or phrase that appears in this course.",
            coverage="not_covered",
        )
    answer = generate(build_tutor_prompt(question, evidence, language))
    return TutorReply(
        answer=answer,
        citations=[citation_for_chunk(chunk) for chunk in evidence],
        follow_up="What part would you like to practise next?",
        coverage="course_backed",
    )
