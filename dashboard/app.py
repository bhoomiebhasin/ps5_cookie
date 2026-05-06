"""
Phantom Consensus dashboard.

Run from repo root:
    streamlit run dashboard/app.py

Six panels, in priority order (each one is a tiebreaker against teams
that ship a thinner dashboard):

  1. Final Agreement + Alliances        - the headline output
  2. Decision Trace tables              - per-rep and per-proposal reasoning
  3. Alliance Graph                     - networkx + plotly, faction-colored
  4. Trust Matrix Heatmap               - reps x reps, asymmetry visible
  5. Proposal Viability Bars            - priority vs controversy vs viability
  6. Data Quality Report                - what was dropped, deduped, clamped
  7. Threshold Sliders (sidebar)        - rerun pipeline live with new values
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import thresholds as default_thresholds
from src.consensus import run_consensus
from src.features import relationship_score
from src.loader import load_clean

st.set_page_config(page_title="Phantom Consensus", layout="wide")


# ---------------------------------------------------------------------------
# Sidebar - threshold sliders (Differentiator: live sensitivity)
# ---------------------------------------------------------------------------

st.sidebar.title("Phantom Consensus")
st.sidebar.markdown("**Strategic Consensus Engine**")
st.sidebar.divider()
st.sidebar.subheader("Thresholds (live)")
st.sidebar.caption(
    "Move a slider to recompute the entire pipeline. This is how we explore "
    "sensitivity - it shows the engine's decisions are not magic numbers."
)

slider_cfg = [
    ("TAU_BETRAY",    "Trojan cutoff",       0.0, 1.0, default_thresholds.TAU_BETRAY,    0.05),
    ("TAU_ALLIANCE",  "Alliance reciprocity",0.0, 1.0, default_thresholds.TAU_ALLIANCE,  0.05),
    ("TAU_RIVALRY",   "Rivalry max",         0.0, 100.0, default_thresholds.TAU_RIVALRY, 5.0),
    ("TAU_LOYALTY",   "Faction loyalty min", 0.0, 1.0, default_thresholds.TAU_LOYALTY,   0.05),
    ("TAU_CASCADE",   "Cascade max",         0.0, 1.0, default_thresholds.TAU_CASCADE,   0.05),
    ("TAU_VIABILITY", "Viability min",       0.0, 10.0, default_thresholds.TAU_VIABILITY, 0.5),
    ("TAU_OBJ_BLOCK", "Severe objection",    0.0, 10.0, default_thresholds.TAU_OBJ_BLOCK, 0.5),
    ("TAU_BUDGET",    "Objection budget",    0.0, 100.0, default_thresholds.TAU_BUDGET,  5.0),
]
overrides: dict[str, float] = {}
for name, label, lo, hi, value, step in slider_cfg:
    overrides[name] = st.sidebar.slider(label, lo, hi, float(value), step=step)

# Push slider values back into the thresholds module so the pipeline picks
# them up. This is a deliberate runtime patch - simple and effective.
for name, value in overrides.items():
    setattr(default_thresholds, name, value)


# ---------------------------------------------------------------------------
# Run pipeline
# ---------------------------------------------------------------------------

data = load_clean()
result = run_consensus(data)

st.title("Phantom Consensus - Strategic Consensus Engine")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Reps loaded",      len(data.reps))
c2.metric("Reps accepted",    result.trace.summary.get("accepted_reps", 0))
c3.metric("Proposals chosen", result.trace.summary.get("selected_proposals", 0))
c4.metric("Alliances",        result.trace.summary.get("alliances", 0))

st.divider()


# ---------------------------------------------------------------------------
# Panel 1 - Final Agreement
# ---------------------------------------------------------------------------

st.header("Final Agreement")
ag_left, ag_right = st.columns([1, 1])
with ag_left:
    st.subheader("Selected Proposals")
    if not result.final_agreement["proposals"]:
        st.warning("No proposals selected.")
    else:
        prop_by_id = {p.id: p for p in data.proposals}
        prop_meta = []
        for pid in result.final_agreement["proposals"]:
            p = prop_by_id.get(pid)
            if p is None:
                continue
            tr = next(
                (t for t in result.trace.proposals if t.proposal_id == pid),
                None,
            )
            prop_meta.append({
                "id": p.id,
                "title": p.title,
                "sponsor": p.sponsor,
                "priority": p.priority,
                "adj_viability": tr.metrics.get("adj_viability", 0) if tr else 0,
            })
        st.dataframe(pd.DataFrame(prop_meta), use_container_width=True, hide_index=True)

with ag_right:
    st.subheader("Supporting Reps")
    rep_by_id = {r.id: r for r in data.reps}
    sup_meta = []
    for rid in result.final_agreement["supporting_reps"]:
        r = rep_by_id.get(rid)
        if r is None:
            continue
        tr = next((t for t in result.trace.reps if t.rep_id == rid), None)
        sup_meta.append({
            "id": r.id,
            "name": r.name,
            "faction": r.faction,
            "influence": r.influence,
            "supporter_score": tr.metrics.get("supporter_score", 0) if tr else 0,
        })
    if sup_meta:
        st.dataframe(pd.DataFrame(sup_meta), use_container_width=True, hide_index=True)
    else:
        st.warning("No supporters identified.")

st.subheader("Detected Alliances")
if not result.alliances:
    st.info("No alliances satisfy bidirectional reciprocity + low rivalry.")
else:
    alliance_rows = []
    for pair in result.alliances:
        a, b = pair[0], pair[1]
        ra, rb = rep_by_id.get(a), rep_by_id.get(b)
        if not ra or not rb:
            continue
        alliance_rows.append({
            "rep_1": a, "rep_1_faction": ra.faction,
            "rep_2": b, "rep_2_faction": rb.faction,
        })
    st.dataframe(pd.DataFrame(alliance_rows), use_container_width=True, hide_index=True)

st.divider()


# ---------------------------------------------------------------------------
# Panel 2 - Decision Trace tables
# ---------------------------------------------------------------------------

st.header("Decision Trace")
trace_left, trace_right = st.columns([1, 1])

with trace_left:
    st.subheader("Reps")
    rep_rows = []
    for t in result.trace.reps:
        rep_rows.append({
            "id": t.rep_id,
            "status": t.status,
            "influence":          t.metrics.get("influence"),
            "betrayal_risk":      t.metrics.get("personal_betrayal_risk"),
            "faction_loyalty":    t.metrics.get("faction_loyalty"),
            "cascade_risk":       t.metrics.get("cascade_risk"),
            "supporter_score":    t.metrics.get("supporter_score"),
            "rejection":          "; ".join(t.rejections) if t.rejections else "",
        })
    df_reps = pd.DataFrame(rep_rows)

    def color_status(val):
        return {
            "supporter":     "background-color: #c8e6c9",
            "alliance_only": "background-color: #fff9c4",
            "rejected":      "background-color: #ffcdd2",
        }.get(val, "")

    st.dataframe(
        df_reps.style.map(color_status, subset=["status"])
        .format(precision=3, na_rep="-"),
        use_container_width=True,
        hide_index=True,
    )

with trace_right:
    st.subheader("Proposals")
    prop_rows = []
    for t in result.trace.proposals:
        prop_rows.append({
            "id": t.proposal_id,
            "status": t.status,
            "priority":          t.metrics.get("priority"),
            "objection_weight":  t.metrics.get("objection_weight"),
            "controversy":       t.metrics.get("controversy"),
            "coalition_amp":     t.metrics.get("coalition_amp"),
            "adj_viability":     t.metrics.get("adj_viability"),
            "rejection":         t.rejection_reason or "",
        })
    df_props = pd.DataFrame(prop_rows)

    def color_pstatus(val):
        return {
            "selected": "background-color: #c8e6c9",
            "rejected": "background-color: #ffcdd2",
        }.get(val, "")

    st.dataframe(
        df_props.style.map(color_pstatus, subset=["status"])
        .format(precision=3, na_rep="-"),
        use_container_width=True,
        hide_index=True,
    )

st.divider()


# ---------------------------------------------------------------------------
# Panel 3 - Alliance Graph (networkx + plotly)
# ---------------------------------------------------------------------------

st.header("Alliance Graph")
st.caption(
    "Nodes coloured by faction. Solid green edges are mutual alliances; "
    "dashed grey edges are asymmetric (one-direction trust > threshold but "
    "not the other - False-Friend candidates that we correctly do not pair)."
)

try:
    import networkx as nx

    G = nx.DiGraph()
    for r in data.reps:
        G.add_node(r.id, faction=r.faction, influence=r.influence, name=r.name)
    for e in data.edges:
        G.add_edge(e.from_id, e.to_id,
                   score=relationship_score(e.trust, e.betrayal_prob),
                   trust=e.trust, betrayal=e.betrayal_prob)

    pos = nx.spring_layout(G, seed=42, k=1.6, iterations=100)

    factions = list({r.faction for r in data.reps})
    palette = ["#1976d2", "#388e3c", "#d32f2f", "#7b1fa2", "#f57c00", "#5d4037"]
    faction_color = {f: palette[i % len(palette)] for i, f in enumerate(factions)}

    alliance_set = {tuple(sorted(p)) for p in result.alliances}

    edge_x_alliance, edge_y_alliance = [], []
    edge_x_other,    edge_y_other    = [], []
    for u, v, attrs in G.edges(data=True):
        x0, y0 = pos[u]; x1, y1 = pos[v]
        pair = tuple(sorted([u, v]))
        if pair in alliance_set:
            edge_x_alliance += [x0, x1, None]
            edge_y_alliance += [y0, y1, None]
        else:
            edge_x_other += [x0, x1, None]
            edge_y_other += [y0, y1, None]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x_other, y=edge_y_other, mode="lines",
        line=dict(width=0.7, color="rgba(160,160,160,0.5)"),
        hoverinfo="none", name="trust edge",
    ))
    fig.add_trace(go.Scatter(
        x=edge_x_alliance, y=edge_y_alliance, mode="lines",
        line=dict(width=3.0, color="#2e7d32"),
        hoverinfo="none", name="alliance",
    ))

    for f in factions:
        nodes = [n for n, d in G.nodes(data=True) if d.get("faction") == f]
        fig.add_trace(go.Scatter(
            x=[pos[n][0] for n in nodes],
            y=[pos[n][1] for n in nodes],
            mode="markers+text",
            marker=dict(
                size=[12 + (G.nodes[n]["influence"] / 6) for n in nodes],
                color=faction_color[f],
                line=dict(width=1.5, color="white"),
            ),
            text=nodes, textposition="top center", textfont=dict(size=11),
            name=f,
            hovertext=[
                f"{n}<br>{G.nodes[n]['name']}<br>"
                f"faction={f}<br>influence={G.nodes[n]['influence']:.0f}"
                for n in nodes
            ],
            hoverinfo="text",
        ))

    fig.update_layout(
        showlegend=True, height=480,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
except ImportError:
    st.info("Install `networkx` to render this panel: `pip install networkx`.")

st.divider()


# ---------------------------------------------------------------------------
# Panel 4 - Trust Matrix Heatmap
# ---------------------------------------------------------------------------

st.header("Trust Matrix")
st.caption(
    "relationship_score = (trust/100) * (1 - betrayal_prob). "
    "Asymmetry along the diagonal reflects directed trust differences "
    "(a False-Friend signature)."
)

rep_ids = sorted(r.id for r in data.reps)
matrix = [[None] * len(rep_ids) for _ in rep_ids]
for e in data.edges:
    if e.from_id in rep_ids and e.to_id in rep_ids:
        i = rep_ids.index(e.from_id)
        j = rep_ids.index(e.to_id)
        matrix[i][j] = round(relationship_score(e.trust, e.betrayal_prob), 3)

fig_heat = go.Figure(go.Heatmap(
    z=matrix,
    x=rep_ids, y=rep_ids,
    colorscale="RdYlGn", zmin=0, zmax=1,
    text=matrix, texttemplate="%{text}",
    hovertemplate="from %{y} -> %{x}<br>score=%{z}<extra></extra>",
))
fig_heat.update_layout(
    height=max(380, 24 * len(rep_ids)),
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(title="to"), yaxis=dict(title="from", autorange="reversed"),
)
st.plotly_chart(fig_heat, use_container_width=True)

st.divider()


# ---------------------------------------------------------------------------
# Panel 5 - Proposal Viability Bars
# ---------------------------------------------------------------------------

st.header("Proposal Viability")
st.caption(
    "viability = priority * (1 - controversy), then boosted by sponsor "
    "credibility and amplified by coalition concentration."
)

if result.trace.proposals:
    df_v = pd.DataFrame([
        {
            "id": t.proposal_id,
            "priority":         t.metrics.get("priority", 0),
            "controversy":      t.metrics.get("controversy", 0),
            "adj_controversy":  t.metrics.get("adj_controversy", 0),
            "viability":        t.metrics.get("viability", 0),
            "adj_viability":    t.metrics.get("adj_viability", 0),
            "status":           t.status,
        }
        for t in result.trace.proposals
    ])
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        name="priority", x=df_v["id"], y=df_v["priority"],
        marker_color="#90caf9",
    ))
    fig_bar.add_trace(go.Bar(
        name="adj_viability", x=df_v["id"], y=df_v["adj_viability"],
        marker_color=[
            "#388e3c" if s == "selected" else "#ef5350"
            for s in df_v["status"]
        ],
    ))
    fig_bar.add_hline(
        y=default_thresholds.TAU_VIABILITY, line_dash="dot",
        annotation_text=f"TAU_VIABILITY={default_thresholds.TAU_VIABILITY}",
    )
    fig_bar.update_layout(
        barmode="group", height=380,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("No proposal traces.")

st.divider()


# ---------------------------------------------------------------------------
# Panel 6 - Data Quality Report
# ---------------------------------------------------------------------------

st.header("Data Quality Report")
st.caption("Every record we dropped, deduped, or clamped, with the reason.")

qr = data.quality_report
qcols = st.columns(4)
qcols[0].metric("Rejected reps",       len(qr.rejected_reps))
qcols[1].metric("Rejected proposals",  len(qr.rejected_proposals))
qcols[2].metric("Rejected objections", len(qr.rejected_objections))
qcols[3].metric("Rejected edges",      len(qr.rejected_edges))

qcols2 = st.columns(2)
qcols2[0].metric("Deduped",     len(qr.deduped))
qcols2[1].metric("Clamped",     len(qr.clamped_values))

quality_tabs = st.tabs([
    "Reps", "Proposals", "Objections", "Edges", "Deduped", "Clamped"
])
with quality_tabs[0]:
    st.dataframe(pd.DataFrame(qr.rejected_reps, columns=["id", "reason"]),
                 use_container_width=True, hide_index=True)
with quality_tabs[1]:
    st.dataframe(pd.DataFrame(qr.rejected_proposals, columns=["id", "reason"]),
                 use_container_width=True, hide_index=True)
with quality_tabs[2]:
    st.dataframe(pd.DataFrame(qr.rejected_objections, columns=["pair", "reason"]),
                 use_container_width=True, hide_index=True)
with quality_tabs[3]:
    st.dataframe(pd.DataFrame(qr.rejected_edges, columns=["pair", "reason"]),
                 use_container_width=True, hide_index=True)
with quality_tabs[4]:
    st.dataframe(pd.DataFrame(qr.deduped, columns=["id", "action"]),
                 use_container_width=True, hide_index=True)
with quality_tabs[5]:
    st.dataframe(pd.DataFrame(qr.clamped_values, columns=["id", "field", "action"]),
                 use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Phantom Consensus | five S-tier differentiators: trust-weighted betrayal, "
    "coalition-aware controversy, sponsor credibility, stability-aware Pareto "
    "selection, multiplicative supporter scoring."
)
