"""
Prompt Injection Detection for ReCog

Detects potential prompt injection attacks in uploaded documents
before they are sent to LLM APIs.

Uses regex pattern matching for lightweight, dependency-free detection.
Designed for defense-in-depth - warns rather than hard-blocks to avoid
false positives on legitimate documents.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
"""

import os
import re
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class InjectionRisk(Enum):
    """Risk level for detected injection attempts."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class InjectionMatch:
    """Represents a detected injection pattern."""
    pattern_name: str
    matched_text: str
    start: int
    end: int
    risk: InjectionRisk
    description: str


@dataclass
class InjectionResult:
    """Result of injection detection scan."""
    is_suspicious: bool
    risk_level: InjectionRisk
    confidence: float
    reason: str
    matches: List[InjectionMatch]

    @property
    def should_warn(self) -> bool:
        """Whether to warn the user about potential injection."""
        return self.risk_level in (InjectionRisk.MEDIUM, InjectionRisk.HIGH, InjectionRisk.CRITICAL)

    @property
    def should_block(self) -> bool:
        """Whether to block the content (only for critical risk)."""
        return self.risk_level == InjectionRisk.CRITICAL


class InjectionDetector:
    """
    Regex-based prompt injection detector.

    Detects common injection patterns without external dependencies.
    Designed to minimize false positives while catching obvious attacks.
    """

    # Pattern definitions: (pattern, name, risk, description)
    PATTERNS: List[Tuple[re.Pattern, str, InjectionRisk, str]] = [
        # Instruction override attempts
        (re.compile(r'ignore\s+(all\s+)?(previous|prior|above)\s+instructions?', re.IGNORECASE),
         "instruction_override", InjectionRisk.HIGH,
         "Attempts to override system instructions"),

        (re.compile(r'disregard\s+(all\s+)?(previous|prior|above)', re.IGNORECASE),
         "instruction_disregard", InjectionRisk.HIGH,
         "Attempts to disregard prior context"),

        (re.compile(r'forget\s+(everything|all|what)\s+(you|i)\s+(said|told|know)', re.IGNORECASE),
         "memory_wipe", InjectionRisk.HIGH,
         "Attempts to clear model memory"),

        # Role/mode manipulation
        (re.compile(r'you\s+are\s+now\s+(in\s+)?(developer|admin|sudo|root|god)\s+mode', re.IGNORECASE),
         "mode_switch", InjectionRisk.CRITICAL,
         "Attempts to switch to elevated mode"),

        (re.compile(r'(act|pretend|behave)\s+(as|like)\s+(if\s+)?(you\s+are\s+)?(a\s+)?(different|new|another)', re.IGNORECASE),
         "role_change", InjectionRisk.MEDIUM,
         "Attempts to change model role"),

        (re.compile(r'from\s+now\s+on[,\s]+(you|your)\s+(will|must|should|are)', re.IGNORECASE),
         "persistent_change", InjectionRisk.MEDIUM,
         "Attempts to make persistent changes"),

        # Prompt extraction attempts
        (re.compile(r'(reveal|show|print|display|output)\s+(your\s+)?(system\s+)?(prompt|instructions?)', re.IGNORECASE),
         "prompt_extraction", InjectionRisk.HIGH,
         "Attempts to extract system prompt"),

        (re.compile(r'(what|tell\s+me)\s+(are\s+)?(your\s+)?(initial|original|system)\s+(instructions?|prompt)', re.IGNORECASE),
         "prompt_query", InjectionRisk.HIGH,
         "Queries for system prompt"),

        (re.compile(r'repeat\s+(the\s+)?(text|words?|instructions?)\s+(above|before)', re.IGNORECASE),
         "prompt_repeat", InjectionRisk.HIGH,
         "Attempts to repeat prior text"),

        # XML/markup injection
        (re.compile(r'<\s*system\s*>', re.IGNORECASE),
         "xml_system_tag", InjectionRisk.CRITICAL,
         "Attempts to inject system XML tag"),

        (re.compile(r'<\s*/?\s*(?:assistant|user|human)\s*>', re.IGNORECASE),
         "xml_role_tag", InjectionRisk.HIGH,
         "Attempts to inject role XML tags"),

        # Jailbreak keywords
        (re.compile(r'\b(DAN|do\s+anything\s+now)\b', re.IGNORECASE),
         "dan_jailbreak", InjectionRisk.CRITICAL,
         "Known jailbreak pattern (DAN)"),

        (re.compile(r'\bjailbreak(ed|ing)?\b', re.IGNORECASE),
         "jailbreak_keyword", InjectionRisk.MEDIUM,
         "Jailbreak keyword detected"),

        # Output manipulation
        (re.compile(r'(respond|reply|answer)\s+(only\s+)?(with|using)\s+(yes|no|true|false|json)', re.IGNORECASE),
         "output_constraint", InjectionRisk.LOW,
         "Attempts to constrain output format"),

        # Base64 encoded content (potential hidden instructions)
        (re.compile(r'[A-Za-z0-9+/]{50,}={0,2}'),
         "base64_content", InjectionRisk.LOW,
         "Large base64-encoded content detected"),

        # Delimiter attacks
        (re.compile(r'(```|"""|\'\'\')\s*(system|instructions?|prompt)', re.IGNORECASE),
         "delimiter_attack", InjectionRisk.MEDIUM,
         "Attempts to inject with code delimiters"),
    ]

    # Patterns that increase suspicion when combined
    COMBINATION_PATTERNS: List[Tuple[re.Pattern, str]] = [
        (re.compile(r'\b(important|critical|urgent|must|always)\b', re.IGNORECASE), "urgency"),
        (re.compile(r'\b(override|bypass|ignore|skip|disable)\b', re.IGNORECASE), "bypass_verb"),
        (re.compile(r'\b(secret|hidden|internal|private)\b', re.IGNORECASE), "secrecy"),
    ]

    def detect(self, text: str) -> InjectionResult:
        """
        Scan text for potential prompt injection.

        Args:
            text: Text to scan

        Returns:
            InjectionResult with detection details
        """
        matches = []
        text_lower = text.lower()

        # Check main patterns
        for pattern, name, risk, description in self.PATTERNS:
            for match in pattern.finditer(text):
                matches.append(InjectionMatch(
                    pattern_name=name,
                    matched_text=match.group()[:100],  # Truncate for logging
                    start=match.start(),
                    end=match.end(),
                    risk=risk,
                    description=description,
                ))

        # Calculate overall risk
        if not matches:
            # Check for suspicious combinations even without direct matches
            combination_score = self._check_combinations(text_lower)
            if combination_score >= 3:
                return InjectionResult(
                    is_suspicious=True,
                    risk_level=InjectionRisk.LOW,
                    confidence=0.3,
                    reason="Suspicious keyword combinations detected",
                    matches=[],
                )
            return InjectionResult(
                is_suspicious=False,
                risk_level=InjectionRisk.NONE,
                confidence=0.0,
                reason="Clean",
                matches=[],
            )

        # Determine highest risk level
        risk_levels = [m.risk for m in matches]
        if InjectionRisk.CRITICAL in risk_levels:
            overall_risk = InjectionRisk.CRITICAL
        elif InjectionRisk.HIGH in risk_levels:
            overall_risk = InjectionRisk.HIGH
        elif InjectionRisk.MEDIUM in risk_levels:
            overall_risk = InjectionRisk.MEDIUM
        else:
            overall_risk = InjectionRisk.LOW

        # Calculate confidence based on number and severity of matches
        confidence = min(0.9, 0.3 + (len(matches) * 0.15))

        # Build reason string
        pattern_names = list(set(m.pattern_name for m in matches))
        reason = f"Detected: {', '.join(pattern_names[:3])}"
        if len(pattern_names) > 3:
            reason += f" (+{len(pattern_names) - 3} more)"

        return InjectionResult(
            is_suspicious=True,
            risk_level=overall_risk,
            confidence=confidence,
            reason=reason,
            matches=matches,
        )

    def _check_combinations(self, text_lower: str) -> int:
        """Check for suspicious keyword combinations."""
        score = 0
        for pattern, _ in self.COMBINATION_PATTERNS:
            if pattern.search(text_lower):
                score += 1
        return score


