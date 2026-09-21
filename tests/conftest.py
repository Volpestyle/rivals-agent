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


import pytest


def pytest_addoption(parser):
    parser.addoption("--corpus", action="store_true", default=False,
                     help="also run tests marked `corpus` (they read the demonstration corpus under data/)")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "corpus: reads the recorded demonstration corpus under data/; skipped unless --corpus is given")


def pytest_collection_modifyitems(config, items):
    """A test that reads the demonstration corpus runs only when asked for by name of intent.

    The corpus holds sealed sources and files mid-migration, so a whole-file or broad `-k` run must
    not open it by accident. Mark such a test `@pytest.mark.corpus`; it is skipped without `--corpus`.
    """
    if config.getoption("--corpus"):
        return
    skip = pytest.mark.skip(reason="reads the demonstration corpus; pass --corpus to run it")
    for item in items:
        if "corpus" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _no_real_dotenv(monkeypatch):
    """The developer's .env (endpoint, keys) never reaches a test."""
    from agent import jev
    monkeypatch.setattr(jev, "_dotenv", lambda path=None: {})
