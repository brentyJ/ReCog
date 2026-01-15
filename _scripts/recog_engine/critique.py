"""
ReCog Critique Engine - Validation & Self-Correction Layer

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root
Commercial licenses available: brent@ehkolabs.io

The Critique Engine validates insights and patterns before storage,
preventing hallucination propagation in the recursive pipeline.

Validation checks:
1. Citation validation - Does the excerpt support the claim?
2. Confidence calibration - Is the significance score justified?
3. Contradiction detection - Conflicts with existing patterns?
4. Grounding verification - Is this fabricated or evidence-based?

The reflexion loop allows failed items to be refined and re-evaluated.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from uuid import uuid4

from .pii_redactor import redact_for_llm, is_pii_redaction_enabled

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND TYPES
# =============================================================================

class CritiqueResult(Enum):
    """Outcome of a critique check."""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"      # Passed but with concerns
    REFINE = "refine"  # Needs adjustment, not outright rejection


class CritiqueType(Enum):
    """Types of critique checks."""
    CITATION = "citation"           # Does excerpt support claim?
    CONFIDENCE = "confidence"       # Is significance justified?
    CONTRADICTION = "contradiction" # Conflicts with existing?
    GROUNDING = "grounding"         # Fabricated vs evidence-based?
    COHERENCE = "coherence"         # Internal consistency?


class StrictnessLevel(Enum):
    """How strict the critique should be."""
    LENIENT = "lenient"     # Accept most, flag obvious issues
    STANDARD = "standard"   # Balanced validation
    STRICT = "strict"       # Rigorous, reject uncertain claims


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CritiqueCheck:
    """Result of a single critique check."""
    check_type: str
    result: str           # pass, fail, warn, refine
    score: float          # 0-1 confidence in the check result
    reason: str
    suggestions: List[str] = field(default_factory=list)
    evidence: Optional[str] = None


@dataclass
class CritiqueReport:
    """Full critique report for an item."""
    id: str
    target_type: str      # 'insight' or 'pattern'
    target_id: str
    overall_result: str   # pass, fail, warn, refine
    overall_score: float  # 0-1 aggregate confidence
    checks: List[CritiqueCheck]
    recommendation: str   # What to do with this item
    refinement_prompt: Optional[str] = None  # If refine, how to fix
    created_at: Optional[str] = None
    model_used: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['checks'] = [asdict(c) for c in self.checks]
        return d
    
    @property
    def passed(self) -> bool:
        return self.overall_result in ('pass', 'warn')
    
    @property
    def needs_refinement(self) -> bool:
        return self.overall_result == 'refine'
    
    @property
    def failed(self) -> bool:
        return self.overall_result == 'fail'


# =============================================================================
# CRITIQUE PROMPTS
# =============================================================================

CRITIQUE_SYSTEM_PROMPT = """You are a rigorous fact-checker and quality assurance system for a personal insight extraction engine.

Your job is to validate that extracted insights and synthesised patterns are:
1. GROUNDED - Claims are supported by the provided excerpts
2. CALIBRATED - Confidence/significance scores match the evidence strength
3. CONSISTENT - No contradictions with established patterns
4. COHERENT - Internal logic is sound

You are NOT checking if the content is true in an absolute sense - you're checking if the EXTRACTION is faithful to the SOURCE MATERIAL.

Be constructive: if something can be fixed, suggest how. Only fail items that are fundamentally unsound.

You think like a careful editor, not a harsh critic."""


INSIGHT_CRITIQUE_PROMPT = """Evaluate this extracted insight for quality and grounding.

## INSIGHT TO CRITIQUE
Summary: {summary}
Insight Type: {insight_type}
Significance: {significance} (0-1 scale)
Confidence: {confidence} (0-1 scale)
Themes: {themes}
Emotional Tags: {emotional_tags}

## SUPPORTING EXCERPT
"{excerpt}"

## SOURCE CONTEXT
Source Type: {source_type}
Source ID: {source_id}

## CRITIQUE CHECKS

Perform these validations:

1. **CITATION CHECK**: Does the excerpt actually support the summary claim?
   - Does the text evidence the insight, or is it inferred/fabricated?
   - Are specific claims traceable to the excerpt?

