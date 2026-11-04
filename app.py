import streamlit as st
import streamlit.components.v1 as components

# Set page to wide mode to better accommodate notebook content
st.set_page_config(layout="wide", page_title="Read and Memorise the Quran")

# Load and render the static notebook.html file
try:
    with open("notebook.html", "r", encoding="utf-8") as f:
        html_data = f.read()
    
    # Adjust height (in pixels) depending on how long your notebook page is
    components.html(html_data, height=1200, scrolling=True)

except FileNotFoundError:
    st.error("Error: 'notebook.html' file could not be found in the repository root.")
