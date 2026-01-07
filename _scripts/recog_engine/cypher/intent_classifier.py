"""
Cypher Intent Classification
Hybrid approach: regex patterns first, LLM fallback for ambiguous cases
"""

import re
import json
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Intent definitions
INTENTS = {
    "entity_correction": "Remove/reclassify entity",
    "entity_validation": "Validate entities with AI",
    "entity_validation_confirm": "Confirm/reject validation suggestions",
    "filter_request": "Show subset of data",
    "navigation": "Go to specific page/view",
    "analysis_query": "Answer question about data",
    "processing_control": "Start/stop/pause extraction",
    "clarification": "Explain something",
    "file_upload": "Add documents to case",
    "pattern_feedback": "Confirm/reject suggested pattern",
}

# Regex patterns for intent classification (fast, free)
# ORDER MATTERS: navigation must come before filter_request to avoid "show me entities" matching filter
INTENT_PATTERNS = {
    "entity_correction": [
        # "X isn't a person/name/entity"
        r"['\"]?(\w+)['\"]?\s+(isn't|is not|ain't|isnt)\s+(a\s+|an\s+)?(person|name|entity)",
        # "X is our/a/the intranet/system/tool/company/project"
        r"['\"]?(\w+)['\"]?\s+is\s+(our|a|an|the)\s+(intranet|system|tool|company|project|product|software|platform|website|app)",
        # "remove X from entities"
        r"remove\s+['\"]?(\w+)['\"]?\s+from\s+(entities|registry|list)",
        # "X should be a location/organization/system"
        r"['\"]?(\w+)['\"]?\s+should\s+be\s+(a\s+|an\s+)?(location|organization|system|place|company)",
        # "X is not a name"
        r"['\"]?(\w+)['\"]?\s+(is\s+)?not\s+a\s+(name|person|entity)",
        # "that's not a person" (referring to previously mentioned entity)
        r"that('s|\s+is)\s+not\s+a\s+(person|name|entity)",
        # "exclude X"
        r"exclude\s+['\"]?(\w+)['\"]?",
        # "blacklist X"
        r"blacklist\s+['\"]?(\w+)['\"]?",
    ],
    "entity_validation": [
        # "validate entities" / "check entities"
        r"(validate|check|review|clean\s*up)\s+(the\s+)?(entities|names|people)",
        # "find false positives"
        r"find\s+(false\s+positives?|bad\s+entities|wrong\s+names)",
        # "clean up entities"
        r"clean\s*up\s+(the\s+)?(entities|names|entity\s+list)",
        # "AI validate"
        r"(ai|llm)\s+validat",
    ],
    "entity_validation_confirm": [
        # "yes remove them/those" / "remove those"
        r"(yes,?\s+)?(remove|delete)\s+(them|those|all)",
        # "keep X" / "X is a name" / "X is valid"
        r"keep\s+['\"]?(\w+)['\"]?",
        r"['\"]?(\w+)['\"]?\s+is\s+(a\s+)?(valid\s+)?(name|person)",
        # "confirm (the) removal"
        r"confirm\s+(the\s+)?removal",
        # "looks good" / "that's correct"
        r"(looks?\s+good|that('s|\s+is)\s+(correct|right))",
        # "no, keep them"
        r"no,?\s+keep\s+(them|those|all)",
    ],
    "navigation": [
        # "show me (the) entities/insights/timeline" - MUST come before filter_request
        r"show\s+me\s+(the\s+)?(timeline|findings?|entities?|insights?|dashboard|cases?|patterns?|upload|preflight)",
        # "show/open/go to (me) (the) X page/view/tab"
        r"(show|open|go\s+to)\s+(me\s+)?(the\s+)?(\w+)\s+(page|view|tab)",
        # "take me to / navigate to X"
        r"(take\s+me\s+to|navigate\s+to)\s+['\"]?(\w+)['\"]?",
        # "view/see (the) timeline/findings/entities/insights"
        r"(view|see)\s+(the\s+)?(timeline|findings?|entities?|insights?|dashboard|cases?|patterns?)",
        # "go to X"
        r"go\s+to\s+['\"]?(\w+)['\"]?",
        # "open X"
        r"open\s+['\"]?(\w+)['\"]?",
    ],
    "filter_request": [
        # "focus on X" / "filter by X" (NOT just "show X" - that's ambiguous)
        r"(focus\s+on|filter\s+by)\s+['\"]?(\w+)['\"]?",
        # "only show (me) X"
        r"(only|just)\s+show\s+(me\s+)?['\"]?(\w+)['\"]?",
        # "documents/insights/entities about/from/related to X"
        r"(documents?|insights?|entities?)\s+(about|from|related\s+to|mentioning|involving)\s+['\"]?(\w+)['\"]?",
        # "find X"
        r"find\s+['\"]?(.+?)['\"]?(?:\s|$)",
        # "search for X"
        r"search\s+(?:for\s+)?['\"]?(.+?)['\"]?(?:\s|$)",
    ],
    "analysis_query": [
        # "are there / show me / find ... gaps/patterns/anomalies"
        r"(are\s+there|show\s+me|find)\s+.*(gaps?|patterns?|anomalies?|issues?)",
        # "what happened/occurred/changed in/on/during X"
        r"what\s+(happened|occurred|changed)\s+(in|on|during)\s+(\w+)",
        # "who is/was involved/mentioned/responsible"
        r"who\s+(is|was)\s+(involved|mentioned|responsible)",
        # "how many X"
        r"how\s+many\s+(\w+)",
        # "when did X"
        r"when\s+did\s+(.+)",
        # "summarize X"
        r"summarize\s+(.+)",
        # "what are the X"
        r"what\s+are\s+the\s+(\w+)",
    ],
    "processing_control": [
        # "start/begin analysis/processing/extraction"
        r"(start|begin|run)\s+(analysis|processing|extraction)",
        # "stop/pause/cancel processing"
        r"(stop|pause|cancel)\s+(processing|extraction|analysis)",
        # "process these/the documents"
        r"process\s+(these|the|my)\s+documents?",
    ],
    "file_upload": [
        # "analyze/process/upload/add (these/the) documents"
        r"(analyze|process|upload|add)\s+(these\s+|the\s+)?documents?",
        # "I've uploaded X"
        r"(i've|i\s+have)\s+uploaded",
        # "here are (the) files"
        r"here\s+are\s+(the\s+)?files?",
    ],
    "pattern_feedback": [
        # "that pattern is correct/wrong"
        r"that\s+pattern\s+is\s+(correct|wrong|right|incorrect)",
        # "yes, that's right / no, that's wrong"
        r"(yes|no),?\s+that('s|\s+is)\s+(right|wrong|correct|incorrect)",
        # "confirm/reject pattern"
        r"(confirm|reject)\s+(the\s+)?pattern",
    ],
}


