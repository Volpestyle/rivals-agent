# Terminal receipt byte preservation

Addendum to result packet c1ec5e75. Git normalized only `terminal.json` from CRLF to LF. The original SHA256SUMS terminal entry pins the original raw bytes, preserved losslessly as `raw_base64` in receipt.json. Decode that field to recover them; its raw SHA256 is 9d4ee28ca5e26edf1f0d53a70577b6be4d8ee3b74dc259c4093f00970eff7c96. The normalized Git blob parses to identical JSON. All other pinned result files match their committed bytes.

This additive receipt preserves the original frozen packet and history. No scientific results, process exits, artifact hashes or Mac-release status changed.
