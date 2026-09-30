"""Pixel counterfactual from run-02 responses; coarse gain is a stated assumption."""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKET = Path(__file__).resolve().parent
record = json.loads((ROOT / 'data/calibration/compat-check-20260929/run-02/result.json').read_text())
pulses = [e for e in record['events'] if e['event']=='pulse']
responses = [e for e in record['events'] if e['event']=='response']
observations = [e for e in record['events'] if e['event']=='observe']
proof = next(e for e in observations if e['t']==pulses[0]['proof_t'])
initial = {d['id']:[((d['bbox'][0]+d['bbox'][2])/2-1280)/2,
                    ((d['bbox'][1]+d['bbox'][3])/2-720)/2] for d in proof['detections']}
pitch = [r['pixel_change_1280'] for p,r in zip(pulses,responses) if p['axis']==1]
response_delay = statistics.median(r['observed_delay_s'] for r in responses)
overhead = statistics.median(pulses[i+1]['t']-pulses[i]['t']-responses[i]['observed_delay_s']
                             for i in range(len(pulses)-1))
map_record = json.loads((ROOT/'agent/camera_maps/alt-247-124.json').read_text())
yaw_rates = {sign:{p['stick']:p['measurement']['value'] for p in map_record['yaw'][direction]}
             for sign,direction in [(1,'positive'),(-1,'negative')]}


def replay(coarse_ratio, alias=True, v4=True, starts=None):
    errors = {k:list(v) for k,v in (starts or initial).items()}
    used, time_s, pitch_index, total = 0., 0., 0, 0
    sides = []
    for target in (2,1):
        start_t, start_input = time_s, used
        side = {'target':target, 'initial_error':list(errors[target]), 'pulses':[]}
        while max(abs(v) for v in errors[target])>12:
            x,y = errors[target]
            axis = 0 if abs(x)>12 else 1
            coarse = v4 and axis==1 and abs(y)>39
            duration = .1 if coarse else .05
            magnitude = (.3 if abs(x)>96 else .2 if abs(x)>48 else .1) if axis==0 and v4 else .2 if coarse else .1
            if total>=40 or used+duration>2+1e-9:
                side['stop']='cumulative_input_limit'
                break
            cycle = response_delay+(duration-.05)+overhead*(.5 if alias else 1.)
            # Reserve a full response window just as the real runner does.
            if time_s-start_t+cycle+.75>=15:
                side['stop']='insufficient_response_budget'
                break
            if axis==1:
                change = pitch[pitch_index%len(pitch)]*(coarse_ratio if coarse else 1.)
                pitch_index+=1
            else:
                sign = 1 if x>0 else -1
                change = responses[0]['pixel_change_1280']*yaw_rates[sign][magnitude]/yaw_rates[-1][.1]
            signed = change*(1 if errors[target][axis]>0 else -1)
            before = list(errors[target])
            for error in errors.values():
                error[axis]-=signed
            total+=1;used+=duration;time_s+=cycle
            side['pulses'].append({'axis':axis,'magnitude':magnitude,'duration_s':duration,
                                   'change_px_1280':change,'before':before,'after':list(errors[target])})
        if 'stop' not in side:
            time_s+=.12  # explicit three-observation confirmation allowance
        side.update({'pulse_count':len(side['pulses']), 'elapsed_s':time_s-start_t,
                     'reserved_input_s':used-start_input,'final_error':list(errors[target])})
        sides.append(side)
        if 'stop' in side:
            break
    return {'sides':sides,'pulse_count':total,'reserved_input_s':used,'elapsed_s':time_s,
            'passed':len(sides)==2 and all('stop' not in s for s in sides)}


output = {'assumptions':{'fine_pitch_responses':pitch,'response_delay_s':response_delay,
          'recorded_cycle_overhead_s':overhead,'alias_overhead_fraction':.5,
          'coarse_threshold_px_1280':12+4*max(pitch),
          'coarse_gain_unmeasured':True,'freshness_and_tracking_not_simulated_here':True},
          'baseline_v3':replay(1.,False,False), 'v4_coarse_ratio_4':replay(4.),
          'v4_coarse_ratio_2':replay(2.),
          'v4_from_failure':replay(4.,starts={2:[-7.,-45.75],1:[278.,-45.75]})}
if __name__=='__main__':
    (PACKET/'response-replay.json').write_text(json.dumps(output,indent=2)+'\n')
    print({name:{k:v for k,v in row.items() if k not in ('sides','pulses')} for name,row in output.items() if name!='assumptions'})
    for name,row in output.items():
        if name!='assumptions':
            print(name,[{k:v for k,v in side.items() if k!='pulses'} for side in row['sides']])
