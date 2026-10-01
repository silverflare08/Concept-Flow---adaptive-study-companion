# Track D execution plan and acceptance criteria

This document converts each Track D requirement into an observable product
behavior. It is both the build checklist and the final demo checklist.

## Scope decision

The demo will use **one coherent public course module** with at least one video,
one slide deck, and one PDF/textbook source. A narrow course produces a more
credible knowledge graph, stronger source-location test set, and cleaner demo
than several disconnected subjects. The source will be selected before
ingestion and kept legal to redistribute or demonstrate.

## Required capabilities

| ID | Build behavior | Acceptance test |
| --- | --- | --- |
| KB-1 | Upload PDF, PPTX, and video directly. | A new course is indexed without a human copying text into the app. |
| KB-2 | Every retrieved chunk has exactly one page, slide, or timestamp anchor. | A citation opens the matching source location. |
| KB-3 | Create a topic -> concept -> prerequisite graph. | The course map shows at least 3 topics, 10 concepts, and meaningful prerequisite edges. |
| KB-4 | Incorporate visuals. | A diagram-only question retrieves its image caption/OCR evidence and cites its source. |
| GR-1 | Generate answers only from retrieved evidence. | Off-material test prompts cause abstention, not unsupported course claims. |
| AS-1 | Generate MCQ, short-answer, and numerical questions. | Each item has source, topic, difficulty, answer key, and explanation metadata. |
| AS-2 | Verify and de-duplicate items. | An unsupported item is rejected; a semantic repeat is not served twice. |
| AS-3 | Give cited feedback and diagnosis. | Assessment report identifies weak topics, likely misconception, and linked evidence. |
| LM-1 | Onboard a new learner. | Diagnostic quiz initializes a concept mastery map. |
| LM-2 | Adapt across sessions. | Different answer histories produce different next activities. |
| EV-1 | Evaluate RAG and personalization honestly. | Report includes RAGAS faithfulness, relevancy, context precision/recall, and failures. |
| EV-2 | Simulate learner profiles. | Compare BKT policy with random selection for mastery gain and repeats. |

## Milestones

### M0 - contracts and course fixture

Define source/citation/visual/concept/learner/assessment schemas, select the
demo course, and create a 20-question gold test-set template.

### M1 - multimodal ingestion

Build PDF, PPTX, and video parsers; extract visuals; generate anchored chunks,
concept tags, and course graph. Chunks may never cross source locations.

### M2 - retrieval bench

Implement BM25, dense retrieval, hybrid reciprocal-rank fusion, and reranking.
Choose the approach that measures best on Recall@5 and MRR, not by assumption.

### M3 - source-grounded tutor

Deliver answer prompts, evidence cards, citations, confidence threshold, and
abstention. The UI labels `Course-backed answer` and `Not covered by course`.

### M4 - verified assessment engine

Generate scoped assessment candidates, validate each answer against its cited
evidence, block duplicates, grade responses, and report misconceptions.

### M5 - adaptive learner loop

Implement diagnostic intake, BKT updates, prerequisite-aware next-item policy,
mastery dashboard, and targeted revision material.

### M6 - evidence for judges

Create RAGAS report, hand-authored source-location test set, learner simulation
report, ablation table, failure analysis, demo script/video, and documentation.

## Evaluation design

### Grounding test set

Create 40-60 prompts before final tuning: 25 in-material questions with gold
anchors, 10 visual/diagram questions, 10 off-material questions, and 5
cross-source questions. Version the prompt, expected answer outline, source ID,
and source anchor in JSONL.

### Metrics

- Retrieval: Recall@5, MRR, citation-anchor accuracy.
- RAGAS: faithfulness, answer relevancy, context precision, context recall.
- Assessment: verifier pass rate, source-tag accuracy, duplicate rate.
- Personalization: mastery gain, prerequisite violations, and repeat rate,
  compared with random selection.

### Simulated learners

Use three deterministic profiles: strong-but-rusty, novice, and
misconception-prone. Each has hidden per-concept mastery, guess, slip, and
learning probabilities. Clearly label these results as simulation, not a claim
about real learners.

## Non-negotiable product rules

1. Citation metadata travels from ingestion to UI; an LLM never invents it.
2. The tutor abstains when its evidence cannot support the response.
3. Visuals are searchable source evidence, not decoration.
4. Questions require evidence validation and cannot repeat.
5. Every reported metric has a documented dataset, configuration, and failures.
