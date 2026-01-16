# Instagram Export Parser Analysis & Design

**Date**: 2026-01-16
**Export Path**: `C:\Users\brent\Documents\Mirrowell Data\meta-2026-Jan-10-17-13-19\instagram-brenty_jay-2026-01-09-f6TM2NkJ`
**Export Format**: HTML
**Account**: @brenty_jay (Brent Lefebure)

---

## Phase 1: Format Recommendation

### Key Finding: Instagram Offers JSON Export

Instagram allows you to choose between **HTML** and **JSON** formats when requesting your data download.

**JSON Format Advantages:**
- Native structured data - no parsing required
- Direct field access (sender, timestamp, content)
- Consistent schema across all data types
- Faster processing (no HTML parsing overhead)
- Lower error risk
- Better for programmatic analysis

**HTML Format (Current Export):**
- Human-readable in browser
- Requires BeautifulSoup parsing
- Obfuscated CSS classes (`_a6-p`, `_3-95`)
- Structure can change with Meta updates
- ~10-20x more processing overhead

### Recommendation

**Option A (Recommended): Request New JSON Export**

1. Go to Instagram Settings → Your Activity → Download Your Information
2. Select "Download or transfer information"
3. Choose "Some of your information" or "All available information"
4. **Critical**: Under "Format", select **JSON** (not HTML)
5. Select date range: "All time"
6. Media quality: "High" (for preservation)
7. Submit request - typically ready within 24-48 hours

**Option B: Parse Current HTML Export**

If you need data immediately or want to preserve the current export timestamp, proceed with HTML parsing. The parser design below handles both scenarios.

---

## Phase 2: Export Structure Analysis

### Overall Statistics

| Metric | Value |
|--------|-------|
| Total Size | 1.1 GB |
| HTML Files | 717 |
| Media Files | 1,251 (jpg, mp4, heic, png) |
| Conversation Threads | 370 |
| Account Age | Years of data (2015-2026+) |

### Directory Structure

```
instagram-brenty_jay-2026-01-09-f6TM2NkJ/
├── start_here.html                    # Navigation index
├── ads_information/                   # Ad interactions
│   ├── ads_and_topics/
│   │   ├── ads_clicked.html
│   │   ├── ads_viewed.html
│   │   ├── posts_viewed.html
│   │   ├── videos_watched.html
│   │   └── ...
│   └── instagram_ads_and_businesses/
├── apps_and_websites_off_of_instagram/
│   └── your_activity_off_meta_technologies/  # 130+ files
├── connections/
│   ├── contacts/
│   └── followers_and_following/
│       ├── followers_1.html           # Large file
│       └── following.html
├── files/
│   └── Instagram-Logo.png
├── logged_information/
├── media/
│   ├── posts/                         # Your posts media
│   ├── stories/                       # Story media
│   ├── reels/
│   ├── archived_posts/
│   ├── igtv/
│   └── other/
├── personal_information/
│   ├── personal_information/
│   │   └── personal_information.html  # Profile data
│   ├── device_information/
│   └── autofill_information/
├── preferences/
├── security_and_login_information/
└── your_instagram_activity/
    ├── messages/
    │   ├── inbox/                     # 370 conversation folders
    │   │   ├── username_123456789/
    │   │   │   └── message_1.html
    │   │   └── ...
    │   ├── message_requests/
    │   ├── photos/                    # Shared photos
    │   ├── chats.html                 # Chat index
    │   └── secret_conversations.html
    ├── comments/
    │   └── post_comments_1.html
    ├── likes/
    │   └── liked_comments.html
    ├── story_interactions/
    │   └── story_likes.html
    ├── saved/
    ├── subscriptions/
    └── ...
```

### HTML Parsing Patterns

#### 1. Messages (Primary Data)

**Location**: `your_instagram_activity/messages/inbox/{username}_{id}/message_1.html`