2. **CONFIDENCE CHECK**: Is the significance score ({significance}) appropriate?
   - High significance (>0.7) should have strong, clear evidence
   - Medium (0.4-0.7) for moderate evidence
   - Low (<0.4) for weak or ambiguous evidence

3. **COHERENCE CHECK**: Is the insight internally consistent?
   - Do themes match the content?
   - Do emotional tags align with the excerpt tone?

4. **GROUNDING CHECK**: Is this grounded in evidence or potentially hallucinated?
   - Red flags: specific names/dates not in excerpt, invented context
   - Green flags: direct quotes, clear paraphrasing

## RESPONSE FORMAT
Return JSON only:
```json
{{
  "checks": [
    {{
      "check_type": "citation|confidence|coherence|grounding",
      "result": "pass|fail|warn|refine",
      "score": 0.0-1.0,
      "reason": "Brief explanation",
      "suggestions": ["How to fix if needed"],
      "evidence": "Specific text supporting your judgment"
    }}
  ],
  "overall_result": "pass|fail|warn|refine",
  "overall_score": 0.0-1.0,
  "recommendation": "What to do with this insight",
  "refinement_prompt": "If refine, specific instructions for improvement"
}}
```"""


PATTERN_CRITIQUE_PROMPT = """Evaluate this synthesised pattern for quality and grounding.

## PATTERN TO CRITIQUE
Name: {name}
Description: {description}
Pattern Type: {pattern_type}
Strength: {strength} (0-1 scale)
Confidence: {confidence} (0-1 scale)
Entities Involved: {entities}

## SUPPORTING INSIGHTS ({insight_count} insights)
{insight_summaries}

## SUPPORTING EXCERPTS
{excerpts}

## CONTRADICTIONS NOTED
{contradictions}

## CRITIQUE CHECKS

Perform these validations:

1. **CITATION CHECK**: Do the supporting insights justify this pattern?
   - Is there sufficient evidence across multiple insights?
   - Are the excerpts relevant to the pattern claim?

2. **CONFIDENCE CHECK**: Is the strength score ({strength}) appropriate?
   - Strong patterns (>0.7) need clear, repeated evidence
   - Medium (0.4-0.7) for emerging patterns
   - Low (<0.4) for tentative observations

3. **CONTRADICTION CHECK**: Are noted contradictions handled appropriately?
   - Are contradictions acknowledged or explained?
   - Does the pattern still hold despite contradictions?

4. **SYNTHESIS CHECK**: Is this a genuine pattern or forced connection?
   - Red flags: cherry-picked evidence, ignoring counter-examples
   - Green flags: multiple independent sources, temporal consistency

## RESPONSE FORMAT
Return JSON only:
```json
{{
  "checks": [
    {{
      "check_type": "citation|confidence|contradiction|synthesis",
      "result": "pass|fail|warn|refine",
      "score": 0.0-1.0,
      "reason": "Brief explanation",
      "suggestions": ["How to fix if needed"],
      "evidence": "Specific text supporting your judgment"
    }}
  ],
  "overall_result": "pass|fail|warn|refine",
  "overall_score": 0.0-1.0,
  "recommendation": "What to do with this pattern",
  "refinement_prompt": "If refine, specific instructions for improvement"
}}
```"""


REFINEMENT_PROMPT = """You previously extracted an insight that needs refinement.

## ORIGINAL INSIGHT
{original_insight}

## CRITIQUE FEEDBACK
{critique_feedback}

## REFINEMENT INSTRUCTIONS
{refinement_instructions}

## SOURCE EXCERPT
"{excerpt}"

Please provide a refined version of this insight that addresses the critique.
Maintain the same JSON structure but improve the content based on feedback.

