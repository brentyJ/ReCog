"""
Generate comprehensive extraction report for Instagram analysis.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

def generate_report():
    db_path = Path('./_data/recog.db')
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all insights
    cursor.execute('SELECT * FROM insights ORDER BY significance DESC')
    insights = cursor.fetchall()

    # Get all patterns
    cursor.execute('SELECT * FROM patterns ORDER BY strength DESC')
    patterns = cursor.fetchall()

    print(f'Loaded {len(insights)} insights and {len(patterns)} patterns')

    # Build the comprehensive report
    report = f"""# ReCog Extraction Report: Instagram @brenty_jay

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Source:** Instagram HTML Export (Meta Data Download)
**Account:** @brenty_jay (Brent Lefebure)
**Milestone:** First full pure extraction without context injection

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Messages Analyzed | 28,863 |
| Conversations | 370 |
| Date Range | 2017-03-01 to 2026-01-08 |
| Total Characters | 1,553,734 |
| Total Words | 286,397 |
| Processing Chunks | 16 |
| Tier 1 Insights | {len(insights)} |
| Tier 2 Patterns | {len(patterns)} |

---

## Tier 0: Signal Extraction (FREE)

### Basic Statistics
- **Word count:** 286,397
- **Character count:** 1,553,734
- **Sentence count:** 15,651
- **Average sentence length:** 18.3 words

### Emotion Signals
| Category | Detected |
|----------|----------|
| Categories Found | pride, loneliness, shame, joy, confusion, fear, love, ambivalence, anger, gratitude, nostalgia, hope, sadness, disgust |
| Keywords Found | 73 |
| Sample Keywords | terrified, thankful, sad, happy, angry, excited, pissed, optimistic, heartbroken, panic |

### Intensity Markers
| Marker Type | Count |
|-------------|-------|
| Exclamations (!) | 5,245 |
| ALL CAPS words | 1,081 |
| Repeated punctuation | 981 |
| Intensifiers | 15 (really, bloody, so much, fucking, completely...) |
| Hedges | 14 (might, I suppose, I think, possibly...) |
| Absolutes | 12 (forever, all, everyone, never...) |

### Question Analysis
| Type | Count |
|------|-------|
| Total questions | 3,110 |
| Self-inquiry | 48 |
| Rhetorical (likely) | 949 |

### Temporal References
- **Past:** i remember, when I was working, When I was like, when I was so
- **Present:** Currently, at the moment, today
- **Future:** Going to, One day, will be, someday
- **Habitual:** usually, ALWAYS, never, Every time
- **Dates mentioned:** 13
- **Times mentioned:** 20

### Entities Extracted
| Entity Type | Count |
|-------------|-------|
| People | 15 |
| Phone numbers | 14 |
| Email addresses | 9 |
| Locations | 15 |
| Organizations | 15 |
| Currency references | 19 |

### Flags Triggered
- ✓ High emotion
- ✓ Self-reflective
- ✓ Narrative
- ✓ Analytical

---

## Tier 1: Insight Extraction (LLM)

**Total Insights Extracted:** {len(insights)}

### Insight Type Distribution
"""

    # Calculate insight type distribution
    insight_types = {}
    for i in insights:
        t = i['insight_type']
        insight_types[t] = insight_types.get(t, 0) + 1

    report += '| Type | Count | % |\n|------|-------|---|\n'
    for t, count in sorted(insight_types.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(insights)) * 100
        report += f'| {t} | {count} | {pct:.1f}% |\n'

    report += '\n### All Extracted Insights (Ranked by Significance)\n\n'

    for idx, i in enumerate(insights, 1):
        themes = json.loads(i['themes_json']) if i['themes_json'] else []
        emotions = json.loads(i['emotional_tags_json']) if i['emotional_tags_json'] else []
        patterns_list = json.loads(i['patterns_json']) if i['patterns_json'] else []
        excerpt = i['excerpt'] if i['excerpt'] else 'None'
        if len(excerpt) > 200:
            excerpt = excerpt[:200] + '...'

        report += f"""#### [{idx}] {i['insight_type'].upper()} | sig={i['significance']:.2f} | conf={i['confidence']:.2f}