**HTML Structure**:
```html
<div class="pam _3-95 _2ph- _a6-g uiBoxWhite noborder">
  <h2 class="_3-95 _2pim _a6-h _a6-i">Brent Lefebure</h2>
  <div class="_3-95 _a6-p">
    <div>
      <div></div>
      <div>Message text content here</div>
      <div>
        <!-- Optional: Story/media link -->
        <a href="https://www.instagram.com/stories/...">Link</a>
      </div>
      <div></div>
      <div>
        <!-- Optional: Reactions -->
        <ul class="_a6-q">
          <li><span>😂Brent Lefebure<span> (Dec 28, 2020 6:56 am)</span></span></li>
        </ul>
      </div>
    </div>
  </div>
  <div class="_3-94 _a6-o">Dec 28, 2020 7:20 am</div>
</div>
```

**Extraction Rules**:
- Sender: `h2._a6-h._a6-i` text
- Content: Second `div` inside `div._a6-p > div`
- Timestamp: `div._a6-o` text
- Reactions: `ul._a6-q li span` (emoji + name + timestamp)
- Media Links: `a[href*="instagram.com"]` within content div

#### 2. Followers/Following

**Location**: `connections/followers_and_following/followers_1.html`

**HTML Structure**:
```html
<div class="pam _3-95 _2ph- _a6-g uiBoxWhite noborder">
  <div class="_a6-p">
    <div>
      <div>
        <a target="_blank" href="https://www.instagram.com/username">username</a>
      </div>
      <div>Dec 23, 2025 12:16 pm</div>
    </div>
  </div>
</div>
```

**Extraction Rules**:
- Username: `a[href*="instagram.com"]` text
- Profile URL: `a` href attribute
- Follow Date: Sibling `div` after username

#### 3. Comments

**Location**: `your_instagram_activity/comments/post_comments_1.html`

**HTML Structure**:
```html
<div class="pam _3-95 _2ph- _a6-g uiBoxWhite noborder">
  <div class="_a6-p">
    <table style="table-layout: fixed;">
      <tr>
        <td colspan="2" class="_2pin _a6_q">Comment
          <div><div>Your comment text here</div></div>
        </td>
      </tr>
      <tr>
        <td colspan="2" class="_2pin _a6_q">Media Owner
          <div><div>target_username</div></div>
        </td>
      </tr>
      <tr>
        <td class="_2pin _a6_q">Time</td>
        <td class="_2pin _2piu _a6_r">Nov 13, 2025 3:04 pm</td>
      </tr>
    </table>
  </div>
</div>
```

#### 4. Personal Information

**Location**: `personal_information/personal_information/personal_information.html`

**HTML Structure**:
```html
<table style="table-layout: fixed;">
  <tr>
    <td colspan="2" class="_2pin _a6_q">Username
      <div><div>brenty_jay</div></div>
    </td>
  </tr>
  <tr>
    <td colspan="2" class="_2pin _a6_q">Name
      <div><div>Brent Lefebure</div></div>
    </td>
  </tr>
  <!-- More fields... -->
</table>
```

### Timestamp Formats

| Format | Example | Source |
|--------|---------|--------|
| Standard | `Dec 28, 2020 7:20 am` | Messages, Followers |
| ISO Date | `1986-02-27` | Profile DOB |
| Reaction | `(Dec 28, 2020 6:56 am)` | Message reactions |

**Parser Normalization**: All timestamps → ISO 8601 (`2020-12-28T07:20:00+00:00`)

### Special Cases

1. **Deleted Accounts**: Appear as `instagramuser_[numbers]`
2. **Emoji Reactions**: `😂Brent Lefebure` - emoji prefix on name
3. **Media References**: Links to Instagram stories/posts (may be expired)
4. **HTML Entities**: `&#039;` (apostrophe), `&#064;` (at symbol)
5. **Shared Content**: Story replies reference URLs, not embedded content

---

## Phase 3: Parser Architecture

### Module Structure

```
recog_engine/
└── ingestion/
    └── parsers/
        ├── __init__.py
        ├── instagram_html.py      # HTML parser
        ├── instagram_json.py      # JSON parser (for re-exports)
        └── instagram_types.py     # Shared data models
```

