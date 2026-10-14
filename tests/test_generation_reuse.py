import io
import json
import pytest
from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType
from studybuddy.tutor.course_map_generator import generate_course_map
from studybuddy.tutor.evidence_context import evidence_texts
from studybuddy.tutor import grounded


def chunk(text="A definition of energy."):
    return KnowledgeChunk(chunk_id="energy-1", text=text, token_count=len(text.split()),
                          citation=CitationAnchor(source_id="energy", source_name="Physics", source_type=SourceType.PDF, page=1))


def draft():
    return json.dumps({"concepts": [{"concept_id": "energy", "name": "Energy", "topic": "Physics",
        "description": "A source-backed definition.", "evidence_chunk_ids": ["energy-1"],
        "key_points": ["Read the definition"], "study_steps": ["Recall the definition"]}], "prerequisite_edges": []})


def test_validated_guide_is_reused_and_changed_content_invalidates(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCEPTFLOW_CACHE_DIR", str(tmp_path))
    calls = []
    def generate(prompt):
        calls.append(prompt)
        return draft()
    first = generate_course_map("Physics", [chunk()], generate_json=generate, reuse_cache=True)
    updates = []
    second = generate_course_map("Physics", [chunk()], generate_json=generate, reuse_cache=True,
                                 on_progress=lambda done, total: updates.append((done, total)))
    assert first == second and len(calls) == 1 and updates[-1] == (1, 1)
    generate_course_map("Physics", [chunk("Changed evidence.")], generate_json=generate, reuse_cache=True)
    assert len(calls) == 2
    monkeypatch.setenv("OLLAMA_MODEL", "another-model")
    generate_course_map("Physics", [chunk()], generate_json=generate, reuse_cache=True)
    assert len(calls) == 3


def test_offline_guide_is_not_cached_as_completed_ai_result(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCEPTFLOW_CACHE_DIR", str(tmp_path))
    def offline(prompt):
        raise RuntimeError("Offline")
    generate_course_map("Physics", [chunk()], generate_json=offline, reuse_cache=True)
    calls = []
    generate_course_map("Physics", [chunk()], generate_json=lambda prompt: calls.append(prompt) or draft(), reuse_cache=True)
    assert len(calls) == 1


def test_overlap_compaction_keeps_new_words_and_never_crosses_pages():
    first = chunk("intro " + " ".join(f"word{i}" for i in range(12)))
    second = chunk(" ".join(f"word{i}" for i in range(12)) + " new equation")
    assert evidence_texts([first, second]) == [first.text, "new equation"]
    other_page = second.model_copy(update={"citation": second.citation.model_copy(update={"page": 2})})
    assert evidence_texts([first, other_page]) == [first.text, second.text]
    assert second.text.endswith("new equation")


def test_approved_lesson_check_is_cached_but_rejections_are_not(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCEPTFLOW_CACHE_DIR", str(tmp_path))
    calls = []
    def response(request, **kwargs):
        calls.append(request)
        return io.BytesIO(json.dumps({"message": {"content": '{"supported": true, "issues": []}'}}).encode())
    monkeypatch.setattr(grounded, "urlopen", response)
    assert grounded.verify_lesson("same evidence and lesson") == grounded.verify_lesson("same evidence and lesson")
    assert len(calls) == 1
    def rejected(request, **kwargs):
        calls.append(request)
        return io.BytesIO(json.dumps({"message": {"content": '{"supported": false, "issues": ["wrong"]}'}}).encode())
    monkeypatch.setattr(grounded, "urlopen", rejected)
    grounded.verify_lesson("bad lesson")
    grounded.verify_lesson("bad lesson")
    assert len(calls) == 3


def test_truncated_checks_are_not_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCEPTFLOW_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(grounded, "urlopen", lambda *args, **kwargs: io.BytesIO(json.dumps({
        "done_reason": "length", "message": {"content": '{"supported": true}'},
    }).encode()))
    with pytest.raises(RuntimeError, match="complete verdict"):
        grounded.verify_lesson("unfinished check")
    assert not list(tmp_path.rglob("*.json"))


def test_assessment_model_call_uses_a_schema_and_exact_question_count(monkeypatch):
    seen = []
    def response(request, **kwargs):
        seen.append(json.loads(request.data))
        return io.BytesIO(json.dumps({"message": {"content": '{"title": "Quiz", "questions": []}'}}).encode())
    monkeypatch.setattr(grounded, "urlopen", response)
    grounded.call_ollama_json("Create exactly 2 assessment questions for Physics.")
    schema = seen[0]["format"]
    assert isinstance(schema, dict)
    assert schema["properties"]["questions"]["minItems"] == 2
    assert schema["properties"]["questions"]["maxItems"] == 2


def test_assessment_verifier_schema_locks_every_question_id(monkeypatch):
    seen = []
    questions = [
        {"question_id": "question-one", "prompt": "Q1"},
        {"question_id": "question-two", "prompt": "Q2"},
    ]

    def response(request, **kwargs):
        seen.append(json.loads(request.data))
        return io.BytesIO(json.dumps({"message": {"content": '{"decisions": []}'}}).encode())

    monkeypatch.setattr(grounded, "urlopen", response)
    prompt = (
        "Independently solve every assessment question from the supplied evidence.\n"
        "QUESTIONS: " + json.dumps(questions) + "\nEVIDENCE:\nsource text"
    )
    grounded.call_ollama_json(prompt)

    schema = seen[0]["format"]
    decision = schema["properties"]["decisions"]
    assert decision["minItems"] == decision["maxItems"] == 2
    assert decision["items"]["properties"]["question_id"]["enum"] == ["question-one", "question-two"]


def test_hinglish_assessment_schema_locks_the_verified_answer_key(monkeypatch):
    from studybuddy.assessment import AssessmentDraft, AssessmentQuestion
    from studybuddy.language import HINGLISH_INSTRUCTION
    assessment = AssessmentDraft(title="BFS", questions=[AssessmentQuestion(
        question_type="mcq", prompt="Which structure does BFS use?", topic="BFS", difficulty="easy",
        options=["Queue", "Stack", "Tree", "Heap"], correct_answer="Queue", explanation="BFS uses a queue.",
        evidence_chunk_ids=["bfs-1"],
    )])
    seen = []
    def response(request, **kwargs):
        seen.append(json.loads(request.data))
        return io.BytesIO(json.dumps({"message": {"content": assessment.model_dump_json()}}).encode())
    monkeypatch.setattr(grounded, "urlopen", response)
    grounded.call_ollama_json("Rewrite this VERIFIED assessment. " + HINGLISH_INSTRUCTION + "\nASSESSMENT JSON:\n" + assessment.model_dump_json() + "\nThe previous language rewrite failed. Try again.")
    fields = seen[0]["format"]["properties"]["questions"]["items"]["anyOf"][0]["properties"]
    assert fields["correct_answer"]["const"] == "Queue"
    assert fields["options"]["const"] == ["Queue", "Stack", "Tree", "Heap"]
    assert fields["evidence_chunk_ids"]["const"] == ["bfs-1"]
