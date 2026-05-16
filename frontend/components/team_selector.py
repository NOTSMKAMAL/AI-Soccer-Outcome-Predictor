from typing import Any
import streamlit as st


def team_selector(
    label: str,
    teams: list[dict[str, Any]],
    key: str,
    exclude_id: int | None = None,
) -> dict[str, Any] | None:
    options = [t for t in teams if t["id"] != exclude_id]
    if not options:
        st.warning("No teams available.")
        return None

    display_names = [f"{t['name']} ({t['country']})" for t in options]
    selected_index = st.selectbox(label, range(len(options)), format_func=lambda i: display_names[i], key=key)
    return options[selected_index]
