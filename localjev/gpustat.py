"""GPU load and GPU-visible memory while the server answers, without sudo.

powermetrics needs root; these are the IOAccelerator driver's own counters, which any
user can read. Utilization is the whole GPU's, not this process's, so run it while
nothing else uses the GPU.

    uv run python -m localjev.gpustat [samples] [interval_s]
"""
import re
import subprocess
import sys
import time

FIELDS = ("Device Utilization %", "Renderer Utilization %", "In use system memory", "Alloc system memory")


def sample():
    out = subprocess.run(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"],
                         capture_output=True, text=True).stdout
    m = re.search(r'"PerformanceStatistics" = \{([^}]*)\}', out)
    if not m:
        return None
    f = dict(re.findall(r'"([^"]+)"=(\d+)', m.group(1)))
    return {k: int(f[k]) for k in FIELDS if k in f}


def main(argv=None):
    a = argv or sys.argv[1:]
    n, iv = int(a[0]) if a else 10, float(a[1]) if len(a) > 1 else 1.0
    peak = {}
    for i in range(n):
        s = sample()
        if s is None:
            print("no IOAccelerator statistics", flush=True)
            return
        for k, v in s.items():
            peak[k] = max(peak.get(k, 0), v)
        print(f"{time.strftime('%H:%M:%S')} util={s['Device Utilization %']}% "
              f"renderer={s['Renderer Utilization %']}% "
              f"inuse={s['In use system memory'] / 2**30:.1f}GB "
              f"alloc={s['Alloc system memory'] / 2**30:.1f}GB", flush=True)
        if i < n - 1:
            time.sleep(iv)
    print(f"peak: util={peak['Device Utilization %']}% "
          f"inuse={peak['In use system memory'] / 2**30:.1f}GB "
          f"alloc={peak['Alloc system memory'] / 2**30:.1f}GB")


if __name__ == "__main__":
    main()
