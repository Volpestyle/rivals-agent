import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
import cv2
from perception.camera_ready_pose import band
cv2.setNumThreads(2)
p=Path('data/calibration/alt-cam-20260928/yaw-01')
a=band(cv2.imread(str(p/'ready-attach.png')))
b=band(cv2.imread(str(p/'frames/0000029-before-attach.png')))
for w,h,xs,ys in ((96,60,(16,152),(16,74)),(80,60,(16,96,176),(16,74)),(64,48,(16,100,184),(16,86))):
    print('size',w,h)
    for y in ys:
        for x in xs:
            s=cv2.matchTemplate(b[y-12:y+h+12,x-12:x+w+12],a[y:y+h,x:x+w],cv2.TM_CCOEFF_NORMED)
            _,peak,_,(ix,iy)=cv2.minMaxLoc(s)
            s[max(0,iy-2):iy+3,max(0,ix-2):ix+3]=-1
            print(x,y,round(peak,4),round(peak-float(s.max()),4),ix-12,iy-12)
