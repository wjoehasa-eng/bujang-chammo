#!/usr/bin/env python3
"""부장 참모 PWA 빌드 — src 조각을 하나의 index.html로 합칩니다."""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"

css = (SRC / "style.css").read_text(encoding="utf-8")
js = "\n".join([
    (SRC / "data-playbooks.js").read_text(encoding="utf-8"),
    (SRC / "data-core.js").read_text(encoding="utf-8"),
    (SRC / "app.js").read_text(encoding="utf-8"),
])
shell = (SRC / "shell.html").read_text(encoding="utf-8")

out = shell.replace("/*__CSS__*/", css).replace("/*__JS__*/", js)
assert "__CSS__" not in out and "__JS__" not in out

target = ROOT / "index.html"
target.write_text(out, encoding="utf-8")
pathlib.Path("/workspace/bujang_chammo.html").write_text(out, encoding="utf-8")

print("built", target, len(out), "chars")
print("standalone /workspace/bujang_chammo.html")