def extract_entities_from_match(pattern: str, message: str, intent: str) -> Dict[str, Any]:
    """Extract relevant entities from a regex match"""
    match = re.search(pattern, message, re.IGNORECASE)
    if not match:
        return {}

    groups = match.groups()
    entities = {}

    if intent == "entity_correction":
        # First captured group is usually the entity name
        if groups:
            # Find the first non-empty group that looks like a name
            for g in groups:
                if g and g.lower() not in ('a', 'an', 'the', 'our', 'is', 'not', "isn't", "isnt"):
                    entities["name"] = g
                    break
        entities["correction_type"] = "not_a_person"

    elif intent == "filter_request":
        # Extract the filter term (usually the last non-None group)
        # Patterns are structured so the search term is typically in the last group
        skip_terms = {'focus', 'on', 'show', 'filter', 'by', 'only', 'just', 'me',
                      'focus on', 'filter by', 'documents', 'insights', 'entities',
                      'about', 'from', 'related to', 'mentioning', 'involving'}
        # Work backwards through groups to find the actual search term
        for g in reversed(groups):
            if g and g.lower().strip() not in skip_terms:
                entities["focus"] = g.strip()
                break

    elif intent == "navigation":
        # Extract the target view
        for g in groups:
            if g and g.lower() in ('timeline', 'findings', 'entities', 'insights', 'dashboard', 'cases', 'patterns', 'upload', 'preflight'):
                entities["target"] = g.lower()
                break
        # Also check for singular forms
        if not entities.get("target"):
            for g in groups:
                if g:
                    target = g.lower().rstrip('s')  # Remove trailing 's'
                    if target in ('timeline', 'finding', 'entitie', 'insight', 'dashboard', 'case', 'pattern'):
                        entities["target"] = target if target != 'entitie' else 'entities'
                        break

    elif intent == "analysis_query":
        # Extract query type and parameters
        if 'gap' in message.lower():
            entities["query_type"] = "timeline_gap"
        elif 'pattern' in message.lower():
            entities["query_type"] = "pattern_search"
        elif 'anomal' in message.lower():
            entities["query_type"] = "anomaly_detection"
        else:
            entities["query_type"] = "general"

        # Try to extract time references
        time_match = re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', message, re.IGNORECASE)
        if time_match:
            entities["month"] = time_match.group(1).capitalize()

    return entities


