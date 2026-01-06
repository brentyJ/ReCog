"""
ReCog Case Store Tests - Case Architecture

Tests the CaseStore, FindingsStore, and TimelineStore classes
without requiring the server to be running.

Run with: pytest tests/test_cases.py -v
"""

import sys
import json
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# pytest is optional for standalone runner
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    pytest = None

from recog_engine.case_store import Case, CaseDocument, CaseContext, CaseStore
from recog_engine.findings_store import Finding, FindingsStore
from recog_engine.timeline_store import TimelineEvent, TimelineStore, VALID_EVENT_TYPES


# =============================================================================
# DATABASE SETUP HELPER
# =============================================================================

def create_test_db(db_path):
    """Initialize test database with required tables."""
    conn = sqlite3.connect(str(db_path))

    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            context TEXT,
            focus_areas_json TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived')),
            document_count INTEGER DEFAULT 0,
            findings_count INTEGER DEFAULT 0,
            patterns_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS case_documents (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            added_at TEXT,
            impact_notes TEXT,
            findings_count INTEGER DEFAULT 0,
            entities_count INTEGER DEFAULT 0,
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
            UNIQUE(case_id, document_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            insight_id TEXT NOT NULL,
            status TEXT DEFAULT 'needs_verification'
                CHECK(status IN ('verified', 'needs_verification', 'rejected')),
            verified_at TEXT,
            verified_by TEXT,
            tags_json TEXT,
            user_notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
            UNIQUE(case_id, insight_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS case_timeline (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data_json TEXT,
            human_annotation TEXT,
            timestamp TEXT,
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS insights (
            id TEXT PRIMARY KEY,
            case_id TEXT,
            summary TEXT,
            significance REAL DEFAULT 0.5,
            confidence REAL DEFAULT 0.5,
            excerpt TEXT,
            themes_json TEXT,
            status TEXT DEFAULT 'raw'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id TEXT PRIMARY KEY,
            case_id TEXT
        )
    """)

    conn.commit()
    conn.close()


# =============================================================================
# FIXTURES (pytest only)
# =============================================================================

if HAS_PYTEST:
    @pytest.fixture
    def db_path():
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = Path(f.name)

        create_test_db(temp_path)

        yield temp_path

        try:
            temp_path.unlink()
        except:
            pass

    @pytest.fixture
    def case_store(db_path):
        """Create a CaseStore instance."""
        return CaseStore(db_path)

    @pytest.fixture
    def findings_store(db_path):
        """Create a FindingsStore instance."""
        return FindingsStore(db_path)

    @pytest.fixture
    def timeline_store(db_path):
        """Create a TimelineStore instance."""
        return TimelineStore(db_path)

    @pytest.fixture
    def sample_case(case_store):
        """Create a sample case for testing."""
        return case_store.create_case(
            title="Test Investigation",
            context="Investigating Q3 revenue drop",
            focus_areas=["revenue", "pricing", "competition"]
        )

    @pytest.fixture
    def sample_insight(db_path):
        """Create a sample insight for findings tests."""
        conn = sqlite3.connect(str(db_path))
        insight_id = "test-insight-001"
        conn.execute("""
            INSERT INTO insights (id, summary, significance, confidence, excerpt, themes_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (insight_id, "Test insight summary", 0.8, 0.9, "Test excerpt", '["test", "theme"]', "refined"))
        conn.commit()
        conn.close()
        return insight_id


# =============================================================================
# CASE STORE TESTS
# =============================================================================

class TestCaseStore:
    """Tests for CaseStore class."""

    def test_create_case(self, case_store):
        """Should create a new case with all fields."""
        case = case_store.create_case(
            title="Test Case",
            context="Test context",
            focus_areas=["area1", "area2"]
        )

        assert case is not None
        assert case.id is not None
        assert case.title == "Test Case"
        assert case.context == "Test context"
        assert case.focus_areas == ["area1", "area2"]
        assert case.status == "active"
        assert case.document_count == 0
        assert case.created_at is not None

    def test_create_case_minimal(self, case_store):
        """Should create a case with just a title."""
        case = case_store.create_case(title="Minimal Case")

        assert case is not None
        assert case.title == "Minimal Case"
        assert case.context == ""
        assert case.focus_areas == []

    def test_get_case(self, case_store, sample_case):
        """Should retrieve a case by ID."""
        retrieved = case_store.get_case(sample_case.id)

        assert retrieved is not None
        assert retrieved.id == sample_case.id
        assert retrieved.title == sample_case.title
        assert retrieved.focus_areas == sample_case.focus_areas

    def test_get_case_not_found(self, case_store):
        """Should return None for non-existent case."""
        result = case_store.get_case("nonexistent-id")
        assert result is None

    def test_list_cases(self, case_store):
        """Should list all cases."""
        case_store.create_case(title="Case 1")
        case_store.create_case(title="Case 2")
        case_store.create_case(title="Case 3")

        result = case_store.list_cases()

        assert result["total"] == 3
        assert len(result["cases"]) == 3

    def test_list_cases_filter_status(self, case_store):
        """Should filter cases by status."""
        case1 = case_store.create_case(title="Active Case")
        case2 = case_store.create_case(title="Archived Case")
        case_store.update_case(case2.id, status="archived")

        active = case_store.list_cases(status="active")
        archived = case_store.list_cases(status="archived")

        assert active["total"] == 1
        assert archived["total"] == 1

    def test_list_cases_pagination(self, case_store):
        """Should support pagination."""
        for i in range(10):
            case_store.create_case(title=f"Case {i}")

        page1 = case_store.list_cases(limit=3, offset=0)
        page2 = case_store.list_cases(limit=3, offset=3)

        assert len(page1["cases"]) == 3
        assert len(page2["cases"]) == 3
        assert page1["cases"][0]["id"] != page2["cases"][0]["id"]

    def test_update_case_title(self, case_store, sample_case):
        """Should update case title."""
        result = case_store.update_case(sample_case.id, title="New Title")

        assert result is True
        updated = case_store.get_case(sample_case.id)
        assert updated.title == "New Title"

    def test_update_case_context(self, case_store, sample_case):
        """Should update case context."""
        result = case_store.update_case(sample_case.id, context="New context")

        assert result is True
        updated = case_store.get_case(sample_case.id)
        assert updated.context == "New context"

    def test_update_case_status(self, case_store, sample_case):
        """Should update case status."""
        result = case_store.update_case(sample_case.id, status="archived")

        assert result is True
        updated = case_store.get_case(sample_case.id)
        assert updated.status == "archived"

    def test_update_case_invalid_status(self, case_store, sample_case):
        """Should reject invalid status."""
        with pytest.raises(ValueError):
            case_store.update_case(sample_case.id, status="invalid")

    def test_update_case_not_found(self, case_store):
        """Should return False for non-existent case."""
        result = case_store.update_case("nonexistent", title="New")
        assert result is False

    def test_delete_case(self, case_store, sample_case):
        """Should delete a case."""
        result = case_store.delete_case(sample_case.id)

        assert result is True
        assert case_store.get_case(sample_case.id) is None

    def test_delete_case_not_found(self, case_store):
        """Should return False for non-existent case."""
        result = case_store.delete_case("nonexistent")
        assert result is False

    def test_add_document(self, case_store, sample_case):
        """Should add a document to a case."""
        doc = case_store.add_document(
            sample_case.id,
            "doc-123",
            impact_notes="Important document"
        )

        assert doc is not None
        assert doc.case_id == sample_case.id
        assert doc.document_id == "doc-123"
        assert doc.impact_notes == "Important document"

        # Check count updated
        updated = case_store.get_case(sample_case.id)
        assert updated.document_count == 1

    def test_add_document_duplicate(self, case_store, sample_case):
        """Should not allow duplicate documents."""
        case_store.add_document(sample_case.id, "doc-123")
        result = case_store.add_document(sample_case.id, "doc-123")

        assert result is None

    def test_add_document_invalid_case(self, case_store):
        """Should return None for invalid case."""
        result = case_store.add_document("nonexistent", "doc-123")
        assert result is None

    def test_list_documents(self, case_store, sample_case):
        """Should list documents in a case."""
        case_store.add_document(sample_case.id, "doc-1")
        case_store.add_document(sample_case.id, "doc-2")
        case_store.add_document(sample_case.id, "doc-3")

        docs = case_store.list_documents(sample_case.id)

        assert len(docs) == 3

    def test_remove_document(self, case_store, sample_case):
        """Should remove a document from a case."""
        case_store.add_document(sample_case.id, "doc-123")
        result = case_store.remove_document(sample_case.id, "doc-123")

        assert result is True

        updated = case_store.get_case(sample_case.id)
        assert updated.document_count == 0

    def test_get_context(self, case_store, sample_case):
        """Should return case context for prompt injection."""
        context = case_store.get_context(sample_case.id)

        assert context is not None
        assert isinstance(context, CaseContext)
        assert context.title == sample_case.title
        assert context.context == sample_case.context
        assert context.focus_areas == sample_case.focus_areas

    def test_get_context_prompt_string(self, case_store, sample_case):
        """Should generate prompt string from context."""
        context = case_store.get_context(sample_case.id)
        prompt = context.to_prompt_string()

        assert "CASE CONTEXT:" in prompt
        assert sample_case.title in prompt
        assert "revenue" in prompt  # focus area

    def test_get_stats(self, case_store, sample_case):
        """Should return case statistics."""
        case_store.add_document(sample_case.id, "doc-1")
        case_store.add_document(sample_case.id, "doc-2")

        stats = case_store.get_stats(sample_case.id)

        assert stats is not None
        assert stats["case_id"] == sample_case.id
        assert stats["document_count"] == 2

    def test_case_to_dict(self, sample_case):
        """Case should serialize to dict."""
        d = sample_case.to_dict()

        assert d["id"] == sample_case.id
        assert d["title"] == sample_case.title
        assert d["focus_areas"] == sample_case.focus_areas


# =============================================================================
# FINDINGS STORE TESTS
# =============================================================================

class TestFindingsStore:
    """Tests for FindingsStore class."""

    def test_promote_insight(self, findings_store, sample_case, sample_insight):
        """Should promote an insight to a finding."""
        finding = findings_store.promote_insight(
            sample_case.id,
            sample_insight,
            tags=["important"],
            user_notes="Key finding"
        )

        assert finding is not None
        assert finding.case_id == sample_case.id
        assert finding.insight_id == sample_insight
        assert finding.status == "needs_verification"
        assert "important" in finding.tags
        assert finding.user_notes == "Key finding"

    def test_promote_insight_auto_verify(self, findings_store, sample_case, sample_insight):
        """Should auto-verify if requested."""
        finding = findings_store.promote_insight(
            sample_case.id,
            sample_insight,
            auto_verify=True
        )

        assert finding is not None
        assert finding.status == "verified"
        assert finding.verified_at is not None
        assert finding.verified_by == "auto"

    def test_promote_insight_duplicate(self, findings_store, sample_case, sample_insight):
        """Should not allow duplicate promotions."""
        findings_store.promote_insight(sample_case.id, sample_insight)
        result = findings_store.promote_insight(sample_case.id, sample_insight)

        assert result is None

    def test_promote_insight_invalid_case(self, findings_store, sample_insight):
        """Should return None for invalid case."""
        result = findings_store.promote_insight("nonexistent", sample_insight)
        assert result is None

    def test_promote_insight_invalid_insight(self, findings_store, sample_case):
        """Should return None for invalid insight."""
        result = findings_store.promote_insight(sample_case.id, "nonexistent")
        assert result is None

    def test_get_finding(self, findings_store, sample_case, sample_insight):
        """Should retrieve a finding by ID."""
        created = findings_store.promote_insight(sample_case.id, sample_insight)

        finding = findings_store.get_finding(created.id)

        assert finding is not None
        assert finding.id == created.id

    def test_get_finding_with_insight(self, findings_store, sample_case, sample_insight):
        """Should include insight details when requested."""
        created = findings_store.promote_insight(sample_case.id, sample_insight)

        finding = findings_store.get_finding(created.id, include_insight=True)

        assert finding is not None
        assert finding.insight_summary == "Test insight summary"
        assert finding.insight_significance == 0.8

    def test_list_findings(self, findings_store, sample_case, db_path):
        """Should list findings for a case."""
        # Create multiple insights
        conn = sqlite3.connect(str(db_path))
        for i in range(3):
            conn.execute(
                "INSERT INTO insights (id, summary) VALUES (?, ?)",
                (f"insight-{i}", f"Summary {i}")
            )
        conn.commit()
        conn.close()

        # Promote all
        for i in range(3):
            findings_store.promote_insight(sample_case.id, f"insight-{i}")

        result = findings_store.list_findings(sample_case.id)

        assert result["total"] == 3
        assert len(result["findings"]) == 3

    def test_list_findings_filter_status(self, findings_store, sample_case, db_path):
        """Should filter findings by status."""
        conn = sqlite3.connect(str(db_path))
        for i in range(3):
            conn.execute(
                "INSERT INTO insights (id, summary) VALUES (?, ?)",
                (f"insight-{i}", f"Summary {i}")
            )
        conn.commit()
        conn.close()

        f1 = findings_store.promote_insight(sample_case.id, "insight-0")
        f2 = findings_store.promote_insight(sample_case.id, "insight-1", auto_verify=True)
        f3 = findings_store.promote_insight(sample_case.id, "insight-2")

        verified = findings_store.list_findings(sample_case.id, status="verified")
        needs = findings_store.list_findings(sample_case.id, status="needs_verification")

        assert verified["total"] == 1
        assert needs["total"] == 2

    def test_update_status_verified(self, findings_store, sample_case, sample_insight):
        """Should update status to verified."""
        finding = findings_store.promote_insight(sample_case.id, sample_insight)

        result = findings_store.update_status(finding.id, "verified")

        assert result is True
        updated = findings_store.get_finding(finding.id)
        assert updated.status == "verified"
        assert updated.verified_at is not None

    def test_update_status_rejected(self, findings_store, sample_case, sample_insight):
        """Should update status to rejected."""
        finding = findings_store.promote_insight(sample_case.id, sample_insight)

        result = findings_store.update_status(finding.id, "rejected")

        assert result is True
        updated = findings_store.get_finding(finding.id)
        assert updated.status == "rejected"

    def test_update_status_invalid(self, findings_store, sample_case, sample_insight):
        """Should reject invalid status."""
        finding = findings_store.promote_insight(sample_case.id, sample_insight)

        with pytest.raises(ValueError):
            findings_store.update_status(finding.id, "invalid")

    def test_add_note(self, findings_store, sample_case, sample_insight):
        """Should add user notes to finding."""
        finding = findings_store.promote_insight(sample_case.id, sample_insight)

        result = findings_store.add_note(finding.id, "This is an important observation")

        assert result is True
        updated = findings_store.get_finding(finding.id)
        assert updated.user_notes == "This is an important observation"

    def test_update_tags(self, findings_store, sample_case, sample_insight):
        """Should update finding tags."""
        finding = findings_store.promote_insight(sample_case.id, sample_insight)

        result = findings_store.update_tags(finding.id, ["tag1", "tag2", "tag3"])

        assert result is True
        updated = findings_store.get_finding(finding.id)
        assert updated.tags == ["tag1", "tag2", "tag3"]

    def test_delete_finding(self, findings_store, sample_case, sample_insight):
        """Should delete (demote) a finding."""
        finding = findings_store.promote_insight(sample_case.id, sample_insight)

        result = findings_store.delete_finding(finding.id)

        assert result is True
        assert findings_store.get_finding(finding.id) is None

    def test_get_stats(self, findings_store, sample_case, db_path):
        """Should return findings statistics."""
        conn = sqlite3.connect(str(db_path))
        for i in range(5):
            conn.execute(
                "INSERT INTO insights (id, summary) VALUES (?, ?)",
                (f"insight-{i}", f"Summary {i}")
            )
        conn.commit()
        conn.close()

        findings_store.promote_insight(sample_case.id, "insight-0", auto_verify=True)
        findings_store.promote_insight(sample_case.id, "insight-1", auto_verify=True)
        findings_store.promote_insight(sample_case.id, "insight-2")
        findings_store.promote_insight(sample_case.id, "insight-3")
        findings_store.promote_insight(sample_case.id, "insight-4")

        stats = findings_store.get_stats(sample_case.id)

        assert stats["total"] == 5
        assert stats["by_status"]["verified"] == 2
        assert stats["by_status"]["needs_verification"] == 3
        assert stats["verified_rate"] == 40.0

    def test_finding_to_dict(self, findings_store, sample_case, sample_insight):
        """Finding should serialize to dict."""
        finding = findings_store.promote_insight(sample_case.id, sample_insight)
        d = finding.to_dict()

        assert d["id"] == finding.id
        assert d["case_id"] == sample_case.id
        assert d["status"] == "needs_verification"


# =============================================================================
# TIMELINE STORE TESTS
# =============================================================================

class TestTimelineStore:
    """Tests for TimelineStore class."""

    def test_log_event(self, timeline_store, sample_case):
        """Should log a timeline event."""
        event = timeline_store.log_event(
            sample_case.id,
            "case_created",
            {"title": sample_case.title}
        )

        assert event is not None
        assert event.case_id == sample_case.id
        assert event.event_type == "case_created"
        assert event.event_data["title"] == sample_case.title
        assert event.timestamp is not None

    def test_log_event_with_annotation(self, timeline_store, sample_case):
        """Should log event with human annotation."""
        event = timeline_store.log_event(
            sample_case.id,
            "note_added",
            {"note": "Important observation"},
            human_annotation="Added by analyst"
        )

        assert event.human_annotation == "Added by analyst"

    def test_log_event_invalid_type(self, timeline_store, sample_case):
        """Should reject invalid event types."""
        with pytest.raises(ValueError):
            timeline_store.log_event(sample_case.id, "invalid_type")

    def test_valid_event_types(self):
        """All expected event types should be valid."""
        expected = [
            "case_created", "doc_added", "doc_removed",
            "finding_added", "finding_verified", "finding_rejected",
            "pattern_found", "note_added", "context_updated",
            "status_changed", "insights_extracted"
        ]

        for event_type in expected:
            assert event_type in VALID_EVENT_TYPES

    def test_add_annotation(self, timeline_store, sample_case):
        """Should add annotation to existing event."""
        event = timeline_store.log_event(sample_case.id, "doc_added", {})

        result = timeline_store.add_annotation(event.id, "New annotation")

        assert result is True
        updated = timeline_store.get_event(event.id)
        assert updated.human_annotation == "New annotation"

    def test_add_annotation_not_found(self, timeline_store):
        """Should return False for non-existent event."""
        result = timeline_store.add_annotation("nonexistent", "Note")
        assert result is False

    def test_get_timeline(self, timeline_store, sample_case):
        """Should retrieve timeline events."""
        timeline_store.log_event(sample_case.id, "case_created", {})
        timeline_store.log_event(sample_case.id, "doc_added", {})
        timeline_store.log_event(sample_case.id, "finding_added", {})

        result = timeline_store.get_timeline(sample_case.id)

        assert result["total"] == 3
        assert len(result["events"]) == 3

    def test_get_timeline_filter_types(self, timeline_store, sample_case):
        """Should filter by event types."""
        timeline_store.log_event(sample_case.id, "case_created", {})
        timeline_store.log_event(sample_case.id, "doc_added", {})
        timeline_store.log_event(sample_case.id, "doc_added", {})
        timeline_store.log_event(sample_case.id, "finding_added", {})

        result = timeline_store.get_timeline(
            sample_case.id,
            event_types=["doc_added"]
        )

        assert result["total"] == 2

    def test_get_timeline_pagination(self, timeline_store, sample_case):
        """Should support pagination."""
        for _ in range(10):
            timeline_store.log_event(sample_case.id, "note_added", {})

        page1 = timeline_store.get_timeline(sample_case.id, limit=3, offset=0)
        page2 = timeline_store.get_timeline(sample_case.id, limit=3, offset=3)

        assert len(page1["events"]) == 3
        assert len(page2["events"]) == 3

    def test_get_timeline_order(self, timeline_store, sample_case):
        """Should support ordering."""
        timeline_store.log_event(sample_case.id, "case_created", {"order": 1})
        timeline_store.log_event(sample_case.id, "doc_added", {"order": 2})
        timeline_store.log_event(sample_case.id, "doc_added", {"order": 3})

        desc = timeline_store.get_timeline(sample_case.id, order="DESC")
        asc = timeline_store.get_timeline(sample_case.id, order="ASC")

        # DESC should have newest first (highest order)
        assert desc["events"][0]["event_data"]["order"] == 3
        # ASC should have oldest first (lowest order)
        assert asc["events"][0]["event_data"]["order"] == 1

    def test_get_event(self, timeline_store, sample_case):
        """Should retrieve single event."""
        created = timeline_store.log_event(sample_case.id, "case_created", {})

        event = timeline_store.get_event(created.id)

        assert event is not None
        assert event.id == created.id

    def test_get_event_not_found(self, timeline_store):
        """Should return None for non-existent event."""
        result = timeline_store.get_event("nonexistent")
        assert result is None

    def test_get_recent_activity(self, timeline_store, sample_case):
        """Should return recent events."""
        for i in range(20):
            timeline_store.log_event(sample_case.id, "note_added", {"num": i})

        recent = timeline_store.get_recent_activity(sample_case.id, limit=5)

        assert len(recent) == 5

    def test_get_summary(self, timeline_store, sample_case):
        """Should return timeline summary."""
        timeline_store.log_event(sample_case.id, "case_created", {})
        timeline_store.log_event(sample_case.id, "doc_added", {})
        timeline_store.log_event(sample_case.id, "doc_added", {})
        timeline_store.log_event(sample_case.id, "finding_verified", {})

        summary = timeline_store.get_summary(sample_case.id)

        assert summary["total_events"] == 4
        assert summary["by_type"]["doc_added"] == 2
        assert summary["by_type"]["case_created"] == 1

    def test_event_description(self, timeline_store, sample_case):
        """Event should generate human-readable description."""
        event = timeline_store.log_event(
            sample_case.id,
            "case_created",
            {"title": "Test Investigation"}
        )

        d = event.to_dict()

        assert "description" in d
        assert "Test Investigation" in d["description"]

    def test_timeline_event_to_dict(self, timeline_store, sample_case):
        """TimelineEvent should serialize to dict."""
        event = timeline_store.log_event(sample_case.id, "note_added", {"note": "test"})
        d = event.to_dict()

        assert d["id"] == event.id
        assert d["case_id"] == sample_case.id
        assert d["event_type"] == "note_added"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestCaseIntegration:
    """Integration tests across stores."""

    def test_case_timeline_auto_logged(self, case_store, timeline_store, db_path):
        """Case creation should auto-log timeline event."""
        case = case_store.create_case(title="Test", focus_areas=["test"])

        events = timeline_store.get_timeline(case.id)

        assert events["total"] >= 1
        assert any(e["event_type"] == "case_created" for e in events["events"])

    def test_document_timeline_auto_logged(self, case_store, timeline_store, sample_case):
        """Document addition should auto-log timeline event."""
        case_store.add_document(sample_case.id, "doc-123")

        events = timeline_store.get_timeline(sample_case.id)

        assert any(e["event_type"] == "doc_added" for e in events["events"])

    def test_finding_timeline_auto_logged(self, findings_store, timeline_store, sample_case, sample_insight):
        """Finding promotion should auto-log timeline event."""
        findings_store.promote_insight(sample_case.id, sample_insight)

        events = timeline_store.get_timeline(sample_case.id)

        assert any(e["event_type"] == "finding_added" for e in events["events"])

    def test_case_counts_accurate(self, case_store, findings_store, sample_case, db_path):
        """Case counts should stay accurate."""
        # Add documents
        case_store.add_document(sample_case.id, "doc-1")
        case_store.add_document(sample_case.id, "doc-2")

        # Add insights and promote
        conn = sqlite3.connect(str(db_path))
        for i in range(3):
            conn.execute(
                "INSERT INTO insights (id, summary) VALUES (?, ?)",
                (f"insight-{i}", f"Summary {i}")
            )
        conn.commit()
        conn.close()

        findings_store.promote_insight(sample_case.id, "insight-0")
        findings_store.promote_insight(sample_case.id, "insight-1")

        # Update counts
        case_store.update_counts(sample_case.id)

        case = case_store.get_case(sample_case.id)
        assert case.document_count == 2
        assert case.findings_count == 2


# =============================================================================
# STANDALONE RUNNER
# =============================================================================

if __name__ == "__main__":
    import traceback

    print("=" * 60)
    print("CASE STORE TEST SUITE")
    print("=" * 60)
    print("Note: Run with pytest for full test execution")
    print("      pytest tests/test_cases.py -v")
    print()

    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Initialize database using helper
        create_test_db(temp_path)

        # Initialize stores
        case_store = CaseStore(temp_path)
        findings_store = FindingsStore(temp_path)
        timeline_store = TimelineStore(temp_path)

        tests = [
            ("CaseStore: Create case", lambda: case_store.create_case("Test") is not None),
            ("CaseStore: Get case", lambda: case_store.get_case(case_store.list_cases()["cases"][0]["id"]) is not None),
            ("CaseStore: List cases", lambda: case_store.list_cases()["total"] >= 1),
            ("TimelineStore: Log event", lambda: timeline_store.log_event(
                case_store.list_cases()["cases"][0]["id"], "note_added", {}
            ) is not None),
            ("TimelineStore: Get timeline", lambda: timeline_store.get_timeline(
                case_store.list_cases()["cases"][0]["id"]
            )["total"] >= 0),
        ]

        passed = 0
        failed = 0

        for name, test_fn in tests:
            try:
                if test_fn():
                    print(f"  {name}")
                    passed += 1
                else:
                    print(f"  {name}")
                    failed += 1
            except Exception as e:
                print(f"  {name}: {e}")
                failed += 1

        print()
        print(f"Results: {passed} passed, {failed} failed")

    finally:
        try:
            temp_path.unlink()
        except:
            pass