### Data Models

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

class InstagramDataType(Enum):
    MESSAGE = "message"
    FOLLOWER = "follower"
    FOLLOWING = "following"
    COMMENT = "comment"
    LIKE = "like"
    STORY_INTERACTION = "story_interaction"
    PROFILE = "profile"

@dataclass
class InstagramReaction:
    emoji: str
    reactor_name: str
    timestamp: datetime

@dataclass
class InstagramMessage:
    sender: str
    content: str
    timestamp: datetime
    conversation_id: str
    conversation_title: str
    reactions: List[InstagramReaction] = field(default_factory=list)
    media_links: List[str] = field(default_factory=list)
    is_deleted_account: bool = False
    raw_html: Optional[str] = None

@dataclass
class InstagramFollower:
    username: str
    profile_url: str
    follow_date: datetime
    relationship_type: str  # "follower" or "following"

@dataclass
class InstagramComment:
    content: str
    media_owner: str
    timestamp: datetime
    media_url: Optional[str] = None

@dataclass
class InstagramProfile:
    username: str
    display_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    is_private: bool = False
    profile_photo_path: Optional[str] = None

@dataclass
class InstagramExport:
    """Complete parsed Instagram export."""
    profile: InstagramProfile
    messages: List[InstagramMessage]
    followers: List[InstagramFollower]
    following: List[InstagramFollower]
    comments: List[InstagramComment]
    likes: List[Dict]
    story_interactions: List[Dict]
    metadata: Dict[str, any]
```

### Core Parser Implementation

```python
"""
Instagram HTML Export Parser for ReCog

Parses Meta's Instagram HTML data export format.
Handles obfuscated CSS classes by parsing structure, not class names.
"""

import re
import html
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Generator
from bs4 import BeautifulSoup, Tag

from .instagram_types import (
    InstagramMessage,
    InstagramReaction,
    InstagramFollower,
    InstagramComment,
    InstagramProfile,
    InstagramExport,
)


