"""Al-Mu'allim: Streamlit shell.

All the real work (live voice with Muallim, words that light up while you recite, the
teacher photos, the plan) lives in index.html, which is plain HTML and JavaScript. Streamlit
cannot do live audio or instant word lighting, because every interaction reloads the page,
so this file just serves index.html. It is deliberately tiny so it cannot crash or show a
blank screen the way the old 1,500-line version could.

Keep index.html in the same folder as this file.
"""
import pathlib

import streamlit as st

PAGES_URL = "https://abia2746.github.io/ReadandMemorisetheQuran/"  # your GitHub Pages address

st.set_page_config(layout="wide", page_title="Al-Mu'allim", page_icon="🕌",
                   initial_sidebar_state="collapsed")
st.markdown(
    "<style>header,footer,#MainMenu{visibility:hidden}"
    ".block-container{padding:0 0 0 0!important;max-width:100%!important}"
    "body,.stApp{background:#FAF6EC}</style>",
    unsafe_allow_html=True,
)

page = pathlib.Path(__file__).parent / "index.html"
if not page.is_file():
    st.error("index.html is missing from the repository. Upload it next to app.py and reload.")
    st.stop()

st.markdown(f"<p style='text-align:center;font-size:13px;margin:6px'>"
            f"For the best experience (microphone and live voice) "
            f"<a href='{PAGES_URL}' target='_blank'>open the full-screen version</a>.</p>",
            unsafe_allow_html=True)

shown = False
try:
    import streamlit.components.v1 as components
    components.html(page.read_text(encoding="utf-8"), height=1600, scrolling=True)
    shown = True
except Exception:
    pass

if not shown and hasattr(st, "iframe"):
    try:
        st.iframe(page, height=1600)
        shown = True
    except Exception:
        pass

if not shown:
    st.warning("This Streamlit version could not embed the page. Open the full-screen version "
               "using the link above.")
