# Extraction Run Comparison Report

**Generated:** 2026-01-16 16:23
**Source:** Instagram DMs @brenty_jay (28,863 messages, 2017-2026)

---

## Run Overview

| Metric | Baseline | Run 2 | Delta |
|--------|----------|-------|-------|
| **Name** | Baseline - Pure Extraction | Run 2 - Age + Life Context | - |
| **Insights** | 52 | 78 | +26 (+50%) |
| **Patterns** | 67 | 40 | -27 |
| **DOB Context** | No | Yes (Feb 27, 1986) | Added |
| **Life Context** | No | Yes (15 events) | Added |

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

## Run IDs for Future Reference

- **Baseline:** `dbf20292-dc80-464a-a716-a73a9dc955d6`
- **Run 2:** `9e016a1d-e23a-4fcd-a005-527a5b6e1aa1`

---

## Technical Notes

### Clustering Bug Fix

Original Run 2 produced only 13 patterns due to a bug where `earliest_source_date` was NULL on all insights. This caused temporal clustering to bucket everything into one "2026-01" cluster (using `created_at` fallback).

**Fix:** Populate date fields during extraction based on chunk's estimated year range.

**Result:** 5 clusters → 14 clusters, 13 patterns → 40 patterns

---

## Next Steps

1. Add career timeline to life context (police end date, current role)
2. Run Facebook data extraction for event date refinement
3. Consider running with even richer context (specific conversations, key people)
4. Track deltas between subsequent runs

---

*Generated by ReCog Run Comparison System*
*Updated: 2026-01-16 with Tier 3 synthesis comparison and clustering fix*
