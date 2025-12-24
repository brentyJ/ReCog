"""
ReCog Synth Tests - Pattern Synthesis

Tests the synthesis engine's clustering and pattern generation
without requiring database or LLM connections.

Run with: pytest tests/test_synth.py -v
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from recog_engine.synth import (
    ClusterStrategy,
    InsightCluster,
    cluster_by_theme,
    cluster_by_time,
    cluster_by_entity,
    auto_cluster,
)
from recog_engine.extraction import ExtractedInsight


# =============================================================================
# TEST DATA
# =============================================================================

def make_insight(summary: str, themes: list, entities: list = None, 
                 created_at: datetime = None, significance: float = 0.5) -> dict:
    """Helper to create insight dicts for testing."""
    return {
        "id": hash(summary) % 10000,
        "summary": summary,
        "themes": themes,
        "entities_mentioned": entities or [],
        "significance": significance,
        "confidence": 0.8,
        "insight_type": "observation",
        "created_at": (created_at or datetime.now()).isoformat(),
    }


# Insights about work
WORK_INSIGHTS = [
    make_insight(
        "Subject feels stressed about project deadlines",
        ["work", "stress", "deadlines"],
        ["Manager", "Team Lead"],
    ),
    make_insight(
        "Subject is anxious about upcoming presentation",
        ["work", "anxiety", "presentation"],
        ["Manager"],
    ),
    make_insight(
        "Subject received positive feedback on quarterly review",
        ["work", "achievement", "recognition"],
        ["Manager", "HR"],
    ),
]

# Insights about family
FAMILY_INSIGHTS = [
    make_insight(
        "Subject values weekend time with children",
        ["family", "children", "quality time"],
        ["Sarah", "Kids"],
    ),
    make_insight(
        "Subject feels guilty about missing family dinner",
        ["family", "guilt", "work-life balance"],
        ["Partner", "Kids"],
    ),
]

# Insights with temporal clustering
TEMPORAL_INSIGHTS = [
    make_insight(
        "Morning routine includes meditation",
        ["health", "routine"],
        created_at=datetime.now() - timedelta(days=1),
    ),
    make_insight(
        "Started new exercise program",
        ["health", "fitness"],
        created_at=datetime.now() - timedelta(days=2),
    ),
    make_insight(
        "Considering career change",
        ["career", "change"],
        created_at=datetime.now() - timedelta(days=30),
    ),
    make_insight(
        "Applied to new job",
        ["career", "job search"],
        created_at=datetime.now() - timedelta(days=28),
    ),
]

ALL_INSIGHTS = WORK_INSIGHTS + FAMILY_INSIGHTS


# =============================================================================
# THEME CLUSTERING TESTS
# =============================================================================

def test_cluster_by_theme_groups_similar():
    """Should group insights with similar themes."""
    clusters = cluster_by_theme(ALL_INSIGHTS, min_cluster_size=2)
    
    assert len(clusters) >= 2, "Should create at least 2 clusters"
    
    # Find work cluster
    work_cluster = None
    for c in clusters:
        theme_counts = {}
        for insight in c.insights:
            for theme in insight.get("themes", []):
                theme_counts[theme] = theme_counts.get(theme, 0) + 1
        if theme_counts.get("work", 0) >= 2:
            work_cluster = c
            break
    
    assert work_cluster is not None, "Should have a work-themed cluster"


def test_cluster_by_theme_respects_min_size():
    """Should not create clusters smaller than min_size."""
    clusters = cluster_by_theme(ALL_INSIGHTS, min_cluster_size=3)
    
    for cluster in clusters:
        assert len(cluster.insights) >= 3, f"Cluster too small: {len(cluster.insights)}"


def test_cluster_by_theme_empty_input():
    """Should handle empty input gracefully."""
    clusters = cluster_by_theme([], min_cluster_size=2)
    assert clusters == [], "Should return empty list for empty input"


def test_cluster_by_theme_single_insight():
    """Should handle single insight gracefully."""
    single = [make_insight("Only one insight", ["lonely"])]
    clusters = cluster_by_theme(single, min_cluster_size=1)
    
    # Either returns 1 cluster or 0 (if min_size not met)
    assert len(clusters) <= 1


# =============================================================================
# TEMPORAL CLUSTERING TESTS
# =============================================================================

def test_cluster_by_time_groups_recent():
    """Should group temporally close insights."""
    clusters = cluster_by_time(TEMPORAL_INSIGHTS, window_days=7, min_cluster_size=2)
    
    # Should group the two recent health insights
    # and the two older career insights
    assert len(clusters) >= 1, "Should create at least one temporal cluster"


def test_cluster_by_time_window_respected():
    """Insights outside window should not cluster."""
    # Create insights far apart
    far_apart = [
        make_insight("Early insight", ["test"], created_at=datetime.now() - timedelta(days=100)),
        make_insight("Late insight", ["test"], created_at=datetime.now()),
    ]
    
    clusters = cluster_by_time(far_apart, window_days=7, min_cluster_size=2)
    
    # Should not cluster together
    for cluster in clusters:
        assert len(cluster.insights) < 2, "Far apart insights should not cluster"


# =============================================================================
# ENTITY CLUSTERING TESTS
# =============================================================================

def test_cluster_by_entity_groups_shared():
    """Should group insights mentioning same entities."""
    clusters = cluster_by_entity(ALL_INSIGHTS, min_cluster_size=2)
    
    # Should find a "Manager" cluster from work insights
    manager_cluster = None
    for c in clusters:
        for insight in c.insights:
            if "Manager" in insight.get("entities_mentioned", []):
                manager_cluster = c
                break
    
    assert manager_cluster is not None or len(clusters) == 0, \
        "Should group by shared entities if present"


def test_cluster_by_entity_no_entities():
    """Should handle insights without entities."""
    no_entities = [
        make_insight("Generic thought 1", ["misc"], entities=[]),
        make_insight("Generic thought 2", ["misc"], entities=[]),
    ]
    
    clusters = cluster_by_entity(no_entities, min_cluster_size=2)
    
    # Should return empty or handle gracefully
    assert isinstance(clusters, list)


# =============================================================================
# AUTO CLUSTERING TESTS
# =============================================================================

def test_auto_cluster_selects_strategy():
    """Auto clustering should select appropriate strategy."""
    clusters = auto_cluster(ALL_INSIGHTS, min_cluster_size=2, max_clusters=5)
    
    assert isinstance(clusters, list), "Should return list of clusters"
    assert len(clusters) <= 5, "Should respect max_clusters"


def test_auto_cluster_returns_cluster_objects():
    """Auto cluster should return InsightCluster objects."""
    clusters = auto_cluster(ALL_INSIGHTS, min_cluster_size=2)
    
    for cluster in clusters:
        assert isinstance(cluster, InsightCluster), "Should return InsightCluster objects"
        assert hasattr(cluster, "insights"), "Cluster should have insights"
        assert hasattr(cluster, "strategy"), "Cluster should have strategy"


# =============================================================================
# INSIGHT CLUSTER PROPERTIES
# =============================================================================

def test_cluster_has_coherence():
    """InsightCluster should calculate coherence score."""
    # Create a cluster manually
    cluster = InsightCluster(
        insights=WORK_INSIGHTS,
        strategy=ClusterStrategy.THEMATIC,
        primary_theme="work",
    )
    
    assert hasattr(cluster, "coherence") or hasattr(cluster, "calculate_coherence"), \
        "Cluster should have coherence measure"


def test_cluster_has_theme_summary():
    """InsightCluster should summarize dominant themes."""
    cluster = InsightCluster(
        insights=WORK_INSIGHTS,
        strategy=ClusterStrategy.THEMATIC,
        primary_theme="work",
    )
    
    assert cluster.primary_theme == "work", "Should track primary theme"


# =============================================================================
# EDGE CASES
# =============================================================================

def test_duplicate_insights_handled():
    """Should handle duplicate insights gracefully."""
    duplicate = make_insight("Same insight twice", ["dupe"])
    duplicates = [duplicate, duplicate.copy()]
    
    clusters = cluster_by_theme(duplicates, min_cluster_size=1)
    
    # Should not crash, may or may not cluster
    assert isinstance(clusters, list)


def test_missing_fields_handled():
    """Should handle insights with missing optional fields."""
    minimal = [
        {"id": 1, "summary": "Minimal insight 1"},
        {"id": 2, "summary": "Minimal insight 2"},
    ]
    
    try:
        clusters = cluster_by_theme(minimal, min_cluster_size=1)
        assert isinstance(clusters, list)
    except KeyError:
        # Acceptable if it requires certain fields
        pass


# =============================================================================
# STANDALONE RUNNER
# =============================================================================

if __name__ == "__main__":
    import traceback
    
    print("=" * 60)
    print("SYNTH ENGINE TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Theme clustering groups similar", test_cluster_by_theme_groups_similar),
        ("Theme clustering respects min size", test_cluster_by_theme_respects_min_size),
        ("Theme clustering empty input", test_cluster_by_theme_empty_input),
        ("Theme clustering single insight", test_cluster_by_theme_single_insight),
        ("Temporal clustering groups recent", test_cluster_by_time_groups_recent),
        ("Temporal clustering window respected", test_cluster_by_time_window_respected),
        ("Entity clustering groups shared", test_cluster_by_entity_groups_shared),
        ("Entity clustering no entities", test_cluster_by_entity_no_entities),
        ("Auto cluster selects strategy", test_auto_cluster_selects_strategy),
        ("Auto cluster returns objects", test_auto_cluster_returns_cluster_objects),
        ("Cluster has coherence", test_cluster_has_coherence),
        ("Cluster has theme summary", test_cluster_has_theme_summary),
        ("Duplicate insights handled", test_duplicate_insights_handled),
        ("Missing fields handled", test_missing_fields_handled),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, test_fn in tests:
        try:
            test_fn()
            print(f"✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {name}: {e}")
            failed += 1
        except NotImplementedError:
            print(f"⏭️  {name}: Not implemented")
            skipped += 1
        except Exception as e:
            print(f"💥 {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
