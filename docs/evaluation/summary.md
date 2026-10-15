# Summary of Results

This audit supports the report's small retrieval baseline and simulated BKT results. It does not certify every report claim. No application behavior, model configuration, assessment pipeline or report PDF was changed by this audit.

## Software verification

The current local verification on Windows used Python 3.14.2, pytest 9.1.1 and Node.js 24.18.0. It completed **183 backend tests**, **16 frontend tests**, and the frontend production build. The build has a non-fatal bundle-size warning. These are software regression checks, not answer-accuracy measurements. This was the existing checkout and installed environment, not a clean-device installation or fresh-clone test.

Raw outputs are in [backend-tests.txt](backend-tests.txt), [frontend-tests.txt](frontend-tests.txt), and [frontend-build.txt](frontend-build.txt). [current-checks.json](current-checks.json) records commands, exit codes, runtime versions and the source commit at audit start. The added evidence/docs changes were uncommitted during this run. Python 3.11 remains the setup recommendation; the previous README's specific claim of testing on 3.11.9 is not established by this audit and has been replaced.

The report's **66 backend tests** describes a historical focused subset, not the current complete suite. The corresponding original raw log and exact subset command have not been recovered. Do not present 66 as a freshly verified full-suite count. Prefer the current recorded 183/16 results and identify the run's scope.

## Retrieval baseline

[benchmark_report.py](../../benchmark_report.py) ingests the unmodified `samples/graph-basics.md` using the real reader/chunker, builds the application's BM25 index, and queries twelve manually listed questions. Each question has reference paragraph locations. The script measures where those references appear in the returned passages. A fresh run reproduced the original report artifact's **entire retrieval result object exactly**, including every query's retrieved locations.

| Metric | Reproduced result |
| --- | ---: |
| Indexed passages | 15 |
| Labeled questions | 12 |
| Hit@1 | 75.00% |
| Hit@3 | 100.00% |
| Precision@3 | 41.67% |
| Recall@3 | 97.22% |
| Empty retrieval on zero-overlap queries | 4 / 4 |

Hit@k means at least one labeled reference occurs in the top k results. Precision@3 divides retrieved reference count by three; recall@3 divides by the total labeled references. Scores are averaged across questions. These are custom location-based retrieval metrics, not RAGAS metrics. The test is one small text sample, includes questions similar to the notes' own revision questions, and is not independently held out or multimodal. Empty retrieval does not test whether the tutor correctly refuses a question when irrelevant passages overlap its vocabulary. These numbers are not overall tutor accuracy.

## Fixed-ability simulation

The same script creates three artificial ability profiles, runs thirty seeds for each, and compares adaptive weakest-topic selection with round robin. Each run contains fifty answer events, described as ten consecutive blocks of five. There are no session time gaps, forgetting dynamics or simulated improvement in true ability. The total is **3 profiles × 2 policies × 30 seeds × 10 blocks × 5 answers = 9,000 answer events**, not 9,000 unique questions or real students.

Answers are sampled with probability `ability * (1 - slip) + (1 - ability) * guess`. The application's BKT update and weakest-topic selector are called after each response. Questions come from deterministic source-recall pools, not live model-generated exams. Exact normalized prompt fingerprints measure repetition within each fifty-answer run; they do not measure semantic duplication.

The fresh run reproduced the original report artifact's **entire simulation object exactly**, including all seed-level results, profile abilities and pool sizes (83, 145, 36).

| Profile | Policy | Correct responses | Mean BKT estimate change | Exact repetition |
| --- | --- | ---: | ---: | ---: |
| Novice | Adaptive | 41.73% | +61.07 pp | 0.33% |
| Novice | Round robin | 41.33% | +39.77 pp | 0.00% |
| Intermediate | Adaptive | 63.67% | +78.61 pp | 0.00% |
| Intermediate | Round robin | 64.33% | +73.31 pp | 0.00% |
| Uneven | Adaptive | 38.13% | +56.96 pp | 0.00% |
| Uneven | Round robin | 61.13% | +60.55 pp | 0.00% |

pp means percentage points. All topics start at 20% estimated mastery. True abilities are fixed, while the BKT update assumes a positive learning transition. Consequently, increasing estimates do **not** establish learning gains or prove that adaptive practice is better. The unequal profile's lower adaptive accuracy reflects selection of its weak topic; it is not evidence of worse learning. The experiment checks model updates and selection behavior, not the full live assessment workflow or actual personalization effectiveness.

## BKT defaults

The values in [BKTParameters](../../src/studybuddy/tutor/bkt.py) are `prior=0.20`, `learn=0.15`, `slip=0.10`, `guess=0.20`. These exactly match the report's p0, t, s and g. They are heuristic configuration defaults, not measured or fitted educational parameters. The separate tutoring-exposure transition defaults to 0.04.

## Unsupported or incomplete evidence

- **42.55 seconds:** this was reported as a single historical development observation, but this audit did not recover a retained raw timing record, exact input/output record and environment trace. Treat it as unverified; omit the number from a submission unless the original evidence is recovered. A fresh timing cannot validate the old exact duration. It would be a new measurement and must disclose input, model, cold/warm cache state, hardware, output count and fallbacks.
- **66 backend tests:** historical focused-subset claim without a retained original log/command. Use the current complete-suite record above instead.
- **Framework evaluation:** the report does not supply RAGAS/DeepEval/TruLens generation scores. This requirement remains a gap in the restored project's submission evidence. Do not relabel custom BM25 metrics as framework results. A later experimental evaluation of changed code is not evidence for this restored version; no removed model was reinstalled during this audit.
- **Educational effectiveness:** no real-student improvement, calibrated intake, causal adaptive-learning benefit or semantic question-novelty rate has been demonstrated here.

The report's heading "Evidence Against Evaluation Criteria" can be renamed "Summary of Results" if the author chooses to revise it. This audit deliberately leaves both the PDF and LaTeX source unchanged.

## Reproduce

After installing the project's dependencies, run from the repository root:

```powershell
.venv/Scripts/python.exe benchmark_report.py
.venv/Scripts/python.exe scripts/verify_report_evidence.py
```

On macOS/Linux use `.venv/bin/python`. Alternatively, an activated environment can run `python benchmark_report.py` and `python scripts/verify_report_evidence.py`. The benchmark does not require Ollama or a model download. [benchmark-results.json](../../benchmark-results.json) preserves questions, reference locations, per-seed outputs, runtime metadata and input/script hashes. The verification runner overwrites the current audit logs and reruns the benchmark; those files are explicit outputs, not application data. Test suites use isolated temporary storage. No commit or push is performed by these scripts.
