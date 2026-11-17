"""
Example: How an AI assistant (ChatGPT, Claude, etc.) would use this library.

This is the main use case — give your AI assistant this repo and your
icity credentials, and it can read your diary and write entries for you.

The AI just needs to:
  1. pip install -r requirements.txt
  2. Use ICityClient with the credentials you provide
"""

from icity import ICityClient


def ai_read_diary(email: str, password: str, username: str) -> str:
    """
    AI function: Read all diary entries and return as structured text.

    Returns a formatted string an AI can parse and reason about.
    """
    client = ICityClient(email=email, password=password)

    profile = client.get_profile(username)
    entries = client.get_all_entries(username)

    # Build a structured summary for the AI
    lines = [
        f"# {profile.nickname}'s Diary (@{profile.username})",
        f"Total entries: {profile.diary_count}",
        f"Bio: {profile.bio}",
        "",
    ]

    for entry in entries:
        lines.append(f"## {entry.date} {entry.time}")
        lines.append(entry.content)
        if entry.images:
            for img in entry.images:
                lines.append(f"![image]({img})")
        lines.append("")

    return "\n".join(lines)


def ai_write_diary(email: str, password: str, content: str, title: str = "") -> str:
    """
    AI function: Write a diary entry on behalf of the user.

    Returns the entry token (e.g. 'm5uk4tx') which can be used as the entry_id.
    """
    client = ICityClient(email=email, password=password)
    return client.post_entry(content, title=title)


def ai_interact(
    email: str, password: str, entry_id: str, action: str, text: str = ""
) -> str | bool:
    """
    AI function: Like, unlike, or comment on an entry.

    Args:
        action: "like", "unlike", or "comment"
        text: Comment text (required if action is "comment")

    Returns:
        bool for like/unlike, str (comment token) for comment.
    """
    client = ICityClient(email=email, password=password)

    if action == "like":
        return client.like_entry(entry_id)
    elif action == "unlike":
        return client.unlike_entry(entry_id)
    elif action == "comment":
        return client.post_comment(entry_id, text)
    else:
        raise ValueError(f"Unknown action: {action}")
