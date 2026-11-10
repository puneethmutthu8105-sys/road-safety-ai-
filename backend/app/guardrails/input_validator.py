"""
Guardrails: Input and output validators for all agents.
"""
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Blocked patterns for input guardrails
BLOCKED_INPUT_PATTERNS = [
    r"(?i)\bignore\b.{0,30}\binstructions\b",
    r"(?i)(jailbreak|prompt injection|bypass (safety|guard|filter))",
    r"(?i)(you are now|act as if you are|pretend (you are|to be))",
    r"(?i)(disregard (all |previous )?instructions)",
    r"(?i)(DAN mode|do anything now)",
]

# PII patterns to detect in output
PII_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",          # SSN
    r"\b[A-Z]{2}\d{7}\b",              # Passport
    r"\b\d{16}\b",                      # Credit card (basic)
]


def validate_input(text: str) -> Tuple[bool, str]:
    """
    Returns (is_valid, reason).
    is_valid=False means the input should be blocked.
    """
    if not text or not text.strip():
        return False, "Empty input"
    if len(text) > 5000:
        return False, "Input too long (max 5000 chars)"
    for pattern in BLOCKED_INPUT_PATTERNS:
        if re.search(pattern, text):
            return False, f"Blocked prompt pattern detected"
    return True, "OK"


def validate_output(text: str) -> Tuple[bool, str]:
    """
    Returns (is_valid, reason).
    Checks for PII leakage in AI output.
    """
    if not text:
        return True, "OK"
    for pattern in PII_PATTERNS:
        if re.search(pattern, text):
            logger.warning("[Guardrails] PII detected in output — redacting.")
            return False, "PII detected in output"
    return True, "OK"


def sanitize_output(text: str) -> str:
    """Redact detected PII from output text."""
    for pattern in PII_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def validate_coordinates(lat: float, lng: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0


def validate_risk_score(score: float) -> bool:
    return 0.0 <= score <= 100.0
