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


def send_to_claude(
    submission_id: int,
    tier: str,
    categories: list[str],
    match_count: int,
    encoding: str | None,
    redacted_input: str,
) -> tuple[str, str | None]:
    api_key = st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not configured in Streamlit secrets.")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    system_blocks = _build_system_blocks(submission_id, tier, categories, match_count, encoding)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=1.0,
        system=system_blocks,
        messages=[{"role": "user", "content": redacted_input}],
    )

    response_text = response.content[0].text if response.content else ""
    response_id = response.id
    return response_text, response_id
