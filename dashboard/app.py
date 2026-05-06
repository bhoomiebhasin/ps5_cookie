"""
OWNER: Track C (Dashboard)

Streamlit app. Run with:
    streamlit run dashboard/app.py

Tiebreaker-grade panels to build (in priority order):
    1. Data Quality Report - what was dropped/clamped/deduped (from quality_report)
    2. Trust Matrix Heatmap - reps x reps, asymmetric cells highlighted
    3. Alliance Graph - networkx + plotly, faction-colored nodes
    4. Proposal Viability Bars - priority vs controversy vs viability
    5. Decision Trace Table - per-rep status + reasons
    6. Threshold Sliders - rerun pipeline live (the killer panel)
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.consensus import run_consensus
from src.loader import load_clean


def main() -> None:
    st.set_page_config(page_title="Phantom Consensus", layout="wide")
    st.title("Phantom Consensus - Strategic Consensus Engine")

    data = load_clean()
    st.sidebar.header("Data Summary")
    st.sidebar.metric("Reps loaded", len(data.reps))
    st.sidebar.metric("Proposals loaded", len(data.proposals))
    st.sidebar.metric("Objections loaded", len(data.objections))
    st.sidebar.metric("Edges loaded", len(data.edges))

    try:
        result = run_consensus(data)
        st.success("Consensus pipeline ran successfully.")
        st.subheader("Final Agreement")
        st.json(result.final_agreement)
        st.subheader("Alliances")
        st.json(result.alliances)
        st.subheader("Decision Trace (raw)")
        st.json(result.trace.summary)
    except NotImplementedError as e:
        st.warning(f"Strategy pipeline still stubbed: {e}")
        st.info("Track B is filling in src/features.py, src/graph.py, "
                "src/strategy.py. Dashboard panels will populate once "
                "those land.")

    st.subheader("Data Quality Report")
    qr = data.quality_report
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rejected reps", len(qr.rejected_reps))
    col2.metric("Rejected proposals", len(qr.rejected_proposals))
    col3.metric("Rejected objections", len(qr.rejected_objections))
    col4.metric("Deduped", len(qr.deduped))


if __name__ == "__main__":
    main()
