# Task runner. Install once: `uv tool install rust-just` (or `winget install Casey.Just` / `brew install just`).
# Every recipe is one command that reads the same in PowerShell and zsh, except test-perception's two variants.
# Arguments are spliced unquoted: quote a multi-word one twice, e.g. just test -k "'brain and not replay'".

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

# tests import hash-pinned scripts under data/ and docs/evidence/; keep bytecode out of those folders
export PYTHONDONTWRITEBYTECODE := "1"

ruff := "uvx ruff@0.14.0"

default:
    @just --list

# stdlib-only offline suite: no game, no network; cv2/numpy harnesses are skipped
test *args:
    uv run pytest {{args}}

# perception group, then `uv sync` back to stdlib-only even when tests fail; exits with pytest's status
[unix]
test-perception *args:
    uv run --group perception pytest {{args}}; rc=$?; uv sync; exit $rc

# perception group, then `uv sync` back to stdlib-only even when tests fail; exits with pytest's status
[windows]
test-perception *args:
    uv run --group perception pytest {{args}}; $rc = $LASTEXITCODE; uv sync; exit $rc

# whitespace errors (unstaged and staged), then lint; never `ruff format`, which would rewrite pinned files
check:
    git diff --check
    git diff --cached --check
    {{ruff}} check .

# git blob, LF and CRLF sha256 of the five identity-pinned files; exits 1 if any differs from HEAD
closure *args:
    uv run python scripts/pins.py closure {{args}}
