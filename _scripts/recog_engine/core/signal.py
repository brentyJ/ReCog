"""
ReCog Core - Signal Processor v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Tier 0: Zero-LLM-cost signal extraction from raw text.
Runs on every document to flag structural patterns, emotion markers,
intensity signals, and question patterns.

This is a refactored version of tier0.py, using the new core types.
"""

import re
from datetime import datetime
from typing import Dict, List, Any, Optional

from .types import Document


# =============================================================================
# KEYWORD DICTIONARIES
# =============================================================================

EMOTION_KEYWORDS = {
    # Negative valence
    "anger": ["hate", "angry", "furious", "resentment", "bitter", "rage", "pissed", "frustrated", "annoyed"],
    "fear": ["scared", "afraid", "terrified", "anxious", "worried", "dread", "panic", "nervous", "uneasy"],
    "sadness": ["sad", "depressed", "hopeless", "grief", "heartbroken", "miserable", "devastated", "down", "low"],
    "shame": ["ashamed", "embarrassed", "guilty", "humiliated", "worthless", "pathetic", "stupid", "failure"],
    "disgust": ["disgusted", "revolted", "sick of", "repulsed", "gross"],
    
    # Positive valence
    "joy": ["happy", "excited", "thrilled", "elated", "joyful", "ecstatic", "delighted", "pleased", "glad"],
    "pride": ["proud", "accomplished", "confident", "capable", "strong", "successful"],
    "love": ["love", "adore", "cherish", "devoted", "connected", "close", "fond", "care"],
    "gratitude": ["grateful", "thankful", "appreciative", "blessed", "fortunate"],
    "hope": ["hopeful", "optimistic", "looking forward", "excited about", "eager"],
    
    # Complex/mixed
    "confusion": ["confused", "lost", "uncertain", "conflicted", "torn", "unsure", "puzzled"],
    "loneliness": ["lonely", "isolated", "alone", "disconnected", "abandoned", "excluded"],
    "nostalgia": ["miss", "remember when", "used to", "back then", "those days"],
    "ambivalence": ["mixed feelings", "part of me", "on one hand", "not sure if"],
}

INTENSIFIERS = [
    "very", "really", "extremely", "absolutely", "completely", "totally",
    "incredibly", "deeply", "profoundly", "utterly", "genuinely", "truly",
    "so much", "such a", "the most", "fucking", "bloody", "damn"
]

HEDGES = [
    "maybe", "perhaps", "I think", "I guess", "sort of", "kind of",
    "probably", "might", "possibly", "I suppose", "not sure if",
    "I don't know", "I wonder", "seems like"
]

ABSOLUTES = [
    "always", "never", "every time", "no one", "everyone", "nothing",
    "everything", "completely", "totally", "all", "none", "forever"
]

TEMPORAL_PATTERNS = {
    "past": [
        r"when I was \w+",
        r"years ago",
        r"back (then|when)",
        r"used to",
        r"I remember",
        r"growing up",
        r"as a (kid|child|teenager|young)",
        r"last (week|month|year)",
        r"in the past",
        r"before (I|we|that)",
    ],
    "present": [
        r"right now",
        r"currently",
        r"these days",
        r"at the moment",
        r"lately",
        r"nowadays",
        r"today",
    ],
    "future": [
        r"going to",
        r"planning to",
        r"someday",
        r"one day",
        r"eventually",
        r"hoping to",
        r"want to",
        r"will be",
        r"in the future",
    ],
    "habitual": [
        r"\balways\b",
        r"\bnever\b",
        r"every time",
        r"whenever",
        r"constantly",
        r"usually",
        r"often",
    ],
}

SELF_INQUIRY_PATTERNS = [
    r"why do I\b",
    r"why am I\b",
    r"what('s| is) wrong with me",
    r"who am I\b",
    r"what do I (really )?(want|need|feel)",
    r"am I\b.+\?",
    r"should I\b",
    r"how do I\b",
    r"I wonder (if|why|what|whether)",
    r"what if I\b",
    r"do I (really|actually|even)",
]

