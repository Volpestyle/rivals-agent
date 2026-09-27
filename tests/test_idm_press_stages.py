"""Synthetic recovery boundaries; no corpus, media, GPU or cloud calls."""
import json

import pytest

np = pytest.importorskip('numpy')
from policy.idm import press_stages as S


def identity():
    return {'run_config_sha256': '1'*64, 'source_archive_sha256': '2'*64,
            'input_manifest_sha256': '3'*64, 'checkpoint_sha256': '4'*64,
            'app_name': 'synthetic-idm', 'output_volume_id': 'vo-synthetic'}


def fixture(tmp_path):
    values = np.array([[.1,.2,.3],[.7,.8,.9]], dtype=np.float32)
    rows = [['train', 1], ['train', 2]]
    cal = {'method':'synthetic TRAIN only'}
    S.complete(tmp_path/'train', 'train-inference', identity(), values, rows, calibration=cal)
    return values, rows, cal


def test_complete_stage_reuses_without_calling_inference(tmp_path):
    values, rows, cal = fixture(tmp_path)
    def forbidden():
        pytest.fail('complete stage reran inference')
    actual, actual_cal = S.scores(tmp_path/'train', 'train-inference', identity(), rows, forbidden, resume=True)
    np.testing.assert_array_equal(actual, values)
    assert actual_cal == cal
    with pytest.raises(ValueError, match='explicit recovery'):
        S.scores(tmp_path/'train', 'train-inference', identity(), rows, forbidden, resume=False)


def test_partial_stage_refuses_without_compute_or_overwrite(tmp_path):
    path=tmp_path/'partial'
    path.mkdir()
    (path/'probabilities.npy').write_bytes(b'partial')
    def forbidden():
        pytest.fail('partial inference was silently repeated')
    with pytest.raises(ValueError,match='partial inference'):
        S.scores(path,'real',identity(),[['heldout',0]],forbidden,resume=True)
    assert (path/'probabilities.npy').read_bytes()==b'partial'


@pytest.mark.parametrize('key', sorted(S.IDENTITY))
def test_every_identity_field_is_bound(tmp_path,key):
    _,rows,_=fixture(tmp_path)
    changed=identity()
    changed[key]='f'*64 if key.endswith('_sha256') else 'another-run'
    with pytest.raises(ValueError,match='identity mismatch'):
        S.load(tmp_path/'train','train-inference',changed,rows)


def test_corrupt_artifact_and_row_order_refused(tmp_path):
    _,rows,_=fixture(tmp_path)
    with pytest.raises(ValueError,match='row identity/order'):
        S.load(tmp_path/'train','train-inference',identity(),rows[::-1])
    path=tmp_path/'train/probabilities.npy'
    raw=path.read_bytes()
    path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
    with pytest.raises(ValueError,match='artifact hash'):
        S.load(tmp_path/'train','train-inference',identity(),rows)


@pytest.mark.parametrize('bad', [np.zeros((2,2),np.float32), np.zeros((2,3),np.float64),
                                np.full((2,3),np.nan,np.float32)])
def test_bad_probability_payload_refused(tmp_path,bad):
    with pytest.raises(ValueError):
        S.complete(tmp_path/'stage','real',identity(),bad,[['heldout',0],['heldout',1]])
    assert not (tmp_path/'stage/stage-complete.json').exists()


def test_receipt_is_last_and_complete_metadata_is_required(tmp_path):
    _,rows,_=fixture(tmp_path)
    path=tmp_path/'train/stage-complete.json'
    receipt=json.loads(path.read_bytes())
    receipt['completion']['exit']=1
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='completion metadata'):
        S.load(tmp_path/'train','train-inference',identity(),rows)


def test_missing_later_stage_infers_once_then_resumes(tmp_path):
    calls=[]
    values=np.ones((2,3),np.float32)*.5
    def compute():
        calls.append('inference')
        return values
    for _ in range(2):
        actual,_=S.scores(tmp_path/'real','real',identity(),[['heldout',1],['heldout',2]],compute,resume=True)
        np.testing.assert_array_equal(actual,values)
    assert calls==['inference']


def test_worker_reentry_refuses_legacy_partial_and_accepts_complete_train(tmp_path):
    root=tmp_path/'run'
    root.mkdir()
    (root/'started.json').write_text('{}')
    with pytest.raises(ValueError,match='identity absent'):
        S.reentry(root,identity())
    (root/'stage-identity.json').write_bytes(S.json_bytes(identity()))
    with pytest.raises(ValueError,match='partial TRAIN'):
        S.reentry(root,identity())
    values=np.full((2,3),.5,np.float32)
    S.complete(root/'stages/train-inference','train-inference',identity(),values,
               [['train',0],['train',1]],calibration={'method':'synthetic'})
    mode,evidence=S.reentry(root,identity())
    assert mode=='evaluation'
    assert evidence['stage_receipt_sha256']==S.digest(root/'stages/train-inference/stage-complete.json')


def test_completed_final_report_replay_validates_all_stages(tmp_path):
    import shutil
    root=tmp_path/'run'
    root.mkdir()
    (root/'stage-identity.json').write_bytes(S.json_bytes(identity()))
    values=np.full((2,3),.5,np.float32)
    for phase in S.PHASES:
        rows=[['train' if phase=='train-inference' else 'heldout',i] for i in range(2)]
        stage=root/'stages'/phase
        S.complete(stage,phase,identity(),values,rows,
                   calibration={'method':'synthetic'} if phase=='train-inference' else None)
        alias='train' if phase=='train-inference' else phase
        shutil.copyfile(stage/'probabilities.npy',root/(alias+'-probabilities.npy'))
    shutil.copyfile(root/'stages/train-inference/calibration.json',root/'calibration.json')
    shutil.copyfile(root/'stages/real/row-ids.json',root/'heldout-row-ids.json')
    (root/'report.json').write_text(json.dumps({'checkpoint_sha256':identity()['checkpoint_sha256'],
        'manifest_sha256':identity()['run_config_sha256'],'controls':{'real':{},'zero_visuals':{}}}))
    result={'exit':0,'stage_identity':identity(),'files':{}}
    for p in root.rglob('*'):
        if p.is_file():
            result['files'][p.relative_to(root).as_posix()]={'bytes':p.stat().st_size,'sha256':S.digest(p)}
    (root/'result.json').write_text(json.dumps(result))
    before=(root/'result.json').read_bytes()
    mode,value=S.reentry(root,identity())
    assert mode=='report' and value==result
    assert (root/'result.json').read_bytes()==before
    (root/'real-probabilities.npy').write_bytes(b'changed')
    with pytest.raises(ValueError,match='final artifact hash'):
        S.reentry(root,identity())
