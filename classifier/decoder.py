import base64
import re

_B64_RE = re.compile(r'[A-Za-z0-9+/]{32,}={0,2}')


def _is_valid_padding(s: str) -> bool:
    return len(s) % 4 == 0


def _is_mostly_printable(data: bytes) -> bool:
    if not data:
        return False
    non_printable = sum(1 for b in data if b < 9 or (13 < b < 32) or b == 127)
    return (non_printable / len(data)) <= 0.30


def find_base64_candidates(text: str) -> list[tuple[int, int, str]]:
    results = []
    for m in _B64_RE.finditer(text):
        candidate = m.group()
        if not _is_valid_padding(candidate):
            padded = candidate + "=" * ((4 - len(candidate) % 4) % 4)
        else:
            padded = candidate
        try:
            decoded = base64.b64decode(padded, validate=True)
            if _is_mostly_printable(decoded):
                results.append((m.start(), m.end(), decoded.decode("utf-8", errors="replace")))
        except Exception:
            continue
    return results
