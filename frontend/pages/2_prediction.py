import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
from frontend.api_client import get_prediction
from frontend.components.prediction_card import prediction_card
from frontend.components.comparison_chart import full_comparison_chart

st.set_page_config(page_title="Prediction", page_icon="⚽", layout="centered")

st.title("Match Prediction")

team_a = st.session_state.get("selected_team_a")
team_b = st.session_state.get("selected_team_b")

if team_a is None or team_b is None:
    st.warning("No teams selected. Please go to Team Select first.")
    if st.button("Go to Team Select"):
        st.switch_page("pages/1_team_select.py")
    st.stop()

st.markdown(f"**{team_a['name']}** vs **{team_b['name']}**")
st.markdown("---")

cache_key = f"pred_{team_a['id']}_{team_b['id']}"

if cache_key not in st.session_state:
    with st.spinner("Analysing match — this may take a few seconds..."):
        response = get_prediction(team_a["id"], team_b["id"])
        if response.get("status") == "success":
            st.session_state[cache_key] = response["data"]
        else:
            st.error("Prediction failed. Please try again.")
            st.stop()

pred_data = st.session_state[cache_key]

prediction_card(pred_data)

st.markdown("---")
st.markdown("### Statistical Breakdown")

comparison = pred_data.get("comparison", {})
if comparison:
    full_comparison_chart(comparison, team_a["name"], team_b["name"])
else:
    st.info("No comparison data available.")

st.markdown("---")

if st.button("Try Another Prediction", use_container_width=True):
    if cache_key in st.session_state:
        del st.session_state[cache_key]
    st.switch_page("pages/1_team_select.py")
