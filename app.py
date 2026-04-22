import streamlit as st
from db.logger import init_db
from classifier.patterns import PatternRegistry, load_business_terms
from demo.seed import seed_if_empty

st.set_page_config(
    page_title="AI Prompt DLP Analyzer",
    page_icon="shield",
    layout="wide",
)

# Session state init
if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "disabled_categories" not in st.session_state:
    st.session_state["disabled_categories"] = set()
if "extra_business_terms" not in st.session_state:
    st.session_state["extra_business_terms"] = []
if "confirm_clear" not in st.session_state:
    st.session_state["confirm_clear"] = False

init_db()
seed_if_empty()

extra_terms = st.session_state["extra_business_terms"]
registry = PatternRegistry(extra_terms=extra_terms)
base_terms = load_business_terms()
disabled_categories = st.session_state["disabled_categories"]

api_key = st.secrets.get("ANTHROPIC_API_KEY")
demo_mode = not bool(api_key)

# Sidebar
with st.sidebar:
    st.title("AI Prompt DLP")

    if demo_mode:
        st.info("Demo mode - pre-loaded with 50 sample queries. Configure ANTHROPIC_API_KEY to enable live Claude responses.")
    else:
        st.success("API key configured")

    page = st.radio(
        "Navigate",
        ["Analyzer", "Dashboard", "Settings"],
        label_visibility="collapsed",
    )

from ui import analyzer, dashboard, settings

if page == "Analyzer":
    analyzer.render(registry, disabled_categories, demo_mode=demo_mode)
elif page == "Dashboard":
    dashboard.render()
elif page == "Settings":
    settings.render(base_terms)
