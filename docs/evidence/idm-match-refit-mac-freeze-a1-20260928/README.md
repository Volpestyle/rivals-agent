# Pre-launch amendment: exclude mutable pytest cache

Original59d2404 launch check refused changed `.pytest_cache/v/cache/nodeids` before any fit/launch receipt. The runtime inventory now excludes only pytest cache files. Every source/data/receipt/heldout/recipe byte and the six-hour $0 envelope are unchanged. Native29 tests remain valid; metadata preparation reran successfully under amended manifest73d486da. No paid work or training occurred before this amendment.

{
  "removed_non_source_paths": [
    ".pytest_cache/.gitignore",
    ".pytest_cache/CACHEDIR.TAG",
    ".pytest_cache/README.md",
    ".pytest_cache/v/cache/nodeids"
  ],
  "manifest_sha256": "73d486da67f85e87041567cd4d90b553c24a40e22c0cff05a63136e29f771d5c",
  "runtime_sha256": "b603668da3cfd8b9e4d14f5dc85f90ae504cc1f308d3d4fc5ad69539d393d460",
  "original_freeze": "59d24047535bc41af886e89f601701ffc176cf68"
}