PEOPLE_TITLES = [
    "Mr", "Mrs", "Ms", "Dr", "Mum", "Mom", "Dad", "Father", "Mother",
    "Uncle", "Aunt", "Grandma", "Grandpa", "Gran", "Pop", "Nan",
    "Brother", "Sister", "Son", "Daughter", "Wife", "Husband",
    "Boss", "Manager", "Teacher", "Coach", "Therapist"
]


# =============================================================================
# SIGNAL PROCESSOR
# =============================================================================

class SignalProcessor:
    """
    Tier 0 signal extraction processor.
    
    Extracts structural and semantic signals from text without using LLMs.
    These signals guide later extraction passes.
    """
    
    VERSION = "1.0"
    
    def process(self, document: Document) -> Document:
        """
        Process a document and populate its signals field.
        
        Args:
            document: Document to process
            
        Returns:
            Same document with signals populated
        """
        signals = self.extract_signals(document.content)
        document.signals = signals
        return document
    
    def extract_signals(self, text: str) -> Dict[str, Any]:
        """
        Extract signals from raw text.
        
        Args:
            text: Raw text to analyse
            
        Returns:
            Dictionary of extracted signals
        """
        if not text or not text.strip():
            return self._empty_result()
        
        result = {
            "version": self.VERSION,
            "processed_at": datetime.utcnow().isoformat() + "Z",
            "word_count": 0,
            "char_count": len(text),
            "emotion_signals": {},
            "intensity_markers": {},
            "question_analysis": {},
            "temporal_references": {},
            "entities": {},
            "structural": {},
            "flags": {},
        }
        
        # Basic counts
        words = text.split()
        result["word_count"] = len(words)
        
        # Run extractors
        result["emotion_signals"] = self._extract_emotion_signals(text, len(words))
        result["intensity_markers"] = self._extract_intensity_markers(text)
        result["question_analysis"] = self._analyse_questions(text, len(words))
        result["temporal_references"] = self._extract_temporal_refs(text)
        result["entities"] = self._extract_basic_entities(text)
        result["structural"] = self._analyse_structure(text)
        
        # Compute composite flags
        result["flags"] = self._compute_flags(result)
        
        return result
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "version": self.VERSION,
            "processed_at": datetime.utcnow().isoformat() + "Z",
            "word_count": 0,
            "char_count": 0,
            "emotion_signals": {"keywords_found": [], "keyword_count": 0, "keyword_density": 0.0},
            "intensity_markers": {"exclamations": 0, "all_caps_words": 0, "repeated_punctuation": 0, "intensifiers": [], "hedges": []},
            "question_analysis": {"question_count": 0, "question_density": 0.0, "self_inquiry": 0, "rhetorical_likely": 0},
            "temporal_references": {"past": [], "present": [], "future": [], "habitual": []},
            "entities": {"people": [], "places": [], "organisations": []},
            "structural": {"paragraph_count": 0, "sentence_count": 0, "avg_sentence_length": 0, "longest_sentence": 0, "speaker_changes": 0},
            "flags": {"high_emotion": False, "self_reflective": False, "narrative": False, "analytical": False},
        }
    
    def _extract_emotion_signals(self, text: str, word_count: int) -> Dict:
        """Find emotion keywords and calculate density."""
        text_lower = text.lower()
        found = []
        categories_found = set()
        
        for category, keywords in EMOTION_KEYWORDS.items():
            for kw in keywords:
                if " " in kw:
                    if kw in text_lower:
                        found.append(kw)
                        categories_found.add(category)
                else:
                    if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                        found.append(kw)
                        categories_found.add(category)
        
        return {
            "keywords_found": list(set(found)),
            "categories": list(categories_found),
            "keyword_count": len(found),
            "keyword_density": len(found) / max(word_count, 1),
        }
    
    def _extract_intensity_markers(self, text: str) -> Dict:
        """Find intensity indicators."""
        text_lower = text.lower()
        
        exclamations = text.count("!")
        all_caps = len([w for w in text.split() if w.isupper() and len(w) > 2 and w.isalpha()])
        repeated_punct = len(re.findall(r"[!?]{2,}", text))
        
        intensifiers_found = []
        for i in INTENSIFIERS:
            if i.lower() in text_lower:
                intensifiers_found.append(i)
        
        hedges_found = []
        for h in HEDGES:
            if h.lower() in text_lower:
                hedges_found.append(h)
        
        absolutes_found = []
        for a in ABSOLUTES:
            if re.search(rf"\b{re.escape(a.lower())}\b", text_lower):
                absolutes_found.append(a)
        
        return {
            "exclamations": exclamations,
            "all_caps_words": all_caps,
            "repeated_punctuation": repeated_punct,
            "intensifiers": list(set(intensifiers_found)),
            "hedges": list(set(hedges_found)),
            "absolutes": list(set(absolutes_found)),
        }
    
    def _analyse_questions(self, text: str, word_count: int) -> Dict:
        """Analyse question patterns."""
        questions = re.findall(r"[^.!?]*\?", text)
        question_count = len(questions)
        
        self_inquiry = 0
        for pattern in SELF_INQUIRY_PATTERNS:
            self_inquiry += len(re.findall(pattern, text, re.IGNORECASE))
        
        rhetorical = 0
        for q in questions:
            q_words = len(q.split())
            if q_words < 5 or "really" in q.lower() or "right?" in q.lower():
                rhetorical += 1
        
        return {
            "question_count": question_count,
            "question_density": question_count / max(word_count, 1),
            "self_inquiry": self_inquiry,
            "rhetorical_likely": rhetorical,
        }
    
    def _extract_temporal_refs(self, text: str) -> Dict:
        """Extract temporal reference patterns."""
        result = {"past": [], "present": [], "future": [], "habitual": []}
        
        for category, patterns in TEMPORAL_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        result[category].append(" ".join(match))
                    else:
                        result[category].append(match)
            result[category] = list(set(result[category]))[:5]
        
        return result
    
    def _extract_basic_entities(self, text: str) -> Dict:
        """Basic entity extraction without NLP library."""
        sentences = re.split(r"[.!?]", text)
        people = []
        
        for sentence in sentences:
            words = sentence.split()
            for i, word in enumerate(words):
                if i == 0:
                    continue
                
                clean = re.sub(r"[^a-zA-Z']", "", word)
                if not clean:
                    continue
                
                if clean[0].isupper():
                    if i > 0:
                        prev = re.sub(r"[^a-zA-Z]", "", words[i-1])
                        if prev in PEOPLE_TITLES:
                            people.append(clean)
                            continue
                    
                    if clean in PEOPLE_TITLES:
                        people.append(clean)
                        continue
                    
                    if clean not in ["I", "I'm", "I've", "I'll", "I'd"]:
                        people.append(clean)
        
        return {
            "people": list(set(people))[:10],
            "places": [],
            "organisations": [],
        }
    
    def _analyse_structure(self, text: str) -> Dict:
        """Analyse text structure."""
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        sentence_lengths = [len(s.split()) for s in sentences]
        
        speaker_changes = 0
        speaker_patterns = [
            r"\*\*Me:\*\*", r"\*\*Ehko:\*\*", r"\*\*User:\*\*", r"\*\*Assistant:\*\*",
            r"^Me:", r"^You:", r"^Ehko:",
            r"<USER_MESSAGE>", r"<EHKO_MESSAGE>", r"<ASSISTANT_MESSAGE>",
        ]
        for pattern in speaker_patterns:
            speaker_changes += len(re.findall(pattern, text, re.MULTILINE))
        
        return {
            "paragraph_count": len(paragraphs),
            "sentence_count": len(sentences),
            "avg_sentence_length": round(sum(sentence_lengths) / max(len(sentence_lengths), 1), 1),
            "longest_sentence": max(sentence_lengths) if sentence_lengths else 0,
            "speaker_changes": speaker_changes,
        }
    
    def _compute_flags(self, result: Dict) -> Dict:
        """Compute composite flags from extracted data."""
        emotion = result["emotion_signals"]
        questions = result["question_analysis"]
        intensity = result["intensity_markers"]
        temporal = result["temporal_references"]
        structural = result["structural"]
        
        return {
            "high_emotion": (
                emotion["keyword_count"] >= 2 or
                intensity["exclamations"] >= 2 or
                intensity["all_caps_words"] >= 1 or
                len(intensity.get("absolutes", [])) >= 2
            ),
            "self_reflective": (
                questions["self_inquiry"] >= 1 or
                questions["question_density"] > 0.02
            ),
            "narrative": (
                len(temporal["past"]) >= 2 or
                structural["paragraph_count"] >= 3
            ),
            "analytical": (
                len(intensity["hedges"]) >= 2 and
                questions["question_count"] >= 2
            ),
        }
    
    def summarise_for_prompt(self, signals: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of signals for LLM prompts.
        
        Args:
            signals: Output from extract_signals()
            
        Returns:
            Formatted string for inclusion in extraction prompts
        """
        if not signals:
            return "No signals available."
        
        parts = []
        
        # Emotion signals
        if signals.get("emotion_signals", {}).get("keywords_found"):
            keywords = signals["emotion_signals"]["keywords_found"][:5]
            parts.append(f"Emotion keywords: {', '.join(keywords)}")
        
        if signals.get("emotion_signals", {}).get("categories"):
            cats = signals["emotion_signals"]["categories"][:3]
            parts.append(f"Emotion categories: {', '.join(cats)}")
        
        # Flags
        flags = signals.get("flags", {})
        active_flags = [k.replace("_", " ") for k, v in flags.items() if v]
        if active_flags:
            parts.append(f"Flags: {', '.join(active_flags)}")
        
        # Temporal
        if signals.get("temporal_references", {}).get("past"):
            past_refs = signals["temporal_references"]["past"][:3]
            parts.append(f"Past references: {', '.join(past_refs)}")
        
        # People
        if signals.get("entities", {}).get("people"):
            people = signals["entities"]["people"][:5]
            parts.append(f"People mentioned: {', '.join(people)}")
        
        # Intensity
        intensity = signals.get("intensity_markers", {})
        if intensity.get("exclamations", 0) >= 2:
            parts.append(f"High exclamation count: {intensity['exclamations']}")
        if intensity.get("absolutes"):
            parts.append(f"Absolute statements: {', '.join(intensity['absolutes'][:3])}")
        
        # Questions
        questions = signals.get("question_analysis", {})
        if questions.get("self_inquiry", 0) >= 1:
            parts.append(f"Self-inquiry questions: {questions['self_inquiry']}")
        
        if not parts:
            return "No significant signals detected."
        
        return "\n".join(f"- {p}" for p in parts)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def process_text(text: str) -> Dict[str, Any]:
    """
    Convenience function to extract signals from text.
    
    Args:
        text: Raw text to analyse
        
    Returns:
        Dictionary of extracted signals
    """
    processor = SignalProcessor()
    return processor.extract_signals(text)


def process_document(document: Document) -> Document:
    """
    Convenience function to process a document.
    
    Args:
        document: Document to process
        
    Returns:
        Same document with signals populated
    """
    processor = SignalProcessor()
    return processor.process(document)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "SignalProcessor",
    "process_text",
    "process_document",
    # Dictionaries (for customisation)
    "EMOTION_KEYWORDS",
    "INTENSIFIERS",
    "HEDGES",
    "ABSOLUTES",
]