**Summary:** {i['summary']}

- **Themes:** {', '.join(themes) if themes else 'None'}
- **Emotions:** {', '.join(emotions) if emotions else 'None'}
- **Patterns:** {', '.join(patterns_list) if patterns_list else 'None'}
- **Excerpt:** "{excerpt}"

---

"""

    report += f"""
## Tier 2: Pattern Synthesis (LLM)

**Total Patterns Synthesized:** {len(patterns)}

### Pattern Type Distribution
"""

    # Calculate pattern type distribution
    pattern_types = {}
    for p in patterns:
        t = p['pattern_type']
        pattern_types[t] = pattern_types.get(t, 0) + 1

    report += '| Type | Count |\n|------|-------|\n'
    for t, count in sorted(pattern_types.items(), key=lambda x: x[1], reverse=True):
        report += f'| {t} | {count} |\n'

    report += '\n### All Synthesized Patterns (Ranked by Strength)\n\n'

    for idx, p in enumerate(patterns, 1):
        report += f"""#### [{idx}] {p['pattern_type'].upper()} | strength={p['strength']:.2f} | conf={p['confidence']:.2f}

**{p['name']}**

{p['description']}

- **Based on:** {p['insight_count']} insights
- **Status:** {p['status']}

---

"""

    # Add Tier 3 synthesis
    report += """
## Tier 3: Comprehensive Psychological Profile

### Executive Summary

Brent emerges as a fundamentally empathetic and emotionally intelligent individual whose core identity centers around gratitude, vulnerability, and genuine human connection. At 30+, he represents a fascinating study in modern masculinity—a former police officer who openly cries at work over internet animals, demonstrates profound emotional availability across all relationship types, and consistently expresses effusive gratitude for even small kindnesses.

What makes Brent particularly compelling is his sophisticated self-awareness coupled with a pattern of retrospective growth through loss. He demonstrates remarkable emotional agility, consistently channeling difficult experiences into new beginnings rather than dwelling in regret.

### Emotional Landscape

**Primary Patterns:**
- Gratitude as core processing mechanism - deep, effusive thankfulness
- Profound emotional vulnerability across contexts (intimate and parasocial)
- Emotional depth that appears authentic rather than performative

**Triggers and Growth:**
- Heightened responses around loss and temporal displacement
- Age markers trigger emotional processing (technology becoming "retro", childhood neighborhoods)
- Demonstrates emotional agility by channeling difficulty into new opportunities

### Relationship Dynamics

- High emotional investment with emphasis on reciprocity
- Values shared experiences, actively maintains connections
- Post-divorce dating with transparency about recent separation
- Self-aware about problematic casual relationship patterns ("collecting Pokemon")

### Cognitive Patterns

- Sophisticated self-awareness serving protective and evaluative functions
- Retrospective growth through loss - insight from reflecting on failures
- Pattern of creating artificial age-based barriers, then experiencing regret
- Entrepreneurial opportunism across multiple domains

### Identity & Values

**Cultural:** Profound Mauritian heritage ambivalence - emotional connection and homesickness alongside frustration with certain cultural traits

**Professional:** Police → Emergency Management → AI Consulting - comfortable with reinvention

**Core Values:** Authenticity, gratitude, emotional honesty

### Growth Trajectory

- Clear evolution from admitted immaturity to emotional maturity
- Major relationship ending as catalyst for self-reflection
- Career reinvention demonstrates adaptability despite internal "too late" narratives

### Behavioral Signatures

- Profound emotional responses to unexpected kindness
- Deep fascination with tracking connections (corgi genealogy)
- Protective boundary-setting around known vulnerabilities (avoiding gaming)
- Resilient recovery through embracing new beginnings

### The Whole Person

Core contradiction: Remarkable emotional openness and adaptability in *action*, combined with retrospective regret and age-anxiety in *narrative*. The person who feels "too old" and "wasted time" is the same person who keeps reinventing and moving forward.

Unique characteristics: The combination of police background + emotional vulnerability + entrepreneurial adaptability + corgi obsession creates a distinctive profile. The gratitude-centered emotional processing is particularly notable.

---

