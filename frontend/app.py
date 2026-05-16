import streamlit as st

st.set_page_config(
    page_title="AI Sports Outcome Predictor",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.title("AI Sports Outcome Predictor")
st.markdown(
    """
    Welcome to the **AI Sports Outcome Predictor** — a tool that uses statistical analysis
    and an AI agent powered by Google Gemini to forecast international soccer match results.
    """
)

st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 1. Select Teams")
    st.markdown("Choose two national teams from our database of international squads.")

with col2:
    st.markdown("### 2. Run Prediction")
    st.markdown("Our AI agent analyses attack, defence, and recent form statistics.")

with col3:
    st.markdown("### 3. View Results")
    st.markdown("See the predicted winner, confidence score, and a full stat breakdown.")

st.markdown("---")
st.markdown("**Get started:** open **Team Select** in the sidebar.")

st.caption(
    "Predictions are probabilistic estimates based on historical statistics and are not guarantees of match outcomes."
)
