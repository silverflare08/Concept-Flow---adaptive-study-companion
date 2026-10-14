"""Fast recall questions with answer keys copied from indexed source text.

These are deliberately simple retrieval exercises, not AI-verified reasoning
problems. They provide usable practice when model drafting fails.
"""
from __future__ import annotations

import re
from collections.abc import Iterator

from studybuddy.ingestion.models import KnowledgeChunk

_STOP = set("a an the this that these those is are was were be been being and or of to in on at by for with from as it its they their we you your not can may will should must which what when where how then than also".split())


def source_practice_candidates(chunks: list[KnowledgeChunk], question_types: list[str]) -> Iterator[dict]:
    """Emit only requested formats, retaining an exact passage and source ID."""
    passages = []
    for chunk in chunks:
        for raw in re.split(r"(?<=[.!?])\s+|\n+", chunk.text):
            sentence = " ".join(raw.split()).strip()
            if not 35 <= len(sentence) <= 650 or len(sentence.split()) < 6:
                continue
            if "[unclear" in sentence.casefold() or sentence.startswith(("http://", "https://")):
                continue
            passages.append((chunk, sentence))
    # Round-robin by format, sentence, then term keeps the pool diverse.
    pools = {kind: [] for kind in question_types}
    for chunk, sentence in passages:
        topic = chunk.concepts[0] if chunk.concepts else chunk.citation.source_name
        common = {
            "topic": topic, "difficulty": "easy", "evidence_chunk_ids": [chunk.chunk_id],
            "explanation": f"The cited material states: {sentence} Compare your answer with this statement and identify the key idea it describes.",
        }
        words = list(dict.fromkeys(
            match.group() for match in re.finditer(r"\b[A-Za-z][A-Za-z-]{3,}\b", sentence)
            if match.group().casefold() not in _STOP
        ))
        words.sort(key=lambda word: (-len(word), sentence.index(word)))
        for answer in words[:8]:
            blanked = re.sub(r"\b" + re.escape(answer) + r"\b", "____", sentence, count=1)
            if "fill_blank" in pools:
                pools["fill_blank"].append({**common, "question_type": "fill_blank",
                    "prompt": f"Complete this passage exactly as written in your material:\n{blanked}",
                    "correct_answer": answer})
            if "mcq" in pools:
                alternatives = [word for word in words if word.casefold() != answer.casefold()][:3]
                if len(alternatives) == 3:
                    options = [answer, *alternatives]
                    offset = len(pools["mcq"]) % 4
                    options = options[offset:] + options[:offset]
                    pools["mcq"].append({**common, "question_type": "mcq",
                        "prompt": f"Which option completes this quoted passage from your material?\n{blanked}",
                        "options": options, "correct_answer": answer})
        if "true_false" in pools:
            pools["true_false"].append({**common, "question_type": "true_false",
                "prompt": f"The material makes the following statement. True or false?\n{sentence}",
                "options": ["True", "False"], "correct_answer": "True"})
        if "short_answer" in pools:
            pools["short_answer"].append({**common, "question_type": "short_answer",
                "prompt": f"Explain the main idea of this passage in your own words and identify its key terms:\n{sentence}",
                "correct_answer": sentence, "grading_criteria": [f"Accurately explain this source statement: {sentence}"]})
        if "numerical" in pools:
            for match in re.finditer(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", sentence):
                answer = match.group()
                blanked = sentence[:match.start()] + "____" + sentence[match.end():]
                pools["numerical"].append({**common, "question_type": "numerical",
                    "prompt": f"Enter the missing numerical value from this passage (number only):\n{blanked}",
                    "correct_answer": answer, "numerical_tolerance": 0})
    index = 0
    while any(index < len(pool) for pool in pools.values()):
        for kind in question_types:
            if index < len(pools[kind]):
                yield pools[kind][index]
        index += 1
