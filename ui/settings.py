import streamlit as st
from db.logger import clear_all_logs, query_submissions

CATEGORIES = ["PII", "FINANCIAL", "CREDENTIAL", "BUSINESS", "SECRETS_IN_FORMAT"]


def render(business_terms: list[str]):
    st.header("Settings")

    st.subheader("Pattern Category Toggles")
    st.caption("Disable categories to exclude them from classification.")
    disabled = st.session_state.get("disabled_categories", set())

    for cat in CATEGORIES:
        enabled = cat not in disabled
        toggled = st.toggle(cat, value=enabled, key=f"cat_toggle_{cat}")
        if toggled and cat in disabled:
            disabled.discard(cat)
        elif not toggled and cat not in disabled:
            disabled.add(cat)

    st.session_state["disabled_categories"] = disabled

    st.divider()
    st.subheader("Business Terms")
    st.caption("These terms trigger HIGH-tier classification. Changes are session-only and reset on refresh.")

    session_terms = st.session_state.get("extra_business_terms", [])
    all_terms = business_terms + session_terms

    for term in all_terms:
        source = "(session)" if term in session_terms else "(config)"
        st.checkbox(f"{term} {source}", value=True, key=f"term_{term}", disabled=True)

    new_term = st.text_input("Add term (this session only)", key=f"new_term_{len(session_terms)}")
    if st.button("Add term"):
        if new_term.strip() and new_term not in all_terms:
            session_terms.append(new_term.strip())
            st.session_state["extra_business_terms"] = session_terms
            st.success(f"Added '{new_term}' for this session.")
            st.rerun()
        elif new_term in all_terms:
            st.warning("Term already in list.")

    st.divider()
    st.subheader("Danger Zone")
    st.caption("This clears all logs from the SQLite database. For development use only.")

    if "confirm_clear" not in st.session_state:
        st.session_state["confirm_clear"] = False

    if not st.session_state["confirm_clear"]:
        if st.button("Clear logs (dev only)", type="secondary"):
            st.session_state["confirm_clear"] = True
            st.rerun()
    else:
        n = len(query_submissions())
        st.warning(f"This will delete {n} submission(s) and all associated pattern hits. This cannot be undone.")
        col1, col2 = st.columns(2)
        if col1.button("Yes, clear all logs", type="primary"):
            clear_all_logs()
            st.session_state["confirm_clear"] = False
            st.success("All logs cleared.")
            st.rerun()
        if col2.button("Cancel"):
            st.session_state["confirm_clear"] = False
            st.rerun()
