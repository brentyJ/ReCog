"""
ReCog Engine - Tier 0 Pre-Annotation Processor v0.3

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Zero-LLM-cost signal extraction from raw text.
Runs on every document/chunk to flag emotion markers, intensity, 
entities, temporal references, and question patterns.

This is the FREE processing tier - no API calls required.

v0.3 Changes:
- Added confidence scoring for person entities (HIGH/MEDIUM/LOW)
- Added blacklist support for rejected entities
- Added common English words filter for better false positive reduction
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Set


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

# Common titles/indicators for people - these BOOST confidence
PEOPLE_TITLES = [
    "Mr", "Mrs", "Ms", "Dr", "Mum", "Mom", "Dad", "Father", "Mother",
    "Uncle", "Aunt", "Grandma", "Grandpa", "Gran", "Pop", "Nan",
    "Brother", "Sister", "Son", "Daughter", "Wife", "Husband",
    "Boss", "Manager", "Teacher", "Coach", "Therapist", "Professor",
    "Officer", "Detective", "Sergeant", "Captain", "Pastor", "Reverend"
]

# Words that are often capitalised but are NOT people names
# This prevents false positives like "The", "This", "Monday" being flagged
NON_NAME_CAPITALS = {
    # Pronouns and articles
    "I", "I'm", "I've", "I'll", "I'd", "The", "This", "That", "These", "Those",
    "It", "He", "She", "We", "They", "My", "Your", "His", "Her", "Our", "Their",
    "Me", "You", "Him", "Us", "Them", "What", "Which", "Who", "Whom", "Whose",
    "Where", "When", "Why", "How", "Some", "Any", "All", "Each", "Every",
    "Both", "Few", "Many", "Much", "Most", "Other", "Another", "Such",
    
    # Days of the week
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun",
    
    # Months
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
    "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    
    # Common sentence starters / transition words
    "But", "And", "Or", "So", "Yet", "For", "Nor", "If", "Then", "Because",
    "Although", "However", "Therefore", "Moreover", "Furthermore", "Nevertheless",
    "Meanwhile", "Otherwise", "Instead", "Besides", "Still", "Thus", "Hence",
    "Also", "Even", "Just", "Only", "Now", "Here", "There", "Today", "Tomorrow",
    "Yesterday", "Tonight", "After", "Before", "During", "Since", "Until",
    
    # Common verbs/words that appear capitalised after quotes
    "Said", "Asked", "Told", "Replied", "Answered", "Thought", "Felt",
    "Knew", "Wanted", "Needed", "Tried", "Started", "Began", "Ended",
    
    # Tech/common nouns often capitalised
    "Internet", "Email", "Phone", "App", "Website", "Server", "Computer",
    "Facebook", "Google", "Twitter", "Instagram", "LinkedIn", "YouTube",
    "iPhone", "Android", "Windows", "Mac", "Linux",
    
    # Places (too generic to be useful as person detection)
    "Australia", "Melbourne", "Sydney", "Brisbane", "Perth", "Adelaide",
    "Victoria", "Queensland", "NSW", "London", "Paris", "Tokyo", "Berlin",
    "America", "England", "France", "Germany", "Japan", "China", "India",
    "USA", "UK", "EU", "UN", "US",
    
    # Common nouns that get capitalised
    "OK", "Yes", "No", "Maybe", "Please", "Thanks", "Sorry", "Hello", "Hi",
    "Goodbye", "Bye", "Well", "Right", "Sure", "True", "False",
    "God", "Christmas", "Easter", "New", "Year", "Years",
    
    # Common verbs / modal verbs that appear capitalised
    "Can", "Could", "Would", "Should", "Will", "Won", "Did", "Does", "Do",
    "Was", "Were", "Is", "Are", "Am", "Been", "Being", "Be", "Has", "Have", "Had",
    "Got", "Get", "Going", "Gone", "Go", "Went", "Come", "Came", "Coming",
    "Made", "Make", "Making", "Take", "Took", "Taking", "Taken",
    "See", "Saw", "Seen", "Seeing", "Look", "Looking", "Looked",
    "Think", "Thinking", "Thought", "Know", "Knowing", "Known",
    "Like", "Liked", "Liking", "Want", "Wanted", "Wanting",
    "Need", "Needed", "Needing", "Let", "Put", "Set", "Keep", "Kept",
    "Say", "Saying", "Says", "Tell", "Telling", "Tells",
    "Give", "Gave", "Given", "Giving", "Find", "Found", "Finding",
    "Try", "Tried", "Trying", "Leave", "Left", "Leaving",
    "Call", "Called", "Calling", "Work", "Working", "Worked",
    "Seem", "Seemed", "Seems", "Feel", "Felt", "Feeling",
    "Become", "Became", "Becoming", "Show", "Showed", "Shown",
    "Hear", "Heard", "Hearing", "Play", "Played", "Playing",
    "Run", "Ran", "Running", "Move", "Moved", "Moving",
    "Live", "Lived", "Living", "Believe", "Believed",
    
    # Negatives and qualifiers
    "Not", "Never", "None", "Nothing", "Nobody", "Nowhere",
    "Always", "Already", "Almost", "Again", "Away", "Anyway",
    "Really", "Actually", "Probably", "Certainly", "Definitely",
    "Enough", "Rather", "Quite", "Very", "Too", "More", "Less",
    "First", "Last", "Next", "Later", "Earlier", "Soon", "Once",
    
    # Question words that might appear mid-sentence
    "Whenever", "Whatever", "Whoever", "However", "Wherever",
    
    # Single letters / abbreviations
    "A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "O", "P",
    "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "AI", "ML", "IT", "HR", "CEO", "CTO", "CFO", "PM", "AM", "PM",
}

# =============================================================================
# COMMON ENGLISH WORDS - Words that are valid English but unlikely to be names
# These get flagged as LOW confidence when capitalised mid-sentence
# =============================================================================

COMMON_ENGLISH_WORDS = {
    # Emotions/states as nouns (often in titles like "Monday Morning Dread")
    "dread", "fear", "hope", "love", "hate", "joy", "grief", "rage", "calm",
    "peace", "stress", "anxiety", "panic", "bliss", "pain", "ache", "relief",
    
    # Abstract nouns commonly capitalised in titles
    "point", "break", "change", "shift", "start", "end", "rise", "fall",
    "truth", "lies", "life", "death", "time", "space", "light", "dark",
    "power", "force", "mind", "body", "soul", "spirit", "heart", "dream",
    
    # Actions/verbs that appear capitalised
    "woke", "wake", "broke", "break", "spoke", "speak", "wrote", "write",
    "drove", "drive", "chose", "choose", "froze", "freeze", "rose", "rise",
    "fell", "fall", "grew", "grow", "knew", "know", "threw", "throw",
    "flew", "fly", "drew", "draw", "wore", "wear", "tore", "tear",
    "bit", "bite", "hit", "quit", "split", "cut", "shut", "hurt",
    
    # Common words that get capitalised in informal writing
    "yay", "wow", "ooh", "ahh", "ugh", "hmm", "huh", "meh", "nah", "yep",
    "nope", "yeah", "okay", "alright", "whatever", "anyway", "besides",
    
    # Food/drink that might appear capitalised
    "pinot", "merlot", "shiraz", "champagne", "prosecco", "whiskey", "bourbon",
    "coffee", "latte", "mocha", "espresso", "chai", "matcha",
    
    # Days/time words
    "morning", "afternoon", "evening", "night", "noon", "midnight", "dawn", "dusk",
    "weekend", "weekday", "holiday", "vacation",
    
    # Directions and positions
    "north", "south", "east", "west", "left", "right", "up", "down",
    "front", "back", "top", "bottom", "side", "middle", "center",
    
    # Common adjectives that appear capitalised
    "big", "small", "old", "young", "new", "good", "bad", "best", "worst",
    "great", "grand", "major", "minor", "prime", "chief", "main",
    
    # Misc common words
    "just", "only", "even", "still", "yet", "already", "always", "never",
    "ever", "often", "sometimes", "usually", "rarely", "perhaps", "maybe",
    "probably", "possibly", "certainly", "definitely", "absolutely",
}

# Pre-compute lowercase sets for case-insensitive matching
NON_NAME_CAPITALS_LOWER = {w.lower() for w in NON_NAME_CAPITALS}
COMMON_ENGLISH_WORDS_LOWER = {w.lower() for w in COMMON_ENGLISH_WORDS}
PEOPLE_TITLES_LOWER = {t.lower() for t in PEOPLE_TITLES}

# =============================================================================
# BLACKLIST SUPPORT
# =============================================================================

# Runtime blacklist - loaded from database
_entity_blacklist: Set[str] = set()


def load_blacklist_from_db(db_path) -> Set[str]:
    """
    Load blacklisted entity values from database.
    Call this at startup or when blacklist changes.
    """
    global _entity_blacklist
    import sqlite3
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT normalised_value FROM entity_blacklist 
            WHERE entity_type = 'person'
        """)
        _entity_blacklist = {row[0].lower() for row in cursor.fetchall()}
        conn.close()
    except Exception:
        _entity_blacklist = set()
    
    return _entity_blacklist


