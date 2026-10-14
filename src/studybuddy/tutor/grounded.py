"""Source-grounded tutor orchestration.

This module owns the RAG boundary: retrieve course evidence first, then ask an
LLM to teach from that evidence only. It deliberately returns citations from
our retrieval layer rather than trusting an LLM to invent page numbers.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

from studybuddy.ingestion.models import KnowledgeChunk
from studybuddy.language import HINGLISH_INSTRUCTION, matches_requested_language, rewrite_prompt
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
    evidence_chunk_ids: list[str]


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


def build_tutor_prompt(
    question: str, evidence: Iterable[KnowledgeChunk], language: str = "english",
    learner_context: str = "No learner history is available yet.",
) -> str:
    """Build a constrained prompt from cited course evidence."""
    passages = []
    for number, chunk in enumerate(evidence, start=1):
        passages.append(f"[{number}] {chunk.citation.label()}\n{chunk.text[:1400]}")
    context = "\n\n".join(passages)
    language_instruction = {
        "english": "Explain in clear, natural English.",
        "hindi": "Explain in natural Hindi using Devanagari script, while retaining necessary technical terms in English.",
        "hinglish": HINGLISH_INSTRUCTION,
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
Make mathematical expressions human-readable. Use Unicode for simple equations.
For fractions, sums, integrals or complex expressions, use valid LaTeX enclosed in
$...$ for inline maths or $$...$$ for a separate equation; the app typesets these.
Never output raw LaTeX commands outside math delimiters. Put each equation on its own line.
Preserve the source notation exactly. If symbols or equations are unclear or contradictory,
say they need checking in the original page; never guess a correction.
Use clean Markdown like a short textbook chapter: meaningful headings, short paragraphs,
labelled definitions, numbered solution steps, and concise bullet lists. Never use repeated
asterisks, slashes, raw formatting characters, or ASCII art as decoration.

LEARNER MODEL:
{learner_context}
Adapt the depth to this history. Re-explain weak topics slowly, connect to stronger prior topics,
and finish with one check question suited to the learner's current mastery.

COURSE EVIDENCE:
{context}

STUDENT QUESTION: {question}
"""


from studybuddy.cancellation import cancellable
from studybuddy.local_cache import cache_path, read_cached, save_cached

