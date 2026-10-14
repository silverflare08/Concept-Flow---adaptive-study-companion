import json
from studybuddy.assessment import AssessmentQuestion, enrich_objective_misconceptions, grade_objective
from test_assessment import chunk, mcq_payload

def test_specific_hypothesis_preserves_score():
    q = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    result = grade_objective(q, "Positive gradient")
    source = chunk()
    payload = {"items": [{"id": q.question_id, "misconception": "You may have confused ascent with descent.",
        "correction": "Review the negative gradient direction in the cited passage.",
        "evidence_id": source.chunk_id, "quote": source.text}]}
    output = enrich_objective_misconceptions([q], [result], {source.chunk_id: source},
        analyse_json=lambda _: json.dumps(payload))[0]
    assert output.misconception and "Revision guidance" in output.feedback
    assert output.score == result.score and output.correct == result.correct
    payload["items"][0]["quote"] = "This fabricated quote does not exist in the notes."
    assert enrich_objective_misconceptions([q], [result], {source.chunk_id: source},
        analyse_json=lambda _: json.dumps(payload))[0].misconception is None

def test_blank_and_correct_skip_inference():
    q = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    def unexpected(_):
        raise AssertionError("Unexpected model call")
    for answer in ("", q.correct_answer):
        result = grade_objective(q, answer)
        assert enrich_objective_misconceptions([q], [result], {"optimisation-1": chunk()},
            analyse_json=unexpected)[0].misconception is None

def test_failure_and_uncertainty_do_not_block_report():
    q = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    result = grade_objective(q, "Positive gradient")
    def offline(_):
        raise RuntimeError("offline")
    for analyser in (offline, lambda _: "invalid", lambda _: '{"items":[]}'):
        assert enrich_objective_misconceptions([q], [result], {"optimisation-1": chunk()},
            analyse_json=analyser) == [result]
