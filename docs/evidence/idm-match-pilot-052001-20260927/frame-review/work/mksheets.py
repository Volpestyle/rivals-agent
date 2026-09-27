import json,cv2,numpy as np,os,sys
ev=json.load(open(r'C:/Users/volpe/repos/rivals-agent/data/human/sessions/20260927T052001-827Z-150600-5/segments-evidence.json'))
R={}
for l in open('run/frames.jsonl'):
    r=json.loads(l); R[r['frame_index']]=r
S=554275865572800
os.makedirs('sheets',exist_ok=True)
TW,TH,C,RW=480,270,5,4
def sheet(name,idx):
    for k in range(0,len(idx),C*RW):
        chunk=idx[k:k+C*RW]
        img=np.zeros((TH*RW,TW*C,3),np.uint8)
        for j,i in enumerate(chunk):
            r=R[i]; t=cv2.resize(cv2.imread('run/'+r['image']),(TW,TH),interpolation=cv2.INTER_AREA)
            lab=f"{(r['composition_ns']-S)/1e9:.2f}s f{i}"
            cv2.rectangle(t,(0,0),(210,22),(0,0,0),-1); cv2.putText(t,lab,(3,16),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,255),1)
            y,x=divmod(j,C); img[y*TH:(y+1)*TH,x*TW:(x+1)*TW]=t
        fn=f'sheets/{name}-{k//(C*RW):02d}.jpg'; cv2.imwrite(fn,img,[cv2.IMWRITE_JPEG_QUALITY,88]); print(fn,len(chunk))
for s in ev['segments']:
    sid=s['segment_id']
    if sid not in ['seg-004','seg-008','seg-014','seg-020','seg-026','seg-032']: continue
    ins=sorted(i for i,r in R.items() if s['start_ns']<=r['composition_ns']<s['end_ns'])
    a,b=ins[0],ins[-1]
    bulk=[i for i in ins if (i-a)%120==0]
    if bulk[-1]!=b: bulk.append(b)
    sheet(f'{sid}-bulk',bulk)
    edge=[a-1]+[i for i in ins if i<a+120 and (i-a)%12==0]+[i for i in ins if i>b-120 and (b-i)%12==0]+[b,b+1]
    sheet(f'{sid}-edges',sorted(set(i for i in edge if i in R)))

if len(sys.argv) > 1:
    pass
