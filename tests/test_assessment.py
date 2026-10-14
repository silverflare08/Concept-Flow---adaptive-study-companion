import json

import pytest

from studybuddy.assessment import (
    AssessmentQuestion,
    generate_assessment,
    grade_objective,
    grade_short_answer,
    grade_short_answer_set,
    humanize_math_text,
    localize_assessment,
    parse_assessment_draft,
    question_fingerprint,
    question_similarity,
    verify_question_set,
    question_quality_problem,
    evaluate_numeric_expression,
    validate_new_question_structure,
)
from studybuddy.ingestion.models import CitationAnchor, KnowledgeChunk, SourceType


def chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="optimisation-1",
        text="Gradient descent updates parameters in the negative gradient direction. A learning rate of 0.1 controls the step size.",
        token_count=18,
        citation=CitationAnchor(
            source_id="notes", source_name="ML notes.pdf", source_type=SourceType.PDF, page=8,
        ),
    )


def test_raw_latex_is_converted_to_readable_math() -> None:
    assert humanize_math_text(r"\(\frac{a}{b} \times \pi\)") == "(a) ÷ (b) × π"


def mcq_payload(prompt: str = "Which direction does gradient descent use?") -> dict:
    return {
        "title": "Optimisation check",
        "questions": [{
            "question_type": "mcq",
            "prompt": prompt,
            "topic": "Gradient descent",
            "difficulty": "easy",
            "options": ["Negative gradient", "Positive gradient", "Random direction", "No direction"],
            "correct_answer": "Negative gradient",
            "explanation": "The notes state that gradient descent moves parameters in the negative gradient direction. This direction reduces the objective locally, so the negative gradient is the supported answer rather than a positive or random direction.",
            "grading_criteria": [],
            "evidence_chunk_ids": ["optimisation-1"],
        }],
    }


def verifier(prompt: str) -> str:
    questions = json.loads(prompt.split("QUESTIONS: ", 1)[1].split("\nEVIDENCE:", 1)[0])
    return json.dumps({"decisions": [
        {"question_id": question["question_id"], "valid": True, "verified_answer": "Negative gradient", "reason": "Supported by the passage.",
         "support_quote": "Gradient descent updates parameters in the negative gradient direction.", "cognitive_level": question["difficulty"]}
        for question in questions
    ]})


def test_question_schema_rejects_invalid_mcq() -> None:
    payload = mcq_payload()
    payload["questions"][0]["options"] = ["A", "B"]
    with pytest.raises(ValueError, match="four distinct options"):
        parse_assessment_draft(json.dumps(payload), allowed_chunk_ids={"optimisation-1"})


def test_label_only_mcq_cannot_bypass_source_checks():
    payload = mcq_payload()
    item = payload["questions"][0]
    item.update(options=["A", "B", "C", "D"], correct_answer="D")
    with pytest.raises(ValueError, match="actual answer choices"):
        parse_assessment_draft(json.dumps(payload), allowed_chunk_ids={"optimisation-1"})


def test_independent_solver_never_receives_the_proposed_key_or_explanation():
    question = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    def independent(prompt):
        data = json.loads(prompt.split("QUESTIONS: ", 1)[1].split("\nEVIDENCE:", 1)[0])[0]
        assert "correct_answer" not in data and "explanation" not in data and "grading_criteria" not in data
        return json.dumps({"decisions": [{"question_id": "1", "valid": True, "verified_answer": "Negative gradient",
            "support_quote": "Gradient descent updates parameters in the negative gradient direction.",
            "cognitive_level": "easy", "reason": "The quoted update rule specifies the direction."}]})
    result = verify_question_set([question], {"optimisation-1": chunk()}, verify_json=independent)
    assert result[question.question_id][0]


@pytest.mark.parametrize("quote,level", [("Invented support that does not appear in the source.", "easy"),
                                         ("Gradient descent updates parameters in the negative gradient direction.", "hard")])
def test_verifier_rejects_invented_support_or_wrong_difficulty(quote, level):
    question = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    result = verify_question_set([question], {"optimisation-1": chunk()}, verify_json=lambda prompt: json.dumps({
        "decisions": [{"question_id": "1", "valid": True, "verified_answer": "Negative gradient",
                       "support_quote": quote, "cognitive_level": level, "reason": "Supported"}]}))
    assert not result[question.question_id][0]


