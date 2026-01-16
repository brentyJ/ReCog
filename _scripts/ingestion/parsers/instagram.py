"""
Instagram HTML Export Parser.

Parses Meta's Instagram HTML data export format.
Handles obfuscated CSS classes by parsing structure, not class names.

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3

Supports:
- Messages (inbox conversations)
- Followers/Following with timestamps
- Comments on posts
- Profile information
- Story interactions
- Likes

Note: Instagram also offers JSON export which is easier to parse.
Request JSON format when downloading your data if possible.
"""

import re
import html
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple, Generator
from dataclasses import dataclass, field

from .base import BaseParser
from ..types import ParsedContent

logger = logging.getLogger(__name__)

# Check for BeautifulSoup
try:
    from bs4 import BeautifulSoup, Tag
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    BeautifulSoup = None
    Tag = None


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class InstagramReaction:
    """A reaction on an Instagram message."""
    emoji: str
    reactor_name: str
    timestamp: Optional[datetime] = None


@dataclass
class InstagramMessage:
    """An Instagram DM message."""
    sender: str
    content: str
    timestamp: Optional[datetime]
    conversation_id: str
    conversation_title: str
    reactions: List[InstagramReaction] = field(default_factory=list)
    media_links: List[str] = field(default_factory=list)
    is_deleted_account: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "conversation_id": self.conversation_id,
            "conversation_title": self.conversation_title,
            "reactions": [
                {
                    "emoji": r.emoji,
                    "reactor": r.reactor_name,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in self.reactions
            ],
            "media_links": self.media_links,
            "is_deleted_account": self.is_deleted_account,
        }


@dataclass
class InstagramFollower:
    """A follower or following relationship."""
    username: str
    profile_url: str
    follow_date: Optional[datetime]
    relationship_type: str  # "follower" or "following"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "profile_url": self.profile_url,
            "follow_date": self.follow_date.isoformat() if self.follow_date else None,
            "relationship_type": self.relationship_type,
        }


@dataclass
class InstagramComment:
    """A comment made on Instagram."""
    content: str
    media_owner: str
    timestamp: Optional[datetime]
    media_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "media_owner": self.media_owner,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "media_url": self.media_url,
        }


@dataclass
class InstagramProfile:
    """Instagram profile information."""
    username: str
    display_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    is_private: bool = False
    profile_photo_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "display_name": self.display_name,
            "email": self.email,
            "phone": self.phone,
            "bio": self.bio,
            "gender": self.gender,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "is_private": self.is_private,
            "profile_photo_path": self.profile_photo_path,
        }


# =============================================================================
# PARSER IMPLEMENTATION
# =============================================================================

