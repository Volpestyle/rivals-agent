# Original audit bytes

The original audit JSON files were emitted with Windows CRLF newlines. Git may
normalize them on checkout. `manifest.json` and the source hashes in `summary.json`
refer to the bytes actually measured, not a future checkout's newline convention.

`raw-json-and-sources.zip` preserves the original JSON and all four measured source
files byte-for-byte; use those entries when verifying the recorded hashes. Native
JPEGs are binary and remain unchanged. No evidence or running source was edited.

Archive SHA256: `fb15d700ecb6fd8ef05cc754c708ef1eef3398277e59e5145fba086fc585fcd1`.
