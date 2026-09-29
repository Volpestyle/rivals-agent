"""Transcribe the 120 visually inspected overlay cells, preserving CSV identity."""
import csv
import hashlib
import json
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[3]
run=root/'data/calibration/alt-cam-20260928b/inference-fps-aba'
source=run/'fps-annotations.csv'
target=run/'fps-manual.csv'
# All other cells were visually read as 240, not inferred from the cap.
values=[240]*120
for index in (0,1,4,8,15,20,21,26,29,30,38,
              40,41,43,45,50,54,58,59,62,63,77,
              83,89,91,94,96,99,100,110,115,119):
    values[index]=239
values[66],values[68],values[73],values[98]=241,232,218,224
assert not target.exists()
shutil.copyfile(source,target)
with target.open(newline='',encoding='utf8') as f:
    rows=list(csv.DictReader(f))
assert len(rows)==120
for index,row in enumerate(rows):
    assert row['path']==f'frames/{index:07d}-fps.png'
    row['fps']=str(values[index])
with target.open('w',newline='',encoding='utf8') as f:
    writer=csv.DictWriter(f,fieldnames=rows[0])
    writer.writeheader()
    writer.writerows(rows)
with (Path(__file__).parent/'manual-transcription.json').open('x') as f:
    json.dump({'method':'Assistant visual reading of all120 native overlay crops in overlay-A1/B/A2.png; no OCR or imputation.',
        'values_by_csv_row':values,'source_csv_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'manual_csv_sha256':hashlib.sha256(target.read_bytes()).hexdigest()},f,indent=2)
print(target)
