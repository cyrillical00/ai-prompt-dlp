import re
from dataclasses import dataclass, field
from classifier.patterns import PatternRegistry
from classifier.decoder import find_base64_candidates
from classifier.redactor import is_placeholder

TIER_ORDER = ["BLOCKED", "HIGH", "MEDIUM", "LOW", "NONE"]


@dataclass
class Match:
    name: str
    category: str
    tier: str
    value: str
    span: tuple[int, int]
    encoding: str | None = None


@dataclass
class ClassificationResult:
    final_tier: str
    matches: list[Match]
    encoding_detected: str | None
    escalation_applied: list[str] = field(default_factory=list)


def _tier_rank(tier: str) -> int:
    try:
        return TIER_ORDER.index(tier)
    except ValueError:
        return len(TIER_ORDER)


def _higher(a: str, b: str) -> str:
    return a if _tier_rank(a) <= _tier_rank(b) else b


def _luhn(number: str) -> bool:
    digits = [int(d) for d in re.sub(r'\D', '', number)]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _context_match(text: str, span_start: int, span_end: int, keywords: list[str], window: int = 20) -> bool:
    lo = max(0, span_start - window)
    hi = min(len(text), span_end + window)
    surrounding = text[lo:hi].lower()
    return any(kw.lower() in surrounding for kw in keywords)


def classify(
    text: str,
    registry: PatternRegistry,
    disabled_categories: set[str] | None = None,
) -> ClassificationResult:
    disabled = disabled_categories or set()
    matches: list[Match] = []
    seen_spans: dict[tuple[int, int], Match] = {}

    def _add(match: Match):
        key = match.span
        if key in seen_spans:
            existing = seen_spans[key]
            if _tier_rank(match.tier) < _tier_rank(existing.tier):
                seen_spans[key] = match
        else:
            seen_spans[key] = match

    for p in registry.regex_patterns:
        if p["category"] in disabled:
            continue
        for m in p["compiled"].finditer(text):
            value = m.group()
            if is_placeholder(value):
                continue

            if p.get("luhn_check"):
                if not _luhn(value):
                    continue

            if p.get("context_keywords"):
                if not _context_match(text, m.start(), m.end(), p["context_keywords"]):
                    continue

            _add(Match(
                name=p["name"],
                category=p["category"],
                tier=p["tier"],
                value=value,
                span=(m.start(), m.end()),
            ))

    for p in registry.context_patterns:
        if p["category"] in disabled:
            continue
        if "substring" in p:
            idx = text.find(p["substring"])
            if idx != -1:
                value = p["substring"]
                if not is_placeholder(value):
                    _add(Match(
                        name=p["name"],
                        category=p["category"],
                        tier=p["tier"],
                        value=value,
                        span=(idx, idx + len(value)),
                    ))
        elif "compiled" in p:
            for m in p["compiled"].finditer(text):
                value = m.group()
                if is_placeholder(value):
                    continue
                if p.get("context_keywords"):
                    if not _context_match(text, m.start(), m.end(), p["context_keywords"]):
                        continue
                _add(Match(
                    name=p["name"],
                    category=p["category"],
                    tier=p["tier"],
                    value=value,
                    span=(m.start(), m.end()),
                ))

    if "BUSINESS" not in disabled:
        for term in registry.business_terms:
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            for m in pattern.finditer(text):
                value = m.group()
                if not is_placeholder(value):
                    _add(Match(
                        name=f"business_term:{term.lower().replace(' ', '_')}",
                        category="BUSINESS",
                        tier="HIGH",
                        value=value,
                        span=(m.start(), m.end()),
                    ))

    encoding_detected = None
    b64_candidates = find_base64_candidates(text)
    for start, end, decoded_text in b64_candidates:
        sub_result = classify(decoded_text, registry, disabled)
        if sub_result.matches:
            encoding_detected = "base64"
            for sub_match in sub_result.matches:
                _add(Match(
                    name=sub_match.name,
                    category=sub_match.category,
                    tier=sub_match.tier,
                    value=sub_match.value,
                    span=(start, end),
                    encoding="base64",
                ))

    all_matches = list(seen_spans.values())

    if not all_matches:
        return ClassificationResult(
            final_tier="LOW",
            matches=[],
            encoding_detected=encoding_detected,
        )

    base_tier = "NONE"
    for match in all_matches:
        base_tier = _higher(base_tier, match.tier)

    escalation_applied = []
    final_tier = base_tier

    if final_tier != "BLOCKED":
        medium_count = sum(1 for m in all_matches if m.tier == "MEDIUM" and not m.encoding)
        low_count = sum(1 for m in all_matches if m.tier == "LOW")
        low_plus_medium = sum(1 for m in all_matches if m.tier in ("LOW", "MEDIUM"))

        if final_tier == "MEDIUM" and medium_count >= 2:
            final_tier = "HIGH"
            escalation_applied.append("E1")

        if low_count >= 10 and _tier_rank(final_tier) > _tier_rank("MEDIUM"):
            final_tier = "MEDIUM"
            escalation_applied.append("E2a")

        if low_plus_medium >= 25 and _tier_rank(final_tier) > _tier_rank("HIGH"):
            final_tier = "HIGH"
            escalation_applied.append("E2b")

    return ClassificationResult(
        final_tier=final_tier,
        matches=all_matches,
        encoding_detected=encoding_detected,
        escalation_applied=escalation_applied,
    )


def result_to_match_dicts(result: ClassificationResult) -> list[dict]:
    out = []
    for m in result.matches:
        out.append({
            "name": m.name,
            "category": m.category,
            "tier": m.tier,
            "encoding": m.encoding,
        })
    return out
