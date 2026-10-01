"""A small, inspectable Bayesian Knowledge Tracing implementation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParameters:
    """Per-topic BKT parameters, each expressed as a probability."""

    prior: float = 0.2
    learn: float = 0.15
    guess: float = 0.2
    slip: float = 0.1

    def __post_init__(self) -> None:
        if any(not 0 <= value <= 1 for value in self.__dict__.values()):
            raise ValueError("BKT probabilities must be in [0, 1]")


def update_mastery(
    mastery: float, correct: bool, parameters: BKTParameters = BKTParameters()
) -> float:
    """Update mastery after an answer, then allow learning from the activity."""
    if not 0 <= mastery <= 1:
        raise ValueError("mastery must be in [0, 1]")

    p_correct = mastery * (1 - parameters.slip) + (1 - mastery) * parameters.guess
    if correct:
        posterior = mastery * (1 - parameters.slip) / p_correct
    else:
        p_incorrect = 1 - p_correct
        posterior = mastery * parameters.slip / p_incorrect
    return posterior + (1 - posterior) * parameters.learn


def choose_weakest_topic(masteries: dict[str, float], threshold: float = 0.8) -> str | None:
    """Return the lowest-mastery topic still needing practice, if there is one."""
    candidates = [(mastery, topic) for topic, mastery in masteries.items() if mastery < threshold]
    return min(candidates)[1] if candidates else None
