import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
from frontend.api_client import get_teams
from frontend.components.team_selector import team_selector

st.set_page_config(page_title="Team Select", page_icon="⚽", layout="centered")

st.title("Select Teams")
st.markdown("Choose the two national teams you want to compare.")

if "teams" not in st.session_state:
    with st.spinner("Loading teams..."):
        st.session_state["teams"] = get_teams()

teams = st.session_state["teams"]

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Team A")
    team_a = team_selector("Select Team A", teams, key="team_a_select")

with col2:
    st.subheader("Team B")
    exclude_id = team_a["id"] if team_a else None
    team_b = team_selector("Select Team B", teams, key="team_b_select", exclude_id=exclude_id)

st.markdown("---")

if st.button("Predict Match Outcome", type="primary", use_container_width=True):
    if team_a is None or team_b is None:
        st.error("Please select both teams before predicting.")
    elif team_a["id"] == team_b["id"]:
        st.error("Please select two different teams.")
    else:
        st.session_state["selected_team_a"] = team_a
        st.session_state["selected_team_b"] = team_b
        st.session_state["prediction_ready"] = False
        st.switch_page("pages/2_prediction.py")
