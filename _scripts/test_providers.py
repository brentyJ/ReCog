"""
ReCog LLM Provider Test Harness v1.0

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3

Runs comparative extraction tests across providers and logs results.
Usage: python test_providers.py [--samples N]
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from recog_engine.core.providers import create_provider, get_available_providers
from recog_engine import preprocess_text, build_extraction_prompt, parse_extraction_response


# =============================================================================
# TEST SAMPLES
# =============================================================================

TEST_SAMPLES = [
    {
        "id": "reflection_frustration",
        "text": "I felt frustrated today dealing with the bureaucracy at work. Tom mentioned we should try a different approach next quarter.",
        "source_type": "reflection",
        "expected_emotions": ["anger"],
        "notes": "Short personal reflection with emotional content",
    },
    {
        "id": "reflection_gratitude",
        "text": "Had a really meaningful conversation with Dad today. He shared stories about his childhood that I'd never heard before. Made me realise how much I don't know about my own family history. Want to record more of these before it's too late.",
        "source_type": "reflection",
        "expected_emotions": ["gratitude", "nostalgia"],
        "notes": "Medium reflection with family themes, urgency",
    },
    {
        "id": "work_decision",
        "text": "Meeting with Sarah about the Q2 projections went better than expected. We agreed to pivot the marketing strategy toward the enterprise segment. Risk is higher but the TAM justifies it. Need to update the board deck by Friday.",
        "source_type": "document",
        "expected_emotions": [],
        "notes": "Business content, low emotional, high factual",
    },
    {
        "id": "therapy_insight",
        "text": "Dr Chen helped me see a pattern I'd been blind to - every time I feel criticised at work, I withdraw instead of engaging. It's the same thing I did with Mum growing up. The avoidance feels safe but it's actually making things worse. Going to try responding instead of retreating this week.",
        "source_type": "reflection",
        "expected_emotions": ["fear", "hope"],
        "notes": "Therapeutic insight, self-reflection, behavioural pattern",
    },
    {
        "id": "mundane_logistics",
        "text": "Picked up groceries. Need to remember to call the electrician about the kitchen light. Ordered new running shoes online.",
        "source_type": "document",
        "expected_emotions": [],
        "notes": "Should yield 0 insights - pure logistics",
    },
]


# =============================================================================
# TEST RUNNER
# =============================================================================

def run_extraction_test(
    provider_name: str,
    sample: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run extraction on a sample with a specific provider.
    
    Returns metrics dict.
    """
    start_time = time.time()
    
    try:
        provider = create_provider(provider_name)
        
        # Tier 0
        tier0 = preprocess_text(sample["text"])
        
        # Build prompt
        prompt = build_extraction_prompt(
            content=sample["text"],
            source_type=sample["source_type"],
            source_description=sample["id"],
            pre_annotation=tier0,
            is_chat=False,
        )
        
        # Call LLM
        response = provider.generate(
            prompt=prompt,
            system_prompt="You are an insight extraction system. Return valid JSON only.",
            temperature=0.3,
            max_tokens=2000,
        )
        
        elapsed = time.time() - start_time
        
        if not response.success:
            return {
                "success": False,
                "error": response.error,
                "elapsed_seconds": elapsed,
            }
        
        # Parse result
        result = parse_extraction_response(
            response.content,
            sample["source_type"],
            sample["id"],
        )
        
        # Calculate metrics
        insights = result.insights
        total_themes = sum(len(i.themes) for i in insights)
        total_patterns = sum(len(i.patterns) for i in insights)
        total_emotions = sum(len(i.emotional_tags) for i in insights)
        avg_confidence = sum(i.confidence for i in insights) / len(insights) if insights else 0
        avg_significance = sum(i.significance for i in insights) / len(insights) if insights else 0
        
        # Unique emotions found
        emotions_found = set()
        for i in insights:
            emotions_found.update(i.emotional_tags)
        
        return {
            "success": True,
            "provider": provider_name,
            "model": response.model,
            "sample_id": sample["id"],
            "word_count": len(sample["text"].split()),
            "tokens_used": response.usage.get("total_tokens", 0) if response.usage else 0,
            "elapsed_seconds": round(elapsed, 2),
            "insight_count": len(insights),
            "total_themes": total_themes,
            "total_patterns": total_patterns,
            "total_emotions": total_emotions,
            "emotions_found": list(emotions_found),
            "avg_confidence": round(avg_confidence, 2),
            "avg_significance": round(avg_significance, 2),
            "content_quality": result.content_quality,
            "insights_raw": [i.to_dict() for i in insights],
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "elapsed_seconds": time.time() - start_time,
        }


