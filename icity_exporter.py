#!/usr/bin/env python3
"""
icity-exporter: Export all diary entries from icity.ly

Logs into icity.ly via Playwright, paginates through all diary entries,
and exports them as structured JSON and/or plain text.

Usage:
    python icity_exporter.py --email YOUR_EMAIL --password YOUR_PASSWORD [--output diary.json] [--format json|txt|both]

Requirements:
    pip install playwright
    playwright install chromium
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright is required. Install with:")
    print("  pip install playwright && playwright install chromium")
    sys.exit(1)


def login(page, email: str, password: str) -> bool:
    """Log into icity.ly. Returns True on success."""
    page.goto("https://icity.ly/welcome", timeout=30000)
    page.wait_for_load_state("networkidle", timeout=15000)

    email_input = page.query_selector('input[name="icty_user[login]"]')
    if not email_input:
        print("Error: Could not find login form. The site may have changed.")
        return False

    page.fill('input[name="icty_user[login]"]', email)
    page.fill('input[name="icty_user[password]"]', password)
    page.click('input[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(2)

    # Check if login succeeded by looking for redirect away from /welcome
    if "/welcome" in page.url or "sign_in" in page.url:
        print("Error: Login failed. Check your email and password.")
        return False

    return True


def get_username(page) -> str | None:
    """Extract the logged-in user's username from the page."""
    # Try to find username from profile link
    username = page.evaluate('''() => {
        const link = document.querySelector('a[href*="/u/"]');
        if (link) {
            const match = link.href.match(/\\/u\\/([^/]+)/);
            return match ? match[1] : null;
        }
        return null;
    }''')
    return username


