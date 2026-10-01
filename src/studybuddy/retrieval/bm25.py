"""Small, dependency-free BM25 baseline for source-grounded retrieval.

This is our first retrieval baseline, not a shortcut around dense retrieval.
Its deterministic scores make it easy to inspect why a source was returned,
and later ablations will compare it to dense and hybrid approaches.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from studybuddy.ingestion.models import KnowledgeChunk


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: KnowledgeChunk
    score: float
    rank: int
    retriever: str = "bm25"


class BM25Index:
    """In-memory Okapi BM25 index suitable for the first course-sized corpus."""

    def __init__(self, chunks: Iterable[KnowledgeChunk], *, k1: float = 1.5, b: float = 0.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("k1 must be positive and b must be in [0, 1]")
        self.chunks = list(chunks)
        if not self.chunks:
            raise ValueError("BM25 index needs at least one chunk")
        self.k1 = k1
        self.b = b
        self._tokens = [tokenize(chunk.text) for chunk in self.chunks]
        self._lengths = [len(tokens) for tokens in self._tokens]
        self._average_length = sum(self._lengths) / len(self._lengths)
        self._document_frequency: dict[str, int] = defaultdict(int)
        self._term_frequencies: list[Counter[str]] = []
        for tokens in self._tokens:
            frequencies = Counter(tokens)
            self._term_frequencies.append(frequencies)
            for token in frequencies:
                self._document_frequency[token] += 1

    def _idf(self, term: str) -> float:
        document_count = len(self.chunks)
        frequency = self._document_frequency.get(term, 0)
        return math.log(1 + (document_count - frequency + 0.5) / (frequency + 0.5))

    def _score(self, query_tokens: list[str], document_index: int) -> float:
        frequency = self._term_frequencies[document_index]
        document_length = self._lengths[document_index]
        score = 0.0
        for term in set(query_tokens):
            term_frequency = frequency.get(term, 0)
            if not term_frequency:
                continue
            denominator = term_frequency + self.k1 * (
                1 - self.b + self.b * document_length / self._average_length
            )
            score += self._idf(term) * (term_frequency * (self.k1 + 1) / denominator)
        return score

    def search(self, query: str, *, limit: int = 5) -> list[RetrievedChunk]:
        if limit < 1:
            raise ValueError("limit must be positive")
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scored = [(index, self._score(query_tokens, index)) for index in range(len(self.chunks))]
        scored.sort(key=lambda item: (-item[1], self.chunks[item[0]].chunk_id))
        return [
            RetrievedChunk(chunk=self.chunks[index], score=score, rank=rank)
            for rank, (index, score) in enumerate(scored[:limit], start=1)
            if score > 0
        ]
