import streamlit as st
import pandas as pd
from db.logger import query_submissions, query_pattern_hits

WINDOW_OPTIONS = {
    "All time": None,
    "Last 7 days": 7,
    "Last 30 days": 30,
    "Last 90 days": 90,
}

PAGE_SIZE = 25


def render():
    st.header("Dashboard")

    window_label = st.selectbox("Time window", list(WINDOW_OPTIONS.keys()), index=2)
    window_days = WINDOW_OPTIONS[window_label]

    submissions = query_submissions(window_days)
    hits = query_pattern_hits(window_days)

    if not submissions:
        st.info("No submissions yet. Analyze a prompt to get started.")
        return

    df = pd.DataFrame(submissions)
    hits_df = pd.DataFrame(hits) if hits else pd.DataFrame(columns=["pattern_name", "category", "tier"])

    # KPIs
    total = len(df)
    blocked_count = (df["risk_tier"] == "BLOCKED").sum()
    passed_pct = df["passed_to_llm"].mean() * 100 if total > 0 else 0

    most_triggered = "none"
    if not hits_df.empty:
        vc = hits_df["pattern_name"].value_counts()
        most_triggered = f"{vc.idxmax()} ({vc.max()}x)"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Submissions", total)
    col2.metric("BLOCKED", blocked_count)
    col3.metric("% Passed to LLM", f"{passed_pct:.1f}%")
    col4.metric("Top Pattern", most_triggered)

    st.divider()

    # Risk tier distribution
    st.subheader("Risk Tier Distribution")
    tier_counts = df["risk_tier"].value_counts().reset_index()
    tier_counts.columns = ["Tier", "Count"]
    tier_counts = tier_counts.set_index("Tier")
    st.bar_chart(tier_counts)

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Top 10 Patterns")
        if not hits_df.empty:
            top10 = hits_df["pattern_name"].value_counts().head(10).reset_index()
            top10.columns = ["Pattern", "Hits"]
            top10 = top10.set_index("Pattern")
            st.bar_chart(top10)
        else:
            st.info("No pattern hits yet.")

    with col_b:
        st.subheader("Submissions Over Time")
        df["date"] = pd.to_datetime(df["timestamp"], utc=True).dt.date
        time_series = df.groupby("date").size().reset_index(name="Count")
        time_series = time_series.set_index("date")
        st.line_chart(time_series)

    st.divider()
    st.subheader("Recent Submissions")

    prev_filter = st.session_state.get("tier_filter_prev", None)
    tier_filter = st.multiselect(
        "Filter by tier",
        ["LOW", "MEDIUM", "HIGH", "BLOCKED"],
        default=["LOW", "MEDIUM", "HIGH", "BLOCKED"],
        key="tier_filter",
    )
    if tier_filter != prev_filter:
        st.session_state.tier_filter_prev = tier_filter
        st.session_state.dash_page = 0

    display_cols = ["timestamp", "risk_tier", "redacted_preview", "passed_to_llm"]
    if "is_seed" in df.columns:
        display_cols.append("is_seed")
    display_df = df[display_cols].copy()

    if "is_seed" in display_df.columns:
        display_df["risk_tier"] = display_df.apply(
            lambda r: f"SEED | {r['risk_tier']}" if r.get("is_seed") == 1 else r["risk_tier"],
            axis=1,
        )
        display_df = display_df.drop(columns=["is_seed"])

    display_df = display_df[df["risk_tier"].isin(tier_filter)]
    display_df.columns = ["Timestamp", "Tier", "Redacted Preview", "Sent to LLM"]
    display_df["Sent to LLM"] = display_df["Sent to LLM"].map({0: "No", 1: "Yes"})
    display_df["Redacted Preview"] = display_df["Redacted Preview"].str[:80] + "..."

    total_rows = len(display_df)
    total_pages = max(1, (total_rows + PAGE_SIZE - 1) // PAGE_SIZE)

    if "dash_page" not in st.session_state:
        st.session_state.dash_page = 0
    st.session_state.dash_page = max(0, min(st.session_state.dash_page, total_pages - 1))

    page = st.session_state.dash_page
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    st.dataframe(display_df.iloc[start:end], use_container_width=True)
    st.caption(f"Showing {start + 1}-{min(end, total_rows)} of {total_rows}")

    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("Prev", disabled=page == 0, use_container_width=True):
            st.session_state.dash_page -= 1
            st.rerun()
    with col_info:
        st.markdown(
            f"<p style='text-align:center;margin-top:8px'>Page {page + 1} of {total_pages}</p>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("Next", disabled=page >= total_pages - 1, use_container_width=True):
            st.session_state.dash_page += 1
            st.rerun()

    st.divider()
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download logs as CSV",
        data=csv,
        file_name="dlp_logs.csv",
        mime="text/csv",
    )
