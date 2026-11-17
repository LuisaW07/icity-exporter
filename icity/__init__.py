"""
icity - Python client for icity.ly diary platform

A lightweight library that lets you (or your AI assistant) read and write
diary entries on icity.ly. No browser engine required — just HTTP requests.

Quick start:
    from icity import ICityClient

    # Anonymous: read recent public entries
    client = ICityClient()
    entries = client.get_entries("username")

    # Authenticated: full read + write access
    client = ICityClient(email="you@example.com", password="yourpass")
    entries = client.get_entries("username", page=1, per_page=50)
    client.post_entry("Today was a good day!")
    client.like_entry("entry_id")
    client.post_comment("entry_id", "Nice post!")
"""

from .client import ICityClient
from .models import DiaryEntry, UserProfile, Comment
from .exceptions import (
    ICityError,
    LoginError,
    NotAuthenticatedError,
    EntryNotFoundError,
)

__version__ = "2.0.0"
__all__ = [
    "ICityClient",
    "DiaryEntry",
    "UserProfile",
    "Comment",
    "ICityError",
    "LoginError",
    "NotAuthenticatedError",
    "EntryNotFoundError",
]
