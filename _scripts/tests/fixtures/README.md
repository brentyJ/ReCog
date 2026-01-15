# Test Fixtures

Minimal valid examples for parser testing.

## Contents

### Calendar (ICS)
- `minimal.ics` - Single event, UTC time
- `outlook.ics` - Windows timezone format
- `recurring.ics` - Event with RRULE

### Contacts (VCF)
- `minimal.vcf` - Single contact, UTF-8
- `legacy.vcf` - vCard 2.1, Windows-1252 encoding
- `multi.vcf` - Multiple contacts

### CSV
- `minimal.csv` - Basic CSV
- `bom.csv` - UTF-8 with BOM
- `linkedin.csv` - LinkedIn Connections format
- `spotify.csv` - Spotify streaming history

### Archives
- `minimal.zip` - Single text file
- (NOTE: zip bomb and nested archive tests use programmatic fixtures)

### XML
- `health_sample.xml` - Apple Health export sample

## Creating Test Files

Most fixtures are created programmatically in tests to ensure:
1. No external dependencies
2. Consistent, known content
3. Easy updates when format requirements change

Use `conftest.py` fixtures like:
```python
@pytest.fixture
def sample_ics(tmp_path):
    ics = tmp_path / "test.ics"
    ics.write_bytes(b"BEGIN:VCALENDAR...")
    return ics
```

## Sample Data Sources

For realistic test data (not checked in):
- **Facebook**: facebook.com/dyi → "Download Your Information"
- **Twitter**: twitter.com/settings/download_your_data
- **Google**: takeout.google.com
- **Apple Health**: Health app → Profile → Export All Health Data
- **LinkedIn**: linkedin.com/psettings/member-data

Never commit real personal data. Use synthetic/fake data for tests.