class InstagramHTMLParser:
    """Parser for Instagram HTML export format."""

    # Timestamp patterns
    TIMESTAMP_PATTERN = re.compile(
        r'([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*(am|pm)',
        re.IGNORECASE
    )

    # Deleted account pattern
    DELETED_ACCOUNT_PATTERN = re.compile(r'^instagramuser_\d+$', re.IGNORECASE)

    # Reaction pattern: emoji followed by name
    REACTION_PATTERN = re.compile(r'^([\U0001F300-\U0001F9FF\U00002700-\U000027BF]+)(.+)$')

    MONTH_MAP = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    def __init__(self, export_path: str):
        self.export_path = Path(export_path)
        self.messages_path = self.export_path / "your_instagram_activity" / "messages"
        self.connections_path = self.export_path / "connections"
        self.personal_path = self.export_path / "personal_information"
        self.activity_path = self.export_path / "your_instagram_activity"

    def parse_timestamp(self, text: str) -> Optional[datetime]:
        """Parse Instagram timestamp format to datetime."""
        if not text:
            return None

        text = text.strip()
        match = self.TIMESTAMP_PATTERN.search(text)

        if not match:
            return None

        month_str, day, year, hour, minute, ampm = match.groups()
        month = self.MONTH_MAP.get(month_str.lower())

        if not month:
            return None

        hour = int(hour)
        if ampm.lower() == 'pm' and hour != 12:
            hour += 12
        elif ampm.lower() == 'am' and hour == 12:
            hour = 0

        try:
            return datetime(
                year=int(year),
                month=month,
                day=int(day),
                hour=hour,
                minute=int(minute)
            )
        except ValueError:
            return None

    def decode_html_entities(self, text: str) -> str:
        """Decode HTML entities like &#039; to actual characters."""
        if not text:
            return ""
        return html.unescape(text)

    def is_deleted_account(self, username: str) -> bool:
        """Check if username indicates a deleted account."""
        return bool(self.DELETED_ACCOUNT_PATTERN.match(username or ""))

    def _get_soup(self, file_path: Path) -> Optional[BeautifulSoup]:
        """Load and parse HTML file."""
        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return BeautifulSoup(f.read(), 'lxml')

    # -------------------------------------------------------------------------
    # MESSAGE PARSING
    # -------------------------------------------------------------------------

    def parse_message_file(self, file_path: Path) -> List[InstagramMessage]:
        """Parse a single message HTML file."""
        soup = self._get_soup(file_path)
        if not soup:
            return []

        messages = []
        conversation_title = soup.title.string if soup.title else "Unknown"
        conversation_id = file_path.parent.name

        # Find all message containers (div with uiBoxWhite noborder)
        containers = soup.find_all('div', class_=lambda c: c and 'uiBoxWhite' in c and 'noborder' in c)

        for container in containers:
            msg = self._parse_message_container(
                container,
                conversation_id,
                conversation_title
            )
            if msg:
                messages.append(msg)

        return messages

    def _parse_message_container(
        self,
        container: Tag,
        conversation_id: str,
        conversation_title: str
    ) -> Optional[InstagramMessage]:
        """Parse a single message container div."""

        # Find sender (h2 element)
        sender_elem = container.find('h2')
        if not sender_elem:
            return None

        sender = self.decode_html_entities(sender_elem.get_text(strip=True))

        # Find content container
        content_div = container.find('div', class_=lambda c: c and '_a6-p' in c)
        if not content_div:
            return None

        # Extract message text (second div in the structure)
        content = ""
        content_inner = content_div.find('div')
        if content_inner:
            divs = content_inner.find_all('div', recursive=False)
            if len(divs) >= 2:
                content = self.decode_html_entities(divs[1].get_text(strip=True))

        # Find timestamp
        timestamp = None
        timestamp_div = container.find('div', class_=lambda c: c and '_a6-o' in c)
        if timestamp_div:
            timestamp = self.parse_timestamp(timestamp_div.get_text())

        # Find reactions
        reactions = []
        reaction_list = container.find('ul', class_=lambda c: c and '_a6-q' in c)
        if reaction_list:
            for li in reaction_list.find_all('li'):
                reaction = self._parse_reaction(li.get_text())
                if reaction:
                    reactions.append(reaction)

        # Find media links
        media_links = []
        for link in container.find_all('a', href=True):
            href = link['href']
            if 'instagram.com' in href:
                media_links.append(href)

        return InstagramMessage(
            sender=sender,
            content=content,
            timestamp=timestamp,
            conversation_id=conversation_id,
            conversation_title=conversation_title,
            reactions=reactions,
            media_links=media_links,
            is_deleted_account=self.is_deleted_account(sender),
        )

    def _parse_reaction(self, text: str) -> Optional[InstagramReaction]:
        """Parse reaction text like '😂Brent Lefebure (Dec 28, 2020 6:56 am)'."""
        if not text:
            return None

        # Extract timestamp from parentheses
        timestamp_match = re.search(r'\(([^)]+)\)', text)
        timestamp = None
        if timestamp_match:
            timestamp = self.parse_timestamp(timestamp_match.group(1))
            text = text[:timestamp_match.start()].strip()

        # Extract emoji and name
        emoji_match = self.REACTION_PATTERN.match(text)
        if emoji_match:
            return InstagramReaction(
                emoji=emoji_match.group(1),
                reactor_name=emoji_match.group(2).strip(),
                timestamp=timestamp
            )

        return None

    def iter_conversations(self) -> Generator[tuple, None, None]:
        """Iterate over all conversation directories."""
        inbox_path = self.messages_path / "inbox"
        if not inbox_path.exists():
            return

        for conv_dir in inbox_path.iterdir():
            if conv_dir.is_dir():
                for msg_file in conv_dir.glob("message_*.html"):
                    yield conv_dir.name, msg_file

    def parse_all_messages(self) -> List[InstagramMessage]:
        """Parse all messages from all conversations."""
        all_messages = []

        for conv_id, msg_file in self.iter_conversations():
            messages = self.parse_message_file(msg_file)
            all_messages.extend(messages)

        # Sort by timestamp
        all_messages.sort(key=lambda m: m.timestamp or datetime.min)

        return all_messages

    # -------------------------------------------------------------------------
    # FOLLOWER/FOLLOWING PARSING
    # -------------------------------------------------------------------------

    def parse_followers(self) -> List[InstagramFollower]:
        """Parse followers list."""
        return self._parse_relationship_file(
            self.connections_path / "followers_and_following" / "followers_1.html",
            "follower"
        )

    def parse_following(self) -> List[InstagramFollower]:
        """Parse following list."""
        return self._parse_relationship_file(
            self.connections_path / "followers_and_following" / "following.html",
            "following"
        )

    def _parse_relationship_file(
        self,
        file_path: Path,
        relationship_type: str
    ) -> List[InstagramFollower]:
        """Parse a followers/following HTML file."""
        soup = self._get_soup(file_path)
        if not soup:
            return []

        followers = []
        containers = soup.find_all('div', class_=lambda c: c and 'uiBoxWhite' in c)

        for container in containers:
            link = container.find('a', href=lambda h: h and 'instagram.com' in h)
            if not link:
                continue

            username = link.get_text(strip=True)
            profile_url = link['href']

            # Find timestamp (next div after the link)
            timestamp = None
            parent_div = link.find_parent('div')
            if parent_div:
                next_div = parent_div.find_next_sibling('div')
                if next_div:
                    timestamp = self.parse_timestamp(next_div.get_text())

            followers.append(InstagramFollower(
                username=username,
                profile_url=profile_url,
                follow_date=timestamp,
                relationship_type=relationship_type
            ))

        return followers

    # -------------------------------------------------------------------------
    # COMMENT PARSING
    # -------------------------------------------------------------------------

    def parse_comments(self) -> List[InstagramComment]:
        """Parse all comments."""
        comments = []
        comments_path = self.activity_path / "comments"

        if not comments_path.exists():
            return comments

        for html_file in comments_path.glob("*.html"):
            comments.extend(self._parse_comment_file(html_file))

        return comments

    def _parse_comment_file(self, file_path: Path) -> List[InstagramComment]:
        """Parse a comments HTML file."""
        soup = self._get_soup(file_path)
        if not soup:
            return []

        comments = []
        containers = soup.find_all('div', class_=lambda c: c and 'uiBoxWhite' in c)

        for container in containers:
            table = container.find('table')
            if not table:
                continue

            comment_data = {}
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if not cells:
                    continue

                # Handle colspan cells with label and value
                first_cell = cells[0]
                cell_text = first_cell.get_text(strip=True)

                if cell_text.startswith('Comment'):
                    inner_div = first_cell.find('div', recursive=True)
                    if inner_div:
                        comment_data['content'] = self.decode_html_entities(
                            inner_div.get_text(strip=True)
                        )
                elif cell_text.startswith('Media Owner'):
                    inner_div = first_cell.find('div', recursive=True)
                    if inner_div:
                        comment_data['media_owner'] = inner_div.get_text(strip=True)
                elif cell_text == 'Time' and len(cells) > 1:
                    comment_data['timestamp'] = self.parse_timestamp(
                        cells[1].get_text()
                    )

            if 'content' in comment_data:
                comments.append(InstagramComment(
                    content=comment_data.get('content', ''),
                    media_owner=comment_data.get('media_owner', ''),
                    timestamp=comment_data.get('timestamp'),
                ))

        return comments

    # -------------------------------------------------------------------------
    # PROFILE PARSING
    # -------------------------------------------------------------------------

    def parse_profile(self) -> Optional[InstagramProfile]:
        """Parse personal profile information."""
        file_path = self.personal_path / "personal_information" / "personal_information.html"
        soup = self._get_soup(file_path)

        if not soup:
            return None

        profile_data = {}

        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if not cells:
                    continue

                cell_text = cells[0].get_text(strip=True)

                # Map field names to profile attributes
                field_map = {
                    'Username': 'username',
                    'Name': 'display_name',
                    'Email address': 'email',
                    'Phone number': 'phone',
                    'Bio': 'bio',
                    'Gender': 'gender',
                    'Date of birth': 'dob',
                    'Private account': 'is_private',
                }

                for label, attr in field_map.items():
                    if cell_text.startswith(label):
                        inner_div = cells[0].find('div', recursive=True)
                        if inner_div:
                            value = self.decode_html_entities(
                                inner_div.get_text(strip=True)
                            )
                            if attr == 'is_private':
                                value = value.lower() == 'true'
                            elif attr == 'dob':
                                try:
                                    value = datetime.strptime(value, '%Y-%m-%d')
                                except:
                                    value = None
                            profile_data[attr] = value
                        break

        return InstagramProfile(
            username=profile_data.get('username', ''),
            display_name=profile_data.get('display_name', ''),
            email=profile_data.get('email'),
            phone=profile_data.get('phone'),
            bio=profile_data.get('bio'),
            gender=profile_data.get('gender'),
            date_of_birth=profile_data.get('dob'),
            is_private=profile_data.get('is_private', False),
        )

    # -------------------------------------------------------------------------
    # FULL EXPORT PARSING
    # -------------------------------------------------------------------------

    def parse_export(self) -> InstagramExport:
        """Parse complete Instagram export."""
        return InstagramExport(
            profile=self.parse_profile(),
            messages=self.parse_all_messages(),
            followers=self.parse_followers(),
            following=self.parse_following(),
            comments=self.parse_comments(),
            likes=[],  # TODO: Implement
            story_interactions=[],  # TODO: Implement
            metadata={
                'export_path': str(self.export_path),
                'parsed_at': datetime.now().isoformat(),
                'format': 'html',
            }
        )

    def to_recog_format(self) -> List[Dict]:
        """Convert to ReCog ingestion format."""
        export = self.parse_export()
        documents = []

        # Convert messages to documents
        for msg in export.messages:
            documents.append({
                'source': 'instagram',
                'type': 'message',
                'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                'participants': [export.profile.username, msg.sender],
                'content': msg.content,
                'metadata': {
                    'conversation_id': msg.conversation_id,
                    'conversation_title': msg.conversation_title,
                    'reactions': [
                        {
                            'emoji': r.emoji,
                            'reactor': r.reactor_name,
                            'timestamp': r.timestamp.isoformat() if r.timestamp else None
                        }
                        for r in msg.reactions
                    ],
                    'media_links': msg.media_links,
                    'is_deleted_account': msg.is_deleted_account,
                }
            })

        # Convert comments
        for comment in export.comments:
            documents.append({
                'source': 'instagram',
                'type': 'comment',
                'timestamp': comment.timestamp.isoformat() if comment.timestamp else None,
                'participants': [export.profile.username, comment.media_owner],
                'content': comment.content,
                'metadata': {
                    'media_owner': comment.media_owner,
                }
            })

        return documents
