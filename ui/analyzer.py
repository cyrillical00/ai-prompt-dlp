import streamlit as st
from classifier.patterns import PatternRegistry
from classifier.engine import classify, result_to_match_dicts
from classifier.redactor import redact
from db.logger import insert_submission, mark_passed_to_llm, mark_blocked
from llm.claude_client import send_to_claude

TIER_COLORS = {
    "LOW": "green",
    "MEDIUM": "orange",
    "HIGH": "orange",
    "BLOCKED": "red",
}

TIER_LABELS = {
    "LOW": ":green[LOW]",
    "MEDIUM": ":orange[MEDIUM]",
    "HIGH": ":orange[HIGH - Escalated]",
    "BLOCKED": ":red[BLOCKED]",
}

INPUT_CAP = 50_000


def render(registry: PatternRegistry, disabled_categories: set[str], demo_mode: bool = False):
    st.header("Prompt Analyzer")
    text = st.text_area("Prompt to analyze", height=250, key="analyzer_input")

    if st.button("Analyze", type="primary"):
        if not text.strip():
            st.warning("Enter a prompt to analyze.")
            return

        if len(text) > INPUT_CAP:
            st.error(f"Input exceeds PoC limit (50k chars). Split into smaller chunks.")
            return

        result = classify(text, registry, disabled_categories)
        match_dicts = result_to_match_dicts(result)

        redacted = redact(
            text,
            [(m.span[0], m.span[1], m.category, m.encoding or "") for m in result.matches],
            list(registry.business_terms),
        )

        submission_id = insert_submission(
            risk_tier=result.final_tier,
            matched_patterns=match_dicts,
            redacted_preview=redacted,
            original_length=len(text),
            encoding_detected=result.encoding_detected,
        )

        if result.final_tier == "BLOCKED":
            blocked_names = [m.name for m in result.matches if m.tier == "BLOCKED"]
            reason = f"Detected: {', '.join(blocked_names)}"
            mark_blocked(submission_id, reason)

        st.session_state["last_result"] = {
            "submission_id": submission_id,
            "final_tier": result.final_tier,
            "matches": match_dicts,
            "redacted": redacted,
            "original_length": len(text),
            "encoding_detected": result.encoding_detected,
            "escalation_applied": result.escalation_applied,
            "categories": list({m.category for m in result.matches}),
            "match_count": len(result.matches),
            "llm_response": None,
        }

    last = st.session_state.get("last_result")
    if not last:
        return

    st.divider()
    st.subheader("Classification Result")

    tier = last["final_tier"]
    st.markdown(f"**Risk Tier:** {TIER_LABELS.get(tier, tier)}")

    ESCALATION_LABELS = {
        "E1": "E1 (2+ MEDIUM -> HIGH)",
        "E2a": "E2a (10+ LOW -> MEDIUM)",
        "E2b": "E2b (25+ LOW+MEDIUM -> HIGH)",
    }
    if last["escalation_applied"]:
        labels = [ESCALATION_LABELS.get(e, e) for e in last["escalation_applied"]]
        st.caption(f"Escalation applied: {', '.join(labels)}")

    TIER_RANK = {"BLOCKED": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
    if last["matches"]:
        import pandas as pd
        rows = []
        for m in last["matches"]:
            rows.append({
                "Category": m["category"],
                "Pattern": m["name"],
                "Tier": m["tier"],
                "Encoded": m.get("encoding") or "",
                "_rank": TIER_RANK.get(m["tier"], 99),
            })
        rows.sort(key=lambda r: r["_rank"])
        for r in rows:
            del r["_rank"]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("No sensitive patterns detected.")

    st.subheader("Redacted Preview")
    st.code(last["redacted"], language=None)
    if len(last["redacted"]) >= 498:
        st.caption(f"Preview truncated at 500 chars. Original input was {last.get('original_length', '?')} chars.")

    if tier == "BLOCKED":
        st.error("This prompt contains BLOCKED content and cannot be sent to Claude.")
        blocked_names = [m["name"] for m in last["matches"] if m["tier"] == "BLOCKED"]
        st.button(
            "Send to Claude with risk annotation",
            disabled=True,
            help=f"Blocked: {', '.join(blocked_names)}",
        )
    else:
        btn_label = "Send to Claude with risk annotation (Demo)" if demo_mode else "Send to Claude with risk annotation"
        if st.button(btn_label, type="secondary"):
            spinner_msg = "Generating demo response..." if demo_mode else "Sending to Claude..."
            with st.spinner(spinner_msg):
                try:
                    response_text, response_id = send_to_claude(
                        submission_id=last["submission_id"],
                        tier=last["final_tier"],
                        categories=last["categories"],
                        match_count=last["match_count"],
                        encoding=last["encoding_detected"],
                        redacted_input=last["redacted"],
                        demo_mode=demo_mode,
                    )
                    mark_passed_to_llm(last["submission_id"], response_id)
                    st.session_state["last_result"]["llm_response"] = response_text
                except Exception as exc:
                    st.error(f"Claude API error: {exc}")

    if last.get("llm_response"):
        st.subheader("Claude Response")
        st.markdown(last["llm_response"])