def add_to_blacklist(value: str) -> None:
    """Add a value to the runtime blacklist."""
    _entity_blacklist.add(value.lower())


def is_blacklisted(value: str) -> bool:
    """Check if a value is in the blacklist."""
    return value.lower() in _entity_blacklist


def get_blacklist() -> Set[str]:
    """Get current blacklist."""
    return _entity_blacklist.copy()


# =============================================================================
# CONFIDENCE SCORING
# =============================================================================

class Confidence:
    """Entity confidence levels."""
    HIGH = "high"      # Very likely a name (preceded by title, or known pattern)
    MEDIUM = "medium"  # Probably a name (capitalised mid-sentence, passes filters)
    LOW = "low"        # Uncertain (common word, short, suspicious pattern)


def score_person_confidence(
    word: str,
    preceded_by_title: bool = False,
    is_title: bool = False,
    context_words: List[str] = None
) -> str:
    """
    Score confidence that a word is a person's name.
    
    Returns: 'high', 'medium', or 'low'
    """
    word_lower = word.lower()
    
    # HIGH confidence indicators
    if preceded_by_title or is_title:
        return Confidence.HIGH
    
    # Check for name-like patterns (e.g., followed by possessive or relational verb)
    if context_words:
        next_words = [w.lower() for w in context_words[:3]]
        # "Marcus said", "Sarah's", "John told me"
        if any(w in ["said", "says", "told", "asked", "replied", "'s", "is", "was", "has", "had"] for w in next_words):
            return Confidence.HIGH
    
    # LOW confidence indicators
    
    # Too short (2-3 chars after cleaning)
    if len(word) < 4:
        return Confidence.LOW
    
    # Is a common English word
    if word_lower in COMMON_ENGLISH_WORDS_LOWER:
        return Confidence.LOW
    
    # Ends in common non-name suffixes
    non_name_suffixes = ('ing', 'tion', 'ment', 'ness', 'able', 'ible', 'ful', 'less', 'ous', 'ive', 'ity', 'ism')
    if word_lower.endswith(non_name_suffixes):
        return Confidence.LOW
    
    # Is blacklisted
    if is_blacklisted(word):
        return Confidence.LOW
    
    # Contains numbers (unlikely for names)
    if any(c.isdigit() for c in word):
        return Confidence.LOW
    
    # All remaining cases - MEDIUM confidence
    return Confidence.MEDIUM


