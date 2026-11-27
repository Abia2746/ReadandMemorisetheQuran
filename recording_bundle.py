"""Shared browser assets for the recorder and the main Mushaf."""
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
RECORDING_JS = "\n".join((_ROOT / name).read_text(encoding="utf-8") for name in (
    "recording_practice.mjs", "recording_tracker.mjs", "recording_audit.mjs", "mushaf_rules.mjs", "recording_lab.js"
))
RECORDING_CSS = (_ROOT / "recitation.css").read_text(encoding="utf-8")