def classify_intent(
    message: str,
    context: Dict[str, Any],
    anthropic_client=None
) -> Tuple[str, Dict[str, Any], float]:
    """
    Classify user intent using hybrid approach:
    1. Try pattern matching first (fast, free)
    2. Fallback to LLM for ambiguous cases

    Returns: (intent, entities, confidence)
    """
    message = message.strip()

    # Try pattern matching first
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message, re.IGNORECASE):
                entities = extract_entities_from_match(pattern, message, intent)
                logger.debug(f"Pattern match: intent={intent}, entities={entities}")
                return intent, entities, 1.0  # High confidence for pattern match

    # Fallback to LLM classification if available
    if anthropic_client:
        return llm_classify_intent(message, context, anthropic_client)

    # No LLM available, try to guess from keywords
    message_lower = message.lower()

    # Simple keyword fallbacks
    if any(word in message_lower for word in ['entity', 'person', 'name', 'remove', 'isn\'t']):
        return "entity_correction", {}, 0.3
    elif any(word in message_lower for word in ['show', 'view', 'go to', 'open']):
        return "navigation", {}, 0.3
    elif any(word in message_lower for word in ['filter', 'focus', 'find', 'search']):
        return "filter_request", {}, 0.3
    elif any(word in message_lower for word in ['how many', 'what', 'when', 'who', 'gap', 'pattern']):
        return "analysis_query", {}, 0.3

    # Default to clarification needed
    return "clarification", {}, 0.0


def llm_classify_intent(
    message: str,
    context: Dict[str, Any],
    anthropic_client
) -> Tuple[str, Dict[str, Any], float]:
    """Use Anthropic API to classify ambiguous intents"""
    prompt = f"""Classify this user message into one of these intents:
{', '.join(INTENTS.keys())}

User message: "{message}"
Current context: {json.dumps(context)}

Respond with JSON only, no other text:
{{"intent": "one of the intent names", "entities": {{"relevant": "extracted data"}}, "confidence": 0.0-1.0}}

Intent descriptions:
{json.dumps(INTENTS, indent=2)}
"""

    try:
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response
        response_text = response.content[0].text.strip()

        # Try to extract JSON from response
        # Handle case where response might have markdown code blocks
        if '```' in response_text:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

        result = json.loads(response_text)
        intent = result.get("intent", "clarification")
        entities = result.get("entities", {})
        confidence = result.get("confidence", 0.5)

        # Validate intent
        if intent not in INTENTS:
            logger.warning(f"LLM returned unknown intent: {intent}")
            intent = "clarification"
            confidence = 0.3

        logger.debug(f"LLM classification: intent={intent}, confidence={confidence}")
        return intent, entities, confidence

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
        return "clarification", {}, 0.0
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return "clarification", {}, 0.0