# =============================================================================
# MODULE-LEVEL FUNCTIONS
# =============================================================================

# Global detector instance
_detector: Optional[InjectionDetector] = None


def get_detector() -> InjectionDetector:
    """Get the global injection detector instance."""
    global _detector
    if _detector is None:
        _detector = InjectionDetector()
    return _detector


def detect_injection(text: str) -> InjectionResult:
    """
    Detect potential prompt injection in text.

    Args:
        text: Text to scan

    Returns:
        InjectionResult with detection details
    """
    return get_detector().detect(text)


def is_injection_detection_enabled() -> bool:
    """
    Check if injection detection is enabled.

    Controlled by RECOG_INJECTION_DETECTION environment variable.
    Values: "warn" (default), "block", "off"
    """
    setting = os.environ.get("RECOG_INJECTION_DETECTION", "warn").lower()
    return setting in ("warn", "block")


def get_injection_mode() -> str:
    """
    Get the injection detection mode.

    Returns: "warn", "block", or "off"
    """
    return os.environ.get("RECOG_INJECTION_DETECTION", "warn").lower()


__all__ = [
    "InjectionRisk",
    "InjectionMatch",
    "InjectionResult",
    "InjectionDetector",
    "get_detector",
    "detect_injection",
    "is_injection_detection_enabled",
    "get_injection_mode",
]
