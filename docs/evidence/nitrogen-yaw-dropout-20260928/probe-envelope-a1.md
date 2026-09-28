# Pre-launch probe allowance refinement, within approved $6.25

Three globally paced AppCreates span at least 30 seconds. A 30-second synthetic
work interval cannot reliably demonstrate three-way worker overlap. Use a
60-second synthetic work loop with a 120-second funded work window for import,
base/input verification, serialization and volume completion. Startup300 and
cleanup120 are unchanged. This changes launcher testing, not the scientific arm.

Accepted v1.0.5 `bootstrap` rounding: probe hold $0.407660 each, $1.222980 for
three. Full fits stay $1.643714 each / $4.931142. Combined **$6.154122 <= $6.25**;
$0.095878 unallocated. Probe envelope allocation $1.23 and fit envelope $5.02
sum to the existing $6.25. No extra slot, retry or money is authorized.

This supersedes the preliminary 60-second funded probe rows in sizing and
authorization.md. Report actual overlap; a short synthetic probe establishes no
full-fit p95. No existing launcher or guard was altered.
