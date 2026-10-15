"""Small reproducible report checks; run with ConceptFlow's installed Python.

This is a retrieval baseline and a fixed-ability BKT simulation, not RAGAS
generation scoring or evidence of real-student learning gains.
"""
import argparse
from datetime import datetime
import hashlib
import platform
from importlib.metadata import version
import json
import random
import statistics
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parent)
parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "benchmark-results.json")
args = parser.parse_args()
sys.path.insert(0, str(args.project / "src"))

from studybuddy.ingestion.documents import ingest_text_document
from studybuddy.ingestion.chunker import chunk_segments
from studybuddy.retrieval.bm25 import BM25Index
from studybuddy.tutor.bkt import BKTParameters, update_mastery, choose_weakest_topic
from studybuddy.source_practice import source_practice_candidates
from studybuddy.assessment import question_fingerprint

source = args.project / "samples" / "graph-basics.md"
segments = ingest_text_document(source, source_id="report-graphs", source_name=source.name).segments
chunks = chunk_segments(segments)
index = BM25Index(chunks)

# References are paragraph locations in the unmodified bundled sample file.
cases = [
    ("Which data structure does BFS use?", [7, 13, 15]),
    ("Which data structure does DFS use?", [13]),
    ("How does depth-first search explore branches?", [13]),
    ("What are graph vertices and edges?", [4]),
    ("How does an adjacency list store neighbours?", [4]),
    ("What is the space requirement of an adjacency matrix?", [5]),
    ("What is a sparse graph?", [5]),
    ("What is BFS time complexity with an adjacency list?", [9, 15]),
    ("Does BFS find shortest paths in an unweighted graph?", [9]),
    ("Does BFS find a minimum-weight path in a weighted graph?", [9]),
    ("What is the BFS order starting at A in the worked example?", [11]),
    ("What is the distance from A to D in the example?", [11, 15]),
]
retrieval = []
for query, paragraphs in cases:
    expected = {f"paragraph {number}" for number in paragraphs}
    ranked = index.search(query, limit=3)
    locations = [item.chunk.citation.section for item in ranked]
    matched = set(locations) & expected
    retrieval.append({"query": query, "reference_locations": sorted(expected),
        "retrieved_locations": locations, "hit_at_1": bool(locations and locations[0] in expected),
        "hit_at_3": bool(matched), "precision_at_3": len(matched) / 3,
        "recall_at_3": len(matched) / len(expected)})
off_material = ["mitochondria ATP", "quadratic discriminant", "monsoon cyclones", "covariance eigenvectors"]
empty_count = sum(not index.search(query, limit=3) for query in off_material)

topics = {"Graph representations": [4, 5], "BFS": [7, 8, 9, 11, 15], "DFS": [13]}
pools = {}
for topic, paragraphs in topics.items():
    selected = [chunk.model_copy(update={"concepts": [topic]}) for chunk in chunks
        if chunk.citation.section in {f"paragraph {number}" for number in paragraphs}]
    pools[topic] = list(source_practice_candidates(selected, ["mcq", "true_false", "fill_blank"]))
    assert pools[topic], topic

params = BKTParameters()
profiles = {"Novice": [0.25, 0.30, 0.35], "Intermediate": [0.55, 0.65, 0.75], "Uneven": [0.10, 0.85, 0.80]}
simulations = []
for profile, abilities in profiles.items():
    for policy in ("adaptive", "round_robin"):
        runs = []
        for seed in range(30):
            rng = random.Random(seed)
            mastery = dict.fromkeys(topics, params.prior)
            seen = set()
            cursors = dict.fromkeys(topics, 0)
            correct = repeats = weak_selections = 0
            for question_number in range(50):
                weak = min(mastery, key=lambda key: (mastery[key], key))
                topic = (choose_weakest_topic(mastery) or weak) if policy == "adaptive" else list(topics)[question_number % len(topics)]
                weak_selections += topic == weak
                candidate = pools[topic][cursors[topic] % len(pools[topic])]
                cursors[topic] += 1
                fingerprint = question_fingerprint(candidate["prompt"])
                repeats += fingerprint in seen
                seen.add(fingerprint)
                ability = abilities[list(topics).index(topic)]
                probability = ability * (1 - params.slip) + (1 - ability) * params.guess
                response = rng.random() < probability
                correct += response
                mastery[topic] = update_mastery(mastery[topic], response, params)
            runs.append({"seed": seed, "correct_rate": correct / 50,
                "final_mean_mastery": statistics.mean(mastery.values()),
                "estimated_mastery_change": statistics.mean(mastery.values()) - params.prior,
                "repetition_rate": repeats / 50, "weakest_topic_selection_rate": weak_selections / 50})
        simulations.append({"profile": profile, "policy": policy, "seeds": 30,
            "sessions_per_run": 10, "questions_per_session": 5,
            "mean_correct_rate": statistics.mean(row["correct_rate"] for row in runs),
            "mean_final_mastery": statistics.mean(row["final_mean_mastery"] for row in runs),
            "mean_estimated_mastery_change": statistics.mean(row["estimated_mastery_change"] for row in runs),
            "mean_repetition_rate": statistics.mean(row["repetition_rate"] for row in runs),
            "mean_weakest_topic_selection_rate": statistics.mean(row["weakest_topic_selection_rate"] for row in runs),
            "runs": runs})

report = {"date": datetime.now().astimezone().date().isoformat(), "material": "samples/graph-basics.md", "indexed_passages": len(chunks),
    "retrieval": {"questions": len(cases),
        "hit_at_1": statistics.mean(row["hit_at_1"] for row in retrieval),
        "hit_at_3": statistics.mean(row["hit_at_3"] for row in retrieval),
        "precision_at_3": statistics.mean(row["precision_at_3"] for row in retrieval),
        "recall_at_3": statistics.mean(row["recall_at_3"] for row in retrieval),
        "zero_overlap_queries": len(off_material), "empty_retrieval_count": empty_count,
        "cases": retrieval},
    "simulation": {"profiles": profiles, "parameters": params.__dict__, "question_pool_sizes": {topic: len(pool) for topic, pool in pools.items()},
        "fixed_ability": True, "results": simulations},
    "scope": "Custom retrieval metrics and fixed-ability simulation; no generated-answer faithfulness, RAGAS scores or real learning gains are measured."}
report["provenance"] = {
    "python": platform.python_version(),
    "platform": platform.platform(),
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "pydantic": version("pydantic"),
    "seed_range": [0, 29],
    "answer_events": len(profiles) * 2 * 30 * 10 * 5,
    "uses_live_llm": False,
    "session_boundary_note": "Ten sessions are ten consecutive blocks of five answers; no time gaps or forgetting are simulated."
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
print(json.dumps({key: value for key, value in report.items() if key not in {"simulation", "retrieval"}}, indent=2))
print(f"Saved all per-question and per-seed results to {args.output}")
