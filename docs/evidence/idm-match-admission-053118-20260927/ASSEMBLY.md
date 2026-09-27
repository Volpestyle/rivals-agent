# Match -6: assembled, admission pending

The ping-a1 packet has independent frame agreement on all 57 segments: nine
accepted, 257.649989703 seconds. The finalized independent verdict is
`independent-review.v2.verdicts.json`, SHA256
`e8fd29046ff6f484fdd6c5f978e7d49a343c4a8823aecee1d6b5279aa5868b91`;
the identical canonical copy was used by assembly. The conflicting intermediate
hold message was explicitly withdrawn by frame-review after checking these bytes.

Guarded assembly and receipt runs exited 0 without failures. Assembly decoded
52,541 frames, confirmed the 21 ms muxer offset (maximum residual 1/3000 s),
and emitted 12,930 steps, including 7,723 accepted gap-free steps. Counted
accepted time is 4.29416649505 minutes. Peak observed working set was
158,269,440 bytes. Capture/display/input-delivery latency remains uncalibrated.

The pending receipt is [match-admission-053118.pending.json](receipt/match-admission-053118.pending.json),
SHA256 `75d52be2bfcc6d66db4dff81dfc4b85644748f62b768577119b977b4a683557a`. Its table and imported-demo pins were rechecked by the owner.
The assembly freeze SHA256 is
`a2d300460108b80c6e6d34088fb69d69dbcf699b7f5e4a712c9e42ba33803409`.
Large steps, demo and review images remain local under the session directory;
the metadata packet and hash manifest are versioned.

This is produced evidence, not an accepted receipt. Required admission review
and lead acceptance remain before consumer use. The -4/-5 historical
acceptances remain superseded while their changed boundaries are reviewed.
