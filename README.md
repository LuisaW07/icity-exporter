# icity-exporter

Python client for [icity.ly](https://icity.ly) — read and write diary entries without a browser.

Designed so any AI assistant (Claude, ChatGPT, etc.) can interact with icity diaries using just `pip install` and a few lines of Python. No Playwright, no browser, no headless Chrome.

## Features

- 📖 **Read** diary entries, images, comments, and profile info
- ✍️ **Write** new diary entries
- 💬 **Comment** on entries
- ❤️ **Like** entries
- 📤 **Export** full diary as JSON or plain text
- 🤖 **AI-friendly** — lightweight enough for code interpreters

## Quick Start

```bash
pip install requests beautifulsoup4
```

```python
from icity import ICityClient

# Anonymous: read recent public entries (~3 most recent)
client = ICityClient()
profile = client.get_profile("some_user")
entries = client.get_entries("some_user")

# Authenticated: full read + write access
client = ICityClient(email="you@example.com", password="yourpassword")
all_entries = client.get_all_entries("some_user")  # all 1000+ entries
client.post_entry("Hello from Python! 🐍")
client.like_entry("abc123")
client.post_comment("abc123", "Nice!")
```

## Installation

```bash
git clone https://github.com/LuisaW07/icity-exporter.git
cd icity-exporter
pip install -r requirements.txt
```

Or install as a package:

```bash
pip install -e .
```

## Usage

### For AI Assistants

Give your AI assistant this repo and your icity credentials. It can then:

```python
from icity import ICityClient

# Read your diary
client = ICityClient(email="...", password="...")
entries = client.get_all_entries("your_username")

for entry in entries:
    print(entry.date, entry.time)
    print(entry.content)
    print(entry.images)  # list of image URLs (1280x1280)

# Write on your behalf
token = client.post_entry("AI wrote this for me ✨")
comment_id = client.post_comment("entry_id", "Great post!")
client.like_entry("entry_id")
client.unlike_entry("entry_id")
```

### Reading Entries

```python
client = ICityClient(email="...", password="...")

# Get user profile
profile = client.get_profile("username")
print(profile.nickname, profile.diary_count)

# Get one page of entries
entries = client.get_entries("username", page=1, per_page=200)

# Get ALL entries (auto-pagination)
all_entries = client.get_all_entries("username")

# Get comments on an entry
comments = client.get_entry_comments("entry_id")
```

### Writing

```python
client = ICityClient(email="...", password="...")

# Post a diary entry (returns entry token string)
token = client.post_entry("Today was a good day.")
token = client.post_entry("Private thoughts.", privacy=0)  # private entry
token = client.post_entry("Titled entry", title="My Title")

# Like / unlike an entry
client.like_entry("abc123")    # returns True
client.unlike_entry("abc123")  # returns True

# Comment on an entry (returns comment token string)
comment_token = client.post_comment("abc123", "Love this!")
```

### Export

```python
client = ICityClient(email="...", password="...")

# Export as JSON
client.export_json("username", "diary.json")

# Export as plain text
client.export_txt("username", "diary.txt")
```

### Legacy CLI (v1)

The original Playwright-based export script is still available:

```bash
python icity_exporter.py --email you@example.com --password pass --format both
```

## Data Models

### DiaryEntry

| Field | Type | Description |
|-------|------|-------------|
| `content` | str | Entry text |
| `entry_id` | str | Short ID (e.g. `'aihy1u3'`) |
| `date` | str | Date string (e.g. `'11月17日 2026'`) |
| `time` | str | Time string (e.g. `'00:25'`) |
| `datetime_iso` | str | ISO 8601 datetime |
| `images` | list[str] | Image URLs (1280×1280) |
| `likes` | int | Like count |
| `comments_count` | int | Comment count |
| `source` | str | Post source (e.g. `'iCity'`) |
| `permalink` | str | Full URL |

### UserProfile

| Field | Type | Description |
|-------|------|-------------|
| `username` | str | Username |
| `nickname` | str | Display name |
| `bio` | str | Bio text |
| `avatar_url` | str | Avatar image URL |
| `diary_count` | int | Number of diary entries |
| `photo_count` | int | Number of photos |
| `follower_count` | int | Followers |
| `following_count` | int | Following |

## Anonymous vs Authenticated

| Feature | Anonymous | Authenticated |
|---------|-----------|---------------|
| Read profile | ✅ | ✅ |
| Read recent entries | ✅ (~3 entries) | ✅ (all entries) |
| Pagination | ❌ | ✅ (per_page up to 200) |
| Read comments | ❌ | ✅ |
| Post diary | ❌ | ✅ |
| Like entries | ❌ | ✅ |
| Unlike entries | ❌ | ✅ |
| Post comments | ❌ | ✅ |
| Export | ❌ | ✅ |

## How It Works

icity.ly has no public API. This library uses `requests` + `BeautifulSoup` to:

1. **Login**: Extract CSRF token from `/welcome`, POST credentials
2. **Read**: Parse the HTML `.posts-list` structure from profile/posts pages
3. **Write**: POST to icity's activity system (`/activities` with `act_id`) with CSRF tokens
4. **Paginate**: Use the undocumented `per_page` parameter (up to 200)

## Limitations

- Anonymous access is limited to ~3 recent entries (icity server restriction)
- Image upload for diary entries is not yet supported (text-only posts)
- The `per_page` parameter is undocumented and could change
- No rate limiting built in — be respectful with large exports

## License

MIT
