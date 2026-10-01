# M0 - demo course decision

## Selected scope

**MIT 6.006 Graph Algorithms:** graph representations, BFS, DFS, cycle
detection, topological sorting, weighted graphs, and Dijkstra's algorithm.

This is deliberately one unit rather than an entire algorithms course. Track D
requires a working multimodal system, not a huge corpus. A compact unit lets us
test every requirement with real evidence and show a coherent learner journey.

## Why this course is ideal for the hackathon

1. **It is genuinely multimodal.** The official MIT 6.006 material has a
   lecture video/transcript and graphical slide content. An open textbook
   chapter will supply the third source type required by the brief.
2. **Visual evidence matters.** Graph diagrams, traversal trees, queue/stack
   states, and shortest-path tables allow us to prove that figure extraction is
   useful rather than merely present.
3. **The prerequisite graph is defensible.** Graph representations underpin
   BFS/DFS; DFS underpins cycle detection/topological sorting; weighted graphs
   underpin Dijkstra. This maps cleanly into BKT and an adaptive policy.
4. **It supports all required assessment formats.** Definitions and invariants
   produce MCQs, trace-a-traversal produces short answers, and path costs produce
   numerical questions.
5. **It demos clearly.** We can show a novice failing a negative-edge Dijkstra
   question, receive cited remediation on weighted graphs, then get a suitable
   next question instead of another Dijkstra question.

## Resource roles

| Resource | Purpose in ConceptFlow | Citation format |
| --- | --- | --- |
| MIT lecture video | spoken explanation and timestamped evidence | `Lecture 10, mm:ss` |
| MIT slide PDF | diagrams, formulas, and slide/page evidence | `DFS slides, p. n` |
| Open textbook chapter | detailed prose and cross-source retrieval | `Textbook, p. n` |

The actual upload workflow will use local copies selected/downloaded from their
official public pages. The product stores original file information separately
from extracted content, allowing citations to open the upload or official link.

## M0 exit criteria

- [x] A demo course and concept scope are fixed.
- [x] Resource roles and citation expectations are explicit.
- [x] A concept/prerequisite graph validates as a DAG.
- [x] Source segment schema supports text, transcript, OCR, and visual evidence.
- [ ] Local PDF, PPTX, and video fixture files are collected for parser testing.
- [ ] Gold source-location questions are authored before retrieval tuning.