# =============================================================================
# PROCESSING FUNCTIONS
# =============================================================================

def preprocess_text(text: str, include_low_confidence: bool = True) -> Dict[str, Any]:
    """
    Run Tier 0 pre-annotation on raw text.
    
    Args:
        text: Raw text to analyse
        include_low_confidence: If False, exclude LOW confidence entities from results
        
    Returns:
        JSON-serialisable dict with extracted signals
    """
    if not text or not text.strip():
        return _empty_result()
    
    result = {
        "version": "0.3",
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
    result["emotion_signals"] = extract_emotion_signals(text, len(words))
    result["intensity_markers"] = extract_intensity_markers(text)
    result["question_analysis"] = analyse_questions(text, len(words))
    result["temporal_references"] = extract_temporal_refs(text)
    result["entities"] = extract_basic_entities(text, include_low_confidence=include_low_confidence)
    result["structural"] = analyse_structure(text)
    
    # Compute composite flags
    result["flags"] = compute_flags(result)
    
    return result


def _empty_result() -> Dict[str, Any]:
    """Return empty result structure for empty/null input."""
    return {
        "version": "0.3",
        "processed_at": datetime.utcnow().isoformat() + "Z",
        "word_count": 0,
        "char_count": 0,
        "emotion_signals": {"keywords_found": [], "keyword_count": 0, "keyword_density": 0.0},
        "intensity_markers": {"exclamations": 0, "all_caps_words": 0, "repeated_punctuation": 0, "intensifiers": [], "hedges": []},
        "question_analysis": {"question_count": 0, "question_density": 0.0, "self_inquiry": 0, "rhetorical_likely": 0},
        "temporal_references": {"past": [], "present": [], "future": [], "habitual": []},
        "entities": {"people": [], "phone_numbers": [], "email_addresses": [], "places": [], "organisations": []},
        "structural": {"paragraph_count": 0, "sentence_count": 0, "avg_sentence_length": 0, "longest_sentence": 0, "speaker_changes": 0},
        "flags": {"high_emotion": False, "self_reflective": False, "narrative": False, "analytical": False},
    }


def extract_emotion_signals(text: str, word_count: int) -> Dict:
    """Find emotion keywords and calculate density."""
    text_lower = text.lower()
    found = []
    categories_found = set()
    
    for category, keywords in EMOTION_KEYWORDS.items():
        for kw in keywords:
            # Use word boundary matching for single words
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


def extract_intensity_markers(text: str) -> Dict:
    """Find intensity indicators."""
    text_lower = text.lower()
    
    # Punctuation-based
    exclamations = text.count("!")
    all_caps = len([w for w in text.split() if w.isupper() and len(w) > 2 and w.isalpha()])
    repeated_punct = len(re.findall(r"[!?]{2,}", text))
    
    # Word-based
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


def analyse_questions(text: str, word_count: int) -> Dict:
    """Analyse question patterns."""
    questions = re.findall(r"[^.!?]*\?", text)
    question_count = len(questions)
    
    # Self-inquiry detection
    self_inquiry = 0
    for pattern in SELF_INQUIRY_PATTERNS:
        self_inquiry += len(re.findall(pattern, text, re.IGNORECASE))
    
    # Rhetorical detection (heuristic: short questions, or containing "really")
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


def extract_temporal_refs(text: str) -> Dict:
    """Extract temporal reference patterns."""
    result = {"past": [], "present": [], "future": [], "habitual": []}
    
    for category, patterns in TEMPORAL_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            # Flatten any tuple matches from groups
            for match in matches:
                if isinstance(match, tuple):
                    result[category].append(" ".join(match))
                else:
                    result[category].append(match)
        # Dedupe and cap
        result[category] = list(set(result[category]))[:5]
    
    return result


# Phone number patterns (AU focus with international support)
PHONE_PATTERNS = [
    # Australian formats
    r'\+61\s?4\d{2}\s?\d{3}\s?\d{3}',      # +61 4XX XXX XXX
    r'\+61\s?[23478]\s?\d{4}\s?\d{4}',     # +61 X XXXX XXXX (landline)
    r'04\d{2}\s?\d{3}\s?\d{3}',             # 04XX XXX XXX
    r'0[23478]\s?\d{4}\s?\d{4}',            # 0X XXXX XXXX (landline)
    # International formats
    r'\+1\s?\d{3}\s?\d{3}\s?\d{4}',        # US +1 XXX XXX XXXX
    r'\+44\s?\d{4}\s?\d{6}',               # UK +44 XXXX XXXXXX
    r'\+\d{1,3}\s?\d{6,12}',               # Generic international
    # Compact formats
    r'\b04\d{8}\b',                         # 04XXXXXXXX
    r'\b0[23478]\d{8}\b',                   # 0XXXXXXXXX (landline)
]

# Email pattern
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'


def extract_phone_numbers(text: str) -> List[Dict]:
    """
    Extract phone numbers with context.
    Returns list of {raw, normalised, context} dicts.
    """
    phones = []
    seen = set()
    
    for pattern in PHONE_PATTERNS:
        for match in re.finditer(pattern, text):
            raw = match.group(0)
            # Normalise: remove spaces, keep + for international
            normalised = re.sub(r'[\s\-\(\)]', '', raw)
            
            if normalised in seen:
                continue
            seen.add(normalised)
            
            # Get context (30 chars before and after)
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            
            phones.append({
                'raw': raw,
                'normalised': normalised,
                'context': context,
            })
    
    return phones


def extract_email_addresses(text: str) -> List[Dict]:
    """
    Extract email addresses with context.
    Returns list of {raw, normalised, context, domain} dicts.
    """
    emails = []
    seen = set()
    
    for match in re.finditer(EMAIL_PATTERN, text, re.IGNORECASE):
        raw = match.group(0)
        normalised = raw.lower()
        
        if normalised in seen:
            continue
        seen.add(normalised)
        
        # Extract domain
        domain = normalised.split('@')[1] if '@' in normalised else ''
        
        # Get context
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 30)
        context = text[start:end].strip()
        
        emails.append({
            'raw': raw,
            'normalised': normalised,
            'domain': domain,
            'context': context,
        })
    
    return emails


