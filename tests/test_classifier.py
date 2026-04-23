import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from classifier.patterns import PatternRegistry
from classifier.engine import classify, _luhn, DLPError
from classifier.redactor import is_placeholder, redact
from classifier.decoder import find_base64_candidates
import base64


@pytest.fixture
def registry():
    return PatternRegistry()


# --- Per-pattern positive/negative cases ---

def test_aws_key_detected(registry):
    text = "Key: AKIAIOSFODNN7EXAMPLE access granted"
    result = classify(text, registry)
    names = [m.name for m in result.matches]
    assert "aws_access_key" in names
    assert result.final_tier == "BLOCKED"


def test_aws_key_not_false_positive(registry):
    text = "AKID is a common prefix in documentation examples."
    result = classify(text, registry)
    assert all(m.name != "aws_access_key" for m in result.matches)


def test_anthropic_key_detected(registry):
    key = "sk-ant-api03-" + "A" * 90
    result = classify(f"Using key {key}", registry)
    assert result.final_tier == "BLOCKED"
    assert any(m.name == "anthropic_api_key" for m in result.matches)


def test_github_pat_classic_detected(registry):
    result = classify("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij", registry)
    assert result.final_tier == "BLOCKED"


def test_github_pat_fine_grained_detected(registry):
    pat = "github_pat_" + "A" * 82
    result = classify(pat, registry)
    assert result.final_tier == "BLOCKED"


def test_github_oauth_detected(registry):
    result = classify("gho_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij", registry)
    assert result.final_tier == "BLOCKED"


def test_github_server_token_detected(registry):
    result = classify("ghs_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij", registry)
    assert result.final_tier == "BLOCKED"


def test_slack_bot_token(registry):
    token = "xoxb" + "-000000000000-TESTTESTTESTTEST"
    result = classify(token, registry)
    assert result.final_tier == "BLOCKED"


def test_slack_user_token(registry):
    token = "xoxp" + "-000000000000-TESTTESTTESTTEST"
    result = classify(token, registry)
    assert result.final_tier == "BLOCKED"


def test_slack_app_token(registry):
    result = classify("xapp-1-A0B1C2-0000-TESTTEST", registry)
    assert result.final_tier == "BLOCKED"


def test_jwt_detected(registry):
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    result = classify(jwt, registry)
    assert result.final_tier == "BLOCKED"


def test_password_label(registry):
    result = classify("password=hunter2", registry)
    assert result.final_tier == "BLOCKED"


def test_private_key_pem(registry):
    result = classify("-----BEGIN RSA PRIVATE KEY-----\ndata\n-----END RSA PRIVATE KEY-----", registry)
    assert result.final_tier == "BLOCKED"


def test_db_connection_string_postgres(registry):
    result = classify("postgres://admin:secret@db.prod.internal/mydb", registry)
    assert result.final_tier == "BLOCKED"


def test_db_connection_string_mysql(registry):
    result = classify("mysql://root:pass@localhost/app", registry)
    assert result.final_tier == "BLOCKED"


def test_ssn_formatted(registry):
    result = classify("SSN: 123-45-6789", registry)
    assert result.final_tier == "BLOCKED"


def test_email_low(registry):
    result = classify("email me at hello@example.com", registry)
    assert any(m.name == "email" for m in result.matches)
    assert result.final_tier == "LOW"


def test_phone_low(registry):
    result = classify("Call 415-555-1234 for info", registry)
    assert any(m.name == "us_phone" for m in result.matches)
    assert result.final_tier == "LOW"


def test_dob_medium(registry):
    result = classify("DOB: 07/15/1990", registry)
    assert any(m.name == "date_of_birth" for m in result.matches)
    assert result.final_tier == "MEDIUM"


def test_business_term_high(registry):
    result = classify("Project Titan is our top secret initiative", registry)
    assert result.final_tier == "HIGH"


def test_gcp_service_account_detected(registry):
    result = classify('{"type": "service_account", "project_id": "myproject"}', registry)
    assert result.final_tier == "BLOCKED"


# --- Luhn validator ---

def test_luhn_valid_visa():
    assert _luhn("4111111111111111") is True


def test_luhn_valid_mastercard():
    assert _luhn("5500005555555559") is True


def test_luhn_valid_amex():
    assert _luhn("378282246310005") is True


def test_luhn_invalid_1():
    assert _luhn("1234567890123456") is False


