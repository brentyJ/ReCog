# EhkoLabs Research Projects

A running list of research topics to inform development. Not everything needs deep study — sometimes a few hours of reading changes the whole approach.

---

## Active Research

### 1. Named Entity Recognition (NER) Enhancement
**Priority**: High  
**Relevant to**: ReCog Tier 0, entity extraction

**Questions**:
- Can spaCy's transformer models (en_core_web_trf) improve extraction accuracy?
- How to handle Australian-specific entities (Medicare, Centrelink, suburb names)?
- Is fine-tuning worth the effort vs prompt engineering?

**Starting points**:
- spaCy NER documentation
- Hugging Face NER models
- Australian NLP datasets (if any exist)

---

### 2. Witness Voice Architecture
**Priority**: High  
**Relevant to**: EhkoForge core philosophy

**Questions**:
- How do we ensure an Ehko speaks *about* someone, never *as* them?
- What grounding techniques prevent hallucination/fabrication?
- How to handle "I don't know" gracefully vs making things up?

**Starting points**:
- Retrieval-Augmented Generation (RAG) research
- Constitutional AI / RLHF alignment papers
- Anthropic's work on honesty and calibration

---

### 3. Long-Term Data Durability
**Priority**: Medium  
**Relevant to**: EhkoForge export-first architecture

**Questions**:
- What file formats will be readable in 50/100/200 years?
- How do we make data self-describing (no external schema needed)?
- Migration strategies — how do archives handle format obsolescence?

**Starting points**:
- Library of Congress format recommendations
- PDF/A archival standard
- SQLite as an archival format (it's surprisingly good)
- Long Now Foundation thinking

---

### 4. Voice/Writing Pattern Extraction
**Priority**: Medium  
**Relevant to**: EhkoForge authenticity

**Questions**:
- How do we capture someone's "voice" from their writing?
- What makes writing recognisably *theirs*?
- Can we measure this objectively (stylometry)?

**Starting points**:
- Stylometry research (authorship attribution)
- Linguistic fingerprinting
- GPT fine-tuning on personal corpora (ethical considerations)

---

### 5. Brief Prep Plugin — Legal Domain
**Priority**: High (commercial)  
**Relevant to**: ReCog enterprise, Victoria Police market

**Questions**:
- What do prosecutors/investigators actually need from case files?
- How to extract timelines from witness statements?
- Contradiction detection across multiple statements?
- What's legally admissible re: AI-generated summaries?

**Starting points**:
- Talk to former colleagues (domain expertise)
- Legal tech landscape (what exists already?)
- Australian evidence law re: AI assistance

---

## Backlog (Future Consideration)

### 6. Semantic Search for Personal Archives
How to find "that conversation about X from years ago" across thousands of documents.

### 7. Privacy-Preserving Analysis
Local LLM options, encrypted processing, enterprise data sovereignty.

### 8. Multi-Modal Ehkos
Voice recordings, photos, videos — not just text. What's feasible?

### 9. Marketplace/Artist Economy
How to let artists create Ehko themes/avatars without IP exploitation.

### 10. Temporal Reasoning
Understanding "before/after/during" relationships in life events.

---

## Research Log

| Date | Topic | Time Spent | Key Insight |
|------|-------|------------|-------------|
| | | | |

---

## How to Use This

1. Pick one topic when you have research time
2. Set a time limit (1-2 hours max per session)
3. Log what you learned — even "this was a dead end" is useful
4. Update priority based on what you discover

Don't try to become an expert. Just gather enough to make informed decisions.

---

*Created: 24 Dec 2025*