def extract_basic_entities(text: str, include_low_confidence: bool = True) -> Dict:
    """
    Entity extraction: people, phone numbers, emails.
    Now with confidence scoring for people.
    
    Args:
        text: Text to extract from
        include_low_confidence: If False, exclude LOW confidence people
    
    Returns:
        Dict with people (now includes confidence), phone_numbers, email_addresses
    """
    # Extract phones and emails
    phones = extract_phone_numbers(text)
    emails = extract_email_addresses(text)
    
    # Extract people (capitalised words, titles) with confidence
    sentences = re.split(r'[.!?]|(?<=["\'])\s+(?=[A-Z])|:\s+', text)
    people = []  # Now list of dicts with 'name' and 'confidence'
    seen_names = set()
    
    for sentence in sentences:
        words = sentence.split()
        for i, word in enumerate(words):
            at_sentence_start = (i == 0)
            
            clean = re.sub(r"[^a-zA-Z']", "", word)
            if not clean:
                continue
            
            # Skip if too short (likely abbreviation or noise)
            if len(clean) < 3:
                continue
            
            # Skip if already seen
            if clean.lower() in seen_names:
                continue
                
            # Check if capitalised
            if clean[0].isupper():
                # Case-insensitive check against non-name words
                if clean.lower() in NON_NAME_CAPITALS_LOWER:
                    continue
                
                # Skip if ALL CAPS (likely emphasis, not names)
                if clean.isupper():
                    continue
                
                # Skip if it looks like a contraction fragment
                if "'" in clean and not clean.endswith("'s"):
                    continue
                
                # Determine confidence boosters
                preceded_by_title = False
                is_title = False
                context_words = words[i+1:i+4] if i+1 < len(words) else []
                
                # Check if preceded by title
                if i > 0:
                    prev = re.sub(r"[^a-zA-Z]", "", words[i-1])
                    if prev in PEOPLE_TITLES:
                        preceded_by_title = True
                
                # Check if it IS a title (Mum, Dad, etc.)
                if clean in PEOPLE_TITLES:
                    is_title = True
                
                # Score confidence
                confidence = score_person_confidence(
                    clean,
                    preceded_by_title=preceded_by_title,
                    is_title=is_title,
                    context_words=context_words
                )
                
                # Sentence-start names get downgraded (could just be capitalised word)
                if at_sentence_start and confidence == Confidence.MEDIUM:
                    confidence = Confidence.LOW
                
                # Skip low confidence if requested
                if not include_low_confidence and confidence == Confidence.LOW:
                    continue
                
                # Add to results
                seen_names.add(clean.lower())
                people.append({
                    'name': clean,
                    'confidence': confidence,
                })
    
    # Sort by confidence (high first) and limit
    confidence_order = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}
    people.sort(key=lambda p: confidence_order.get(p['confidence'], 2))
    people = people[:15]  # Increased limit since we have confidence now
    
    return {
        "people": people,
        "phone_numbers": phones[:20],
        "email_addresses": emails[:20],
        "places": [],  # Would need NER for reliable place detection
        "organisations": [],
    }


