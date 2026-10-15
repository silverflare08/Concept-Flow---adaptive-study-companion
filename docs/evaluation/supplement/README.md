# Retrieval and simulation supplement

This folder contains additional, bounded diagnostics for the report. It does not change the application or its model configuration, and it does not measure RAGAS/DeepEval/TruLens generation quality or tutor refusal behavior.

From the repository root, run with the project's Python environment:

```powershell
.\.venv\Scripts\python.exe docs/evaluation/supplement/extended_checks.py --project .
```

The script checks that the primary benchmark results remain reproducible, then reports the paragraph-15 sensitivity analysis, a four-query paraphrase set, four unsupported retrieval queries, a uniform-random reference baseline, and per-seed simulation spread. It writes `supplement-results.json` beside the script. The output includes SHA-256 hashes for the source notes, query cases and script, plus runtime/platform information. It also records hashes of protected project inputs and verifies that they were unchanged by the run.

Interpretation limits:

- The retrieval data uses one small text file and manually labelled paragraph references. Unlabelled retrieved passages are not automatically confirmed irrelevant.
- The paraphrase set has four questions and is a diagnostic, not a held-out benchmark.
- Unsupported-query results report BM25 retrieval only; no tutor response or refusal was evaluated.
- Simulated abilities remain fixed while BKT applies its configured learning transition. Mastery estimates are not observed learning gains.
- Repetition comes from the finite source-recall pools. It is not a semantic novelty measurement.
