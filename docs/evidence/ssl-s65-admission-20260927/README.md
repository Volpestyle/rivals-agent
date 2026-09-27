# S6.5 whole-file SSL admission, 2026-09-27

Four finalized historical raw sessions qualify for **world-feature SSL only**.
No semantic labels, evaluation use, or gameplay intervals are admitted here.
The consumer (idm-owner) owns native-window inspection and a separate cut-free
sampled-clip manifest before extraction or training. No original was transferred.

Pin `admission.json` raw SHA-256:
`864e54350343a26ce0111d03d6e76d39bddef2f1e3e1c5cdb898b93e1f42dd02`.
Status is `accepted_ssl_only`; independent post-landing review remains pending.

Selection: the four smallest finalized S6.5 raw sessions in `metadata-pass.json`,
excluding derived clips and stubs. Each source has a latest `replaced` log record,
matching size, stable size/mtime through streaming SHA-256, and HEVC codec/duration
from a header-only ffprobe. `finalize.py` and `finalize.log` record the operation.
The hash driver ran BelowNormal, checked game/OBS absence and at least 2 GiB free
RAM every two seconds, and read media in 4 MiB blocks. No frames were decoded.

Forbidden-family checks compare filenames/dates and exact media hashes against
registry/denylist metadata; neither metadata record's media paths were opened.
The allowlist contains only named February raw sessions, excluding every sealed,
held-out, frozen-dev, Gate 2, V-C/V-Q and DayMR family. Selected hashes are unique.
This is an identity check, not a claim of exhaustive perceptual deduplication or
usable gameplay throughout a file. Unknown visual content remains for the consumer.

Files are immutable once this packet is committed. Review findings or later source
selection changes belong in a separate receipt or superseding packet.