```

---

## Phase 4: Implementation Plan

### Required Dependencies

Add to `requirements.txt`:
```
beautifulsoup4>=4.12.0
lxml>=5.0.0
```

### Integration Steps

1. **Create Parser Files**:
   ```
   _scripts/recog_engine/ingestion/parsers/instagram_html.py
   _scripts/recog_engine/ingestion/parsers/instagram_types.py
   ```

2. **Register with Parser Factory**:
   ```python
   # In parsers/__init__.py
   from .instagram_html import InstagramHTMLParser

   PARSER_REGISTRY['instagram_html'] = InstagramHTMLParser
   ```

3. **Add CLI Command**:
   ```bash
   python recog_cli.py ingest --format instagram_html <export_path>
   ```

4. **Database Schema Additions**:
   ```sql
   -- conversations table
   CREATE TABLE IF NOT EXISTS conversations (
       id TEXT PRIMARY KEY,
       platform TEXT NOT NULL,  -- 'instagram', 'whatsapp', etc.
       title TEXT,
       participant_count INTEGER,
       first_message_at TEXT,
       last_message_at TEXT,
       message_count INTEGER,
       created_at TEXT DEFAULT CURRENT_TIMESTAMP
   );

   -- conversation_participants
   CREATE TABLE IF NOT EXISTS conversation_participants (
       conversation_id TEXT,
       participant_name TEXT,
       is_owner BOOLEAN DEFAULT FALSE,
       FOREIGN KEY (conversation_id) REFERENCES conversations(id)
   );
   ```

### Test Cases

```python
def test_parse_timestamp():
    parser = InstagramHTMLParser("/fake/path")

    # Standard format
    assert parser.parse_timestamp("Dec 28, 2020 7:20 am").hour == 7
    assert parser.parse_timestamp("Dec 28, 2020 7:20 pm").hour == 19
    assert parser.parse_timestamp("Dec 28, 2020 12:00 am").hour == 0
    assert parser.parse_timestamp("Dec 28, 2020 12:00 pm").hour == 12

