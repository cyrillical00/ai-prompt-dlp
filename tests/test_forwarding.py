import os

import pytest

from llm.claude_client import ForwardingRefused, check_forwarding_allowed


def test_low_and_medium_pass():
    check_forwarding_allowed("LOW")
    check_forwarding_allowed("MEDIUM")


def test_high_requires_ack():
    with pytest.raises(ForwardingRefused):
        check_forwarding_allowed("HIGH")
    check_forwarding_allowed("HIGH", high_tier_ack=True)


def test_high_blocked_by_policy(monkeypatch):
    monkeypatch.setenv("DLP_BLOCK_HIGH", "true")
    with pytest.raises(ForwardingRefused):
        check_forwarding_allowed("HIGH", high_tier_ack=True)


def test_blocked_and_unknown_tiers_refused():
    for tier in ("BLOCKED", "WHATEVER"):
        with pytest.raises(ForwardingRefused):
            check_forwarding_allowed(tier, high_tier_ack=True)
