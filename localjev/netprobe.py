"""The network floor between this machine and the local Jev server, without the model.

GET /health on one kept-alive connection: everything the real request pays except the
model. Run it from the PC before blaming the server for a slow round trip; on Wi-Fi the
hop has been the larger half.

    uv run python -m localjev.netprobe 192.168.4.126 8724 [n]
"""
import http.client
import statistics
import sys
import time


def probe(host, port=8724, n=40, warmup=5):
    c = http.client.HTTPConnection(host, port, timeout=10)
    ms = []
    for _ in range(n):
        t = time.perf_counter()
        c.request("GET", "/health")
        c.getresponse().read()
        ms.append((time.perf_counter() - t) * 1000)
    c.close()
    return sorted(ms[warmup:])  # the first calls include the TCP handshake


def main(argv=None):
    a = argv or sys.argv[1:]
    host = a[0] if a else "192.168.4.126"
    port = int(a[1]) if len(a) > 1 else 8724
    n = int(a[2]) if len(a) > 2 else 40
    s = probe(host, port, n)
    print(f"/health {host}:{port} on one kept-alive connection, n={len(s)}: "
          f"p50={statistics.median(s):.1f} p95={s[int(0.95 * (len(s) - 1))]:.1f} "
          f"min={s[0]:.1f} max={s[-1]:.1f} ms")


if __name__ == "__main__":
    main()
