"""
ReCog Engine - Tier 0 Pre-Annotation Processor v0.4

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

Zero-LLM-cost signal extraction from raw text.
Runs on every document/chunk to flag emotion markers, intensity,
entities, temporal references, and question patterns.

This is the FREE processing tier - no API calls required.

v0.4 Changes:
- Full name extraction (multi-word names like "Dr. Sarah Smith")
- Organisation detection (companies, institutions, foundations)
- Location/address detection (street addresses, cities)
- Date/time extraction (multiple formats, normalised)
- Currency/amount detection (multiple currencies)

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
    "Mr", "Mrs", "Ms", "Dr", "Prof", "Rev",  # Abbreviated forms
    "Mum", "Mom", "Dad", "Father", "Mother",
    "Uncle", "Aunt", "Grandma", "Grandpa", "Gran", "Pop", "Nan",
    "Brother", "Sister", "Son", "Daughter", "Wife", "Husband",
    "Boss", "Manager", "Teacher", "Coach", "Therapist", "Professor",
    "Officer", "Detective", "Sergeant", "Captain", "Pastor", "Reverend",
    "Sir", "Dame", "Lord", "Lady",  # Formal titles
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
    # US cities
    "Seattle", "Chicago", "Boston", "Denver", "Portland", "Austin", "Dallas",
    "Houston", "Phoenix", "Miami", "Atlanta", "Detroit", "Minneapolis",
    "Philadelphia", "Baltimore", "Washington", "Cleveland", "Pittsburgh",
    "Cincinnati", "Nashville", "Charlotte", "Tampa", "Orlando", "Vegas",
    "Francisco", "Angeles", "Diego", "Jose", "York", "Jersey",
    # Other major cities
    "Toronto", "Vancouver", "Montreal", "Dublin", "Edinburgh", "Manchester",
    "Amsterdam", "Brussels", "Madrid", "Barcelona", "Rome", "Milan", "Vienna",
    "Munich", "Hamburg", "Stockholm", "Oslo", "Copenhagen", "Helsinki",
    "Singapore", "Bangkok", "Seoul", "Beijing", "Shanghai", "Mumbai", "Delhi",
    
    # Common nouns that get capitalised
    "OK", "Yes", "No", "Maybe", "Please", "Thanks", "Sorry", "Hello", "Hi",
    "Goodbye", "Bye", "Well", "Right", "Sure", "True", "False",
    "God", "Christmas", "Easter", "New", "Year", "Years",
    # Business/project terms often capitalised
    "Project", "Phase", "Stage", "Task", "Meeting", "Report", "Update",
    "Review", "Analysis", "Research", "Study", "Plan", "Goal", "Target",
    "Team", "Group", "Department", "Division", "Unit", "Office", "Branch",
    "Date", "Deadline", "Schedule", "Timeline", "Milestone", "Objective",
    "Budget", "Cost", "Price", "Rate", "Fee", "Proposal", "Contract",
    "Document", "File", "Folder", "Record", "Note", "Notes", "Summary",
    "Issue", "Problem", "Solution", "Action", "Item", "Items", "List",
    "Status", "Progress", "Result", "Results", "Outcome", "Findings",
    "Section", "Chapter", "Part", "Volume", "Edition", "Version",
    "Table", "Figure", "Chart", "Graph", "Diagram", "Image", "Photo",
    "Appendix", "Reference", "Source", "Citation", "Bibliography",
    # Research/academic terms
    "Hypothesis", "Theory", "Method", "Methodology", "Protocol",
    "Experiment", "Trial", "Test", "Sample", "Data", "Dataset",
    "Variable", "Factor", "Parameter", "Metric", "Measure", "Index",
    "Subject", "Participant", "Respondent", "Patient", "Client",
    "Conclusion", "Discussion", "Abstract", "Introduction", "Background",
    "Interviewer", "Interviewee", "Cohort", "Site", "Control", "Baseline",
    "Outcome", "Endpoint", "Population", "Subset", "Group", "Arm",
    # Compass/direction words that might be project names
    "Meridian", "Horizon", "Summit", "Peak", "Aurora", "Eclipse", "Zenith",
    "Compass", "Beacon", "Pioneer", "Frontier", "Gateway", "Pathway",
    # Common building/room terms
    "Conference", "Room", "Building", "Floor", "Hall", "Lobby", "Suite",
    "Tower", "Center", "Centre", "Campus", "Complex", "Facility", "Station",
    "Library", "Museum", "Gallery", "Theater", "Theatre", "Arena", "Stadium",
    "Hospital", "Clinic", "School", "University", "College", "Academy",
    "Church", "Temple", "Mosque", "Cathedral", "Chapel",

    # Institutional/organizational terms (often capitalized but not names)
    "Foundation", "Institute", "Organization", "Organisation", "Society",
    "Association", "Corporation", "Company", "Enterprise", "Agency",
    "Board", "Committee", "Council", "Panel", "Commission", "Authority",
    "Program", "Programme", "Project", "Initiative", "Campaign", "Movement",
    "Fund", "Trust", "Endowment", "Grant", "Donation", "Charity",
    "Award", "Prize", "Fellowship", "Scholarship", "Medal", "Honor", "Honour",
    "Network", "Alliance", "Coalition", "Federation", "Union", "League",
    "Ministry", "Embassy", "Consulate", "Bureau", "Administration",
    "Service", "Services", "Support", "Solutions", "Systems", "Technologies",
    "Research", "Development", "Innovation", "Strategy", "Operations",
    "Marketing", "Communications", "Relations", "Affairs", "Resources",
    "Management", "Consulting", "Advisory", "Partners", "Associates",
    "International", "National", "Regional", "Local", "Global", "Worldwide",
    "Annual", "Monthly", "Weekly", "Daily", "Quarterly",
    # More common words that appear capitalised
    "Street", "Avenue", "Road", "Lane", "Drive", "Boulevard", "Way", "Place",
    "Park", "Garden", "Square", "Plaza", "Court", "Circle", "Terrace",
    "North", "South", "East", "West", "Central", "Downtown", "Uptown",
    
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

    # Additional institutional/organizational terms (lowercase)
    "foundation", "institute", "research", "development", "association",
    "organization", "organisation", "committee", "council", "board",
    "program", "programme", "initiative", "campaign", "project",
    "fund", "trust", "grant", "award", "prize", "fellowship",
    "network", "alliance", "coalition", "federation", "union",
    "service", "services", "support", "solutions", "systems",
    "management", "consulting", "advisory", "partners", "associates",
    "international", "national", "regional", "local", "global",
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
# DATE/TIME EXTRACTION
# =============================================================================

# Common date formats
DATE_PATTERNS = [
    # ISO format: 2024-01-15, 2024/01/15
    r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',
    # US format: 01/15/2024, 1/15/24
    r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',
    # UK/AU format: 15/01/2024
    r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',
    # Written: January 15, 2024 or 15 January 2024
    r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[,]?\s+\d{4})\b',
    r'\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?[,]?\s+\d{4})\b',
    # Month and year: January 2024, Jan 2024
    r'\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})\b',
    # Just month and day: January 15, Jan 15th
    r'\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?)\b',
]

TIME_PATTERNS = [
    # 24-hour: 14:30, 09:00
    r'\b(\d{1,2}:\d{2}(?::\d{2})?)\b',
    # 12-hour: 2:30pm, 9:00 AM
    r'\b(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))\b',
    # Written: 2pm, 9 am
    r'\b(\d{1,2}\s*(?:am|pm|AM|PM))\b',
]


def extract_dates(text: str) -> List[Dict]:
    """
    Extract date references from text.
    Returns list of {raw, type, context} dicts.
    """
    dates = []
    seen = set()

    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw = match.group(1) if match.groups() else match.group(0)
            normalised = raw.strip()

            if normalised.lower() in seen:
                continue
            seen.add(normalised.lower())

            # Get context
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            dates.append({
                'raw': raw,
                'normalised': normalised,
                'context': context,
            })

    return dates[:20]


def extract_times(text: str) -> List[Dict]:
    """
    Extract time references from text.
    Returns list of {raw, context} dicts.
    """
    times = []
    seen = set()

    for pattern in TIME_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw = match.group(1) if match.groups() else match.group(0)
            normalised = raw.strip().lower()

            if normalised in seen:
                continue
            seen.add(normalised)

            # Get context
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            times.append({
                'raw': raw,
                'normalised': normalised,
                'context': context,
            })

    return times[:20]


# =============================================================================
# CURRENCY/AMOUNT EXTRACTION
# =============================================================================

CURRENCY_PATTERNS = [
    # Dollar amounts: $100, $1,234.56, $1.5M
    r'(\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?:\s*[KkMmBb](?:illion)?)?)',
    # Euro amounts: €100, EUR 100
    r'(€\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?:\s*[KkMmBb](?:illion)?)?)',
    r'(EUR\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    # Pound amounts: £100, GBP 100
    r'(£\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?:\s*[KkMmBb](?:illion)?)?)',
    r'(GBP\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    # AUD amounts: AUD 100, A$100
    r'(A\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    r'(AUD\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    # Written amounts: 100 dollars, 50 euros
    r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|USD|euros?|pounds?|yen))',
]


def extract_currency(text: str) -> List[Dict]:
    """
    Extract currency/monetary amounts from text.
    Returns list of {raw, normalised, context} dicts.
    """
    amounts = []
    seen = set()

    for pattern in CURRENCY_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw = match.group(1) if match.groups() else match.group(0)
            normalised = raw.strip()

            if normalised.lower() in seen:
                continue
            seen.add(normalised.lower())

            # Get context
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            amounts.append({
                'raw': raw,
                'normalised': normalised,
                'context': context,
            })

    return amounts[:20]


# =============================================================================
# ORGANISATION DETECTION
# =============================================================================

# Common organisation suffixes
ORG_SUFFIXES = [
    'Inc', 'Inc.', 'LLC', 'Ltd', 'Ltd.', 'Corp', 'Corp.', 'Corporation',
    'Co', 'Co.', 'Company', 'Companies',
    'Group', 'Holdings', 'Partners', 'Associates',
    'Foundation', 'Institute', 'University', 'College', 'School',
    'Hospital', 'Clinic', 'Medical', 'Health',
    'Bank', 'Financial', 'Insurance', 'Capital',
    'Technologies', 'Tech', 'Software', 'Systems', 'Solutions',
    'Services', 'Consulting', 'Advisory',
    'Media', 'Entertainment', 'Studios', 'Productions',
    'Industries', 'Manufacturing', 'Enterprises',
    'Association', 'Society', 'Organization', 'Organisation',
    'Agency', 'Bureau', 'Department', 'Ministry',
    'Council', 'Committee', 'Board', 'Commission',
    'Network', 'Alliance', 'Coalition', 'Federation',
    'Trust', 'Fund', 'Charity',
    'Pty', 'Pty.', 'PLC', 'GmbH', 'AG', 'SA', 'NV', 'BV',
]

# Known organisation patterns (regex)
ORG_PATTERNS = [
    # "The X Foundation/Institute/etc"
    r'(?:The\s+)?([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Foundation|Institute|University|College|Hospital|Association|Society|Agency|Bureau|Council|Committee|Board|Trust|Fund))',
    # "X Inc/Ltd/Corp/etc"
    r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Corporation|Company|Co\.?|Group|Holdings|Partners|Pty\.?\s*Ltd\.?))',
    # "X Bank/Financial/Insurance"
    r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Bank|Financial|Insurance|Capital))',
    # "X Technologies/Tech/Software/Systems"
    r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Technologies|Tech|Software|Systems|Solutions|Services))',
]


def extract_organisations(text: str) -> List[Dict]:
    """
    Extract organisation names from text.
    Returns list of {raw, normalised, confidence, context} dicts.
    """
    orgs = []
    seen = set()

    # Pattern-based extraction
    for pattern in ORG_PATTERNS:
        for match in re.finditer(pattern, text):
            raw = match.group(1) if match.groups() else match.group(0)
            normalised = raw.strip()

            if normalised.lower() in seen:
                continue
            seen.add(normalised.lower())

            # Get context
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            orgs.append({
                'raw': raw,
                'normalised': normalised,
                'confidence': 'high',
                'context': context,
            })

    # Also scan for "at/for/with [Org]" patterns
    work_patterns = [
        r'(?:work(?:s|ed|ing)?\s+(?:at|for)|join(?:s|ed|ing)?\s+|left\s+|from\s+)([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})',
    ]

    for pattern in work_patterns:
        for match in re.finditer(pattern, text):
            raw = match.group(1)
            normalised = raw.strip()

            # Skip if it's a known non-org word
            if normalised.lower() in NON_NAME_CAPITALS_LOWER:
                continue
            if normalised.lower() in seen:
                continue

            # Check if it ends with org suffix
            words = normalised.split()
            if words and words[-1] in ORG_SUFFIXES:
                seen.add(normalised.lower())

                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()

                orgs.append({
                    'raw': raw,
                    'normalised': normalised,
                    'confidence': 'medium',
                    'context': context,
                })

    return orgs[:15]


# =============================================================================
# LOCATION/ADDRESS DETECTION
# =============================================================================

# Street type indicators
STREET_TYPES = [
    'Street', 'St', 'St.', 'Avenue', 'Ave', 'Ave.', 'Road', 'Rd', 'Rd.',
    'Drive', 'Dr', 'Dr.', 'Lane', 'Ln', 'Ln.', 'Boulevard', 'Blvd', 'Blvd.',
    'Way', 'Place', 'Pl', 'Pl.', 'Court', 'Ct', 'Ct.', 'Circle', 'Cir',
    'Terrace', 'Tce', 'Highway', 'Hwy', 'Parkway', 'Pkwy',
    'Crescent', 'Cres', 'Close', 'Grove', 'Gardens',
]

ADDRESS_PATTERNS = [
    # Street address: 123 Main Street, 456 Oak Ave
    r'(\d{1,5}\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?\s+(?:' + '|'.join(STREET_TYPES) + r'))',
    # PO Box
    r'(P\.?O\.?\s*Box\s+\d+)',
    # Suite/Unit/Apt
    r'((?:Suite|Unit|Apt\.?|Apartment)\s+\d+[A-Za-z]?)',
]

# Postcode patterns by country
POSTCODE_PATTERNS = [
    # Australian: 3000, 2000
    r'\b(\d{4})\b(?=\s*(?:Australia|AU|VIC|NSW|QLD|SA|WA|TAS|NT|ACT)?)',
    # US ZIP: 12345, 12345-6789
    r'\b(\d{5}(?:-\d{4})?)\b',
    # UK: SW1A 1AA
    r'\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b',
]


def extract_locations(text: str) -> List[Dict]:
    """
    Extract location references (addresses, places) from text.
    Returns list of {raw, type, confidence, context} dicts.
    """
    locations = []
    seen = set()

    # Extract street addresses
    for pattern in ADDRESS_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw = match.group(1) if match.groups() else match.group(0)
            normalised = raw.strip()

            if normalised.lower() in seen:
                continue
            seen.add(normalised.lower())

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            locations.append({
                'raw': raw,
                'normalised': normalised,
                'type': 'address',
                'confidence': 'high',
                'context': context,
            })

    # Extract "in/at/from [City]" patterns
    location_indicators = [
        r'(?:in|at|from|to|near|around|visited?|moved?\s+to|live[sd]?\s+in)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)',
    ]

    # Known cities for validation
    known_cities = {
        'melbourne', 'sydney', 'brisbane', 'perth', 'adelaide', 'hobart', 'darwin', 'canberra',
        'london', 'paris', 'tokyo', 'berlin', 'rome', 'madrid', 'amsterdam', 'vienna',
        'new york', 'los angeles', 'chicago', 'houston', 'phoenix', 'philadelphia',
        'san antonio', 'san diego', 'dallas', 'san francisco', 'seattle', 'boston',
        'toronto', 'vancouver', 'montreal', 'dublin', 'edinburgh', 'manchester',
        'singapore', 'hong kong', 'bangkok', 'seoul', 'mumbai', 'delhi', 'beijing', 'shanghai',
    }

    for pattern in location_indicators:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            raw = match.group(1)
            normalised = raw.strip()

            # Check if it's a known city
            if normalised.lower() in known_cities:
                if normalised.lower() in seen:
                    continue
                seen.add(normalised.lower())

                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()

                locations.append({
                    'raw': raw,
                    'normalised': normalised,
                    'type': 'city',
                    'confidence': 'high',
                    'context': context,
                })

    return locations[:15]


# =============================================================================
# FULL NAME EXTRACTION
# =============================================================================

def extract_full_names(text: str, include_low_confidence: bool = True) -> List[Dict]:
    """
    Extract full names (multi-word) from text with confidence scoring.
    Handles patterns like "Dr. Sarah Smith", "John Smith", "Mary Jane Watson".

    Returns list of {name, confidence, components} dicts.
    """
    # Protect abbreviations from sentence splitting
    abbrev_pattern = r'\b(Dr|Mr|Mrs|Ms|Prof|Rev|Sr|Jr|St|Lt|Sgt|Capt|Gen|Col|Maj|Mt|Ave|Blvd|Apt|Dept|Inc|Corp|Ltd|vs|etc|e\.g|i\.e)\.'
    protected_text = re.sub(abbrev_pattern, r'\1<DOT>', text, flags=re.IGNORECASE)  # Use marker

    # Split into sentences
    sentences = re.split(r'[.!?]|(?<=["\'])\s+(?=[A-Z])|:\s+', protected_text)

    names = []
    seen_names = set()

    for sentence in sentences:
        # Restore periods after titles for processing
        sentence = sentence.replace('<DOT>', '.')
        words = sentence.split()

        i = 0
        while i < len(words):
            word = words[i]
            clean = re.sub(r"[^a-zA-Z'.]", "", word)

            if not clean or len(clean) < 2:
                i += 1
                continue

            # Check if this starts a potential name sequence
            # (title or capitalized word)
            is_title = clean.rstrip('.') in PEOPLE_TITLES
            is_capitalized = clean[0].isupper() and not clean.isupper()

            if not (is_title or is_capitalized):
                i += 1
                continue

            # Skip if in NON_NAME_CAPITALS
            if clean.lower().rstrip('.') in NON_NAME_CAPITALS_LOWER:
                if not is_title:  # Titles are ok
                    i += 1
                    continue

            # Collect consecutive capitalized words
            name_parts = []
            title_part = None
            j = i

            # If starts with title, record it
            if is_title:
                title_part = clean.rstrip('.')
                j += 1

            # Collect capitalized name words
            while j < len(words):
                next_word = words[j]
                next_clean = re.sub(r"[^a-zA-Z']", "", next_word)

                if not next_clean or len(next_clean) < 2:
                    break

                # Must be capitalized (not all caps)
                if not (next_clean[0].isupper() and not next_clean.isupper()):
                    break

                # Skip if non-name word
                if next_clean.lower() in NON_NAME_CAPITALS_LOWER:
                    break

                # Skip if organisation suffix (likely end of org name, not person)
                if next_clean in ORG_SUFFIXES:
                    break

                # Skip if common English word
                if next_clean.lower() in COMMON_ENGLISH_WORDS_LOWER:
                    break

                # Skip words ending with common non-name suffixes
                non_name_suffixes = ('ing', 'tion', 'ment', 'ness', 'able', 'ible', 'ful', 'less', 'ous', 'ive', 'ity', 'ism')
                if next_clean.lower().endswith(non_name_suffixes):
                    break

                name_parts.append(next_clean)
                j += 1

                # Limit to reasonable name length (4 parts max)
                if len(name_parts) >= 4:
                    break

            # Build the full name
            if name_parts:
                full_name = ' '.join(name_parts)
                full_name_with_title = f"{title_part} {full_name}" if title_part else full_name

                # Skip if already seen
                if full_name.lower() in seen_names:
                    i = j
                    continue

                # Skip if blacklisted
                if is_blacklisted(full_name):
                    i = j
                    continue

                # Score confidence
                at_sentence_start = (i == 0)
                confidence = Confidence.HIGH if title_part else Confidence.MEDIUM

                # Boost confidence for multi-part names
                if len(name_parts) >= 2 and not title_part:
                    confidence = Confidence.HIGH

                # Downgrade sentence-start single names
                if at_sentence_start and len(name_parts) == 1 and not title_part:
                    confidence = Confidence.LOW

                # Skip low confidence if requested
                if not include_low_confidence and confidence == Confidence.LOW:
                    i = j
                    continue

                seen_names.add(full_name.lower())
                names.append({
                    'name': full_name_with_title,
                    'confidence': confidence,
                    'components': {
                        'title': title_part,
                        'name_parts': name_parts,
                    }
                })
            elif title_part and not name_parts:
                # Just a title (Mum, Dad, etc.) - these are valid
                if title_part.lower() not in seen_names:
                    # Skip honorifics alone (Mr, Dr, etc without following name)
                    honorifics = {"Mr", "Mrs", "Ms", "Dr", "Prof", "Rev", "Sir", "Dame",
                                  "Lord", "Lady", "Officer", "Detective", "Sergeant",
                                  "Captain", "Pastor", "Reverend", "Professor"}
                    if title_part not in honorifics:
                        seen_names.add(title_part.lower())
                        names.append({
                            'name': title_part,
                            'confidence': Confidence.HIGH,
                            'components': {
                                'title': title_part,
                                'name_parts': [],
                            }
                        })

            i = j if j > i else i + 1

    # Sort by confidence (high first)
    confidence_order = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}
    names.sort(key=lambda n: confidence_order.get(n['confidence'], 2))

    return names[:15]


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
        "version": "0.4",
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
        "version": "0.4",
        "processed_at": datetime.utcnow().isoformat() + "Z",
        "word_count": 0,
        "char_count": 0,
        "emotion_signals": {"keywords_found": [], "keyword_count": 0, "keyword_density": 0.0},
        "intensity_markers": {"exclamations": 0, "all_caps_words": 0, "repeated_punctuation": 0, "intensifiers": [], "hedges": []},
        "question_analysis": {"question_count": 0, "question_density": 0.0, "self_inquiry": 0, "rhetorical_likely": 0},
        "temporal_references": {"past": [], "present": [], "future": [], "habitual": [], "dates": [], "times": []},
        "entities": {"people": [], "phone_numbers": [], "email_addresses": [], "locations": [], "organisations": [], "currency": []},
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
    """Extract temporal reference patterns including specific dates and times."""
    result = {"past": [], "present": [], "future": [], "habitual": [], "dates": [], "times": []}

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

    # Extract specific dates and times
    result["dates"] = extract_dates(text)
    result["times"] = extract_times(text)

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
    Entity extraction: people (full names), organisations, locations, phone numbers, emails, currency.
    Uses confidence scoring for people and organisations.

    Args:
        text: Text to extract from
        include_low_confidence: If False, exclude LOW confidence entities

    Returns:
        Dict with people, organisations, locations, phone_numbers, email_addresses, currency
    """
    # Extract phones, emails, and currency
    phones = extract_phone_numbers(text)
    emails = extract_email_addresses(text)
    currency = extract_currency(text)

    # Extract organisations and locations
    organisations = extract_organisations(text)
    locations = extract_locations(text)

    # Extract full names (multi-word) with confidence scoring
    people = extract_full_names(text, include_low_confidence=include_low_confidence)

    return {
        "people": people,
        "phone_numbers": phones[:20],
        "email_addresses": emails[:20],
        "locations": locations,
        "organisations": organisations,
        "currency": currency,
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

    # Dates
    dates = pre_annotation.get("temporal_references", {}).get("dates", [])
    if dates:
        date_strs = [d.get('normalised', d.get('raw', '?')) for d in dates[:5]]
        parts.append(f"Dates mentioned: {', '.join(date_strs)}")

    # People - now with full names and confidence
    people = pre_annotation.get("entities", {}).get("people", [])
    if people:
        # Filter to HIGH/MEDIUM for prompt summary
        good_people = [p['name'] if isinstance(p, dict) else p for p in people
                       if not isinstance(p, dict) or p.get('confidence') != 'low'][:5]
        if good_people:
            parts.append(f"People mentioned: {', '.join(good_people)}")

    # Organisations
    orgs = pre_annotation.get("entities", {}).get("organisations", [])
    if orgs:
        org_names = [o.get('normalised', o.get('raw', '?')) for o in orgs[:5]]
        parts.append(f"Organisations: {', '.join(org_names)}")

    # Locations
    locations = pre_annotation.get("entities", {}).get("locations", [])
    if locations:
        loc_names = [loc.get('normalised', loc.get('raw', '?')) for loc in locations[:5]]
        parts.append(f"Locations: {', '.join(loc_names)}")

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

    # Currency amounts
    currency = pre_annotation.get("entities", {}).get("currency", [])
    if currency:
        currency_strs = [c.get('normalised', c.get('raw', '?')) for c in currency[:5]]
        parts.append(f"Currency amounts: {', '.join(currency_strs)}")

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
    # New v0.4 extraction functions
    "extract_full_names",
    "extract_organisations",
    "extract_locations",
    "extract_dates",
    "extract_times",
    "extract_currency",
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
    "ORG_SUFFIXES",
    "STREET_TYPES",
    "DATE_PATTERNS",
    "TIME_PATTERNS",
    "CURRENCY_PATTERNS",
]
