"""Controlled coarsening of logged command times, with two frozen TF predictors.

This hides labels from the evaluator only. The predictions were conditioned on
the original history, so this is not a model of natural observational ambiguity.
"""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time

from frontier_event_bounds import frontier_bounds


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches(truth, pred, early=1, late=0):
    i = j = total = 0
    while i < len(truth) and j < len(pred):
        if truth[i] - early <= pred[j] <= truth[i] + late:
            total += 1
            i += 1
            j += 1
        elif pred[j] < truth[i] - early:
            j += 1
        else:
            i += 1
    return total


def sign_resolved(bounds):
    return bounds[0] > 0 or bounds[1] < 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    streams, receipts = [], []
    for seed in (0, 1):
        receipt = json.loads((args.root / f'command-seed{seed}-receipt.json').read_text())
        path = args.root / f'command-seed{seed}.jsonl'
        assert sha(path) == receipt['export_sha256']
        assert receipt['mode'] == 'teacher_forced'
        assert receipt['event_type'] == 'logged_semantic_command_onset_not_cast_effect'
        streams.append([json.loads(line) for line in path.read_text().splitlines()])
        receipts.append(receipt)
    assert receipts[0]['sources'] == receipts[1]['sources']
    assert receipts[0]['actions'] == receipts[1]['actions']
    assert receipts[0]['code_closure'] == receipts[1]['code_closure']
    assert len(streams[0]) == len(streams[1])
    groups = defaultdict(list)
    for a, b in zip(*streams):
        for key in ('session', 'run', 'position', 'source_row', 'step_ns', 'valid', 'press', 'press_known'):
            assert a[key] == b[key], key
        # This pilot refuses gaps or unknowns, rather than inventing negatives.
        assert a['valid'] and all(a['press_known'])
        groups[(a['session'], a['run'])].append((a, b))
    results, excluded = [], []
    for (session, run), rows in groups.items():
        n = len(rows)
        assert [a['position'] for a, _ in rows] == list(range(n))
        for c, action in enumerate(receipts[0]['actions']):
            truth = tuple(i for i, (a, _) in enumerate(rows) if a['press'][c])
            if not truth:
                excluded.append({'session': session, 'action': action, 'reason': 'no true events; not a timing comparison'})
                continue
            pa = tuple(i for i, (a, _) in enumerate(rows) if a['press_probability'][c] >= .5)
            pb = tuple(i for i, (_, b) in enumerate(rows) if b['press_probability'][c] >= .5)
            exact = F(2 * matches(truth, pa), len(truth) + len(pa)) - F(2 * matches(truth, pb), len(truth) + len(pb))
            for width in (1, 2, 4, 8):
                windows = [(t // width * width, min(n - 1, t // width * width + width - 1)) for t in truth]
                paired, stats = frontier_bounds(n, windows, pa, pb, early=1, late=0, max_states=20000)
                aa, _ = frontier_bounds(n, windows, pa, (), early=1, late=0, max_states=20000)
                bb, _ = frontier_bounds(n, windows, pb, (), early=1, late=0, max_states=20000)
                independent = aa[0] - bb[1], aa[1] - bb[0]
                assert independent[0] <= paired[0] <= exact <= paired[1] <= independent[1]
                if width == 1:
                    assert paired == (exact, exact)
                results.append({'session': session, 'run': run, 'action': action, 'bins': n,
                                'events': len(truth), 'predictions': [len(pa), len(pb)],
                                'coarsening_bins': width, 'exact_f1_seed0_minus_seed1': float(exact),
                                'paired_bounds': list(map(float, paired)),
                                'separate_bounds': list(map(float, independent)),
                                'paired_width': float(paired[1] - paired[0]),
                                'separate_width': float(independent[1] - independent[0]),
                                'paired_resolved': sign_resolved(paired),
                                'separate_resolved': sign_resolved(independent), **stats})
    summary = []
    for width in (1, 2, 4, 8):
        rr = [r for r in results if r['coarsening_bins'] == width]
        summary.append({'coarsening_bins': width, 'comparisons': len(rr),
                        'paired_resolved': sum(r['paired_resolved'] for r in rr),
                        'separate_resolved': sum(r['separate_resolved'] for r in rr),
                        'strictly_narrower': sum(r['paired_width'] < r['separate_width'] for r in rr),
                        'mean_paired_width': sum(r['paired_width'] for r in rr) / len(rr),
                        'mean_separate_width': sum(r['separate_width'] for r in rr) / len(rr)})
    result = {'kind': 'controlled_command_label_coarsening', 'summary': summary, 'results': results,
              'excluded': excluded, 'all_truth_contained': True,
              'natural_annotation_uncertainty': False, 'gameplay_claim': False,
              'sources': receipts[0]['sources'], 'export_hashes': [r['export_sha256'] for r in receipts],
              'scripts': {p.name: sha(p) for p in (Path(__file__), Path(__file__).with_name('frontier_event_bounds.py'))},
              'elapsed_s': time.perf_counter() - start}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'summary': summary, 'elapsed_s': result['elapsed_s']}, indent=2))


if __name__ == '__main__':
    main()