def test_medium_exam_does_not_silently_turn_into_copied_recall():
    def offline(prompt):
        raise RuntimeError("Unavailable")
    with pytest.raises(ValueError, match="No questions passed"):
        generate_assessment(course_name="ML", chunks=[chunk()], count=3, difficulty="medium", question_types=["mcq"],
            scope=[], previous_prompts=[], generate_json=offline, verify_json=offline)


def test_copied_passage_is_not_a_medium_reasoning_question():
    question = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    question.difficulty = "medium"
    question.prompt = "Explain this: Gradient descent updates parameters in the negative gradient direction."
    assert "copies" in question_quality_problem(question, {"optimisation-1": chunk()}, "medium")


@pytest.mark.parametrize("expression", ["20", "__import__('os').system('anything')", "x*5", "2**1000000", "1/0"])
def test_numeric_verification_never_executes_code_or_accepts_asserted_results(expression):
    with pytest.raises((ValueError, ZeroDivisionError)):
        evaluate_numeric_expression(expression)


def test_numeric_verification_recomputes_products_and_multi_step_results():
    assert evaluate_numeric_expression("2 * 5") == 10
    assert evaluate_numeric_expression("0.5 * 2 * (3 * 4)**2") == 144


def test_model_cannot_bypass_numerical_checks_with_a_huge_tolerance():
    with pytest.raises(ValueError):
        validate_new_question_structure(AssessmentQuestion(question_type="numerical", prompt="Calculate 2 * 5.", topic="Arithmetic", difficulty="medium",
                           correct_answer="20", explanation="An explanation.", evidence_chunk_ids=["optimisation-1"], numerical_tolerance=100))


def test_historical_label_only_papers_remain_readable_but_cannot_be_new_drafts():
    item = mcq_payload()["questions"][0]
    item.update(options=["A", "B", "C", "D"], correct_answer="D")
    saved_question = AssessmentQuestion.model_validate(item)
    assert saved_question.correct_answer == "D"
    with pytest.raises(ValueError, match="actual answer choices"):
        validate_new_question_structure(saved_question)


def test_answer_key_must_agree_with_its_own_worked_calculation():
    question = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    question.options = ["10 m/s", "20 m/s", "30 m/s", "40 m/s"]
    question.correct_answer = "20 m/s"
    question.explanation = "For a car accelerating from rest, use the source rule v = a*t. Substitute the stated acceleration and time: 2 * 5 = 10 m/s. This gives the final speed."
    assert "contradicts" in question_quality_problem(question, {"optimisation-1": chunk()}, "easy")


def test_blind_verifier_cannot_claim_twenty_for_two_times_five():
    material = chunk().model_copy(update={"text": "For constant acceleration from rest, final speed is v = a*t."})
    question = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    question.prompt = "Calculate the speed after 5 seconds at a constant acceleration of 2 m/s squared from rest."
    question.difficulty = "medium"
    question.options = ["10 m/s", "20 m/s", "30 m/s", "40 m/s"]
    question.correct_answer = "20 m/s"
    result = verify_question_set([question], {"optimisation-1": material}, verify_json=lambda prompt: json.dumps({
        "decisions": [{"question_id": "1", "valid": True, "verified_answer": "20 m/s", "calculation": "2 * 5",
                       "support_quote": material.text, "cognitive_level": "medium", "reason": "Computed"}]}))
    assert not result[question.question_id][0]


def test_numeric_solver_expression_takes_precedence_over_model_mental_arithmetic():
    material = chunk().model_copy(update={"text": "Kinetic energy is K = 0.5*m*v*v in joules."})
    question = AssessmentQuestion(question_type="numerical", prompt="Calculate kinetic energy for mass 1000 kg and speed 20 m/s.",
        topic="Mechanics", difficulty="medium", correct_answer="200000", explanation="A sufficiently detailed worked explanation.", evidence_chunk_ids=["optimisation-1"])
    result = verify_question_set([question], {"optimisation-1": material}, verify_json=lambda prompt: json.dumps({
        "decisions": [{"question_id": "1", "valid": True, "verified_answer": "20000 Joules", "calculation": "0.5 * 1000 * (20^2)",
                       "support_quote": material.text, "cognitive_level": "medium", "reason": "Apply the cited rule."}]}))
    assert result[question.question_id][0]
    assert float(result[question.question_id][2]) == 200000


