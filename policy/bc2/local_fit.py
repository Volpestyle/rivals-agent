"""Local-only driver for the prepared September 30 still-start experiment.

Preflight reads explicit cache metadata only. --run is for the lead-granted Mac
queue slot; it calls train.fit directly and never imports the cloud launcher.
"""
import argparse
import ast
import json
from pathlib import Path

SESSION = '20260930T193113-731Z-163680-1'
FILES = ('feats.npy', 'gray_g.npy', 'gray_c.npy', 'green.npy', 'targets.npz', 'meta.json')


def plan(recipe, human_root, extra_root, expert_root):
    rows = json.loads(Path(recipe).read_text())
    if len(rows) != 1:
        raise ValueError('exactly one exploratory recipe is required')
    r = rows[0]
    expected = json.loads(Path(__file__).with_name('grid-l-static.json').read_text())[0]
    expected.update(name='still-start-193113-static30-s0', extra_train=[SESSION+'-fit'],
                    oversample={SESSION+'-fit': .15},
                    eval_sessions=['20260925T212646-322Z-49728-6', SESSION+'-hold'])
    if r != expected:
        raise ValueError('recipe differs from the assigned still-start comparison')
    # Read literal cohort constants without importing modal or constructing cloud resources.
    tree = ast.parse(Path(__file__).with_name('cloud.py').read_text())
    cohort = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
              if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
              and n.targets[0].id in ('TRAIN', 'DEV', 'VAL')}
    if r['eval_sessions'][0:1] != cohort['VAL']:
        raise ValueError('validation cohort changed')
    groups = {'train': [Path(human_root)/s for s in cohort['TRAIN']] + [Path(extra_root)/(SESSION+'-fit')],
              'dev': [Path(human_root)/s for s in cohort['DEV']],
              'eval': [Path(human_root)/cohort['VAL'][0], Path(extra_root)/(SESSION+'-hold')],
              'expert': [Path(expert_root)/s for s in r['expert_sessions']]}
    deny_path = Path(__file__).resolve().parents[2]/'data/human/sealed-denylist.v2.json'
    deny = {s['session_id'] for s in json.loads(deny_path.read_text())['sessions']}
    paths = [p for group in groups.values() for p in group]
    if len({str(p.absolute()) for p in paths}) != len(paths):
        raise ValueError('duplicate cache across split roles')
    for p in paths:
        if p.name in deny or any('sealed' in x.name.lower() or x.is_symlink() for x in (p, *p.parents)):
            raise ValueError('forbidden cache path')
    return r, groups


def preflight(recipe, human_root, extra_root, expert_root):
    r, groups = plan(recipe, human_root, extra_root, expert_root)
    missing, size = [], 0
    for role, paths in groups.items():
        for p in paths:
            for name in FILES:
                f = p/name
                if not f.is_file():
                    missing.append(str(f))
                elif f.is_symlink():
                    raise ValueError('symlink cache file')
                else:
                    size += f.stat().st_size
            if (p/'meta.json').is_file():
                meta = json.loads((p/'meta.json').read_text())
                if meta.get('session') != p.name:
                    raise ValueError('cache session mismatch')
                source = meta.get('relabel', {}).get('calibration', meta.get('calibration', {})).get('source')
                if role == 'expert' and source != r['expert_label_source']:
                    raise ValueError('expert label source mismatch')
    return r, groups, {'missing': missing, 'cache_gib': size/2**30,
                       'roles': {k: [p.name for p in v] for k, v in groups.items()}}


def run(r, groups, out):
    import torch
    from policy.bc2 import train
    from policy.bc2.model import Config
    torch.set_num_threads(2)
    if not torch.backends.mps.is_available():
        raise RuntimeError('MPS required; no silent CPU or cloud fallback')
    config = Config(use_dt=r['use_dt'], hidden=r['hidden'], layers=r['layers'])
    return train.fit(groups['train'], groups['dev'], groups['eval'], out,
                     config=config, device='mps', seed=r['seed'], epochs=r['epochs'],
                     batch_size=r['batch_size'], expert_dirs=groups['expert'],
                     static_aug=r['static_aug'], expert_mask=r['expert_mask'], oversample=r['oversample'],
                     log=lambda s: print(s, flush=True))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('recipe', 'human-root', 'extra-root', 'expert-root', 'out'):
        p.add_argument('--'+key, required=True)
    p.add_argument('--run', action='store_true', help='Only after explicit GPU/queue grant')
    a = p.parse_args(argv)
    r, groups, check = preflight(a.recipe, a.human_root, a.extra_root, a.expert_root)
    print(json.dumps(check, indent=2), flush=True)
    if not a.run:
        return 1 if check['missing'] else 0
    if check['missing']:
        raise ValueError('incomplete local caches')
    out = Path(a.out)
    if out.exists():
        raise ValueError('output already exists; no overwrite or implicit retry')
    # Eager feature residency is the unchanged trainer's behavior; leave ample room
    # for tensors, optimizer, evaluation and the rest of the Mac.
    if check['cache_gib'] > 80:
        raise ValueError('cache footprint exceeds the planned Mac memory envelope')
    run(r, groups, out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
