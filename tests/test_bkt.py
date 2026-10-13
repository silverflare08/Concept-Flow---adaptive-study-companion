from studybuddy.tutor.bkt import BKTParameters, choose_weakest_topic, update_mastery, update_mastery_from_learning_exposure


def test_correct_answer_increases_mastery() -> None:
    parameters = BKTParameters(prior=0.2, learn=0.1, guess=0.2, slip=0.1)
    assert update_mastery(0.2, True, parameters) > 0.2


def test_incorrect_answer_reduces_mastery_before_learning() -> None:
    parameters = BKTParameters(prior=0.2, learn=0.0, guess=0.2, slip=0.1)
    assert update_mastery(0.8, False, parameters) < 0.8


def test_policy_picks_topic_that_needs_the_most_help() -> None:
    assert choose_weakest_topic({"graphs": 0.75, "trees": 0.35, "arrays": 0.91}) == "trees"
    assert choose_weakest_topic({"graphs": 0.8}) is None


def test_conversation_exposure_is_positive_but_smaller_than_verified_success() -> None:
    exposure = update_mastery_from_learning_exposure(0.2)
    verified = update_mastery(0.2, True)
    assert 0.2 < exposure < verified
