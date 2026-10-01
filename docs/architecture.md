# Architecture decisions

## Citation metadata is a first-class contract

The parser produces `SourceSegment`, never plain text. Every segment has one
`CitationAnchor`: PDF page, slide number, or video timestamp. Visual content
uses the anchor of its parent page/slide. The chunker never combines segments
with different anchors, so an answer citation is evidence rather than a guessed
label.

## Visual content has its own evidence path

Text extraction cannot answer questions about a labelled diagram. The ingestion
pipeline will extract embedded images where possible, obtain OCR text and a
vision-model description, and store both as chunks linked to the parent source.
The UI will identify visual evidence clearly so judges can verify it.

## Retrieval comes before generation

We will measure BM25, dense retrieval, hybrid reciprocal-rank fusion, and
hybrid plus reranking before connecting an LLM. This separates retrieval
failures from generation failures and produces an honest ablation table.

## BKT is the adaptive baseline

Bayesian Knowledge Tracing has four interpretable parameters: initial mastery,
probability of learning, guessing, and slipping. It enables a reproducible
adaptive-vs-random learner simulation and is easier to defend than an opaque
model trained without enough student data.

## Generation is constrained, verified, and auditable

The answer service can only make claims tied to retrieved chunks; otherwise it
abstains. The assessment generator is two-stage: create candidate items, then
validate each answer against the cited evidence. Item fingerprints and student
history prevent repetitions. Every prompt, retrieved chunk ID, verifier result,
and BKT transition is logged for evaluation.