def calculate_value_score(metrics: Dict) -> float:
    """
    Calculate a composite "value" score for an extraction.
    
    Formula (experimental):
    value = (insights * 10) + (themes * 2) + (patterns * 3) + (emotions * 2)
    value *= avg_significance
    value /= (tokens / 1000)  # Cost normalisation
    
    Higher = better value per token spent
    """
    if not metrics.get("success"):
        return 0.0
    
    raw_value = (
        metrics["insight_count"] * 10 +
        metrics["total_themes"] * 2 +
        metrics["total_patterns"] * 3 +
        metrics["total_emotions"] * 2
    )
    
    # Weight by significance
    raw_value *= metrics["avg_significance"] if metrics["avg_significance"] > 0 else 0.1
    
    # Normalise by tokens (cost proxy)
    tokens = metrics.get("tokens_used", 1)
    if tokens > 0:
        value_per_1k_tokens = raw_value / (tokens / 1000)
    else:
        value_per_1k_tokens = raw_value
    
    return round(value_per_1k_tokens, 2)


def run_comparative_test(samples: List[Dict] = None) -> Dict[str, Any]:
    """
    Run all samples across all available providers.
    
    Returns comparative results.
    """
    if samples is None:
        samples = TEST_SAMPLES
    
    available = get_available_providers()
    print(f"Available providers: {available}")
    
    if not available:
        return {"error": "No providers configured"}
    
    results = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "providers": available,
        "samples_tested": len(samples),
        "results_by_sample": {},
        "summary_by_provider": {},
    }
    
    for sample in samples:
        print(f"\nTesting: {sample['id']}")
        sample_results = {}
        
        for provider in available:
            print(f"  → {provider}...", end=" ", flush=True)
            metrics = run_extraction_test(provider, sample)
            metrics["value_score"] = calculate_value_score(metrics)
            sample_results[provider] = metrics
            
            if metrics["success"]:
                print(f"{metrics['insight_count']} insights, {metrics['tokens_used']} tokens, value={metrics['value_score']}")
            else:
                print(f"ERROR: {metrics.get('error', 'unknown')}")
        
        results["results_by_sample"][sample["id"]] = sample_results
    
    # Aggregate by provider
    for provider in available:
        provider_metrics = []
        for sample_id, sample_results in results["results_by_sample"].items():
            if provider in sample_results and sample_results[provider]["success"]:
                provider_metrics.append(sample_results[provider])
        
        if provider_metrics:
            results["summary_by_provider"][provider] = {
                "samples_successful": len(provider_metrics),
                "total_tokens": sum(m["tokens_used"] for m in provider_metrics),
                "total_insights": sum(m["insight_count"] for m in provider_metrics),
                "avg_tokens_per_sample": round(sum(m["tokens_used"] for m in provider_metrics) / len(provider_metrics)),
                "avg_insights_per_sample": round(sum(m["insight_count"] for m in provider_metrics) / len(provider_metrics), 1),
                "avg_value_score": round(sum(m["value_score"] for m in provider_metrics) / len(provider_metrics), 2),
            }
    
    return results


def save_results(results: Dict, output_dir: Path = None):
    """Save results to JSON file."""
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "_docs"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"provider_test_{timestamp}.json"
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_path}")
    return output_path


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test LLM providers for extraction")
    parser.add_argument("--samples", type=int, default=None, help="Limit to first N samples")
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    args = parser.parse_args()
    
    samples = TEST_SAMPLES[:args.samples] if args.samples else TEST_SAMPLES
    
    print("=" * 60)
    print("ReCog LLM Provider Comparative Test")
    print("=" * 60)
    
    results = run_comparative_test(samples)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY BY PROVIDER")
    print("=" * 60)
    
    for provider, summary in results.get("summary_by_provider", {}).items():
        print(f"\n{provider.upper()}:")
        print(f"  Samples: {summary['samples_successful']}")
        print(f"  Total tokens: {summary['total_tokens']}")
        print(f"  Total insights: {summary['total_insights']}")
        print(f"  Avg tokens/sample: {summary['avg_tokens_per_sample']}")
        print(f"  Avg insights/sample: {summary['avg_insights_per_sample']}")
        print(f"  Avg value score: {summary['avg_value_score']}")
    
    if args.save:
        save_results(results)
    
    return results


if __name__ == "__main__":
    main()
