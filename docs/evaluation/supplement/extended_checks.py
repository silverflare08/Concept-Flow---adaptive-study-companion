"""Read-only project diagnostics; all new outputs stay beside this script.

Run with the project's Python environment:
python extended_checks.py --project PATH_TO_CONCEPTFLOW
No app data, original results, model configuration or source files are modified.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(values):
    return {'mean': statistics.mean(values), 'sample_sd': statistics.stdev(values),
            'minimum': min(values), 'maximum': max(values), 'seeds': len(values)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(project / 'src'))
    from studybuddy.ingestion.documents import ingest_text_document
    from studybuddy.ingestion.chunker import chunk_segments
    from studybuddy.retrieval.bm25 import BM25Index
    from studybuddy.tutor.bkt import BKTParameters, update_mastery, choose_weakest_topic
    from studybuddy.source_practice import source_practice_candidates
    from studybuddy.assessment import question_fingerprint

    original_path = project / 'benchmark-results.json'
    source = project / 'samples/graph-basics.md'
    protected = [original_path, project / 'benchmark_report.py', source,
                 project / 'src/studybuddy/tutor/bkt.py',
                 project / 'src/studybuddy/assessment.py',
                 project / 'src/studybuddy/tutor/grounded.py',
                 project / 'src/studybuddy/retrieval/bm25.py']
    before = {str(path): digest(path) for path in protected}
    old = json.loads(original_path.read_text(encoding='utf-8'))
    cases = json.loads((here / 'cases.json').read_text(encoding='utf-8'))
    chunks = chunk_segments(ingest_text_document(source, source_id='report-graphs', source_name=source.name).segments)
    index = BM25Index(chunks)

    def evaluate(test_cases, candidate_chunks, drop_p15_references=False):
        search = BM25Index(candidate_chunks)
        rows = []
        for case in test_cases:
            refs = set(case['reference_locations'])
            if drop_p15_references:
                refs.discard('paragraph 15')
            if not refs:
                raise ValueError('Ablation removed every reference; cannot compare this query.')
            retrieved = [r.chunk.citation.section for r in search.search(case.get('query'), limit=3)]
            first = next((i+1 for i, location in enumerate(retrieved) if location in refs), None)
            matches = len(set(retrieved) & refs)
            rows.append({'query': case['query'], 'reference_locations': sorted(refs),
                         'retrieved_locations': retrieved, 'first_reference_rank': first,
                         'hit_at_1': first == 1, 'hit_at_3': first is not None,
                         'reciprocal_rank_at_3': 1/first if first else 0,
                         'precision_at_3': matches/3, 'recall_at_3': matches/len(refs)})
        return {'cases': rows, 'metrics': {metric: statistics.mean(row[metric] for row in rows)
                for metric in ['hit_at_1', 'hit_at_3', 'reciprocal_rank_at_3', 'precision_at_3', 'recall_at_3']}}

    original = evaluate(old['retrieval']['cases'], chunks)
    for row, previous in zip(original['cases'], old['retrieval']['cases']):
        for field in ['query', 'reference_locations', 'retrieved_locations', 'hit_at_1', 'hit_at_3', 'precision_at_3', 'recall_at_3']:
            assert row[field] == previous[field], (field, row['query'])
    ref_counts = [len(row['reference_locations']) for row in original['cases']]
    n = len(chunks)
    original['diagnostics'] = {
        'total_labeled_references': sum(ref_counts),
        'precision_at_3_ceiling': sum(min(3, count) for count in ref_counts)/(3*len(ref_counts)),
        'unlabeled_retrieved_slots': sum(3-len(set(row['retrieved_locations']) & set(row['reference_locations'])) for row in original['cases']),
        'paragraph15_in_top3': sum('paragraph 15' in row['retrieved_locations'] for row in original['cases']),
        'paragraph15_in_reference_sets': sum('paragraph 15' in row['reference_locations'] for row in original['cases']),
        'paragraph15_retrieved_without_reference_label': sum('paragraph 15' in row['retrieved_locations'] and 'paragraph 15' not in row['reference_locations'] for row in original['cases']),
        'paragraph15_text': next(c.text for c in chunks if c.citation.section == 'paragraph 15'),
        'label_interpretation': 'Unlabeled slots are not independently adjudicated as wholly irrelevant.'}
    random_baseline = {
        'method': 'Exact combinatorial expectation: three distinct passages sampled uniformly without replacement from all 15 indexed passages, including headings.',
        'expected_hit_at_1': statistics.mean(count/n for count in ref_counts),
        'expected_hit_at_3': statistics.mean(1-math.comb(n-count, 3)/math.comb(n, 3) for count in ref_counts),
        'expected_precision_at_3': statistics.mean(count/n for count in ref_counts)}
    ablation = evaluate(old['retrieval']['cases'], [c for c in chunks if c.citation.section != 'paragraph 15'], True)
    ablation['method'] = 'Rebuild BM25 with paragraph 15 removed (IDF changes); remove it from reference labels too, retaining all 12 queries.'
    paraphrases = evaluate(cases['paraphrases'], chunks)
    negatives = []
    for case in cases['unsupported_queries']:
        retrieved = index.search(case['query'], limit=3)
        negatives.append({**case, 'retrieved_locations': [r.chunk.citation.section for r in retrieved],
                          'empty_retrieval': not retrieved,
                          'tutor_refusal': None})

    topic_locations = {'Graph representations': [4, 5], 'BFS': [7, 8, 9, 11, 15], 'DFS': [13]}
    topics = list(topic_locations)
    pools = {}
    for topic, paragraphs in topic_locations.items():
        selected = [c.model_copy(update={'concepts': [topic]}) for c in chunks
                    if c.citation.section in {f'paragraph {number}' for number in paragraphs}]
        pools[topic] = list(source_practice_candidates(selected, ['mcq', 'true_false', 'fill_blank']))
    parameters = BKTParameters()
    simulation = []
    old_rows = {(r['profile'], r['policy']): r for r in old['simulation']['results']}
    for profile, abilities in old['simulation']['profiles'].items():
        for policy in ['adaptive', 'round_robin']:
            runs = []
            for seed in range(30):
                rng = random.Random(seed)
                estimates = dict.fromkeys(topics, parameters.prior)
                cursors = dict.fromkeys(topics, 0)
                seen = set()
                correct = repeated = weak_selections = 0
                for event in range(50):
                    weak = min(estimates, key=lambda topic: (estimates[topic], topic))
                    topic = (choose_weakest_topic(estimates) or weak) if policy == 'adaptive' else topics[event % 3]
                    weak_selections += topic == weak
                    candidate = pools[topic][cursors[topic] % len(pools[topic])]
                    cursors[topic] += 1
                    fingerprint = question_fingerprint(candidate['prompt'])
                    repeated += fingerprint in seen
                    seen.add(fingerprint)
                    ability = abilities[topics.index(topic)]
                    response = rng.random() < ability*(1-parameters.slip)+(1-ability)*parameters.guess
                    correct += response
                    estimates[topic] = update_mastery(estimates[topic], response, parameters)
                run = {'seed': seed, 'correct_rate': correct/50,
                       'final_mean_mastery': statistics.mean(estimates.values()),
                       'estimated_mastery_change': statistics.mean(estimates.values())-parameters.prior,
                       'repetition_rate': repeated/50, 'weakest_topic_selection_rate': weak_selections/50,
                       'minimum_topic_estimate': min(estimates.values()),
                       'final_topic_estimates': estimates, 'topic_question_counts': cursors,
                       'pool_wrapped_topics': [t for t in topics if cursors[t] > len(pools[t])]}
                previous = old_rows[(profile, policy)]['runs'][seed]
                for key, value in previous.items():
                    assert math.isclose(run[key], value, rel_tol=1e-12, abs_tol=1e-12), (profile, policy, seed, key)
                runs.append(run)
            simulation.append({'profile': profile, 'policy': policy, 'runs': runs,
                'summary': {key: summary([run[key] for run in runs]) for key in
                    ['correct_rate', 'final_mean_mastery', 'estimated_mastery_change', 'minimum_topic_estimate', 'repetition_rate', 'weakest_topic_selection_rate']}})

    after = {str(path): digest(path) for path in protected}
    assert before == after, 'A protected project file changed during the diagnostics.'
    source_hash = digest(source)
    script_hash = digest(Path(__file__))
    try:
        from importlib.metadata import version
        pydantic_version = version('pydantic')
    except Exception:
        pydantic_version = 'unavailable'
    result = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'provenance': {'python': platform.python_version(),
                  'platform': platform.platform(), 'source_sha256': source_hash,
                  'script_sha256': script_hash, 'cases_sha256': digest(here/'cases.json'),
                  'pydantic': pydantic_version, 'seed_range': [0, 29],
                  'uses_live_llm': False, 'answer_events': 9000},
              'project_files_unchanged': before == after, 'input_hashes': before,
              'original_results_reproduced': True, 'original_retrieval': original,
              'uniform_random_top3': random_baseline, 'without_paragraph15': ablation,
              'paraphrases': paraphrases, 'unsupported_queries': negatives,
              'simulation': simulation, 'pool_sizes': {t:len(p) for t,p in pools.items()},
              'limitations': ['Post-hoc diagnostics on one small text sample, not a held-out or multimodal benchmark.',
                  'No LLM calls, tutor refusal checks, framework evaluation or real learning gains.',
                  'Simulated answers depend on fixed topic ability, not question wording or difficulty.',
                  'Minimum-topic figures are model estimates, not demonstrated mastery.',
                  'Original label sets are preserved; this does not establish exhaustive relevance judgments.']}
    output = here / 'supplement-results.json'
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print('Original results reproduced; protected files unchanged:', result['project_files_unchanged'])
    print('Original metrics:', original['metrics'])
    print('Without paragraph 15:', ablation['metrics'])
    print('Uniform random:', random_baseline)
    print('Paraphrases:', paraphrases['metrics'])
    print('Unsupported queries returning passages:', sum(not r['empty_retrieval'] for r in negatives), '/', len(negatives))
    for row in simulation:
        print(row['profile'], row['policy'], json.dumps(row['summary']))
    print('Saved', output)


if __name__ == '__main__':
    main()
