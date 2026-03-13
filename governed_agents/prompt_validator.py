import re


# DETECTION_ONLY
INJECTION_PATTERNS = [
    r"ignore all instructions",
    r"ignore any instructions",
    r"ignore previous instructions",
    r"ignore all previous instructions",
]


def scan_prompt_for_injection(text: str) -> list[str]:
    lowered = text.lower()
    matches = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            matches.append(pattern)
    return matches