def fetch_all_entries(page, username: str, per_page: int = 200) -> list[dict]:
    """
    Fetch all diary entries by paginating through /u/{username}/posts.

    The icity.ly web interface supports an undocumented `per_page` parameter
    that allows fetching up to 200 entries per page, and pagination beyond
    the default 10-page limit.
    """
    all_entries = []
    seen_last_text = None

    for pg in range(1, 100):  # Safety limit
        url = f"https://icity.ly/u/{username}/posts?page={pg}&per_page={per_page}"
        print(f"  Fetching page {pg}...", end=" ", flush=True)

        try:
            page.goto(url, timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                time.sleep(3)
        except Exception as e:
            print(f"error: {e}")
            break

        body = page.evaluate("() => document.body.innerText")

        # Strip header
        if f"{username}日记" in body:
            body = body.split(f"{username}日记\n", 1)[-1]
        # Strip footer
        if "© 2015" in body:
            body = body[: body.index("© 2015")]

        body = body.strip()

        if not body or len(body) < 30:
            print("empty page, done.")
            break

        # Detect duplicate pages (icity returns last page repeatedly)
        last_50 = body[-50:]
        if last_50 == seen_last_text:
            print("duplicate of previous page, done.")
            break
        seen_last_text = last_50

        # Parse entries from this page
        entries = parse_entries(body)
        all_entries.extend(entries)
        print(f"{len(entries)} entries")

        if len(entries) == 0:
            break

    return all_entries


def parse_entries(text: str) -> list[dict]:
    """
    Parse diary entries from page text.

    Entry format:
        {date header}        (e.g., "11月10日 2026")
        {content lines}
        {time} {likes} {comments}  (e.g., "23:36 1  iCity")
    """
    entries = []
    current_date = ""
    buffer_lines = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        # Date header: "11月10日 2026" or "11月 9日 2026"
        date_match = re.match(r"^(\d{1,2}月\s?\d{1,2}日\s+\d{4})$", stripped)
        if date_match:
            current_date = date_match.group(1)
            continue

        # Time marker at end of entry: "23:36" or "23:36 1" or "23:36 1  iCity"
        time_match = re.match(r"^(\d{1,2}:\d{2})\s*([\d\s]*)\s*(iCity)?$", stripped)
        if time_match:
            if buffer_lines:
                content = "\n".join(buffer_lines).strip()
                if content:
                    # Parse likes/comments from the time line
                    meta = time_match.group(2).strip()
                    likes = 0
                    comments = 0
                    if meta:
                        nums = meta.split()
                        if len(nums) >= 1:
                            try:
                                likes = int(nums[0])
                            except ValueError:
                                pass
                        if len(nums) >= 2:
                            try:
                                comments = int(nums[1])
                            except ValueError:
                                pass

                    entries.append({
                        "date": current_date,
                        "time": time_match.group(1),
                        "content": content,
                        "likes": likes,
                        "comments": comments,
                        "has_image": "iCity" in stripped if time_match.group(3) else False,
                    })
            buffer_lines = []
            continue

        buffer_lines.append(stripped)

    # Handle last entry if no trailing time marker
    if buffer_lines:
        content = "\n".join(buffer_lines).strip()
        if content:
            entries.append({
                "date": current_date,
                "time": "",
                "content": content,
                "likes": 0,
                "comments": 0,
                "has_image": False,
            })

    return entries


def export_json(entries: list[dict], path: Path):
    """Export entries as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(entries)} entries to {path}")


def export_txt(entries: list[dict], path: Path):
    """Export entries as plain text."""
    with open(path, "w", encoding="utf-8") as f:
        current_date = ""
        for entry in entries:
            if entry["date"] != current_date:
                current_date = entry["date"]
                f.write(f"\n{'=' * 40}\n")
                f.write(f"  {current_date}\n")
                f.write(f"{'=' * 40}\n\n")
            f.write(f"[{entry['time']}]")
            if entry["likes"]:
                f.write(f" ♡{entry['likes']}")
            if entry["comments"]:
                f.write(f" 💬{entry['comments']}")
            f.write("\n")
            f.write(f"{entry['content']}\n\n")
    print(f"Exported {len(entries)} entries to {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Export all diary entries from icity.ly",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Export as JSON
    python icity_exporter.py --email user@example.com --password mypass

    # Export as plain text
    python icity_exporter.py --email user@example.com --password mypass --format txt

    # Export another user's public diary
    python icity_exporter.py --email user@example.com --password mypass --username someone_else

    # Export both formats with custom output prefix
    python icity_exporter.py --email user@example.com --password mypass --format both --output my_diary
        """,
    )
    parser.add_argument("--email", required=True, help="icity.ly login email")
    parser.add_argument("--password", required=True, help="icity.ly login password")
    parser.add_argument("--username", help="Username to export (default: logged-in user)")
    parser.add_argument("--output", default="icity_diary", help="Output file path/prefix (default: icity_diary)")
    parser.add_argument("--format", choices=["json", "txt", "both"], default="json", help="Output format (default: json)")
    parser.add_argument("--per-page", type=int, default=200, help="Entries per page (default: 200, max ~200)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser headlessly (default)")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window")

    args = parser.parse_args()
    headless = not args.no_headless

    print("icity-exporter")
    print("=" * 40)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        # Login
        print(f"Logging in as {args.email}...")
        if not login(page, args.email, args.password):
            browser.close()
            sys.exit(1)
        print("Login successful!")

        # Determine username
        username = args.username
        if not username:
            username = get_username(page)
            if not username:
                print("Error: Could not detect username. Use --username to specify.")
                browser.close()
                sys.exit(1)
        print(f"Exporting diary for: {username}")

        # Fetch all entries
        print(f"Fetching entries (per_page={args.per_page})...")
        entries = fetch_all_entries(page, username, per_page=args.per_page)
        browser.close()

    if not entries:
        print("No entries found.")
        sys.exit(0)

    print(f"\nTotal entries: {len(entries)}")
    print(f"Date range: {entries[0]['date']} → {entries[-1]['date']}")

    # Export
    output = Path(args.output)
    if args.format in ("json", "both"):
        export_json(entries, output.with_suffix(".json"))
    if args.format in ("txt", "both"):
        export_txt(entries, output.with_suffix(".txt"))

    # Stats
    total_chars = sum(len(e["content"]) for e in entries)
    total_likes = sum(e["likes"] for e in entries)
    print(f"\nStats:")
    print(f"  Total entries:    {len(entries)}")
    print(f"  Total characters: {total_chars:,}")
    print(f"  Total likes:      {total_likes}")
    print(f"  Entries w/ images: {sum(1 for e in entries if e['has_image'])}")


if __name__ == "__main__":
    main()
