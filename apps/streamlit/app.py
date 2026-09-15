"""Minimal HaraLens shell. No analytics or infrastructure calls in the UI."""

import streamlit as st

from haralens import __version__


def home() -> None:
    st.title("HaraLens")
    st.subheader("Understand your data before trusting the decisions built from it.")
    st.info("Phase 0: product and architecture foundation.")
    st.write("Dataset ingestion, profiling, quality checks, and analytics are planned.")
    st.caption(f"Version {__version__}")


st.set_page_config(page_title="HaraLens", layout="wide")
st.navigation([st.Page(home, title="Home", default=True)]).run()
