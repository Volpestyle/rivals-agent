# v1.0.1 evidence transport addendum

Source/release remain a14ff671d7defe08dc78b126e4d4b91d2282ba47 and
72dead55817453c2e31668f0cf203514ff50c59433f007fd04eec226bb8c4547.

Git normalized only the outer CRLF lines of the frozen mutation-tests.json during
commit. Its original working bytes are preserved byte-exact here as
mutation-tests-original.json, SHA256
0a9ff868ec75df05a1d9ccef11ab3bca221480a5782cd297e3d0dc9691928e68.
The committed LF form has SHA256
3e1952c75f1d311eb9b73c69b360ffab4364e6558e4924997f3ea5a70c0fc721.
Replacing CRLF with LF reproduces the committed blob exactly; parsed JSON is equal.
No test output, result, source or release content changed. All other packet pins
match committed blobs. The original frozen packet is untouched.

GIT-SHA256SUMS.txt pins the committed original packet, paths relative to repo root.
The original SHA256SUMS.txt continues to describe the originally frozen working
bytes, with this one transport difference. This addendum corrects the owner's
premature claim that all original packet git hashes had already verified.
