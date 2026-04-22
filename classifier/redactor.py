import re

_PLACEHOLDER_RE = re.compile(r'^[*X#_\-]{4,}$', re.IGNORECASE)
_SAME_CHAR_RE = re.compile(r'^(.)\1{3,}$')
_FAKE_MARKERS = {"test", "example", "xxxx", "1234", "0000"}


def is_placeholder(value: str) -> bool:
    stripped = value.strip()
    if _PLACEHOLDER_RE.match(stripped):
        return True
    if _SAME_CHAR_RE.match(stripped):
        return True
    if stripped.lower() in _FAKE_MARKERS:
        return True
    return False


def _mask_email(m: re.Match) -> str:
    addr = m.group()
    local, _, domain = addr.partition("@")
    domain_parts = domain.rsplit(".", 1)
    tld = domain_parts[1] if len(domain_parts) == 2 else domain
    return f"{local[0]}***@***.{tld}"


def _mask_phone(m: re.Match) -> str:
    digits = re.sub(r'\D', '', m.group())
    return f"***-***-{digits[-4:]}"


def _mask_ssn(m: re.Match) -> str:
    digits = re.sub(r'\D', '', m.group())
    return f"***-**-{digits[-4:]}"


def _mask_cc(digits_only: str) -> str:
    return f"****-****-****-{digits_only[-4:]}"


def _mask_dob(_: re.Match) -> str:
    return "**/**/****"


EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')
PHONE_RE = re.compile(r'\b\(?\d{3}\)?[\-.\s]\d{3}[\-.\s]\d{4}\b')
SSN_RE = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
DOB_RE = re.compile(r'\b(0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])[/\-](19|20)\d{2}\b')
CC_RE = re.compile(r'\b(?:\d[ \-]*?){13,19}\b')
CRED_PATTERNS = [
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'sk-ant-[A-Za-z0-9\-_]{90,}'),
    re.compile(r'sk-[A-Za-z0-9]{48}'),
    re.compile(r'ghp_[A-Za-z0-9]{36}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{82}'),
    re.compile(r'gho_[A-Za-z0-9]{36}'),
    re.compile(r'ghs_[A-Za-z0-9]{36}'),
    re.compile(r'xoxb-[0-9A-Za-z\-]+'),
    re.compile(r'xoxp-[0-9A-Za-z\-]+'),
    re.compile(r'xapp-[0-9A-Za-z\-]+'),
    re.compile(r'eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'),
    re.compile(r'(?i)password\s*[:=]\s*\S+'),
    re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----'),
    re.compile(r'(postgres|mysql|mongodb)(\+srv)?:\/\/[^\s:]+:[^\s@]+@\S+'),
]


def redact(text: str, matched_spans: list[tuple[int, int, str, str]], business_terms: list[str]) -> str:
    replacements: list[tuple[int, int, str]] = []

    for pattern in CRED_PATTERNS:
        for m in pattern.finditer(text):
            replacements.append((m.start(), m.end(), "[REDACTED:CREDENTIAL]"))

    for m in EMAIL_RE.finditer(text):
        if not is_placeholder(m.group()):
            replacements.append((m.start(), m.end(), _mask_email(m)))

    for m in PHONE_RE.finditer(text):
        if not is_placeholder(m.group()):
            replacements.append((m.start(), m.end(), _mask_phone(m)))

    for m in SSN_RE.finditer(text):
        if not is_placeholder(m.group()):
            replacements.append((m.start(), m.end(), _mask_ssn(m)))

    for m in DOB_RE.finditer(text):
        if not is_placeholder(m.group()):
            replacements.append((m.start(), m.end(), _mask_dob(m)))

    for m in CC_RE.finditer(text):
        digits = re.sub(r'\D', '', m.group())
        if len(digits) >= 13 and not is_placeholder(m.group()):
            replacements.append((m.start(), m.end(), _mask_cc(digits)))

    for term in business_terms:
        pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
        for m in pattern.finditer(text):
            replacements.append((m.start(), m.end(), "[REDACTED:BUSINESS]"))

    for span_start, span_end, category, encoding in matched_spans:
        if encoding == "base64":
            replacements.append((span_start, span_end, "[REDACTED:ENCODED_CREDENTIAL]"))

    replacements.sort(key=lambda x: x[0], reverse=True)

    result = text
    seen: set[int] = set()
    for start, end, replacement in replacements:
        if start in seen:
            continue
        result = result[:start] + replacement + result[end:]
        seen.add(start)

    return result[:500]