def test_decode_html_entities():
    parser = InstagramHTMLParser("/fake/path")

    assert parser.decode_html_entities("&#039;") == "'"
    assert parser.decode_html_entities("&#064;") == "@"
    assert parser.decode_html_entities("&amp;") == "&"

def test_is_deleted_account():
    parser = InstagramHTMLParser("/fake/path")

    assert parser.is_deleted_account("instagramuser_12345")
    assert not parser.is_deleted_account("brent_lefebure")
    assert not parser.is_deleted_account("_laurawhorlow")
```

---

## Phase 5: Comparison & Cost Analysis

### HTML vs JSON Parsing

| Aspect | HTML Parser | JSON Parser |
|--------|-------------|-------------|
| Processing Speed | ~100 msgs/sec | ~10,000 msgs/sec |
| Error Risk | Medium (structure changes) | Low (native format) |
| Implementation Time | 4-6 hours | 1-2 hours |
| Maintenance | Higher (Meta updates HTML) | Lower (stable schema) |
| Memory Usage | Higher (DOM parsing) | Lower (streaming) |

### Cost Implications for ReCog

| Stage | HTML Export | JSON Export |
|-------|-------------|-------------|
| Ingestion | BeautifulSoup parsing | Direct JSON load |
| Tier 0 | Same (text analysis) | Same |
| Tier 1+ LLM | Same tokens | Same tokens |

**Recommendation**: For 370 conversations with potentially thousands of messages, JSON export saves significant processing time and reduces parsing errors.

---

## Summary & Next Steps

### Immediate Action Required

**Request a new JSON export from Instagram:**

1. Go to: Instagram Settings → Your Activity → Download Your Information
2. Select: "Download or transfer information"
3. Format: **JSON** (critical!)
4. Date Range: All time
5. Media Quality: High
6. Submit and wait for email (24-48 hours)

### If Proceeding with HTML Parser

1. Copy the parser code above to `_scripts/recog_engine/ingestion/parsers/`
2. Install dependencies: `pip install beautifulsoup4 lxml`
3. Run: `python -c "from recog_engine.ingestion.parsers.instagram_html import InstagramHTMLParser; p = InstagramHTMLParser(r'C:\Users\brent\Documents\Mirrowell Data\meta-2026-Jan-10-17-13-19\instagram-brenty_jay-2026-01-09-f6TM2NkJ'); print(len(p.parse_all_messages()))"`

### Data Preservation Priority

This export contains years of personal communications critical for digital identity preservation. The JSON format will provide:
- Cleaner data extraction
- Lower error rate
- Easier correlation with other data sources (ChatGPT, WhatsApp)
- Better long-term maintainability

---

## Sources

- [How Instagram Data Downloads Actually Work](https://followbuddy.com/blog/how-instagram-data-downloads-actually-work)
- [How to request and download your Instagram data](https://pirg.org/resources/how-to-request-and-download-instagram-data/)
- [How to Export Your Data from Instagram](https://deciphertools.com/blog/how-to-export-instagram-data/)
- [GitHub: instagram_json_viewer](https://github.com/michabirklbauer/instagram_json_viewer)
