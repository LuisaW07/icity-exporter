"""Data models for icity diary entries, profiles, and comments."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DiaryEntry:
    """A single diary entry from icity.ly."""

    content: str
    """The text content of the diary entry."""

    entry_id: str = ""
    """Short ID used in the permalink, e.g. 'aihy1u3' from /a/aihy1u3."""

    date: str = ""
    """Display date, e.g. '11月17日 2026'."""

    time: str = ""
    """Display time, e.g. '00:25'."""

    datetime_iso: str = ""
    """ISO 8601 datetime string from the <time> element."""

    images: list[str] = field(default_factory=list)
    """List of image URLs (upgraded to 1280x1280 resolution)."""

    likes: int = 0
    """Number of likes on this entry."""

    comments_count: int = 0
    """Number of comments on this entry."""

    source: str = ""
    """Where this was posted from, e.g. 'iCity' or 'iCity Web'."""

    permalink: str = ""
    """Full URL to this entry, e.g. 'https://icity.ly/a/aihy1u3'."""

    def to_dict(self) -> dict:
        """Convert to a plain dictionary (JSON-serializable)."""
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "date": self.date,
            "time": self.time,
            "datetime": self.datetime_iso,
            "images": self.images,
            "likes": self.likes,
            "comments_count": self.comments_count,
            "source": self.source,
            "permalink": self.permalink,
        }

    def __str__(self) -> str:
        lines = []
        if self.date:
            lines.append(f"[{self.date} {self.time}]")
        lines.append(self.content)
        if self.images:
            lines.append(f"  📷 {len(self.images)} image(s)")
        if self.likes:
            lines.append(f"  ♡ {self.likes}")
        if self.comments_count:
            lines.append(f"  💬 {self.comments_count}")
        return "\n".join(lines)


@dataclass
class Comment:
    """A comment on a diary entry."""

    author: str = ""
    """Username of the commenter."""

    content: str = ""
    """Text content of the comment."""

    datetime_iso: str = ""
    """ISO 8601 datetime string."""

    def to_dict(self) -> dict:
        return {
            "author": self.author,
            "content": self.content,
            "datetime": self.datetime_iso,
        }


@dataclass
class UserProfile:
    """Public profile information for an icity user."""

    username: str = ""
    """The @username."""

    nickname: str = ""
    """Display name (may differ from username)."""

    bio: str = ""
    """Profile bio text."""

    avatar_url: str = ""
    """URL to the user's avatar image."""

    diary_count: int = 0
    """Total number of diary entries."""

    photo_count: int = 0
    """Total number of photos."""

    follower_count: int = 0
    """Number of followers."""

    following_count: int = 0
    """Number of users they follow."""

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "nickname": self.nickname,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "diary_count": self.diary_count,
            "photo_count": self.photo_count,
            "follower_count": self.follower_count,
            "following_count": self.following_count,
        }