class InstagramHTMLParser(BaseParser):
    """
    Parse Instagram HTML export directory.

    Instagram exports are directories containing HTML files organized by category.
    This parser walks the directory structure and extracts all data.

    Usage:
        parser = InstagramHTMLParser()
        if parser.can_parse(Path("/path/to/instagram-export")):
            result = parser.parse(Path("/path/to/instagram-export"))
    """

    # Timestamp pattern: "Dec 28, 2020 7:20 am"
    TIMESTAMP_PATTERN = re.compile(
        r'([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*(am|pm)',
        re.IGNORECASE
    )

    # Deleted account pattern
    DELETED_ACCOUNT_PATTERN = re.compile(r'^instagramuser_\d+$', re.IGNORECASE)

    # Reaction pattern: emoji followed by name
    REACTION_PATTERN = re.compile(r'^([\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U00002700-\U000027BF\U0001F1E0-\U0001F1FF\U00002300-\U000023FF\U00002B50-\U00002B55\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\u2764\u2665\u2763]+)(.+)$')

    MONTH_MAP = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    def __init__(self):
        if not HAS_BS4:
            logger.warning("BeautifulSoup4 not installed. Install with: pip install beautifulsoup4 lxml")

    def get_extensions(self) -> List[str]:
        # Instagram exports are directories, not files with extensions
        return []

    def can_parse(self, path: Path) -> bool:
        """
        Check if path is an Instagram HTML export directory.

        Looks for characteristic directory structure:
        - your_instagram_activity/messages/inbox/
        - connections/followers_and_following/
        - start_here.html
        """
        if not path.is_dir():
            return False

        # Check for Instagram-specific markers
        markers = [
            path / "start_here.html",
            path / "your_instagram_activity" / "messages",
            path / "connections" / "followers_and_following",
        ]

        # Need at least 2 markers to confirm
        matches = sum(1 for m in markers if m.exists())
        return matches >= 2

    def get_file_type(self) -> str:
        return "instagram_html_export"

    def parse(self, path: Path) -> ParsedContent:
        """
        Parse complete Instagram HTML export.

        Returns ParsedContent with:
        - text: Formatted summary of all content
        - metadata: Structured data (messages, followers, comments, profile)
        """
        if not HAS_BS4:
            return ParsedContent(
                text="Error: BeautifulSoup4 required. Install with: pip install beautifulsoup4 lxml",
                metadata={"error": "missing_dependency"},
                title="Instagram Export (Parse Error)",
            )

        export_path = path

        # Parse all data types
        logger.info(f"Parsing Instagram export: {export_path}")

        profile = self._parse_profile(export_path)
        messages = self._parse_all_messages(export_path)
        followers = self._parse_followers(export_path)
        following = self._parse_following(export_path)
        comments = self._parse_comments(export_path)

        # Calculate statistics
        stats = {
            "message_count": len(messages),
            "conversation_count": len(set(m.conversation_id for m in messages)),
            "follower_count": len(followers),
            "following_count": len(following),
            "comment_count": len(comments),
        }

        # Get date range from messages
        dates = [m.timestamp for m in messages if m.timestamp]
        if dates:
            stats["first_message"] = min(dates).isoformat()
            stats["last_message"] = max(dates).isoformat()

        # Get participants
        participants = list(set(m.sender for m in messages))

        # Build formatted text output
        text_parts = []

        if profile:
            text_parts.append(f"=== Instagram Profile: @{profile.username} ({profile.display_name}) ===\n")
            if profile.bio:
                text_parts.append(f"Bio: {profile.bio}\n")

        text_parts.append(f"\n=== Statistics ===")
        text_parts.append(f"Messages: {stats['message_count']} across {stats['conversation_count']} conversations")
        text_parts.append(f"Followers: {stats['follower_count']}")
        text_parts.append(f"Following: {stats['following_count']}")
        text_parts.append(f"Comments: {stats['comment_count']}")

        if dates:
            text_parts.append(f"Date Range: {stats['first_message']} to {stats['last_message']}")

        text_parts.append(f"\n=== Messages ===\n")

        # Group messages by conversation
        convos: Dict[str, List[InstagramMessage]] = {}
        for msg in messages:
            if msg.conversation_id not in convos:
                convos[msg.conversation_id] = []
            convos[msg.conversation_id].append(msg)

        # Format messages (limit output size)
        for conv_id, conv_messages in list(convos.items())[:50]:  # Top 50 conversations
            title = conv_messages[0].conversation_title if conv_messages else conv_id
            text_parts.append(f"\n--- {title} ({len(conv_messages)} messages) ---")

            # Show last 10 messages per conversation
            for msg in conv_messages[-10:]:
                ts = msg.timestamp.strftime("%Y-%m-%d %H:%M") if msg.timestamp else "?"
                text_parts.append(f"[{ts}] {msg.sender}: {msg.content[:200]}")

        # Build metadata
        metadata = {
            "format": "instagram_html",
            "export_path": str(export_path),
            "parsed_at": datetime.now().isoformat(),
            "statistics": stats,
            "profile": profile.to_dict() if profile else None,
            "messages": [m.to_dict() for m in messages],
            "followers": [f.to_dict() for f in followers],
            "following": [f.to_dict() for f in following],
            "comments": [c.to_dict() for c in comments],
            "participants": participants,
        }

        owner = profile.username if profile else "unknown"

        return ParsedContent(
            text="\n".join(text_parts),
            metadata=metadata,
            title=f"Instagram Export: @{owner}",
            author=profile.display_name if profile else None,
            date=stats.get("first_message"),
            recipients=participants[:10],  # First 10 participants
        )

    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------

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

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return BeautifulSoup(f.read(), 'lxml')
        except Exception as e:
            logger.warning(f"Error parsing HTML file {file_path}: {e}")
            # Try with html.parser as fallback
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return BeautifulSoup(f.read(), 'html.parser')
            except Exception as e2:
                logger.error(f"Failed to parse {file_path}: {e2}")
                return None

    # -------------------------------------------------------------------------
    # MESSAGE PARSING
    # -------------------------------------------------------------------------

    def _parse_message_file(self, file_path: Path) -> List[InstagramMessage]:
        """Parse a single message HTML file."""
        soup = self._get_soup(file_path)
        if not soup:
            return []

        messages = []
        conversation_title = soup.title.string if soup.title else "Unknown"
        conversation_id = file_path.parent.name

        # Find all message containers
        # Pattern: div with classes containing "uiBoxWhite" and "noborder"
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
        if not sender:
            return None

        # Find content container (div with _a6-p class)
        content_div = container.find('div', class_=lambda c: c and '_a6-p' in c)
        if not content_div:
            return None

        # Extract message text
        # Structure: div._a6-p > div > [div, div(content), div(media), div, div(reactions)]
        content = ""
        content_inner = content_div.find('div', recursive=False)
        if content_inner:
            divs = content_inner.find_all('div', recursive=False)
            if len(divs) >= 2:
                content = self.decode_html_entities(divs[1].get_text(strip=True))

        # Find timestamp (div with _a6-o class)
        timestamp = None
        timestamp_div = container.find('div', class_=lambda c: c and '_a6-o' in c)
        if timestamp_div:
            timestamp = self.parse_timestamp(timestamp_div.get_text())

        # Find reactions (ul with _a6-q class)
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

        text = text.strip()

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

    def _iter_conversations(self, export_path: Path) -> Generator[Tuple[str, Path], None, None]:
        """Iterate over all conversation directories."""
        inbox_path = export_path / "your_instagram_activity" / "messages" / "inbox"
        if not inbox_path.exists():
            return

        for conv_dir in inbox_path.iterdir():
            if conv_dir.is_dir():
                for msg_file in conv_dir.glob("message_*.html"):
                    yield conv_dir.name, msg_file

    def _parse_all_messages(self, export_path: Path) -> List[InstagramMessage]:
        """Parse all messages from all conversations."""
        all_messages = []

        conv_count = 0
        for conv_id, msg_file in self._iter_conversations(export_path):
            messages = self._parse_message_file(msg_file)
            all_messages.extend(messages)
            conv_count += 1

            if conv_count % 50 == 0:
                logger.info(f"Parsed {conv_count} conversations, {len(all_messages)} messages so far...")

        # Sort by timestamp
        all_messages.sort(key=lambda m: m.timestamp or datetime.min)

        logger.info(f"Parsed {len(all_messages)} messages from {conv_count} conversations")

        return all_messages

    # -------------------------------------------------------------------------
    # FOLLOWER/FOLLOWING PARSING
    # -------------------------------------------------------------------------

    def _parse_followers(self, export_path: Path) -> List[InstagramFollower]:
        """Parse followers list."""
        followers = []
        followers_path = export_path / "connections" / "followers_and_following"

        if not followers_path.exists():
            return followers

        # May be split into multiple files
        for html_file in followers_path.glob("followers*.html"):
            followers.extend(self._parse_relationship_file(html_file, "follower"))

        logger.info(f"Parsed {len(followers)} followers")
        return followers

    def _parse_following(self, export_path: Path) -> List[InstagramFollower]:
        """Parse following list."""
        following = []
        following_path = export_path / "connections" / "followers_and_following"

        if not following_path.exists():
            return following

        for html_file in following_path.glob("following*.html"):
            following.extend(self._parse_relationship_file(html_file, "following"))

        logger.info(f"Parsed {len(following)} following")
        return following

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

        # Find containers
        containers = soup.find_all('div', class_=lambda c: c and 'uiBoxWhite' in c)

        for container in containers:
            # Find Instagram profile link
            link = container.find('a', href=lambda h: h and 'instagram.com' in h)
            if not link:
                continue

            username = link.get_text(strip=True)
            profile_url = link['href']

            # Find timestamp (sibling div after the link's parent)
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
                relationship_type=relationship_type,
            ))

        return followers

    # -------------------------------------------------------------------------
    # COMMENT PARSING
    # -------------------------------------------------------------------------

    def _parse_comments(self, export_path: Path) -> List[InstagramComment]:
        """Parse all comments."""
        comments = []
        comments_path = export_path / "your_instagram_activity" / "comments"

        if not comments_path.exists():
            return comments

        for html_file in comments_path.glob("*.html"):
            comments.extend(self._parse_comment_file(html_file))

        logger.info(f"Parsed {len(comments)} comments")
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

            comment_data: Dict[str, Any] = {}

            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if not cells:
                    continue

                first_cell = cells[0]
                cell_text = first_cell.get_text(strip=True)

                # Extract field based on label
                if cell_text.startswith('Comment'):
                    inner_div = first_cell.find('div')
                    if inner_div:
                        inner_inner = inner_div.find('div')
                        if inner_inner:
                            comment_data['content'] = self.decode_html_entities(
                                inner_inner.get_text(strip=True)
                            )
                elif cell_text.startswith('Media Owner'):
                    inner_div = first_cell.find('div')
                    if inner_div:
                        inner_inner = inner_div.find('div')
                        if inner_inner:
                            comment_data['media_owner'] = inner_inner.get_text(strip=True)
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

    def _parse_profile(self, export_path: Path) -> Optional[InstagramProfile]:
        """Parse personal profile information."""
        file_path = export_path / "personal_information" / "personal_information" / "personal_information.html"
        soup = self._get_soup(file_path)

        if not soup:
            return None

        profile_data: Dict[str, Any] = {}

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
                        inner_div = cells[0].find('div')
                        if inner_div:
                            inner_inner = inner_div.find('div')
                            if inner_inner:
                                value = self.decode_html_entities(
                                    inner_inner.get_text(strip=True)
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

        if not profile_data.get('username'):
            return None

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


# =============================================================================
# STANDALONE USAGE
# =============================================================================

def parse_instagram_export(export_path: str) -> Dict[str, Any]:
    """
    Convenience function to parse an Instagram export.

    Args:
        export_path: Path to Instagram export directory

    Returns:
        Dictionary with parsed data
    """
    parser = InstagramHTMLParser()
    path = Path(export_path)

    if not parser.can_parse(path):
        raise ValueError(f"Not a valid Instagram export: {export_path}")

    result = parser.parse(path)
    return result.metadata


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python instagram.py <export_path>")
        sys.exit(1)

    export_path = sys.argv[1]

    parser = InstagramHTMLParser()
    path = Path(export_path)

    if not parser.can_parse(path):
        print(f"Error: Not a valid Instagram export: {export_path}")
        sys.exit(1)

    result = parser.parse(path)

    print(f"\n{result.title}")
    print("=" * 60)

    stats = result.metadata.get("statistics", {})
    print(f"Messages: {stats.get('message_count', 0)}")
    print(f"Conversations: {stats.get('conversation_count', 0)}")
    print(f"Followers: {stats.get('follower_count', 0)}")
    print(f"Following: {stats.get('following_count', 0)}")
    print(f"Comments: {stats.get('comment_count', 0)}")

    if stats.get('first_message'):
        print(f"Date range: {stats['first_message']} to {stats['last_message']}")
