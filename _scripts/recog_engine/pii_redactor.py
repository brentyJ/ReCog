"""
PII Redaction Module for ReCog

Detects and redacts personally identifiable information before sending
content to LLM APIs. Supports two backends:

1. Regex Backend (default): Zero dependencies, handles common PII patterns
2. Presidio Backend (optional): ML-powered detection with 50+ entity types

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
"""

import os
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected and redacted."""
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    EMAIL = "email"
    PHONE = "phone"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    BANK_ACCOUNT = "bank_account"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    ADDRESS = "address"
    # Presidio-only types (require ML backend)
    PERSON = "person"
    LOCATION = "location"
    ORGANIZATION = "organization"
    MEDICAL_RECORD = "medical_record"


@dataclass
class PIIMatch:
    """Represents a detected PII instance."""
    pii_type: PIIType
    original: str
    start: int
    end: int
    confidence: float = 1.0
    placeholder: str = ""


@dataclass
class RedactionResult:
    """Result of a redaction operation."""
    redacted_text: str
    matches: List[PIIMatch] = field(default_factory=list)
    placeholder_map: Dict[str, str] = field(default_factory=dict)

    @property
    def pii_found(self) -> bool:
        """Whether any PII was found."""
        return len(self.matches) > 0

    @property
    def pii_count(self) -> int:
        """Total number of PII instances found."""
        return len(self.matches)

    @property
    def pii_types_found(self) -> Set[PIIType]:
        """Set of PII types found."""
        return {m.pii_type for m in self.matches}


class RegexPIIDetector:
    """
    Regex-based PII detection (no external dependencies).

    Handles common PII patterns with reasonable accuracy.
    Does NOT detect names/locations (requires NLP/ML).
    """

    # Pattern definitions: (pattern, pii_type, placeholder_prefix)
    PATTERNS: List[Tuple[re.Pattern, PIIType, str]] = [
        # US Social Security Number (XXX-XX-XXXX or XXXXXXXXX)
        (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), PIIType.SSN, "SSN"),
        (re.compile(r'\b\d{9}\b(?!\d)'), PIIType.SSN, "SSN"),  # 9 digits not followed by more

        # Credit card numbers (various formats)
        (re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|'
                   r'6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b'),
         PIIType.CREDIT_CARD, "CARD"),
        # Credit card with spaces/dashes
        (re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'), PIIType.CREDIT_CARD, "CARD"),

        # Email addresses
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
         PIIType.EMAIL, "EMAIL"),

        # Phone numbers (various formats)
        (re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
         PIIType.PHONE, "PHONE"),
        # International format
        (re.compile(r'\b\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b'),
         PIIType.PHONE, "PHONE"),

        # IP Addresses (IPv4)
        (re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                   r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'),
         PIIType.IP_ADDRESS, "IP"),

        # Date of Birth patterns (US format MM/DD/YYYY, DD/MM/YYYY)
        (re.compile(r'\b(?:dob|date\s+of\s+birth|born)[:\s]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b',
                   re.IGNORECASE), PIIType.DATE_OF_BIRTH, "DOB"),

        # Bank account numbers (generic - 8-17 digits)
        (re.compile(r'\b(?:account|acct)[#:\s]+\d{8,17}\b', re.IGNORECASE),
         PIIType.BANK_ACCOUNT, "ACCOUNT"),

        # US Passport numbers (9 alphanumeric)
        (re.compile(r'\b(?:passport)[#:\s]+[A-Z0-9]{9}\b', re.IGNORECASE),
         PIIType.PASSPORT, "PASSPORT"),

        # Drivers license (state-specific, simplified)
        (re.compile(r'\b(?:dl|driver\'?s?\s+license)[#:\s]+[A-Z0-9]{5,15}\b', re.IGNORECASE),
         PIIType.DRIVERS_LICENSE, "DL"),
    ]

    def detect(self, text: str) -> List[PIIMatch]:
        """
        Detect PII in text using regex patterns.

        Args:
            text: Text to scan for PII

        Returns:
            List of PIIMatch objects for each detected instance
        """
        matches = []
        seen_spans = set()  # Avoid duplicate matches at same position

        for pattern, pii_type, prefix in self.PATTERNS:
            for match in pattern.finditer(text):
                span = (match.start(), match.end())
                # Skip if we already have a match at this position
                if span in seen_spans:
                    continue
                seen_spans.add(span)

                matches.append(PIIMatch(
                    pii_type=pii_type,
                    original=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,  # Regex patterns have high confidence
                    placeholder=f"[{prefix}]",
                ))

        # Sort by position
        matches.sort(key=lambda m: m.start)
        return matches


class PresidioPIIDetector:
    """
    Presidio-based PII detection (requires presidio-analyzer).

    Provides ML-powered detection for names, locations, organizations,
    and 50+ other entity types.
    """

    def __init__(self, language: str = "en"):
        self.language = language
        self._analyzer = None
        self._anonymizer = None

    def _ensure_initialized(self) -> bool:
        """Lazy-load Presidio components."""
        if self._analyzer is not None:
            return True

        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
            logger.info("Presidio PII detection initialized")
            return True
        except ImportError:
            logger.warning(
                "Presidio not installed. Install with: "
                "pip install presidio-analyzer presidio-anonymizer && "
                "python -m spacy download en_core_web_sm"
            )
            return False

    def detect(self, text: str, entities: Optional[List[str]] = None) -> List[PIIMatch]:
        """
        Detect PII using Presidio's ML-based analyzer.

        Args:
            text: Text to scan
            entities: Optional list of entity types to detect

        Returns:
            List of PIIMatch objects
        """
        if not self._ensure_initialized():
            return []

        if entities is None:
            entities = [
                "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
                "US_SSN", "LOCATION", "ORGANIZATION", "US_PASSPORT",
                "US_DRIVER_LICENSE", "IP_ADDRESS", "MEDICAL_LICENSE",
                "US_BANK_NUMBER", "DATE_TIME",
            ]

        results = self._analyzer.analyze(
            text=text,
            entities=entities,
            language=self.language,
        )

        matches = []
        for result in results:
            pii_type = self._map_entity_type(result.entity_type)
            placeholder = self._get_placeholder(result.entity_type)

            matches.append(PIIMatch(
                pii_type=pii_type,
                original=text[result.start:result.end],
                start=result.start,
                end=result.end,
                confidence=result.score,
                placeholder=placeholder,
            ))

        matches.sort(key=lambda m: m.start)
        return matches

    def _map_entity_type(self, entity_type: str) -> PIIType:
        """Map Presidio entity types to PIIType enum."""
        mapping = {
            "PERSON": PIIType.PERSON,
            "EMAIL_ADDRESS": PIIType.EMAIL,
            "PHONE_NUMBER": PIIType.PHONE,
            "CREDIT_CARD": PIIType.CREDIT_CARD,
            "US_SSN": PIIType.SSN,
            "LOCATION": PIIType.LOCATION,
            "ORGANIZATION": PIIType.ORGANIZATION,
            "US_PASSPORT": PIIType.PASSPORT,
            "US_DRIVER_LICENSE": PIIType.DRIVERS_LICENSE,
            "IP_ADDRESS": PIIType.IP_ADDRESS,
            "MEDICAL_LICENSE": PIIType.MEDICAL_RECORD,
            "US_BANK_NUMBER": PIIType.BANK_ACCOUNT,
            "DATE_TIME": PIIType.DATE_OF_BIRTH,
        }
        return mapping.get(entity_type, PIIType.PERSON)

    def _get_placeholder(self, entity_type: str) -> str:
        """Get placeholder text for entity type."""
        placeholders = {
            "PERSON": "[PERSON]",
            "EMAIL_ADDRESS": "[EMAIL]",
            "PHONE_NUMBER": "[PHONE]",
            "CREDIT_CARD": "[CARD]",
            "US_SSN": "[SSN]",
            "LOCATION": "[LOCATION]",
            "ORGANIZATION": "[ORG]",
            "US_PASSPORT": "[PASSPORT]",
            "US_DRIVER_LICENSE": "[DL]",
            "IP_ADDRESS": "[IP]",
            "MEDICAL_LICENSE": "[MEDICAL_ID]",
            "US_BANK_NUMBER": "[ACCOUNT]",
            "DATE_TIME": "[DATE]",
        }
        return placeholders.get(entity_type, f"[{entity_type}]")


class PIIRedactor:
    """
    Main PII redaction interface.

    Combines detection (regex or Presidio) with redaction.
    Supports numbered placeholders for tracking: [PERSON_1], [PERSON_2], etc.
    """

    def __init__(
        self,
        backend: str = "auto",
        use_numbered_placeholders: bool = True,
        min_confidence: float = 0.5,
    ):
        """
        Initialize PII redactor.

        Args:
            backend: "regex", "presidio", or "auto" (try presidio, fall back to regex)
            use_numbered_placeholders: If True, use [TYPE_1], [TYPE_2] format
            min_confidence: Minimum confidence score to redact (presidio only)
        """
        self.use_numbered_placeholders = use_numbered_placeholders
        self.min_confidence = min_confidence

        # Select backend
        if backend == "presidio":
            self._detector = PresidioPIIDetector()
            self._backend_name = "presidio"
        elif backend == "regex":
            self._detector = RegexPIIDetector()
            self._backend_name = "regex"
        else:  # auto
            # Try Presidio first, fall back to regex
            presidio = PresidioPIIDetector()
            if presidio._ensure_initialized():
                self._detector = presidio
                self._backend_name = "presidio"
            else:
                self._detector = RegexPIIDetector()
                self._backend_name = "regex"
                logger.info("Using regex PII backend (Presidio not available)")

    @property
    def backend(self) -> str:
        """Get the active backend name."""
        return self._backend_name

    def detect(self, text: str) -> List[PIIMatch]:
        """
        Detect PII in text without redacting.

        Args:
            text: Text to scan

        Returns:
            List of PIIMatch objects
        """
        matches = self._detector.detect(text)

        # Filter by confidence if using Presidio
        if self._backend_name == "presidio":
            matches = [m for m in matches if m.confidence >= self.min_confidence]

        return matches

    def redact(self, text: str) -> RedactionResult:
        """
        Detect and redact PII, returning mapping for potential restoration.

        Args:
            text: Text to redact

        Returns:
            RedactionResult with redacted text and placeholder mapping
        """
        matches = self.detect(text)

        if not matches:
            return RedactionResult(redacted_text=text)

        # Build redacted text and placeholder map
        placeholder_map = {}
        type_counters = {}
        redacted_parts = []
        last_end = 0

        for match in matches:
            # Add text before this match
            redacted_parts.append(text[last_end:match.start])

            # Generate placeholder
            if self.use_numbered_placeholders:
                pii_type_name = match.pii_type.value.upper()
                count = type_counters.get(pii_type_name, 0) + 1
                type_counters[pii_type_name] = count
                placeholder = f"[{pii_type_name}_{count}]"
            else:
                placeholder = match.placeholder

            # Update match with actual placeholder used
            match.placeholder = placeholder
            placeholder_map[placeholder] = match.original

            redacted_parts.append(placeholder)
            last_end = match.end

        # Add remaining text
        redacted_parts.append(text[last_end:])

        return RedactionResult(
            redacted_text="".join(redacted_parts),
            matches=matches,
            placeholder_map=placeholder_map,
        )

    def redact_for_llm(self, text: str) -> str:
        """
        One-way redaction for LLM prompts.

        Convenience method that just returns the redacted text.

        Args:
            text: Text to redact

        Returns:
            Redacted text string
        """
        return self.redact(text).redacted_text


# =============================================================================
# MODULE-LEVEL FUNCTIONS
# =============================================================================

# Global redactor instance (lazy initialized)
_redactor: Optional[PIIRedactor] = None


def get_redactor() -> PIIRedactor:
    """
    Get the global PII redactor instance.

    Configured via environment variables:
    - RECOG_PII_BACKEND: "regex", "presidio", or "auto" (default: "auto")
    - RECOG_PII_MIN_CONFIDENCE: minimum confidence threshold (default: 0.5)
    """
    global _redactor
    if _redactor is None:
        backend = os.environ.get("RECOG_PII_BACKEND", "auto")
        min_confidence = float(os.environ.get("RECOG_PII_MIN_CONFIDENCE", "0.5"))
        _redactor = PIIRedactor(backend=backend, min_confidence=min_confidence)
        logger.info(f"PII redactor initialized with {_redactor.backend} backend")
    return _redactor


def redact_pii(text: str) -> RedactionResult:
    """
    Redact PII from text using the global redactor.

    Args:
        text: Text to redact

    Returns:
        RedactionResult with redacted text and mapping
    """
    return get_redactor().redact(text)


def redact_for_llm(text: str) -> str:
    """
    Redact PII from text for LLM submission.

    Args:
        text: Text to redact

    Returns:
        Redacted text string
    """
    return get_redactor().redact_for_llm(text)


def is_pii_redaction_enabled() -> bool:
    """
    Check if PII redaction is enabled.

    Controlled by RECOG_PII_REDACTION environment variable.
    Default: True
    """
    return os.environ.get("RECOG_PII_REDACTION", "true").lower() in ("true", "1", "yes")


__all__ = [
    "PIIType",
    "PIIMatch",
    "RedactionResult",
    "PIIRedactor",
    "RegexPIIDetector",
    "PresidioPIIDetector",
    "get_redactor",
    "redact_pii",
    "redact_for_llm",
    "is_pii_redaction_enabled",
]
