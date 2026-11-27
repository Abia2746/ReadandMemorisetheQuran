"""Browser-only timing practice for the Streamlit recording workspace."""
from pathlib import Path
from hashlib import sha256
from hifdh_planner import AYAHS

from recording_bundle import RECORDING_CSS, RECORDING_JS
import streamlit as st

_COUNTS_CSV = ",".join(map(str, AYAHS[1:]))
_ROOT = Path(__file__).resolve().parent
_lab = st.components.v2.component(
    "al_muallim_recording_timing",
    html='<section class="timing-lab"></section>',
    css=RECORDING_CSS,
    js=RECORDING_JS + "\nexport default c=>mountRecitation(c.parentElement.querySelector('.timing-lab'),c.data)",
)


def recording_lab(surah, ayah, end):
    user = st.session_state.get("am_auth") or {}
    profile = sha256(str(user["user_id"]).encode()).hexdigest() if user.get("user_id") else "browser-guest"
    _lab(key=f"timing_{surah}_{ayah}_{end}", data={"surah":surah, "first":ayah, "end":end, "profile":profile, "countsCsv":_COUNTS_CSV})
