The scoped `.gitattributes` disables text newline conversion only within this
new evidence packet. Generated JSON contains the writer's original line endings;
native images, compressed step records and the exact as-run source are also
preserved byte for byte. This prevents the PC's `core.autocrlf=true` from changing
the SHA256-pinned evidence during staging or a future checkout.

`files.sha256.json` was closed before this Git-transport note and attributes were
added; its listed measurements and reports are unchanged. Staged Git blobs are
checked against every listed SHA256 before committing. No repository-wide Git
configuration or existing evidence attributes are changed.