def test_negated_short_answer_cannot_pass_on_keyword_overlap():
    item = mcq_payload()["questions"][0]
    item.update(question_type="short_answer", options=[], correct_answer="Gradient descent does not update parameters in the negative gradient direction.",
                grading_criteria=["Explain the update direction"])
    with pytest.raises(ValueError, match="No questions passed"):
        generate_assessment(course_name="ML", chunks=[chunk()], count=1, difficulty="easy", question_types=["short_answer"],
            scope=[], previous_prompts=[], generate_json=lambda prompt: json.dumps({"title": "Check", "questions": [item]}), verify_json=verifier)


def test_question_cannot_omit_a_condition_from_its_supporting_rule():
    material = chunk().model_copy(update={"text": "With an adjacency list, BFS takes O(V + E) time."})
    question = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    question.prompt = "Given an unweighted graph, determine the time complexity of BFS."
    result = verify_question_set([question], {"optimisation-1": material}, verify_json=lambda prompt: json.dumps({
        "decisions": [{"question_id": "1", "valid": True, "verified_answer": "O(V + E)", "calculation": "",
                       "support_quote": material.text, "cognitive_level": "easy", "reason": "Supported"}]}))
    assert not result[question.question_id][0]


def test_sourced_numerical_expression_repairs_arithmetic_but_not_invented_inputs():
    material = chunk().model_copy(update={"text": "Kinetic energy is K = 0.5*m*v*v in joules."})
    for expression, accepted in [("0.5 * 1000 * (20^2)", True), ("0.5 * 9000 * (20^2)", False)]:
        question = AssessmentQuestion(question_type="numerical", prompt="Calculate kinetic energy for mass 1000 kg and speed 20 m/s.",
            topic="Mechanics", difficulty="medium", correct_answer="40000", explanation="An incorrect calculation in the draft.", evidence_chunk_ids=["optimisation-1"])
        result = verify_question_set([question], {"optimisation-1": material}, verify_json=lambda prompt: json.dumps({
            "decisions": [{"question_id": "1", "valid": True, "verified_answer": "20000", "calculation": expression,
                           "support_quote": material.text, "cognitive_level": "medium", "reason": "Apply source rule"}]}))
        assert result[question.question_id][0] is accepted
        if accepted:
            assert question.correct_answer == "200000"
            assert "= 200000" in question.explanation


def test_large_numerical_answers_do_not_allow_one_percent_scoring_error():
    question = AssessmentQuestion(question_type="numerical", prompt="Calculate the kinetic energy.", topic="Mechanics", difficulty="medium",
        correct_answer="200000", explanation="Use the given mass and speed in the energy formula.", evidence_chunk_ids=["optimisation-1"], numerical_tolerance=0.01)
    assert grade_objective(question, "200000").correct
    assert not grade_objective(question, "199000").correct


def test_question_schema_rejects_unknown_source_chunk() -> None:
    payload = mcq_payload()
    payload["questions"][0]["evidence_chunk_ids"] = ["invented-source"]
    with pytest.raises(ValueError, match="unknown source chunks"):
        parse_assessment_draft(json.dumps(payload), allowed_chunk_ids={"optimisation-1"})


def test_generation_repairs_a_repeated_question() -> None:
    calls = 0

    def generator(prompt: str) -> str:
        nonlocal calls
        calls += 1
        repeated = "Which direction does gradient descent use?"
        replacement = "According to the notes, how are parameters updated by gradient descent?"
        return json.dumps(mcq_payload(repeated if calls == 1 else replacement))

    draft = generate_assessment(
        course_name="Machine Learning",
        chunks=[chunk()],
        count=1,
        difficulty="easy",
        question_types=["mcq"],
        scope=["Gradient descent"],
        previous_prompts=["Which direction does gradient descent use?"],
        generate_json=generator,
        verify_json=verifier,
    )

    assert calls == 2
    assert draft.questions[0].prompt.startswith("According to")


def test_generation_fills_missing_slots_with_source_checked_recall() -> None:
    status: dict[str, str] = {}

    def generator(prompt: str) -> str:
        return json.dumps(mcq_payload())

    draft = generate_assessment(
        allow_source_recall=True,
        course_name="Machine Learning",
        chunks=[chunk()],
        count=3,
        difficulty="easy",
        question_types=["mcq"],
        scope=["Gradient descent"],
        previous_prompts=[],
        generate_json=generator,
        verify_json=verifier,
        generation_status=status,
    )

    assert len(draft.questions) == 3
    assert "2 questions use basic source-recall practice" in status["notice"]
    assert all(item.evidence_chunk_ids == ["optimisation-1"] for item in draft.questions)


