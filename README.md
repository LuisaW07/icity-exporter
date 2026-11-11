# icity-exporter

Export all your diary entries from [icity.ly](https://icity.ly) as JSON or plain text.

## Why?

iCity's web interface limits you to viewing ~300 recent entries (10 pages × 30 entries). This tool bypasses that limitation by using an undocumented `per_page` parameter, letting you export your **entire** diary history — even if you have thousands of entries.

## Features

- 📖 Export **all** diary entries (not just the most recent 300)
- 📄 Output as JSON (structured) or plain text (human-readable)
- ❤️ Preserves likes, comments count, and image indicators
- 👤 Export your own diary or any user's public diary
- 🔒 Credentials are only used for login, never stored

## Requirements

- Python 3.10+
- [Playwright](https://playwright.dev/python/)

## Installation

```bash
# Clone the repo
git clone https://github.com/LuisaW07/icity-exporter.git
cd icity-exporter

# Install dependencies
pip install playwright
playwright install chromium
```

## Usage

### Basic export (JSON)

```bash
python icity_exporter.py --email your@email.com --password yourpassword
```

### Export as plain text

```bash
python icity_exporter.py --email your@email.com --password yourpassword --format txt
```

### Export both formats

```bash
python icity_exporter.py --email your@email.com --password yourpassword --format both --output my_diary
```

### Export another user's diary

```bash
python icity_exporter.py --email your@email.com --password yourpassword --username their_username
```

### Using with Claude

You can use this script directly in a Claude conversation (Claude Code, Cowork, or chat). Just ask Claude to run it and it will execute in the cloud — no local setup needed.

## Output Format

### JSON

```json
[
  {
    "date": "11月10日 2026",
    "time": "23:36",
    "content": "今天天气真好！",
    "likes": 1,
    "comments": 0,
    "has_image": true
  }
]
```

### Plain Text

```
========================================
  11月10日 2026
========================================

[23:36] ♡1
今天天气真好！
```

## How It Works

iCity's web frontend paginates diary entries at 30 per page, with a hard cap at page 10 (300 entries). However, the server accepts a `per_page` query parameter that isn't exposed in the UI. By setting `per_page=200`, we can fetch up to 200 entries per page with no page limit, allowing complete diary export.

The tool uses Playwright to handle login (which requires cookies/CSRF tokens) and then paginates through all pages until it detects an empty or duplicate page.

## Limitations

- Requires a valid icity.ly account to authenticate
- Images/photos are not downloaded (only their presence is noted)
- Rate limiting: the tool adds small delays between pages to be respectful
- The `per_page` parameter is undocumented and could stop working if iCity changes their backend

## License

MIT

## Acknowledgments

- Built with [Playwright](https://playwright.dev/python/) for browser automation
- Inspired by the need to actually read your own diary history 🙃
