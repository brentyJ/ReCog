# Extraction Run Comparison Report

**Generated:** 2026-01-16 16:23
**Source:** Instagram DMs @brenty_jay (28,863 messages, 2017-2026)

---

## Run Overview

| Metric | Baseline | Run 2 | Run 4 | Notes |
|--------|----------|-------|-------|-------|
| **Name** | Baseline - Pure Extraction | Run 2 - Age + Life Context | Run 4 - Timestamp Chunking | - |
| **Insights** | 52 | 78 | 52 | Run 4 uses actual timestamps |
| **Patterns** | 67 | 40 | 85 | Run 4 has best clustering |
| **DOB Context** | No | Yes | Yes | Feb 27, 1986 |
| **Life Context** | No | Yes | Yes | 15 events |
| **Date Coverage** | 0% | 0% (estimated) | 100% (actual) | Key improvement |
| **Avg Significance** | 0.62 | - | 0.66 | +0.04 |
| **Max Significance** | 0.80 | 0.90 | 0.90 | - |

---

## Key Findings

### Context Injection Impact

**With age and life context, the extraction:**
1. **Produced 50% more insights** (78 vs 52) - more granular observations
2. **Higher significance scores** - top insights scored 0.90 vs 0.80
3. **More specific temporal references** - "June 2019", "age 19" now correctly placed
4. **New themes emerged** - police-work, career-transition, life-transition

### Emotional Shift Analysis

| Emotion | Baseline | Run 2 | Change | Interpretation |
|---------|----------|-------|--------|----------------|
| Joy | 9 | 20 | +11 | Context frames events more positively |
| Hope | 7 | 14 | +7 | Life progression visible with timeline |
| Loneliness | 1 | 5 | +4 | Post-separation period identified |
| Nostalgia | 6 | 3 | -3 | Less generic nostalgia, more specific |

### Theme Evolution

**New themes that emerged with context:**
-  (+3) - Career context enabled identification
-  (+3) - Timeline made transitions visible
-  (+2) - Career history enabled tracking
-  (+2) - Age context helped frame struggles

**Themes that decreased:**
-  (-3) - Less generic tagging, more specific

---

## Top Insights Comparison

### Baseline (No Context) - Top 3

**1. [realisation] sig=0.80**
> Brent went through a breakup with Sarah where she kept both of their dogs, but he found solace and healing through getting a new puppy (Artie) who was...
- Themes: relationships, breakup-recovery, pets-as-healing

**2. [realisation] sig=0.80**
> Brent reflects on his 10-year relationship as potentially being "a waste of time" and describes it as taking up his "prime" years, revealing complex f...
- Themes: relationship-regret, time-investment, life-reflection

**3. [observation] sig=0.80**
> Brent demonstrates emotional vulnerability by admitting he was deeply affected by the thought of losing Natalie, revealing the depth of his attachment...
- Themes: emotional-vulnerability, fear-of-loss, attachment


### Run 2 (With Context) - Top 3

**1. [fact] sig=0.90**
> Brent and Sarah broke up several months prior to June 2019, with Brent describing it as a mutual decision where 'everything was too hard' and 'a battl...
- Themes: relationship-breakdown, sacrifice, pet-custody

**2. [realisation] sig=0.90**
> Trust and honesty are fundamental deal-breakers for Brent due to his previous partner's extensive lying, which made him question their entire relation...
- Themes: trust-issues, relationship-trauma, honesty

**3. [realisation] sig=0.90**
> A formative experience of being unlawfully detained by American police at age 19, including false charges, directly motivated Brent's decision to join...
- Themes: career-motivation, personal-injustice, systemic-reform


---

## What Changed and Why

### Attribution Analysis

| Change | Cause | Evidence |
|--------|-------|----------|
| More specific dates | DOB injection | "age 19" instead of "young" |
| Career insights | Life context | Police work themes now identified |
| Relationship timeline | Life context | Sarah J breakup correctly dated to 2019 |
| Higher joy/hope | Age framing | LLM sees growth arc over time |
| Pet references | Life context | Artie/Jessie connection identified |

### Pattern Synthesis Results

After fixing the clustering bug (insights now have proper date fields):
- **Clusters processed:** 14 (was 5 before fix)
- **Patterns generated:** 40 (was 13 before fix)

**Pattern Type Distribution:**

| Type | Baseline | Run 2 | Delta |
|------|----------|-------|-------|
| cognitive | 23 | 9 | -14 |
| emotional | 16 | 8 | -8 |
| behavioral | 10 | 8 | -2 |
| transitional | 8 | 9 | +1 |
| relational | 4 | 6 | +2 |
| temporal | 6 | 0 | -6 |

**Key observation:** Context injection traded quantity for specificity. Fewer generic cognitive patterns, more specific transitional and relational patterns.

---

## Tier 3 Synthesis Comparison

### Side-by-Side Analysis