def analyse_structure(text: str) -> Dict:
    """Analyse text structure."""
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    sentence_lengths = [len(s.split()) for s in sentences]
    
    # Count speaker changes (for chat transcripts)
    speaker_changes = 0
    speaker_patterns = [
        r"\*\*Me:\*\*", r"\*\*User:\*\*", r"\*\*Assistant:\*\*",
        r"^Me:", r"^You:", r"^User:", r"^Assistant:",
        r"<USER_MESSAGE>", r"<ASSISTANT_MESSAGE>",
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


def compute_flags(result: Dict) -> Dict:
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


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def summarise_for_prompt(pre_annotation: Dict) -> str:
    """
    Generate a human-readable summary of pre-annotation for LLM prompts.
    
    Args:
        pre_annotation: Output from preprocess_text()
        
    Returns:
        Formatted string for inclusion in extraction prompts
    """
    parts = []
    
    # Emotion signals
    if pre_annotation.get("emotion_signals", {}).get("keywords_found"):
        keywords = pre_annotation["emotion_signals"]["keywords_found"][:5]
        parts.append(f"Emotion keywords: {', '.join(keywords)}")
    
    if pre_annotation.get("emotion_signals", {}).get("categories"):
        cats = pre_annotation["emotion_signals"]["categories"][:3]
        parts.append(f"Emotion categories: {', '.join(cats)}")
    
    # Flags
    flags = pre_annotation.get("flags", {})
    active_flags = [k.replace("_", " ") for k, v in flags.items() if v]
    if active_flags:
        parts.append(f"Flags: {', '.join(active_flags)}")
    
    # Temporal
    if pre_annotation.get("temporal_references", {}).get("past"):
        past_refs = pre_annotation["temporal_references"]["past"][:3]
        parts.append(f"Past references: {', '.join(past_refs)}")
    
    # People - now with confidence
    people = pre_annotation.get("entities", {}).get("people", [])
    if people:
        # Filter to HIGH/MEDIUM for prompt summary
        good_people = [p['name'] if isinstance(p, dict) else p for p in people 
                       if not isinstance(p, dict) or p.get('confidence') != 'low'][:5]
        if good_people:
            parts.append(f"People mentioned: {', '.join(good_people)}")
    
    # Phone numbers
    phones = pre_annotation.get("entities", {}).get("phone_numbers", [])
    if phones:
        phone_strs = [p.get('normalised', p.get('raw', '?')) for p in phones[:5]]
        parts.append(f"Phone numbers: {', '.join(phone_strs)}")
    
    # Email addresses
    emails = pre_annotation.get("entities", {}).get("email_addresses", [])
    if emails:
        email_strs = [e.get('normalised', e.get('raw', '?')) for e in emails[:5]]
        parts.append(f"Email addresses: {', '.join(email_strs)}")
    
    # Intensity
    intensity = pre_annotation.get("intensity_markers", {})
    if intensity.get("exclamations", 0) >= 2:
        parts.append(f"High exclamation count: {intensity['exclamations']}")
    if intensity.get("absolutes"):
        parts.append(f"Absolute statements: {', '.join(intensity['absolutes'][:3])}")
    
    # Questions
    questions = pre_annotation.get("question_analysis", {})
    if questions.get("self_inquiry", 0) >= 1:
        parts.append(f"Self-inquiry questions: {questions['self_inquiry']}")
    
    if not parts:
        return "No significant signals detected."
    
    return "\n".join(f"- {p}" for p in parts)


def get_low_confidence_entities(pre_annotation: Dict) -> List[Dict]:
    """
    Extract entities that need LLM validation (LOW confidence).
    
    Returns list of entities for Tier 0.5 validation.
    """
    people = pre_annotation.get("entities", {}).get("people", [])
    return [p for p in people if isinstance(p, dict) and p.get('confidence') == 'low']


def to_json(pre_annotation: Dict) -> str:
    """Serialise pre-annotation to JSON string for database storage."""
    return json.dumps(pre_annotation, ensure_ascii=False)


def from_json(json_str: str) -> Optional[Dict]:
    """Deserialise pre-annotation from JSON string."""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


# =============================================================================
# PROCESSOR CLASS (for consistency with other modules)
# =============================================================================

class Tier0Processor:
    """Wrapper class for Tier 0 processing (stateless)."""
    
    @staticmethod
    def process(text: str, include_low_confidence: bool = True) -> Dict[str, Any]:
        """Process text and return pre-annotation."""
        return preprocess_text(text, include_low_confidence=include_low_confidence)
    
    @staticmethod
    def summarise(pre_annotation: Dict) -> str:
        """Summarise pre-annotation for prompts."""
        return summarise_for_prompt(pre_annotation)
    
    @staticmethod
    def get_entities_for_validation(pre_annotation: Dict) -> List[Dict]:
        """Get LOW confidence entities that need LLM validation."""
        return get_low_confidence_entities(pre_annotation)


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Classes
    "Tier0Processor",
    "Confidence",
    # Main functions
    "preprocess_text",
    "summarise_for_prompt",
    "get_low_confidence_entities",
    "to_json",
    "from_json",
    # Extraction functions
    "extract_phone_numbers",
    "extract_email_addresses",
    "extract_basic_entities",
    "extract_emotion_signals",
    "extract_intensity_markers",
    "analyse_questions",
    "extract_temporal_refs",
    "analyse_structure",
    "compute_flags",
    "score_person_confidence",
    # Blacklist functions
    "load_blacklist_from_db",
    "add_to_blacklist",
    "is_blacklisted",
    "get_blacklist",
    # Constants
    "EMOTION_KEYWORDS",
    "INTENSIFIERS",
    "HEDGES",
    "ABSOLUTES",
    "PHONE_PATTERNS",
    "EMAIL_PATTERN",
    "NON_NAME_CAPITALS",
    "NON_NAME_CAPITALS_LOWER",
    "COMMON_ENGLISH_WORDS",
    "COMMON_ENGLISH_WORDS_LOWER",
    "PEOPLE_TITLES",
]
