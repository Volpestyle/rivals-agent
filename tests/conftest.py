"""Keep the default `uv run pytest` stdlib-only.

The perception harnesses import cv2, numpy or the `perception` package. Without opencv and
numpy installed (the default), pytest skips collecting those modules instead of failing at
import; with `uv run --group perception pytest` they are collected. Matching on the module's
imports means no list of files has to be maintained when a lane adds a harness.
"""
import importlib.util
import re

HAVE_PERCEPTION = all(importlib.util.find_spec(m) for m in ("cv2", "numpy"))
NEEDS_PERCEPTION = re.compile(r"^\s*(?:import|from)\s+(?:cv2|numpy|perception)\b", re.M)


def pytest_ignore_collect(collection_path, config):
    if HAVE_PERCEPTION or collection_path.suffix != ".py" or not collection_path.name.startswith("test_"):
        return None
    return True if NEEDS_PERCEPTION.search(collection_path.read_text()) else None
