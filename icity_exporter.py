#!/usr/bin/env python3
"""
icity-exporter: Export all diary entries from icity.ly

Logs into icity.ly via Playwright, paginates through all diary entries,
and exports them as structured JSON and/or plain text — including image URLs.

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

    Uses HTML parsing to extract structured data including image URLs.
    The icity.ly web interface supports an undocumented `per_page` parameter
    that allows fetching up to 200 entries per page, bypassing the default
    10-page limit.
    """
    all_entries = []
    seen_last_html = None

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

        # Extract entries from HTML using JavaScript for reliable parsing
        result = page.evaluate("""() => {
            const entries = [];
            let currentDate = '';

            const items = document.querySelectorAll('.posts-list > li');
            for (const li of items) {
                // Date separator
                if (li.classList.contains('day-cut')) {
                    currentDate = li.textContent.replace(/[^\\d月日 ]/g, '').trim();
                    continue;
                }

                // Diary entry
                if (li.classList.contains('diary')) {
                    const entry = { date: currentDate };

                    // Text content
                    const comment = li.querySelector('.comment:not([data-expand-to])');
                    entry.content = comment ? comment.textContent.trim() : '';

                    // Title (some entries have an h4 title)
                    const h4 = li.querySelector('h4 a');
                    if (h4) {
                        const title = h4.textContent.trim();
                        if (title && title !== entry.content) {
                            entry.content = title + '\\n' + entry.content;
                        }
                    }

                    // Time
                    const timeEl = li.querySelector('time');
                    entry.time = timeEl ? timeEl.textContent.trim() : '';
                    entry.datetime = timeEl ? timeEl.getAttribute('datetime') : '';

                    // Images
                    const imgs = li.querySelectorAll('.photos img');
                    entry.images = [];
                    for (const img of imgs) {
                        let src = img.getAttribute('src') || '';
                        // Get higher resolution: replace /640x640 with /1280x1280
                        src = src.replace(/\\/\\d+x\\d+$/, '/1280x1280');
                        if (src) entry.images.push(src);
                    }

                    // Likes (check for .liked class or count)
                    const likeEl = li.querySelector('.like .fic-ic-like');
                    const likeCount = li.querySelector('.like span');
                    entry.likes = likeCount ? parseInt(likeCount.textContent) || 0 : 0;
                    // If there's a .liked class but no count span, it has at least 1
                    if (entry.likes === 0 && li.querySelector('.like.liked')) {
                        entry.likes = 1;
                    }

                    // Comments count
                    const commentCount = li.querySelector('a.comment[data-expand-to] span');
                    entry.comments = commentCount ? parseInt(commentCount.textContent) || 0 : 0;

                    // Source (iCity app, web, etc)
                    const via = li.querySelector('.via');
                    entry.source = via ? via.textContent.trim() : '';

                    // Permalink
                    const permalink = li.querySelector('.timeago');
                    entry.permalink = permalink ? permalink.getAttribute('href') : '';

                    if (entry.content || entry.images.length > 0) {
                        entries.push(entry);
                    }
                }
            }
            return entries;
        }""")

        if not result or len(result) == 0:
            # Fallback: check if page is truly empty or just different structure
            body = page.evaluate("() => document.body.innerText")
            if not body or len(body.strip()) < 30:
                print("empty page, done.")
                break
            print("no entries parsed (page structure may have changed), done.")
            break

        # Detect duplicate pages (icity returns last page content for out-of-range pages)
        last_sig = result[-1].get("content", "")[-50:] if result else ""
        if last_sig == seen_last_html:
            print("duplicate of previous page, done.")
            break
        seen_last_html = last_sig

        all_entries.extend(result)
        img_count = sum(1 for e in result if e.get("images"))
        print(f"{len(result)} entries ({img_count} with images)")

        if len(result) == 0:
            break

    return all_entries


def export_json(entries: list[dict], path: Path):
    """Export entries as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(entries)} entries to {path}")


def export_txt(entries: list[dict], path: Path):
    """Export entries as plain text with image URLs."""
    with open(path, "w", encoding="utf-8") as f:
        current_date = ""
        for entry in entries:
            if entry["date"] != current_date:
                current_date = entry["date"]
                f.write(f"\n{'=' * 40}\n")
                f.write(f"  {current_date}\n")
                f.write(f"{'=' * 40}\n\n")
            f.write(f"[{entry['time']}]")
            if entry.get("likes"):
                f.write(f" ♡{entry['likes']}")
            if entry.get("comments"):
                f.write(f" 💬{entry['comments']}")
            f.write("\n")
            f.write(f"{entry['content']}\n")
            if entry.get("images"):
                f.write(f"  📷 {len(entry['images'])} image(s):\n")
                for img_url in entry["images"]:
                    f.write(f"    {img_url}\n")
            f.write("\n")
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
    if entries:
        print(f"Date range: {entries[0]['date']} → {entries[-1]['date']}")

    # Export
    output = Path(args.output)
    if args.format in ("json", "both"):
        export_json(entries, output.with_suffix(".json"))
    if args.format in ("txt", "both"):
        export_txt(entries, output.with_suffix(".txt"))

    # Stats
    total_chars = sum(len(e["content"]) for e in entries)
    total_likes = sum(e.get("likes", 0) for e in entries)
    total_images = sum(len(e.get("images", [])) for e in entries)
    entries_with_images = sum(1 for e in entries if e.get("images"))
    print(f"\nStats:")
    print(f"  Total entries:    {len(entries)}")
    print(f"  Total characters: {total_chars:,}")
    print(f"  Total likes:      {total_likes}")
    print(f"  Entries w/ images: {entries_with_images}")
    print(f"  Total images:     {total_images}")


if __name__ == "__main__":
    main()