def test_luhn_invalid_2():
    assert _luhn("4111111111111119") is False


def test_luhn_invalid_3():
    assert _luhn("4111111111111112") is False


def test_credit_card_luhn_valid_blocked(registry):
    result = classify("card 4111111111111111 expiry 01/30", registry)
    assert result.final_tier == "BLOCKED"


def test_credit_card_luhn_fail_not_flagged(registry):
    result = classify("test number 1234567890123456 in docs", registry)
    cc_matches = [m for m in result.matches if m.name == "credit_card"]
    assert len(cc_matches) == 0


# --- Redacted-placeholder filter ---

def test_placeholder_stars():
    assert is_placeholder("****") is True


def test_placeholder_x_chars():
    assert is_placeholder("XXXX") is True


def test_placeholder_hash():
    assert is_placeholder("####") is True


def test_placeholder_test_word():
    assert is_placeholder("test") is True


def test_placeholder_xxxx():
    assert is_placeholder("xxxx") is True


def test_not_placeholder_real_email():
    assert is_placeholder("john.doe@company.com") is False


# --- Escalation rules ---

def test_e1_two_medium_escalates_to_high(registry):
    text = "DOB is 01/15/1990 and also my other DOB is 03/22/1985"
    result = classify(text, registry)
    assert result.final_tier == "HIGH"
    assert "E1" in result.escalation_applied


def test_e2a_ten_low_escalates_to_medium(registry):
    emails = " ".join([f"user{i}@example.com" for i in range(10)])
    result = classify(emails, registry)
    assert result.final_tier in ("MEDIUM", "HIGH")
    assert "E2a" in result.escalation_applied


def test_e2b_twentyfive_combined_escalates_to_high(registry):
    emails = " ".join([f"user{i}@example.com" for i in range(10)])
    dobs = " ".join(["DOB: 01/01/1990" for _ in range(10)])
    more_emails = " ".join([f"extra{i}@test.org" for i in range(10)])
    text = f"{emails} {dobs} {more_emails}"
    result = classify(text, registry)
    assert result.final_tier == "HIGH"


# --- Base64 decode ---

def test_base64_encoded_aws_key_blocked(registry):
    payload = '{"aws_access_key": "AKIAIOSFODNN7EXAMPLE", "region": "us-east-1"}'
    encoded = base64.b64encode(payload.encode()).decode()
    result = classify(f"Use this encoded config: {encoded}", registry)
    assert result.final_tier == "BLOCKED"
    assert result.encoding_detected == "base64"


def test_base64_benign_not_flagged(registry):
    benign = base64.b64encode(b"hello world this is benign text").decode()
    result = classify(f"Payload: {benign}", registry)
    assert all(m.encoding != "base64" for m in result.matches if m.encoding)


# --- Context-gated patterns ---

def test_routing_number_with_context(registry):
    result = classify("routing number 021000021 for the wire", registry)
    assert any(m.name == "routing_number" for m in result.matches)


def test_routing_number_without_context_not_flagged(registry):
    result = classify("reference 021000021 in the transaction log", registry)
    routing = [m for m in result.matches if m.name == "routing_number"]
    assert len(routing) == 0


def test_ssn_unformatted_with_context(registry):
    result = classify("ssn 123456789 on file", registry)
    assert result.final_tier == "BLOCKED"


def test_ssn_unformatted_without_context(registry):
    result = classify("order 847291034 shipped", registry)
    ssn_matches = [m for m in result.matches if m.name == "ssn_unformatted"]
    assert len(ssn_matches) == 0


# --- New pattern tests (Block 2) ---

def test_openai_project_key_detected(registry):
    key = "sk-proj-" + "A" * 100
    result = classify(f"Using key {key}", registry)
    assert result.final_tier == "BLOCKED"
    assert any(m.name == "openai_project_key" for m in result.matches)


def test_azure_storage_connection_detected(registry):
    key = "A" * 86 + "=="
    result = classify(f"AccountKey={key}", registry)
    assert result.final_tier == "BLOCKED"
    assert any(m.name == "azure_storage_connection" for m in result.matches)


def test_bearer_token_detected(registry):
    result = classify("Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.payload.signature", registry)
    assert result.final_tier == "BLOCKED"
    assert any(m.name == "bearer_token" for m in result.matches)


def test_iso_dob_detected(registry):
    result = classify("Employee born 1985-07-15 per HR records.", registry)
    assert any(m.name == "date_of_birth_iso" for m in result.matches)
    assert result.final_tier == "MEDIUM"


