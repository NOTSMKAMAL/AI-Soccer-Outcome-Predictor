from typing import Any
import streamlit as st


def prediction_card(prediction_data: dict[str, Any]) -> None:
    winner = prediction_data.get("winner", "Unknown")
    confidence = prediction_data.get("confidence", 0)
    reasoning = prediction_data.get("reasoning", "")
    teams = prediction_data.get("teams", {})
    team_a_name = teams.get("team_a", {}).get("name", "Team A")
    team_b_name = teams.get("team_b", {}).get("name", "Team B")

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 1.5rem; border-radius: 12px;
                        background: linear-gradient(135deg, #1a1a2e, #16213e);
                        border: 2px solid #0f3460; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                <p style="color: #a0aec0; font-size: 0.9rem; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 1px;">
                    Predicted Winner
                </p>
                <h1 style="color: #f6e05e; font-size: 2.5rem; margin: 0.25rem 0;">
                    {winner}
                </h1>
                <p style="color: #a0aec0; font-size: 0.85rem; margin-top: 0.25rem;">
                    {team_a_name} vs {team_b_name}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")

    conf_color = "#48bb78" if confidence >= 70 else "#ed8936" if confidence >= 55 else "#fc8181"
    st.markdown(
        f"""
        <div style="text-align: center; margin: 1rem 0;">
            <p style="color: #a0aec0; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;">
                Confidence
            </p>
            <h2 style="color: {conf_color}; font-size: 3rem; margin: 0;">{confidence}%</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.progress(confidence / 100)

    st.markdown("### AI Analysis")
    st.info(reasoning)
