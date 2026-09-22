"""Pin this lane only after verifying the frozen measurements still describe it."""
import ast
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = json.loads((OUT / "summary.json").read_text())
    assert digest(ROOT / "perception/hud.py") == report["after_hud_sha256"]
    assert digest(OUT / "baseline_hud.py") == report["before_hud_sha256"]
    trees = []
    for path in (OUT / "baseline_hud.py", ROOT / "perception/hud.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        tree.body = [node for node in tree.body if not (
            isinstance(node, ast.FunctionDef) and node.name == "_countdown_char")]
        trees.append(ast.dump(tree, include_attributes=False))
    assert trees[0] == trees[1], "only the owned function may change"
    paths = [ROOT / "perception/hud.py", ROOT / "tests/test_hud_countdown_performance.py",
             ROOT / "docs/lanes/range-hud-countdown-performance.md"]
    paths += [p for p in OUT.iterdir() if p.is_file() and p.name != "freeze-sha256.json"]
    pins = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in sorted(paths)}
    with (OUT / "freeze-sha256.json").open("x") as out:
        json.dump(pins, out, indent=2)
    print(json.dumps({"files": len(pins), "manifest_sha256": digest(OUT / "freeze-sha256.json")}))


if __name__ == "__main__":
    main()