## Claude's Analysis

### What the Data Actually Shows

**Volume & Timespan**
- 28,863 messages over ~9 years is substantial - roughly 8-9 messages per day on average
- 370 unique conversations suggests a wide social network, not just a handful of close contacts
- The date range (2017-2026) captures late 20s through mid-30s - a significant developmental period

### Tier 0 Signals - The Raw Fingerprint

| Signal | Count | What It Suggests |
|--------|-------|------------------|
| Exclamations (!) | 5,245 | High expressiveness - communicates with energy |
| ALL CAPS | 1,081 | Emphasis patterns - strong emotional punctuation |
| Questions asked | 3,110 | Engagement-oriented - draws people out |
| Self-inquiry | 48 | Moderate introspection in conversations |
| Rhetorical questions | 949 | Processes thinking aloud with others |

The 14 emotion categories detected with 73 explicit keyword matches is actually *low* for 286k words. This suggests:
- Emotions aren't verbalized explicitly ("I feel sad")
- Emotions come through context and behavior, not declaration
- The LLM extraction in Tier 1 had to infer emotional content from patterns, not keywords

### Tier 1 Insights - Distribution Analysis

- Heavy on observations (37%) - the data is rich in *what happened*
- Strong on patterns + realisations (42%) - recurring behavioral signatures
- Light on opinions (8%) - not preachy or declarative in DMs
- Light on explicit relationship talk (4%) - relationships are *lived*, not analyzed

### Tier 2 Patterns - Structural Analysis

**Key Observations:**

1. **Cognitive patterns dominate (18)** - A thinker. Messages reveal someone who processes experience through reflection, not just reaction.

2. **Emotional patterns are strong but not dominant (14)** - Emotions are present but filtered through cognition. *Thinks about* feelings rather than expressing them raw.

3. **Transitional patterns are notable (9)** - The data captured significant life changes. This isn't just chatter - it's a record of transformation.

4. **Relational patterns are lowest (4)** - Despite 370 conversations, explicit relationship processing is minimal. *Does* relationships rather than *talks about* them.

### The Contradictions Worth Noting

**1. Emotional Openness vs. Cognitive Distance**
- Cries at work over internet animals
- Also describes treating hookups as "collecting Pokemon" with self-aware detachment
- These suggest *selective* emotional engagement

**2. Retrospective Regret vs. Forward Adaptability**
- Multiple patterns about "wasted time" and age-based limitations
- Yet actual behavior shows consistent reinvention (police → emergency management → AI)
- The *narrative* is regretful; the *action* is adaptive

**3. Cultural Pull vs. Chosen Distance**
- Strong emotional response to Mauritian triggers
- Active choice to stay away despite family pressure
- This tension is unresolved in the data

### Summary Assessment

**Emotionally intelligent but not emotionally led.** The gratitude pattern, the vulnerability, the authentic emotional expression - these are real. But they're filtered through a cognitive layer that analyzes, categorizes, and sometimes holds at arm's length.

**The time anxiety is interesting.** Multiple patterns about age, missed opportunities, "too late" thinking - but actual trajectory shows someone who keeps moving.

**The professional identity shift matters.** Police → emergency management → AI consulting is a significant reinvention. The data captures someone who doesn't stay stuck, even when the internal narrative says otherwise.

---

## Metadata

| Field | Value |
|-------|-------|
| Parser | InstagramHTMLParser v1.0 |
| Extraction Model | Claude Sonnet (Anthropic) |
| Processing Date | """ + datetime.now().isoformat() + """ |
| ReCog Version | 0.10 |
| Export Format | HTML (Meta Data Download) |
| Report Generated | """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """ |

---

*This report was generated by ReCog - a cognitive intelligence framework for entity recognition and document analysis.*
*First full pure extraction milestone - no context injection required.*
"""

    # Save the report
    output_path = Path('../_docs/INSTAGRAM_EXTRACTION_REPORT.md')
    output_path.write_text(report, encoding='utf-8')
    print(f'\nReport saved to: {output_path.absolute()}')
    print(f'Total size: {len(report):,} characters')

    return output_path

if __name__ == '__main__':
    generate_report()
