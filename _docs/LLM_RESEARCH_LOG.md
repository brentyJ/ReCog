# ReCog LLM Provider Research Log

## Purpose
Track empirical findings on LLM provider performance to optimise cost-to-insight ratio.

---

## Test Session 1: 21 Dec 2025

### Test Input
```
"I felt frustrated today dealing with the bureaucracy at work. Tom mentioned we should try a different approach next quarter."
```
- Source type: reflection
- Word count: 22
- Tier 0 signals: anger emotion, no high-emotion flag

### Results

| Metric | OpenAI (gpt-4o-mini) | Anthropic (Claude Sonnet 4) |
|--------|---------------------|---------------------------|
| Insights extracted | 1 | 2 |
| Tokens used | 835 | 1,057 |
| Token delta | baseline | +26.6% |
| Content quality | high | medium |
| Avg confidence | 0.9 | 0.75 |
| Avg significance | 0.7 | 0.55 |
| Emotions detected | anger | anger, hope |
| Patterns found | 1 | 3 |
| Themes found | 3 | 8 (4+4) |

### Qualitative Observations

**OpenAI gpt-4o-mini:**
- Combined both sentences into single insight
- Higher confidence (0.9) but potentially oversimplified
- Summary: "frustration with bureaucratic processes... Tom's suggestion reflects desire for change"
- Efficient, good for high-volume processing

**Anthropic Claude Sonnet:**
- Split into two distinct insights (frustration + collaborative hope)
- Found nuance: "hope" emotion in Tom's suggestion
- Richer pattern vocabulary (collaborative-coping, forward-thinking-adaptation)
- More themes per insight
- Better for deep analysis, personality synthesis

### Cost Analysis (Approximate)
- gpt-4o-mini: ~$0.00015/1K input, ~$0.0006/1K output
- claude-sonnet: ~$0.003/1K input, ~$0.015/1K output

For this test:
- OpenAI cost: ~$0.0005
- Anthropic cost: ~$0.016

**Anthropic is ~32x more expensive per extraction** but provides:
- 2x insights
- 3x patterns
- 2.7x themes
- Emotional nuance (found hope)

---

## Practical Cost Breakdown

### Per-Extraction Costs
| Provider | Tokens | Cost | Cost/100 docs | Cost/1000 docs |
|----------|--------|------|---------------|----------------|
| gpt-4o-mini | ~835 | $0.0003 | $0.03 | $0.30 |
| Claude Sonnet | ~1,057 | $0.008 | $0.80 | $8.00 |

### Real-World Scenarios

**Year of journal entries (365 docs):**
- OpenAI only: **$0.11**
- Anthropic only: **$2.92**
- Hybrid (90% OpenAI + 10% Anthropic): **$0.40**

**SMS export (2000 conversations):**
- OpenAI only: **$0.60**
- Hybrid with emotional routing: **~$1.50**

### When Anthropic is Worth 27x More

1. **Tier 0 flags `high_emotion: true`** — emotional nuance matters here
2. **First-pass significance > 0.7** — worth deeper analysis
3. **Synthesis/correlation** — happens once per batch, not per doc
4. **Source type: therapy, journal, personal** — flag by content type
5. **User explicitly requests deep analysis** — their choice, their cost

### Implemented Routing Strategy

See `recog_engine/core/routing.py`:

```python
config = RoutingConfig(
    extraction_provider="openai",      # Default: cheap
    synthesis_provider="anthropic",    # Always: complex reasoning
    upgrade_on_high_emotion=True,       # Trigger: emotional content
    upgrade_source_types=["therapy", "journal", "personal"],
    max_anthropic_per_session=50,       # Cap premium calls
    anthropic_budget_cents=100.0,       # Cap spend at $1/session
)
```

---

### Priority 1: Volume vs Depth
- [ ] At what document length does splitting into multiple OpenAI calls beat one Anthropic call?
- [ ] For personal reflections, is emotional nuance worth the cost premium?
- [ ] Can we use OpenAI for first-pass extraction and Anthropic for high-significance items only?

### Priority 2: Quality Metrics
- [ ] Define "insight value" score (themes + patterns + emotional_tags + significance)
- [ ] Track insight deduplication rate per provider
- [ ] Measure downstream correlation success rate by provider

### Priority 3: Hybrid Strategy
- [ ] Test: OpenAI extraction → Anthropic synthesis
- [ ] Test: Tier 0 flags trigger provider selection (high_emotion → Anthropic?)
- [ ] Test: Document type routing (chat → OpenAI, journal → Anthropic)

---

## Test Protocol Template

```markdown
### Test: [Name]
**Date:** YYYY-MM-DD
**Input:** [description, word count]
**Hypothesis:** [what we're testing]

| Metric | Provider A | Provider B |
|--------|------------|------------|
| Insights | | |
| Tokens | | |
| Confidence avg | | |
| Significance avg | | |
| Emotions | | |
| Patterns | | |

**Findings:** [what we learned]
**Action:** [changes to make]
```

---

## Configuration Recommendations (Current)

Based on initial findings:

| Use Case | Recommended Provider | Rationale |
|----------|---------------------|-----------|
| Bulk extraction (>100 docs) | OpenAI gpt-4o-mini | Cost efficiency |
| Personal reflections | TBD - need more data | Emotional nuance may justify cost |
| Chat transcripts | OpenAI gpt-4o-mini | High volume, speaker attribution handled |
| Synthesis reports | Anthropic Claude | Complex reasoning needed |
| Correlation analysis | Anthropic Claude | Pattern recognition strength |

---

*Log created: 21 Dec 2025*
*Last updated: 21 Dec 2025*