| Aspect | Baseline (No Context) | Run 2 (With Context) |
|--------|----------------------|----------------------|
| **Age Reference** | "At 30+", "late 20s through mid-30s" | "39-year-old", "ages 31-39", specific age at events |
| **Career Narrative** | "Police → Emergency Management → AI Consulting" | "Police sergeant → IT sergeant" with psychological insight |
| **Origin Story** | Not identified | "Age 19 police injustice → joined to reform system" |
| **Relationship Timeline** | "Post-divorce dating", "recent separation" | "Sarah (2009-2019)", "Nicole (2020-present)" |
| **Pet References** | "corgi obsession", "corgi genealogy" | "Artie" by name, linked to post-separation healing |
| **COVID Insight** | Not mentioned | "COVID lockdowns became unexpectedly transformative" |
| **Core Framing** | "Gratitude, vulnerability, genuine human connection" | "Justice and reform" as foundational drive |
| **Trust Dynamics** | Not emphasized | "Trust as non-negotiable after extensive deception" |
| **Humor Pattern** | Not identified | "Humor as Emotional Armor" as primary coping |
| **Professional Burnout** | "comfortable with reinvention" | "carrying more stress than realized", "relief" on leaving |

### Qualitative Differences

**Baseline Synthesis Tone:**
- Observational and somewhat distant
- Describes patterns without causal links
- "Fascinating study in modern masculinity"
- Treats subject as interesting case study

**Run 2 Synthesis Tone:**
- Direct address ("You", "Your")
- Explains WHY patterns exist
- Links experiences to outcomes
- Written FOR the subject to read

### Key Insights Only Possible With Context

1. **Injustice → Reform Connection**
   - Baseline: "former police officer" (no explanation)
   - Run 2: "Age 19 detention directly motivated joining police to reform system"

2. **Relationship Authenticity Paradox**
   - Baseline: Generic "self-aware about problematic patterns"
   - Run 2: Specific "belief that being genuine too quickly creates problems" linked to past failures

3. **Career Transition Psychology**
   - Baseline: "comfortable with reinvention"
   - Run 2: "surprising psychological relief" - identifies hidden professional stress

4. **COVID as Growth Catalyst**
   - Baseline: Not mentioned
   - Run 2: "Isolation became unexpectedly transformative" - specific developmental insight

5. **Current Developmental Edge**
   - Baseline: Generic "growth trajectory"
   - Run 2: "integrating wisdom while not losing romantic nature" - actionable

### What Baseline Got Wrong

- Career path listed as "Police → Emergency Management → AI Consulting" (incorrect)
- No mention of IT/sergeant transition
- No understanding of *why* you joined police
- Age estimated as "30+" when actually 31-39 during data period

---

## Run 4: Timestamp-Based Extraction

### Overview

Run 4 introduced actual message timestamps for chunking instead of character-based chunking with estimated dates. This is the most significant technical improvement to the extraction pipeline.

**Key Changes:**
- Messages chunked by 6-month time periods using actual timestamps
- Small chunks (<20 messages) merged with adjacent chunks
- Insights tagged with real `earliest_source_date` / `latest_source_date`
- Life context injection uses actual midpoint date of each chunk

### Run 4 vs Baseline Comparison

| Metric | Baseline | Run 4 | Change |
|--------|----------|-------|--------|
| **Insights** | 52 | 52 | same |
| **Patterns** | 67 | 85 | +18 (+27%) |
| **Avg Significance** | 0.62 | 0.66 | +0.04 |
| **Max Significance** | 0.80 | 0.90 | +0.10 |
| **Date Coverage** | 0% | 100% | +100% |
| **Time Span** | unknown | 2017-03-01 to 2026-01-08 | 9 years |

### Insight Type Shifts

| Type | Baseline | Run 4 | Delta |
|------|----------|-------|-------|
| fact | 5 | 9 | +4 |
| observation | 19 | 26 | +7 |
| opinion | 4 | 1 | -3 |
| pattern | 11 | 5 | -6 |
| realisation | 11 | 9 | -2 |
| relationship | 2 | 2 | 0 |

**Interpretation:** Timestamp-based extraction favors concrete facts and observations over abstract patterns and opinions.

### Theme Changes (Biggest Deltas)

| Theme | Baseline | Run 4 | Delta |
|-------|----------|-------|-------|
| social-connection | 1 | 6 | +5 |
| pet-loss | 0 | 4 | +4 |
| compassion | 0 | 3 | +3 |
| police-work | 0 | 3 | +3 |
| empathy | 1 | 3 | +2 |
| friendship | 1 | 3 | +2 |
| emotional-healing | 0 | 2 | +2 |

### Emotional Tag Changes

| Emotion | Baseline | Run 4 | Delta |
|---------|----------|-------|-------|
| sadness | 5 | 12 | +7 |
| hope | 7 | 12 | +5 |
| joy | 9 | 12 | +3 |
| love | 10 | 12 | +2 |
| nostalgia | 6 | 3 | -3 |

**Interpretation:** Actual timestamps reveal more emotional depth - the full arc of sadness through hope to joy becomes visible when events are properly dated.

### Top Insights Comparison

**Baseline Top Insight (no dates):**
> [realisation] sig=0.80 | no date
> Brent went through a breakup with Sarah where she kept both of their dogs...
> Themes: relationships, breakup-recovery, pets-as-healing