@pytest.mark.parametrize("kind", ["mcq", "short_answer", "numerical", "true_false", "fill_blank"])
def test_model_failure_preserves_requested_format_and_count_when_source_supports_it(kind) -> None:
    text = " ".join(
        f"Experiment {index} measures temperature changes in heated metal samples after {index + 10} minutes."
        for index in range(1, 9)
    )
    material = chunk().model_copy(update={"text": text, "token_count": len(text.split())})
    status = {}

    def offline(prompt):
        raise RuntimeError("Local model unavailable")

    draft = generate_assessment(course_name="Physics", chunks=[material], count=5,
        difficulty="easy", question_types=[kind], scope=[], previous_prompts=[], allow_source_recall=True,
        generate_json=offline, verify_json=offline, generation_status=status)

    assert len(draft.questions) == 5
    assert {question.question_type for question in draft.questions} == {kind}
    assert len({question.prompt for question in draft.questions}) == 5
    assert "source-recall" in status["notice"]
    for question in draft.questions:
        if kind != "true_false":
            assert question.correct_answer in material.text


def test_pure_numerical_request_does_not_invent_values_from_prose() -> None:
    material = chunk().model_copy(update={"text": "Photosynthesis converts sunlight into chemical energy in green plants."})
    def offline(prompt):
        raise RuntimeError("Local model unavailable")
    with pytest.raises(ValueError, match="No questions passed"):
        generate_assessment(course_name="Biology", chunks=[material], count=5,
            difficulty="medium", question_types=["numerical"], scope=[], previous_prompts=[],
            generate_json=offline, verify_json=offline)


def test_mixed_request_keeps_every_selected_format_on_model_failure() -> None:
    text = " ".join(f"Experiment {index} measures temperature changes in heated metal samples after {index + 10} minutes." for index in range(1, 9))
    material = chunk().model_copy(update={"text": text})
    def offline(prompt):
        raise RuntimeError("Local model unavailable")
    kinds = ["mcq", "short_answer", "numerical", "true_false", "fill_blank"]
    draft = generate_assessment(course_name="Physics", chunks=[material], count=12,
        difficulty="easy", question_types=kinds, scope=[], previous_prompts=[], allow_source_recall=True,
        generate_json=offline, verify_json=offline)
    assert len(draft.questions) == 12
    assert {question.question_type for question in draft.questions} == set(kinds)


def test_explicit_stop_is_not_converted_into_fallback_practice() -> None:
    from studybuddy.cancellation import GenerationStopped
    def stopped(prompt):
        raise GenerationStopped("Stopped by you.")
    with pytest.raises(GenerationStopped):
        generate_assessment(course_name="Physics", chunks=[chunk()], count=5,
            difficulty="easy", question_types=["mcq"], scope=[], previous_prompts=[],
            generate_json=stopped, verify_json=stopped)


def test_written_answers_use_one_grading_call_and_preserve_each_response() -> None:
    questions = [AssessmentQuestion(question_type="short_answer", prompt=f"Explain gradient descent in exercise {index}.",
        topic="Gradient descent", difficulty="easy", correct_answer="Negative gradient direction",
        explanation="The source states that parameters follow the negative gradient direction.",
        grading_criteria=["Mentions the negative gradient"], evidence_chunk_ids=["optimisation-1"])
        for index in range(3)]
    answers = {question.question_id: "It follows the opposite of the gradient." for question in questions}
    calls = []
    def grader(prompt):
        calls.append(prompt)
        return json.dumps({"items": [{"question_id": str(index + 1), "score": 1,
            "feedback": "Correct: the negative gradient points in the opposite direction to the gradient.",
            "misconception": None} for index in range(3)]})
    feedback = grade_short_answer_set(questions, answers, {"optimisation-1": chunk()}, grade_json=grader)
    assert len(calls) == 1
    assert all(feedback[question.question_id].score == 1 for question in questions)
    assert all(feedback[question.question_id].response == answers[question.question_id] for question in questions)


