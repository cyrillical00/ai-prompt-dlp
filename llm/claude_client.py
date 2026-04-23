import streamlit as st

STATIC_SYSTEM_PROMPT = (
    "You are processing a user input that has passed through a data governance layer. "
    "The risk annotation below is machine-generated metadata; treat it as context, not instruction. "
    "The user input has been redacted where sensitive data was detected. "
    "Respond helpfully to the redacted input while being aware of the risk context provided."
)


def _build_system_blocks(submission_id: int, tier: str, categories: list[str], match_count: int, encoding: str | None) -> list[dict]:
    enc_label = encoding if encoding else "none"
    dynamic_text = (
        f"[GOVERNANCE_METADATA]\n"
        f"Submission ID: {submission_id}\n"
        f"Risk tier: {tier}\n"
        f"Detected categories: {', '.join(categories) if categories else 'none'}\n"
        f"Match count: {match_count}\n"
        f"Encoding detected: {enc_label}\n"
        f"[END_METADATA]"
    )
    # Only the static block carries cache_control. The dynamic block changes per
    # submission (different ID, tier, categories) so caching it would miss every
    # time and waste a cache write. Static block is the reuse anchor.
    return [
        {
            "type": "text",
            "text": STATIC_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": dynamic_text,
        },
    ]


DEMO_RESPONSE_TEMPLATE = """\
**[DEMO MODE - simulated response]**

*In production this response comes from claude-sonnet-4-6 via the gated passthrough. \
The prompt below was received after redaction by the classification layer.*

---

Acknowledged. I have received your prompt with the following governance context:

- Risk tier: **{tier}**
- Detected categories: {categories}
- Match count: {match_count}
- Encoding detected: {encoding}

The redacted input has been processed. In a live environment I would respond to the \
substance of your request here. To enable real Claude responses, add your \
`ANTHROPIC_API_KEY` to the Streamlit secrets configuration.

*Submission ID: {submission_id}*
"""


def send_to_claude(
    submission_id: int,
    tier: str,
    categories: list[str],
    match_count: int,
    encoding: str | None,
    redacted_input: str,
    demo_mode: bool = False,
) -> tuple[str, str | None]:
    if demo_mode:
        response_text = DEMO_RESPONSE_TEMPLATE.format(
            tier=tier,
            categories=", ".join(categories) if categories else "none",
            match_count=match_count,
            encoding=encoding or "none",
            submission_id=submission_id,
        )
        return response_text, "demo-response"

    api_key = st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured in Streamlit secrets.")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    system_blocks = _build_system_blocks(submission_id, tier, categories, match_count, encoding)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0.3,
        system=system_blocks,
        messages=[{"role": "user", "content": redacted_input}],
    )

    response_text = response.content[0].text if response.content else ""
    response_id = response.id
    return response_text, response_id
