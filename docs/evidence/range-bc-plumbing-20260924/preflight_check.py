import sys
from argparse import Namespace
from policy.range_bc import train
P = sys.argv[1]
b = open(f"{P}/hud-parity-1-p2.json", "rb").read(); print("parity CR", b.count(b"\r"), "LF", b.count(b"\n"))
a = Namespace(scope="fit", preregistration=f"{P}/preregistration.json", epochs=13, weight_decay=1e-4, stride=64,
              max_steps=None, hud_parity=f"{P}/hud-parity-1-p2.json")
pre = train.preregistered(a)
rec = train.parity_record(a, pre)
print("preregistered ok:", {k: pre[k] for k in ("epochs", "weight_decay", "stride")}, "| parity_record:", rec)
for bad in (dict(epochs=20), dict(stride=48), dict(weight_decay=1e-3)):
    try:
        train.preregistered(Namespace(**{**vars(a), **bad})); print("UNEXPECTED accept", bad)
    except train.FitError as e:
        print("refused", bad, "->", str(e)[:90])