Return the refined insight as JSON only."""


# =============================================================================
# CRITIQUE ENGINE
# =============================================================================

class CritiqueEngine:
    """
    Validates insights and patterns before storage.
    
    Implements a reflexion loop:
    1. Extract/Synthesise
    2. Critique
    3. If fail → reject
    4. If refine → adjust and re-critique (max 2 iterations)
    5. If pass/warn → store with critique metadata
    """
    
    def __init__(
        self,
        db_path: Path,
        strictness: StrictnessLevel = StrictnessLevel.STANDARD,
        max_refinements: int = 2,
    ):
        self.db_path = Path(db_path)
        self.strictness = strictness
        self.max_refinements = max_refinements
        
        # Thresholds based on strictness
        self._set_thresholds()
    
    def _set_thresholds(self):
        """Set validation thresholds based on strictness level."""
        if self.strictness == StrictnessLevel.LENIENT:
            self.min_overall_score = 0.3
            self.min_check_score = 0.2
            self.require_all_pass = False
        elif self.strictness == StrictnessLevel.STRICT:
            self.min_overall_score = 0.7
            self.min_check_score = 0.5
            self.require_all_pass = True
        else:  # STANDARD
            self.min_overall_score = 0.5
            self.min_check_score = 0.3
            self.require_all_pass = False
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    # =========================================================================
    # PROMPT BUILDING
    # =========================================================================
    
    def build_insight_critique_prompt(self, insight: Dict) -> str:
        """Build critique prompt for an insight."""
        # Security: Redact PII from summary and excerpt before LLM
        summary = insight.get('summary', '')
        excerpt = insight.get('supporting_excerpt', '')
        if is_pii_redaction_enabled():
            summary = redact_for_llm(summary)
            excerpt = redact_for_llm(excerpt)

        return INSIGHT_CRITIQUE_PROMPT.format(
            summary=summary,
            insight_type=insight.get('insight_type', 'observation'),
            significance=insight.get('significance', 0.5),
            confidence=insight.get('confidence', 0.5),
            themes=', '.join(insight.get('themes', [])),
            emotional_tags=', '.join(insight.get('emotional_tags', [])),
            excerpt=excerpt,
            source_type=insight.get('source_type', 'unknown'),
            source_id=insight.get('source_id', 'unknown'),
        )
    
    def build_pattern_critique_prompt(self, pattern: Dict, insights: List[Dict]) -> str:
        """Build critique prompt for a pattern."""
        redact_pii = is_pii_redaction_enabled()

        # Format insight summaries (with PII redaction if enabled)
        insight_summaries_list = []
        for i, ins in enumerate(insights[:10]):  # Cap at 10
            summary = ins.get('summary', '')
            if redact_pii:
                summary = redact_for_llm(summary)
            insight_summaries_list.append(f"- [{i+1}] {summary}")
        insight_summaries = "\n".join(insight_summaries_list)

        # Format excerpts (with PII redaction if enabled)
        excerpts_list = []
        for i, exc in enumerate(pattern.get('supporting_excerpts', [])[:5]):
            if redact_pii:
                exc = redact_for_llm(exc)
            excerpts_list.append(f"[{i+1}] \"{exc}\"")
        excerpts = "\n".join(excerpts_list)

        # Format contradictions (with PII redaction if enabled)
        contradictions = pattern.get('contradictions', [])
        if contradictions:
            if redact_pii:
                contradictions = [redact_for_llm(c) for c in contradictions]
            contradictions_str = "\n".join(f"- {c}" for c in contradictions)
        else:
            contradictions_str = "None noted"

        # Redact pattern description if needed
        description = pattern.get('description', '')
        if redact_pii:
            description = redact_for_llm(description)

        return PATTERN_CRITIQUE_PROMPT.format(
            name=pattern.get('name', ''),
            description=description,
            pattern_type=pattern.get('pattern_type', 'behavioral'),
            strength=pattern.get('strength', 0.5),
            confidence=pattern.get('confidence', 0.5),
            entities=', '.join(pattern.get('entities_involved', [])),
            insight_count=len(insights),
            insight_summaries=insight_summaries,
            excerpts=excerpts or "No excerpts provided",
            contradictions=contradictions_str,
        )
    
    # =========================================================================
    # RESPONSE PARSING
    # =========================================================================
    
    def parse_critique_response(
        self,
        response_text: str,
        target_type: str,
        target_id: str,
        model_name: str = None,
    ) -> CritiqueReport:
        """Parse LLM critique response into CritiqueReport."""
        now = datetime.now(timezone.utc).isoformat() + "Z"
        
        try:
            # Clean up response
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            data = json.loads(text.strip())
            
            # Parse checks
            checks = []
            for check_data in data.get('checks', []):
                checks.append(CritiqueCheck(
                    check_type=check_data.get('check_type', 'unknown'),
                    result=check_data.get('result', 'warn'),
                    score=float(check_data.get('score', 0.5)),
                    reason=check_data.get('reason', ''),
                    suggestions=check_data.get('suggestions', []),
                    evidence=check_data.get('evidence'),
                ))
            
            return CritiqueReport(
                id=f"crit_{uuid4().hex[:12]}",
                target_type=target_type,
                target_id=target_id,
                overall_result=data.get('overall_result', 'warn'),
                overall_score=float(data.get('overall_score', 0.5)),
                checks=checks,
                recommendation=data.get('recommendation', ''),
                refinement_prompt=data.get('refinement_prompt'),
                created_at=now,
                model_used=model_name,
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse critique response: {e}")
            # Return a warning report
            return CritiqueReport(
                id=f"crit_{uuid4().hex[:12]}",
                target_type=target_type,
                target_id=target_id,
                overall_result='warn',
                overall_score=0.5,
                checks=[CritiqueCheck(
                    check_type='parse_error',
                    result='warn',
                    score=0.5,
                    reason=f"Could not parse critique response: {str(e)}",
                )],
                recommendation="Manual review recommended",
                created_at=now,
                model_used=model_name,
            )
    
    # =========================================================================
    # CRITIQUE EXECUTION
    # =========================================================================
    
    def critique_insight(
        self,
        insight: Dict,
        provider,  # LLMProvider instance
    ) -> CritiqueReport:
        """
        Run critique checks on an insight.
        
        Args:
            insight: Insight dictionary with summary, excerpt, etc.
            provider: LLM provider for critique generation
            
        Returns:
            CritiqueReport with validation results
        """
        prompt = self.build_insight_critique_prompt(insight)
        
        response = provider.generate(
            prompt=prompt,
            system_prompt=CRITIQUE_SYSTEM_PROMPT,
            temperature=0.2,  # Low temp for consistent judgment
            max_tokens=1500,
        )
        
        if not response.success:
            logger.error(f"Critique LLM call failed: {response.error}")
            return CritiqueReport(
                id=f"crit_{uuid4().hex[:12]}",
                target_type='insight',
                target_id=insight.get('id', 'unknown'),
                overall_result='warn',
                overall_score=0.5,
                checks=[CritiqueCheck(
                    check_type='llm_error',
                    result='warn',
                    score=0.5,
                    reason=f"LLM critique failed: {response.error}",
                )],
                recommendation="Proceed with caution - critique unavailable",
                created_at=datetime.now(timezone.utc).isoformat() + "Z",
            )
        
        return self.parse_critique_response(
            response.content,
            target_type='insight',
            target_id=insight.get('id', 'unknown'),
            model_name=response.model,
        )
    
    def critique_pattern(
        self,
        pattern: Dict,
        supporting_insights: List[Dict],
        provider,
    ) -> CritiqueReport:
        """
        Run critique checks on a synthesised pattern.
        
        Args:
            pattern: Pattern dictionary
            supporting_insights: List of insights that formed this pattern
            provider: LLM provider
            
        Returns:
            CritiqueReport with validation results
        """
        prompt = self.build_pattern_critique_prompt(pattern, supporting_insights)
        
        response = provider.generate(
            prompt=prompt,
            system_prompt=CRITIQUE_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=1500,
        )
        
        if not response.success:
            logger.error(f"Pattern critique LLM call failed: {response.error}")
            return CritiqueReport(
                id=f"crit_{uuid4().hex[:12]}",
                target_type='pattern',
                target_id=pattern.get('id', 'unknown'),
                overall_result='warn',
                overall_score=0.5,
                checks=[CritiqueCheck(
                    check_type='llm_error',
                    result='warn',
                    score=0.5,
                    reason=f"LLM critique failed: {response.error}",
                )],
                recommendation="Proceed with caution - critique unavailable",
                created_at=datetime.now(timezone.utc).isoformat() + "Z",
            )
        
        return self.parse_critique_response(
            response.content,
            target_type='pattern',
            target_id=pattern.get('id', 'unknown'),
            model_name=response.model,
        )
    
    # =========================================================================
    # VALIDATION LOGIC
    # =========================================================================
    
    def should_accept(self, report: CritiqueReport) -> bool:
        """Determine if item should be accepted based on critique report."""
        # Check overall score against threshold
        if report.overall_score < self.min_overall_score:
            return False
        
        # Check individual checks if strict mode
        if self.require_all_pass:
            for check in report.checks:
                if check.result == 'fail':
                    return False
                if check.score < self.min_check_score:
                    return False
        
        # Accept pass and warn results
        return report.overall_result in ('pass', 'warn')
    
    def should_refine(self, report: CritiqueReport) -> bool:
        """Determine if item should be refined rather than rejected."""
        return report.overall_result == 'refine' and report.refinement_prompt
    
    # =========================================================================
    # REFLEXION LOOP
    # =========================================================================
    
    def critique_with_refinement(
        self,
        insight: Dict,
        provider,
        refine_callback=None,  # Function to refine insight based on feedback
    ) -> Tuple[Dict, CritiqueReport, int]:
        """
        Run critique with reflexion loop for refinement.
        
        Args:
            insight: Original insight
            provider: LLM provider
            refine_callback: Optional function(insight, report) -> refined_insight
            
        Returns:
            Tuple of (final_insight, final_report, refinement_count)
        """
        current_insight = insight
        refinement_count = 0
        
        for iteration in range(self.max_refinements + 1):
            report = self.critique_insight(current_insight, provider)
            
            # Accept or reject
            if self.should_accept(report):
                return (current_insight, report, refinement_count)
            
            if report.failed:
                return (current_insight, report, refinement_count)
            
            # Try refinement if we have iterations left
            if self.should_refine(report) and iteration < self.max_refinements:
                if refine_callback:
                    current_insight = refine_callback(current_insight, report)
                else:
                    # Use LLM to refine
                    current_insight = self._llm_refine_insight(
                        current_insight, report, provider
                    )
                refinement_count += 1
            else:
                # No more refinements, return current state
                return (current_insight, report, refinement_count)
        
        return (current_insight, report, refinement_count)
    
    def _llm_refine_insight(
        self,
        insight: Dict,
        report: CritiqueReport,
        provider,
    ) -> Dict:
        """Use LLM to refine an insight based on critique feedback."""
        # Build feedback summary
        feedback_parts = []
        for check in report.checks:
            if check.result in ('fail', 'refine', 'warn'):
                feedback_parts.append(f"- {check.check_type}: {check.reason}")
                for suggestion in check.suggestions:
                    feedback_parts.append(f"  → {suggestion}")
        
        prompt = REFINEMENT_PROMPT.format(
            original_insight=json.dumps(insight, indent=2),
            critique_feedback="\n".join(feedback_parts),
            refinement_instructions=report.refinement_prompt or "Address the issues above",
            excerpt=insight.get('supporting_excerpt', ''),
        )
        
        response = provider.generate(
            prompt=prompt,
            system_prompt="You are refining an insight based on critique feedback. Return valid JSON only.",
            temperature=0.3,
            max_tokens=1500,
        )
        
        if not response.success:
            logger.warning(f"Refinement failed: {response.error}")
            return insight  # Return original if refinement fails
        
        try:
            text = response.content.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            refined = json.loads(text.strip())
            # Preserve ID and source info
            refined['id'] = insight.get('id')
            refined['source_type'] = insight.get('source_type')
            refined['source_id'] = insight.get('source_id')
            return refined
            
        except json.JSONDecodeError:
            logger.warning("Could not parse refined insight")
            return insight
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    def save_critique(self, report: CritiqueReport) -> bool:
        """Save critique report to database."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO critique_reports (
                    id, target_type, target_id, overall_result, overall_score,
                    checks_json, recommendation, refinement_prompt,
                    model_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report.id,
                report.target_type,
                report.target_id,
                report.overall_result,
                report.overall_score,
                json.dumps([asdict(c) for c in report.checks]),
                report.recommendation,
                report.refinement_prompt,
                report.model_used,
                report.created_at,
            ))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to save critique: {e}")
            return False
        finally:
            conn.close()
    
    def get_critique(self, critique_id: str) -> Optional[Dict]:
        """Get a critique report by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT id, target_type, target_id, overall_result, overall_score,
                       checks_json, recommendation, refinement_prompt,
                       model_used, created_at
                FROM critique_reports
                WHERE id = ?
            """, (critique_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row['id'],
                'target_type': row['target_type'],
                'target_id': row['target_id'],
                'overall_result': row['overall_result'],
                'overall_score': row['overall_score'],
                'checks': json.loads(row['checks_json']) if row['checks_json'] else [],
                'recommendation': row['recommendation'],
                'refinement_prompt': row['refinement_prompt'],
                'model_used': row['model_used'],
                'created_at': row['created_at'],
            }
        finally:
            conn.close()
    
    def get_critiques_for_target(
        self,
        target_type: str,
        target_id: str,
    ) -> List[Dict]:
        """Get all critiques for a specific insight or pattern."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT id, target_type, target_id, overall_result, overall_score,
                       checks_json, recommendation, refinement_prompt,
                       model_used, created_at
                FROM critique_reports
                WHERE target_type = ? AND target_id = ?
                ORDER BY created_at DESC
            """, (target_type, target_id))
            
            return [{
                'id': row['id'],
                'target_type': row['target_type'],
                'target_id': row['target_id'],
                'overall_result': row['overall_result'],
                'overall_score': row['overall_score'],
                'checks': json.loads(row['checks_json']) if row['checks_json'] else [],
                'recommendation': row['recommendation'],
                'refinement_prompt': row['refinement_prompt'],
                'model_used': row['model_used'],
                'created_at': row['created_at'],
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def list_critiques(
        self,
        target_type: str = None,
        result: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List critique reports with filters."""
        conn = self.get_connection()
        try:
            conditions = []
            params = []
            
            if target_type:
                conditions.append("target_type = ?")
                params.append(target_type)
            if result:
                conditions.append("overall_result = ?")
                params.append(result)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # Get total count
            count_cursor = conn.execute(
                f"SELECT COUNT(*) FROM critique_reports WHERE {where_clause}",
                params
            )
            total = count_cursor.fetchone()[0]
            
            # Get paginated results
            params.extend([limit, offset])
            cursor = conn.execute(f"""
                SELECT id, target_type, target_id, overall_result, overall_score,
                       recommendation, model_used, created_at
                FROM critique_reports
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params)
            
            critiques = [{
                'id': row['id'],
                'target_type': row['target_type'],
                'target_id': row['target_id'],
                'overall_result': row['overall_result'],
                'overall_score': row['overall_score'],
                'recommendation': row['recommendation'],
                'model_used': row['model_used'],
                'created_at': row['created_at'],
            } for row in cursor.fetchall()]
            
            return {
                'critiques': critiques,
                'total': total,
                'limit': limit,
                'offset': offset,
            }
        finally:
            conn.close()
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get critique statistics."""
        conn = self.get_connection()
        try:
            stats = {}
            
            # By result
            cursor = conn.execute("""
                SELECT overall_result, COUNT(*) as count
                FROM critique_reports
                GROUP BY overall_result
            """)
            stats['by_result'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # By target type
            cursor = conn.execute("""
                SELECT target_type, COUNT(*) as count
                FROM critique_reports
                GROUP BY target_type
            """)
            stats['by_target_type'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Average scores
            cursor = conn.execute("""
                SELECT AVG(overall_score), MIN(overall_score), MAX(overall_score)
                FROM critique_reports
            """)
            row = cursor.fetchone()
            stats['scores'] = {
                'avg': round(row[0] or 0, 3),
                'min': round(row[1] or 0, 3),
                'max': round(row[2] or 0, 3),
            }
            
            # Total
            cursor = conn.execute("SELECT COUNT(*) FROM critique_reports")
            stats['total'] = cursor.fetchone()[0]
            
            # Pass rate
            pass_count = stats['by_result'].get('pass', 0) + stats['by_result'].get('warn', 0)
            if stats['total'] > 0:
                stats['pass_rate'] = round(pass_count / stats['total'], 3)
            else:
                stats['pass_rate'] = 0
            
            return stats
        finally:
            conn.close()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_critique_engine: Optional[CritiqueEngine] = None


def init_critique_engine(
    db_path: Path,
    strictness: StrictnessLevel = StrictnessLevel.STANDARD,
) -> CritiqueEngine:
    """Initialize the global critique engine."""
    global _critique_engine
    _critique_engine = CritiqueEngine(db_path, strictness)
    return _critique_engine


def get_critique_engine() -> Optional[CritiqueEngine]:
    """Get the global critique engine."""
    return _critique_engine


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    'CritiqueResult',
    'CritiqueType',
    'StrictnessLevel',
    # Data classes
    'CritiqueCheck',
    'CritiqueReport',
    # Engine
    'CritiqueEngine',
    # Module-level
    'init_critique_engine',
    'get_critique_engine',
]
