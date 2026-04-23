import re
import yaml
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent / "config"


def _load_yaml(filename: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / filename).read_text())


def load_pattern_config() -> dict:
    return _load_yaml("patterns.yaml")


def load_business_terms() -> list[str]:
    return _load_yaml("business_terms.yaml")["terms"]


def load_tier_config() -> dict:
    return _load_yaml("tiers.yaml")


class PatternRegistry:
    def __init__(self, extra_terms: list[str] | None = None):
        cfg = load_pattern_config()
        self.regex_patterns = []
        self.context_patterns = []
        self.business_terms = load_business_terms()
        if extra_terms:
            self.business_terms = self.business_terms + extra_terms
        self._compile(cfg)

    def _compile(self, cfg: dict):
        for p in cfg.get("regex_patterns", []):
            entry = dict(p)
            entry["compiled"] = re.compile(p["pattern"], self._flags(p))
            self.regex_patterns.append(entry)

        for p in cfg.get("context_patterns", []):
            entry = dict(p)
            if "pattern" in p:
                entry["compiled"] = re.compile(p["pattern"], self._flags(p))
            self.context_patterns.append(entry)

    @staticmethod
    def _flags(p: dict) -> int:
        flags = 0
        for name in p.get("pattern_flags", "").split("|"):
            name = name.strip()
            if name:
                flags |= getattr(re, name, 0)
        return flags
