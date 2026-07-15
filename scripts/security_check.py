from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".py", ".js", ".html", ".css", ".md", ".txt", ".toml", ".yaml", ".yml", ".json"}


def tracked_files() -> list[Path]:
    try:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        return [ROOT / part.decode() for part in output.split(b"\0") if part]
    except Exception:
        return [path for path in ROOT.rglob("*") if path.is_file() and not SKIP_PARTS.intersection(path.parts)]


errors: list[str] = []
files = tracked_files()
for path in files:
    relative = path.relative_to(ROOT).as_posix()
    if path.suffix.lower() in {".zip", ".7z", ".rar"}:
        errors.append(f"Archive source is not allowed: {relative}")
        continue
    if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 1_000_000:
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if re.search(r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{20,}", text):
        errors.append(f"Possible hard-coded credential: {relative}")

for relative in ["web/index.html", "web/share.html", "web/viewer.html"]:
    text = (ROOT / relative).read_text(encoding="utf-8")
    if re.search(r"<(script|link)[^>]+(?:src|href)=[\"']https?://", text, re.I):
        errors.append(f"Remote executable/style asset in {relative}")

app_source = (ROOT / "app.py").read_text(encoding="utf-8")
for forbidden in ["/location/latest", "X-Consent", "X-Invite-Token"]:
    if forbidden in app_source:
        errors.append(f"Legacy insecure API contract remains: {forbidden}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)
print(f"Security source check passed ({len(files)} files inspected).")
