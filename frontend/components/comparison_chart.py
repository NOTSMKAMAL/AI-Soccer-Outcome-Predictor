from typing import Any
import plotly.graph_objects as go
import streamlit as st


def comparison_chart(comparison: dict[str, dict[str, float]], team_a_name: str, team_b_name: str) -> None:
    categories = {
        "attack": "Attack Strength",
        "defense": "Defensive Strength",
        "recent_form": "Recent Form",
    }

    for key, title in categories.items():
        if key not in comparison:
            continue

        data = comparison[key]
        keys = list(data.keys())
        values = list(data.values())

        colors = ["#4299e1", "#f6ad55"]
        max_val = 10.0 if key != "recent_form" else 5.0

        fig = go.Figure(
            data=[
                go.Bar(
                    name=keys[0].title(),
                    x=[keys[0].title()],
                    y=[values[0]],
                    marker_color=colors[0],
                    text=[f"{values[0]:.1f}"],
                    textposition="outside",
                    width=0.4,
                ),
                go.Bar(
                    name=keys[1].title() if len(keys) > 1 else "",
                    x=[keys[1].title()] if len(keys) > 1 else [""],
                    y=[values[1]] if len(values) > 1 else [0],
                    marker_color=colors[1],
                    text=[f"{values[1]:.1f}"] if len(values) > 1 else [""],
                    textposition="outside",
                    width=0.4,
                ),
            ]
        )

        fig.update_layout(
            title=dict(text=title, font=dict(size=16)),
            yaxis=dict(range=[0, max_val * 1.2], showgrid=True, gridcolor="#2d3748"),
            xaxis=dict(showticklabels=True),
            plot_bgcolor="#1a1a2e",
            paper_bgcolor="#0d1117",
            font=dict(color="#e2e8f0"),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=60, b=20, l=20, r=20),
            height=280,
            bargap=0.3,
        )

        st.plotly_chart(fig, use_container_width=True)


def full_comparison_chart(comparison: dict[str, dict[str, float]], team_a_name: str, team_b_name: str) -> None:
    categories = ["Attack", "Defense", "Recent Form"]
    keys = ["attack", "defense", "recent_form"]

    team_keys = list(next(iter(comparison.values())).keys()) if comparison else []
    if len(team_keys) < 2:
        return

    name_a = team_keys[0].title()
    name_b = team_keys[1].title()

    normalised_a = []
    normalised_b = []
    for k in keys:
        if k not in comparison:
            normalised_a.append(0)
            normalised_b.append(0)
            continue
        max_val = 5.0 if k == "recent_form" else 10.0
        vals = list(comparison[k].values())
        normalised_a.append(round(vals[0] / max_val * 10, 2) if vals else 0)
        normalised_b.append(round(vals[1] / max_val * 10 if len(vals) > 1 else 0, 2))

    fig = go.Figure()
    fig.add_trace(go.Bar(name=name_a, x=categories, y=normalised_a, marker_color="#4299e1", text=[f"{v:.1f}" for v in normalised_a], textposition="outside"))
    fig.add_trace(go.Bar(name=name_b, x=categories, y=normalised_b, marker_color="#f6ad55", text=[f"{v:.1f}" for v in normalised_b], textposition="outside"))

    fig.update_layout(
        title=dict(text="Team Comparison (normalised 0–10)", font=dict(size=18)),
        barmode="group",
        yaxis=dict(range=[0, 12], showgrid=True, gridcolor="#2d3748", title="Score (0–10)"),
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#0d1117",
        font=dict(color="#e2e8f0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=70, b=20, l=40, r=20),
        height=380,
    )

    st.plotly_chart(fig, use_container_width=True)
