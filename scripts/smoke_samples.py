"""Verify sample ingestion and retrieval without AI downloads or a database."""
from pathlib import Path
from studybuddy.ingestion.router import parse_study_file
from studybuddy.ingestion.chunker import chunk_segments
from studybuddy.retrieval.bm25 import BM25Index

root = Path(__file__).resolve().parents[1]
chunks = []
for filename in ['graph-basics.md', 'bfs_example.py', 'practice-results.csv']:
    parsed = parse_study_file(root / 'samples' / filename, source_id=filename,
                             source_name=filename, source_uri=f'samples/{filename}')
    extracted = chunk_segments(parsed.segments)
    assert extracted, f'No content extracted from {filename}'
    chunks.extend(extracted)
    print(f'{filename}: {len(extracted)} study sections')
hits = BM25Index(chunks).search('BFS queue', limit=3)
assert hits, 'BFS query returned no evidence'
print(f'Retrieval passed: {hits[0].chunk.citation.label()}')
print('No AI model or persistent workspace was required for this check.')