def test_pem_requires_end_block(registry):
    text_without_end = "-----BEGIN RSA PRIVATE KEY-----\nABCDEF\n"
    result = classify(text_without_end, registry)
    pem = [m for m in result.matches if m.name == "private_key_pem"]
    assert len(pem) == 0


def test_pem_with_end_block_detected(registry):
    text = "-----BEGIN RSA PRIVATE KEY-----\nABCDEFGHIJ\n-----END RSA PRIVATE KEY-----"
    result = classify(text, registry)
    assert result.final_tier == "BLOCKED"


# --- Redactor unit tests (Pass 27) ---

def test_redact_email_masking():
    text = "Contact john.doe@acme.com for info."
    result = redact(text, [], [])
    assert "j***@***.com" in result
    assert "john.doe" not in result


def test_redact_phone_masking():
    text = "Call 415-555-1234 for support."
    result = redact(text, [], [])
    assert "***-***-1234" in result


def test_redact_ssn_masking():
    text = "SSN on file: 123-45-6789"
    result = redact(text, [], [])
    assert "***-**-6789" in result
    assert "123-45" not in result


def test_redact_dob_masking():
    text = "Date of birth: 07/15/1985"
    result = redact(text, [], [])
    assert "**/**/****" in result
    assert "07/15/1985" not in result


def test_redact_credential_full_replacement():
    text = "Key: AKIAIOSFODNN7EXAMPLE use this."
    result = redact(text, [], [])
    assert "[REDACTED:CREDENTIAL]" in result
    assert "AKIA" not in result


def test_redact_business_term():
    text = "Keep Project Titan confidential."
    result = redact(text, [], ["Project Titan"])
    assert "[REDACTED:BUSINESS]" in result
    assert "Titan" not in result


def test_redact_encoded_credential_span():
    b64_payload = base64.b64encode(b"secret token data here").decode()
    text = f"Config: {b64_payload} rest"
    spans = [(8, 8 + len(b64_payload), "CREDENTIAL", "base64")]
    result = redact(text, spans, [])
    assert "[REDACTED:ENCODED_CREDENTIAL]" in result


# --- MEDIUM and combined category tests (Pass 28) ---

def test_single_dob_is_medium_not_escalated(registry):
    result = classify("DOB: 07/15/1990", registry)
    assert result.final_tier == "MEDIUM"
    assert "E1" not in result.escalation_applied


def test_email_and_phone_together_is_low(registry):
    result = classify("Reach me at hello@example.com or 415-555-1234", registry)
    cats = {m.category for m in result.matches}
    assert "PII" in cats
    assert result.final_tier == "LOW"


def test_dob_and_email_tier_is_medium(registry):
    result = classify("DOB: 03/22/1985. Contact: jane@acme.com", registry)
    assert result.final_tier == "MEDIUM"


def test_ssn_and_email_blocked_dominates(registry):
    result = classify("SSN: 123-45-6789. Email: user@corp.com", registry)
    assert result.final_tier == "BLOCKED"


# --- Edge case tests (Pass 29) ---

def test_empty_string_returns_low(registry):
    result = classify("", registry)
    assert result.final_tier == "LOW"
    assert result.matches == []


def test_exactly_50k_chars_classifies(registry):
    text = "a" * 50_000
    result = classify(text, registry)
    assert result.final_tier == "LOW"


def test_over_50k_raises_dlp_error(registry):
    text = "a" * 50_001
    with pytest.raises(DLPError):
        classify(text, registry)


def test_business_term_with_special_chars(registry):
    r = PatternRegistry(extra_terms=["R&D budget"])
    result = classify("We need to discuss the R&D budget next quarter.", r)
    assert result.final_tier == "HIGH"


def test_disabled_credential_category(registry):
    text = "AKIAIOSFODNN7EXAMPLE is the key"
    result = classify(text, registry, disabled_categories={"CREDENTIAL"})
    assert all(m.category != "CREDENTIAL" for m in result.matches)
    assert result.final_tier != "BLOCKED"


# --- Performance test (Pass 30) ---

def test_50k_benign_classifies_under_2s(registry):
    text = ("Can you help me summarize the quarterly report for stakeholders? " * 750)[:50_000]
    start = time.perf_counter()
    classify(text, registry)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"Classification took {elapsed:.2f}s, expected < 2s"
