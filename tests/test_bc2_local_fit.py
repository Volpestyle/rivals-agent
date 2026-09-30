"""Local launch plumbing: no real corpus, tensors, devices or cloud calls."""
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from policy.bc2 import local_fit


@pytest.fixture
def prepared(tmp_path):
    recipe = json.loads(Path(local_fit.__file__).with_name('grid-l-static.json').read_text())[0]
    recipe.update(name='still-start-193113-static30-s0',
                  extra_train=[local_fit.SESSION+'-fit'],
                  oversample={local_fit.SESSION+'-fit': .15},
                  eval_sessions=['20260925T212646-322Z-49728-6', local_fit.SESSION+'-hold'])
    path = tmp_path/'recipe.json'
    path.write_text(json.dumps([recipe]))
    args = (path, tmp_path/'human', tmp_path/'extra', tmp_path/'expert')
    return recipe, args


def complete(args):
    recipe, groups = local_fit.plan(*args)
    for role, paths in groups.items():
        for path in paths:
            path.mkdir(parents=True)
            for name in local_fit.FILES:
                (path/name).write_bytes(b'not an array: preflight must not decode it')
            (path/'meta.json').write_text(json.dumps({
                'session': path.name, 'calibration': {'source': recipe['expert_label_source']}}))
    return groups


def test_preflight_works_without_site_packages(prepared):
    _, args = prepared
    complete(args)
    command = [sys.executable, '-S', '-m', 'policy.bc2.local_fit']
    for key, value in zip(('recipe', 'human-root', 'extra-root', 'expert-root'), args):
        command += ['--'+key, str(value)]
    result = subprocess.run(command+['--out', str(args[0].parent/'out')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    roles = json.loads(result.stdout)['roles']
    assert list(map(len, roles.values())) == [9, 2, 2, 13]
    assert roles['eval'][-1].endswith('-hold')
    assert not (args[0].parent/'out').exists()


@pytest.mark.parametrize('key,value', [
    ('expert_sessions', ['../unrequested']), ('eval_sessions', []),
    ('oversample', {}), ('seed', 1), ('unknown_option', True),
])
def test_recipe_changes_refused(prepared, key, value):
    recipe, args = prepared
    recipe[key] = value
    args[0].write_text(json.dumps([recipe]))
    with pytest.raises(ValueError, match='recipe differs'):
        local_fit.plan(*args)


def test_missing_dev_and_val_are_not_dropped(prepared):
    _, args = prepared
    groups = complete(args)
    for role in ('dev', 'eval'):
        (groups[role][0]/'feats.npy').unlink()
    _, _, check = local_fit.preflight(*args)
    assert len(check['missing']) == 2
    assert len(check['roles']['dev']) == len(check['roles']['eval']) == 2


def test_mixed_expert_labels_refused(prepared):
    _, args = prepared
    groups = complete(args)
    path = groups['expert'][0]/'meta.json'
    meta = json.loads(path.read_text())
    meta['relabel'] = {'calibration': {'source': 'v2-cd'}}
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match='label source'):
        local_fit.preflight(*args)


def test_forbidden_root_refused_before_reading_cache(prepared):
    _, args = prepared
    with pytest.raises(ValueError, match='forbidden'):
        local_fit.plan(args[0], args[1]/'sealed', *args[2:])


def test_fit_arguments_preserve_recipe_without_real_torch(prepared, monkeypatch):
    recipe, args = prepared
    _, groups = local_fit.plan(*args)
    calls = {}
    torch = ModuleType('torch')
    torch.set_num_threads = lambda n: calls.update(threads=n)
    torch.backends = SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True))
    trainer = ModuleType('policy.bc2.train')
    trainer.fit = lambda *a, **kw: calls.update(args=a, kwargs=kw)
    model = ModuleType('policy.bc2.model')
    model.Config = lambda **kw: kw
    for name, value in [('torch', torch), ('policy.bc2.train', trainer), ('policy.bc2.model', model)]:
        monkeypatch.setitem(sys.modules, name, value)
    import policy.bc2
    monkeypatch.setattr(policy.bc2, 'train', trainer, raising=False)
    local_fit.run(recipe, groups, args[0].parent/'out')
    assert calls['threads'] == 2
    assert calls['args'][:3] == (groups['train'], groups['dev'], groups['eval'])
    kw = calls['kwargs']
    assert kw['device'] == 'mps'
    for name in ('seed', 'epochs', 'batch_size', 'static_aug', 'expert_mask', 'oversample'):
        assert kw[name] == recipe[name]
    assert kw['config'] == {'use_dt': True, 'hidden': 1536, 'layers': 2}
    assert kw['expert_dirs'] == groups['expert']


def test_existing_output_refused(prepared):
    _, args = prepared
    complete(args)
    argv = []
    for key, value in zip(('recipe', 'human-root', 'extra-root', 'expert-root'), args):
        argv += ['--'+key, str(value)]
    with pytest.raises(ValueError, match='output already exists'):
        local_fit.main(argv+['--out', str(args[0].parent), '--run'])