@cancellable
def call_ollama(prompt: str) -> str:
    """Ask the configured local Ollama model for a non-streaming response."""
    endpoint = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    payload = json.dumps(
        {
            "model": model,
            "stream": False,
            "keep_alive": "10m",
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


@cancellable
def call_ollama_json(prompt: str) -> str:
    """Ask local Ollama for a JSON-only response used by structured features."""
    endpoint = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    output_format: object = "json"
    num_predict = 2400
    request_timeout = 180
    # Assessment schemas constrain structure, not factual correctness. Independent
    # answer/source checks still run after drafting.
    if prompt.startswith("Create exactly") or prompt.startswith("Rewrite this VERIFIED assessment"):
        from studybuddy.assessment import AssessmentDraft
        output_format = AssessmentDraft.model_json_schema()
        requested = re.search(r"Create exactly (\d+) assessment questions", prompt)
        if requested:
            request_timeout = 45
            count = int(requested.group(1))
            # Reserve enough output for the worked explanations and structured
            # fields; too-small caps often truncate the JSON and force another
            # full local-model call. The cap keeps larger exams bounded.
            num_predict = min(4096, max(1200, 600 + count * 400))
            output_format["properties"]["questions"].update(minItems=count, maxItems=count)
            question_schema = output_format["$defs"]["AssessmentQuestion"]
            question_schema["properties"].pop("question_id", None)
            question_schema["required"] = list(dict.fromkeys(question_schema["required"] + ["options", "evidence_chunk_ids"]))
            kinds = re.search(r"Allowed question types: (\[[^\n]+\])", prompt)
            if kinds:
                allowed_types = json.loads(kinds.group(1))
                question_schema["properties"]["question_type"]["enum"] = allowed_types
                if allowed_types == ["mcq"]:
                    question_schema["properties"]["options"].update(minItems=4, maxItems=4)
            ids = list(dict.fromkeys(re.findall(r"CHUNK_ID: ([^\n]+)", prompt)))
            if ids:
                question_schema["properties"]["evidence_chunk_ids"].update(minItems=1, maxItems=2, items={"type": "string", "enum": ids})
        elif "Romanised Hindi" in prompt:
            # Romanise the teaching text while locking the already verified key,
            # IDs and structural fields. Translation must not invalidate a quiz.
            import copy
            original, _ = json.JSONDecoder().raw_decode(prompt.split("ASSESSMENT JSON:\n", 1)[1].lstrip())
            variants = []
            for item in original["questions"]:
                variant = copy.deepcopy(output_format["$defs"]["AssessmentQuestion"])
                for key in ("question_id", "question_type", "difficulty", "evidence_chunk_ids", "numerical_tolerance", "options", "correct_answer"):
                    variant["properties"][key] = {"const": item[key]}
                variant["required"] = list(dict.fromkeys(variant["required"] + list(item)))
                variants.append(variant)
            output_format["properties"]["questions"].update(minItems=len(variants), maxItems=len(variants), items={"anyOf": variants})
    elif prompt.startswith("Independently solve every assessment question"):
        request_timeout = 45
        # The verifier used to return unconstrained JSON and frequently omitted
        # or mistyped random question IDs. The application then treated those
        # otherwise usable decisions as failed verification. Constrain the IDs
        # and require one decision for every submitted question.
        questions_text = prompt.split("QUESTIONS: ", 1)[1].split("\nEVIDENCE:", 1)[0]
        questions = json.loads(questions_text)
        question_ids = list(dict.fromkeys(str(item["question_id"]) for item in questions))
        num_predict = 200 + 180 * len(question_ids)
        output_format = {
            "type": "object",
            "properties": {
                "decisions": {
                    "type": "array",
                    "minItems": len(question_ids),
                    "maxItems": len(question_ids),
                    "items": {
                        "type": "object",
                        "properties": {
                            "question_id": {"type": "string", "enum": question_ids},
                            "valid": {"type": "boolean"},
                            "verified_answer": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["question_id", "valid", "verified_answer", "reason"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["decisions"],
            "additionalProperties": False,
        }
    elif prompt.startswith("Grade these student answers"):
        data = json.loads(prompt.split("\nDATA: ", 1)[1])
        request_timeout = 60
        num_predict = min(4096, 300 + 250 * len(data))
        output_format = {"type": "object", "properties": {"items": {
            "type": "array", "minItems": len(data), "maxItems": len(data),
            "items": {"type": "object", "properties": {
                "question_id": {"type": "string", "enum": [item["question_id"] for item in data]},
                "score": {"type": "number", "minimum": 0, "maximum": 1},
                "feedback": {"type": "string"}, "misconception": {"type": ["string", "null"]},
            }, "required": ["question_id", "score", "feedback", "misconception"], "additionalProperties": False},
        }}, "required": ["items"], "additionalProperties": False}
    elif prompt.startswith("Analyse incorrect objective answers"):
        request_timeout = 30
    elif prompt.startswith("Create a study guide for"):
        from studybuddy.course_map import CourseMap
        output_format = CourseMap.model_json_schema()
        output_format["properties"].pop("course_id", None)
        output_format["properties"].pop("title", None)
        output_format["required"] = ["concepts", "prerequisite_edges"]
        concept_schema = output_format["$defs"]["Concept"]
        concept_schema["required"] = list(concept_schema["properties"])
        ids = list(dict.fromkeys(re.findall(r"CHUNK_ID: ([^\n]+)", prompt)))
        if ids:
            concept_schema["properties"]["evidence_chunk_ids"].update(minItems=1, items={"type": "string", "enum": ids})
    payload = json.dumps(
        {
            "model": model,
            "stream": False,
            "keep_alive": "10m",
            "format": output_format,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": num_predict, "repeat_penalty": 1.1},
        }
    ).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=request_timeout) as response:  # nosec B310 - local configurable endpoint
            body = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError) as error:
        raise RuntimeError("The local model did not finish in time. Try fewer sources or restart Ollama.") from error
    answer = body.get("message", {}).get("content", "").strip()
    if not answer:
        raise RuntimeError("The local tutor model returned an empty map draft.")
    return answer


@cancellable
def call_ollama_long(prompt: str) -> str:
    """Generate a longer grounded lesson while keeping the model local and deterministic."""
    endpoint = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    cached_path = cache_path('lessons', {'version': 2, 'model': model, 'endpoint': endpoint, 'prompt': prompt})
    cached = read_cached(cached_path)
    if cached is not None:
        return cached
    payload = json.dumps({
        "model": model, "stream": False, "keep_alive": "10m",
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1800, "repeat_penalty": 1.12},
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
    from studybuddy.tutor.material_overview import usable_lesson
    if body.get("done_reason") == "length" or not usable_lesson(answer):
        raise RuntimeError("The local model produced an unfinished or repetitive lesson. Showing source excerpts instead.")
    save_cached(cached_path, answer)
    return answer


@cancellable
def verify_lesson(prompt: str) -> str:
    """Independent source-comparison pass, not a mathematical proof of correctness."""
    endpoint = os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    checked_path = cache_path("lesson-checks", {"version": 1, "prompt": prompt, "model": model, "endpoint": endpoint})
    cached = read_cached(checked_path)
    if cached:
        try:
            if json.loads(cached).get("supported") is True:
                return cached
        except (ValueError, AttributeError):
            pass
    payload = json.dumps({
        "model": model, "stream": False,
        "format": "json", "keep_alive": "10m",
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 350},
    }).encode("utf-8")
    try:
        with urlopen(Request(endpoint, data=payload, headers={"Content-Type": "application/json"}), timeout=120) as response:
            body = json.loads(response.read().decode())
        result = body["message"]["content"]
        verdict = json.loads(result)
        if not isinstance(verdict, dict) or not isinstance(verdict.get("supported"), bool) or body.get("done_reason") == "length":
            raise RuntimeError("The lesson check did not return a complete verdict.")
        if verdict["supported"]:
            save_cached(checked_path, result)
        return result
    except (URLError, TimeoutError, KeyError, ValueError) as error:
        raise RuntimeError("The lesson could not be checked against its sources.") from error


def tutor_answer(
    question: str,
    chunks: list[KnowledgeChunk],
    *,
    generate: Callable[[str], str] = call_ollama,
    language: str = "english",
    learner_context: str = "No learner history is available yet.",
) -> TutorReply:
    """Retrieve evidence and generate a grounded teaching response."""
    results = BM25Index(chunks).search(question, limit=4)
    evidence = [result.chunk for result in results]
    if not evidence and (language == "hinglish" or language == "hindi" and re.search(r"[\u0900-\u097f]", question)):
        english_query = generate(
            "Translate this student search query into concise English keywords for retrieving "
            "course notes. Return only the keywords and do not answer the question.\nQUERY: " + question
        ).strip()
        evidence = [result.chunk for result in BM25Index(chunks).search(english_query, limit=4)]
    if not evidence:
        return TutorReply(
            answer="I can't find that in your uploaded material.",
            citations=[],
            follow_up="Try asking about a topic or phrase that appears in this course.",
            coverage="not_covered",
            evidence_chunk_ids=[],
        )
    answer = generate(build_tutor_prompt(question, evidence, language, learner_context))
    if language != "english" and not matches_requested_language(answer, language):
        answer = generate(rewrite_prompt(answer, language))
        if not matches_requested_language(answer, language):
            raise RuntimeError(
                f"The local model did not follow the selected {language.title()} language. Hindi and Hinglish are experimental; try English."
            )
    return TutorReply(
        answer=answer,
        citations=[citation_for_chunk(chunk) for chunk in evidence],
        follow_up="What part would you like to practise next?",
        coverage="course_backed",
        evidence_chunk_ids=[chunk.chunk_id for chunk in evidence],
    )
