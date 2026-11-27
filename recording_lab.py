"""Browser-only timing practice for the Streamlit recording workspace."""
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parent
_lab = st.components.v2.component(
    "al_muallim_recording_timing",
    html='<section class="timing-lab"></section>',
    css="""
    .timing-lab {padding:1rem;border:1px solid #8e805e;border-radius:1rem}
    .timing-lab button,.timing-lab select {font:inherit;padding:.5rem;margin:.25rem;border-radius:.5rem}
    .timing-lab progress,.timing-lab audio {display:block;width:min(100%,32rem);margin:.7rem 0}
    .timing-lab [hidden] {display:none}
    """,
    js=(_ROOT / "recording_audit.mjs").read_text(encoding="utf-8")
    + "\n" + (_ROOT / "recording_lab.js").read_text(encoding="utf-8"),
)


def recording_lab(surah, ayah, end):
    _lab(key=f"timing_{surah}_{ayah}_{end}", data={"surah":surah, "first":ayah, "end":end})