**Run 4 Top Insight (with timestamps):**
> [fact] sig=0.90 | 2017-03-01 to 2019-07-31
> Brent's marriage to Sarah ended in mutual breakup a few months prior, with him describing their relationship as 'everything was too hard'...
> Themes: relationship-breakdown, marriage-dissolution, mutual-separation

---

## Run 4 vs Run 2 Synthesis Comparison

### Temporal Precision

| Aspect | Run 2 (Estimated Dates) | Run 4 (Actual Timestamps) |
|--------|-------------------------|---------------------------|
| **Data Source** | Context injection, chunk index dates | Actual message timestamps 2017-2026 |
| **Date Coverage** | "ages 31-39" (estimated) | Specific: 2017-03-01 to 2026-01-08 |
| **Temporal Anchors** | ~8 references | 23+ specific references |

### Narrative Improvements

**Relationship Timeline:**
- Run 2: "post-divorce reconstruction (2019)" - generic
- Run 4: Full arc from "age 23 to 33" through "Tinder phase 2023" to "August 2025 marriage"

**Career Narrative:**
- Run 2: "patrol officer to IT sergeant" - vague
- Run 4: "patrol → CIU → DRU → Sergeant/IT → Austin Hospital" with dates

**Pet Timeline:**
- Run 2: "deep attachment to Artie" - no dates
- Run 4: "Artie during post-separation (2019)", "Jessie's death late 2024 - crying daily for 15 days", "Kingsley adoption"

**Grief Processing:**
- Run 2: Generic emotional patterns
- Run 4: Quantified: "crying daily for 15 days despite not living with Jessie for 5 years"

### New Insights Only Possible With Timestamps

1. **Specific career units**: CIU, DRU mentioned by name
2. **Austin Hospital role** identified
3. **Jessie grief duration** quantified (15 days)
4. **"Reckless and sociopathic" Tinder phase** (2023) - actual quote with date
5. **Started drawing at age 33** - specific milestone
6. **Kingsley adoption** mentioned
7. **"Compartmentalized crisis management"** as coping pattern

### Core Framing Evolution

| Run | Core Framing | Growth Edge |
|-----|--------------|-------------|
| Baseline | "Gratitude, vulnerability, connection" | Generic "growth trajectory" |
| Run 2 | "Justice and reform" | "integrating wisdom while not losing romantic nature" |
| Run 4 | "Late bloomer renaissance" | "learning to process emotions in real-time rather than through avoidance" |

### Key Improvement Summary

- Run 4 adds **23 specific temporal anchors** vs Run 2's ~8
- Run 4 traces **9 discrete life events** vs Run 2's general descriptions
- Run 4 provides **4 quantified emotional patterns** (e.g., "15 days crying")
- Run 4 identifies **3 new behavioral patterns** not visible in Run 2

---

## Run IDs for Future Reference

- **Baseline:** `dbf20292-dc80-464a-a716-a73a9dc955d6`
- **Run 2:** `9e016a1d-e23a-4fcd-a005-527a5b6e1aa1`
- **Run 3:** `8ddc7cc3-f214-4f57-bef3-ac7b183f53cc` (timestamp chunking, skipped small chunks)
- **Run 4:** `653ce3cc-4112-44f9-93ac-8c8ba72a32ce` (timestamp chunking, merged small chunks)

---

## Technical Notes

### Clustering Bug Fix

Original Run 2 produced only 13 patterns due to a bug where `earliest_source_date` was NULL on all insights. This caused temporal clustering to bucket everything into one "2026-01" cluster (using `created_at` fallback).

**Fix:** Populate date fields during extraction based on chunk's estimated year range.

**Result:** 5 clusters → 14 clusters, 13 patterns → 40 patterns

---

## Technical Notes: Timestamp-Based Chunking

### Run 3 vs Run 4

Run 3 introduced timestamp-based chunking but skipped small chunks (< 1000 chars):
- 17 chunks created, 3 skipped as "too small"
- Early 2017-2018 data lost

Run 4 added small chunk merging:
- Small chunks (< 20 messages) merged with next chunk
- 14 chunks, 0 skipped
- Chunk 1 now spans 2017-03 to 2019-07 (136 msgs) - captures early sparse data

### Chunking Algorithm

```python
def chunk_messages_by_time(messages, chunk_months=6, min_messages=20):
    # 1. Sort messages by timestamp
    # 2. Create chunks at 6-month boundaries
    # 3. Merge small chunks (<20 msgs) with next chunk
    # 4. Return (messages, start_date, end_date) tuples
```

### CLI Usage

```bash
python run_extraction_with_context.py \
  --name "Run Name" \
  --parent <parent_run_id> \
  --months 6 \
  --min-messages 20
```

---

## Next Steps

1. ~~Add career timeline to life context~~ (Done)
2. Run Facebook data extraction for event date refinement
3. Consider running with even richer context (specific conversations, key people)
4. ~~Implement timestamp-based chunking~~ (Done - Run 4)
5. Add conversation-level threading for multi-person context

---

*Generated by ReCog Run Comparison System*
*Updated: 2026-01-16 with Run 4 timestamp-based extraction comparison*
