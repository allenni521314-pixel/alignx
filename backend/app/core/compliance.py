from __future__ import annotations
"""Amazon Listing compliance rule engine."""

# ── Banned words / phrases ──

BANNED_ABSOLUTE = [
    "best", "no.1", "number one", "#1", "guaranteed", "100%",
    "completely eliminates", "permanent", "cure", "safest",
    "always", "never", "perfect", "instant", "flawless",
]

BANNED_HEALTH = [
    "prevents disease", "kills all bacteria", "medical grade",
    "doctor recommended", "allergy cure", "antibacterial",
    "antimicrobial", "kills germs", "sterilizes", "disinfects",
    "health claim", "fda approved",
]

BANNED_ATTACK = [
    "better than all competitors", "other brands are unsafe",
    "competitors are fake", "only brand that",
    "don't buy from others",
]

BANNED_EXAGGERATION = [
    "removes all odors instantly", "works forever",
    "zero smell guaranteed", "never needs maintenance",
    "lasts a lifetime", "never fails",
]

ALL_BANNED = BANNED_ABSOLUTE + BANNED_HEALTH + BANNED_ATTACK + BANNED_EXAGGERATION


def check_compliance(text: str) -> list[str]:
    """Check text against all banned word lists. Returns list of violations."""
    violations = []
    text_lower = text.lower()
    for word in ALL_BANNED:
        if word in text_lower:
            violations.append(word)
    return violations


def compliance_report(texts: dict[str, str]) -> dict:
    """Check all listing fields and return compliance report."""
    results = {}
    for field, text in texts.items():
        if not text:
            continue
        hits = check_compliance(text)
        if hits:
            results[field] = {"violations": hits, "risk": "high" if len(hits) > 2 else "medium"}
    return results