def test_generation_allows_distinct_questions_on_the_same_concept() -> None:
    payload = mcq_payload()
    second = dict(payload["questions"][0])
    second["prompt"] = "What direction does gradient descent use?"
    payload["questions"].append(second)

    draft = generate_assessment(
        course_name="Machine Learning",
        chunks=[chunk()],
        count=2,
        difficulty="easy",
        question_types=["mcq"],
        scope=["Gradient descent"],
        previous_prompts=[],
        generate_json=lambda prompt: json.dumps(payload),
        verify_json=verifier,
    )

    assert len(draft.questions) == 2
    assert draft.questions[0].topic == draft.questions[1].topic


def test_generation_repairs_an_mcq_answer_without_direct_source_support() -> None:
    calls = 0

    def generator(prompt: str) -> str:
        nonlocal calls
        calls += 1
        payload = mcq_payload()
        if calls == 1:
            payload["questions"][0]["options"] = [
                "Increase parameters", "Decrease parameters", "Multiply parameters", "Keep parameters fixed",
            ]
            payload["questions"][0]["correct_answer"] = "Decrease parameters"
        return json.dumps(payload)

    draft = generate_assessment(
        course_name="Machine Learning",
        chunks=[chunk()],
        count=1,
        difficulty="easy",
        question_types=["mcq"],
        scope=["Gradient descent"],
        previous_prompts=[],
        generate_json=generator,
        verify_json=verifier,
    )

    assert calls == 2
    assert draft.questions[0].correct_answer == "Negative gradient"


def test_verified_assessment_is_localized_without_changing_structure() -> None:
    original = parse_assessment_draft(json.dumps(mcq_payload()), allowed_chunk_ids={"optimisation-1"})

    def translate(prompt: str) -> str:
        payload = original.model_dump()
        payload["title"] = "अनुकूलन जाँच"
        question = payload["questions"][0]
        question["prompt"] = "Gradient descent किस दिशा का उपयोग करता है?"
        question["topic"] = "Gradient descent की दिशा"
        question["options"] = ["Negative gradient", "Positive gradient", "Random दिशा", "कोई दिशा नहीं"]
        question["correct_answer"] = "Negative gradient"
        question["explanation"] = "Notes बताते हैं कि parameters negative gradient की दिशा में जाते हैं। इससे objective कम होता है, इसलिए यही सही उत्तर है और positive या random दिशा सही नहीं है।"
        return json.dumps(payload, ensure_ascii=False)

    localized = localize_assessment(
        original, "hindi", generate_json=translate, allowed_chunk_ids={"optimisation-1"},
    )

    assert "किस दिशा" in localized.questions[0].prompt
    assert localized.questions[0].question_id == original.questions[0].question_id
    assert localized.questions[0].evidence_chunk_ids == original.questions[0].evidence_chunk_ids


def test_objective_grading_handles_mcq_and_numeric_tolerance() -> None:
    mcq = AssessmentQuestion.model_validate(mcq_payload()["questions"][0])
    assert grade_objective(mcq, "negative gradient").correct is True
    numerical = AssessmentQuestion(
        question_type="numerical",
        prompt="What learning rate is stated in the notes?",
        topic="Gradient descent",
        difficulty="easy",
        correct_answer="0.1",
        explanation="The passage states 0.1.",
        evidence_chunk_ids=["optimisation-1"],
        numerical_tolerance=0.01,
    )
    assert grade_objective(numerical, "0.105").correct is True
    assert grade_objective(numerical, "0.3").correct is False


def test_short_answer_grading_is_bounded_and_grounded() -> None:
    question = AssessmentQuestion(
        question_type="short_answer",
        prompt="How does gradient descent update parameters?",
        topic="Gradient descent",
        difficulty="medium",
        correct_answer="It updates them in the negative gradient direction.",
        explanation="This is stated in the notes.",
        grading_criteria=["Mentions the negative gradient direction"],
        evidence_chunk_ids=["optimisation-1"],
    )
    result = grade_short_answer(
        question,
        "It moves opposite to the gradient.",
        {"optimisation-1": chunk()},
        grade_json=lambda prompt: json.dumps({
            "score": 0.9, "correct": True, "feedback": "Correct idea.", "misconception": None,
        }),
    )
    assert result.correct is True
    assert result.score == 0.9


def test_novelty_uses_exact_hash_and_lexical_similarity() -> None:
    assert question_fingerprint("What is gradient descent?") == question_fingerprint("What is gradient-descent")
    assert question_similarity(
        "What direction does gradient descent use to update parameters?",
        "Which direction does gradient descent use to update parameters?",
    ) >= 0.82
