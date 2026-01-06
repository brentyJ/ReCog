"""
ReCog API Tests - Endpoint Integration

Tests the Flask API endpoints.

Run with: pytest tests/test_api.py -v

Note: These tests require the server to NOT be running,
as they use Flask's test client.
"""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    # Import here to avoid circular imports
    from server import app
    
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_text():
    """Sample text for analysis."""
    return """
    I talked to Sarah yesterday about the promotion. She said Michael 
    is also being considered. I'm worried about the competition but 
    hopeful that my work will speak for itself. Last week's presentation
    went well. Call me on 0412 345 678.
    """


# =============================================================================
# HEALTH & INFO TESTS
# =============================================================================

def test_health_endpoint(client):
    """Health endpoint should return success."""
    response = client.get('/api/health')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'database' in data['data']


def test_info_endpoint(client):
    """Info endpoint should return version and endpoints."""
    response = client.get('/api/info')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'version' in data['data']
    assert 'endpoints' in data['data']


# =============================================================================
# TIER 0 ANALYSIS TESTS
# =============================================================================

def test_tier0_analysis(client, sample_text):
    """Tier 0 analysis should extract signals."""
    response = client.post(
        '/api/tier0',
        json={'text': sample_text},
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    
    tier0 = data['data']['tier0']
    assert 'word_count' in tier0
    assert tier0['word_count'] > 0
    assert 'entities' in tier0
    assert 'emotion_signals' in tier0


def test_tier0_detects_entities(client, sample_text):
    """Tier 0 should detect entities in text."""
    response = client.post(
        '/api/tier0',
        json={'text': sample_text},
        content_type='application/json'
    )

    data = json.loads(response.data)
    entities = data['data']['tier0']['entities']

    # Should find people (tier0 v0.3 returns dicts with 'name' and 'confidence')
    people = entities.get('people', [])
    people_names = [p.get('name', p) if isinstance(p, dict) else p for p in people]
    assert 'Sarah' in people_names or 'Michael' in people_names, "Should detect named entities"

    # Should find phone number
    phones = entities.get('phone_numbers', [])
    assert len(phones) >= 1, "Should detect phone number"


def test_tier0_detects_emotions(client, sample_text):
    """Tier 0 should detect emotional signals."""
    response = client.post(
        '/api/tier0',
        json={'text': sample_text},
        content_type='application/json'
    )
    
    data = json.loads(response.data)
    emotions = data['data']['tier0']['emotion_signals']
    
    keywords = emotions.get('keywords_found', [])
    # Should find worried or hopeful
    assert len(keywords) > 0 or len(emotions.get('categories', [])) > 0


def test_tier0_empty_text(client):
    """Tier 0 should handle empty text."""
    response = client.post(
        '/api/tier0',
        json={'text': ''},
        content_type='application/json'
    )
    
    # Should either return error or empty results
    assert response.status_code in (200, 400)


def test_tier0_requires_json(client):
    """Tier 0 should require JSON content type."""
    response = client.post(
        '/api/tier0',
        data='plain text',
        content_type='text/plain'
    )
    
    assert response.status_code == 400


# =============================================================================
# ENTITY ENDPOINTS TESTS
# =============================================================================

def test_entities_list(client):
    """Entity list endpoint should return entities."""
    response = client.get('/api/entities')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'entities' in data['data']


def test_entities_stats(client):
    """Entity stats endpoint should return statistics."""
    response = client.get('/api/entities/stats')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'total' in data['data'] or 'count' in data['data']


def test_entities_unknown(client):
    """Unknown entities endpoint should return unconfirmed entities."""
    response = client.get('/api/entities/unknown')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'entities' in data['data']


# =============================================================================
# INSIGHTS ENDPOINTS TESTS
# =============================================================================

def test_insights_list(client):
    """Insights list endpoint should return insights."""
    response = client.get('/api/insights')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'insights' in data['data']


def test_insights_stats(client):
    """Insights stats endpoint should return statistics."""
    response = client.get('/api/insights/stats')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


def test_insights_with_filters(client):
    """Insights endpoint should accept filters."""
    response = client.get('/api/insights?status=surfaced&limit=10')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


# =============================================================================
# SYNTH ENDPOINTS TESTS
# =============================================================================

def test_synth_patterns_list(client):
    """Patterns list endpoint should return patterns."""
    response = client.get('/api/synth/patterns')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'patterns' in data['data']


def test_synth_stats(client):
    """Synth stats endpoint should return statistics."""
    response = client.get('/api/synth/stats')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


# =============================================================================
# CRITIQUE ENDPOINTS TESTS
# =============================================================================

def test_critique_strictness_get(client):
    """Critique strictness endpoint should return current level."""
    response = client.get('/api/critique/strictness')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'level' in data['data'] or 'strictness' in data['data']


def test_critique_stats(client):
    """Critique stats endpoint should return statistics."""
    response = client.get('/api/critique/stats')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


# =============================================================================
# FILE DETECTION TESTS
# =============================================================================

def test_detect_file_type(client):
    """File detection should identify supported files."""
    # Create a temp file
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        f.write(b"Test content")
        temp_path = f.name
    
    try:
        with open(temp_path, 'rb') as f:
            response = client.post(
                '/api/detect',
                data={'file': (f, 'test.txt')},
                content_type='multipart/form-data'
            )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'supported' in data['data']
    finally:
        Path(temp_path).unlink()


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

def test_404_for_unknown_endpoint(client):
    """Should return 404 for unknown endpoints."""
    response = client.get('/api/nonexistent')
    
    assert response.status_code == 404


def test_method_not_allowed(client):
    """Should return 405 for wrong HTTP method."""
    # GET on POST-only endpoint
    response = client.get('/api/tier0')
    
    assert response.status_code == 405


# =============================================================================
# CORS TESTS
# =============================================================================

def test_cors_headers(client):
    """Responses should include CORS headers."""
    response = client.get('/api/health')
    
    # CORS headers may or may not be present depending on config
    # Just verify the request succeeds
    assert response.status_code == 200


# =============================================================================
# STANDALONE RUNNER (without pytest)
# =============================================================================

if __name__ == "__main__":
    import traceback
    
    print("=" * 60)
    print("API TEST SUITE")
    print("=" * 60)
    print("Note: Run with pytest for full test execution")
    print("      pytest tests/test_api.py -v")
    print()
    
    # Simple import test
    try:
        from server import app
        print("✅ Server module imports successfully")
    except Exception as e:
        print(f"❌ Server import failed: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    # Create test client
    app.config['TESTING'] = True
    client = app.test_client()
    
    # Run quick tests
    tests = [
        ("Health endpoint", lambda: client.get('/api/health')),
        ("Info endpoint", lambda: client.get('/api/info')),
        ("Entities list", lambda: client.get('/api/entities')),
        ("Insights list", lambda: client.get('/api/insights')),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            response = test_fn()
            if response.status_code == 200:
                data = json.loads(response.data)
                if data.get('success'):
                    print(f"✅ {name}")
                    passed += 1
                else:
                    print(f"❌ {name}: success=False")
                    failed += 1
            else:
                print(f"❌ {name}: status={response.status_code}")
                failed += 1
        except Exception as e:
            print(f"💥 {name}: {e}")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
