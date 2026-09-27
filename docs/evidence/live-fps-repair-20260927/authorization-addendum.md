# Authorization attribution correction — 2026-09-27

This metadata-only addendum corrects the authorization wording in the frozen
README committed as `1455a92`. It changes no source, measurements, test results,
run receipts or acceptance claims.

**Live-loop**, the integration owner, issued the explicit per-run instruction
for the single bounded saved-PNG CUDA qualification after the CPU/fake checks
passed. Live-loop interpreted herdr-lead's repair/replay request under James's
standing inference permission. The README's phrase "the lead explicitly
authorized one offline CUDA qualification" must not be read as a claim that
herdr-lead explicitly approved this particular replay.

Herdr-lead's subsequent GPU-slot restriction arrived **after this replay had
completed and its process had exited**. Live-loop reported that chronology to
herdr-lead. No further GPU work or automatic retry is queued. This attribution
correction requires no rerun; the original as-run packet and hashes remain intact.
