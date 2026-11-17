"""
Core icity.ly client — read and write diary entries over plain HTTP.

No browser engine needed. Uses requests + BeautifulSoup for lightweight
HTML parsing. Works in any Python environment including AI code interpreters.
"""

import json
import re
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .exceptions import (
    ICityError,
    LoginError,
    NotAuthenticatedError,
    EntryNotFoundError,
)
from .models import DiaryEntry, UserProfile, Comment

BASE_URL = "https://icity.ly"


class ICityClient:
    """
    Client for reading and writing diary entries on icity.ly.

    Two modes:
        Anonymous (no credentials):
            - Read recent public entries from any user's profile page
            - Read user profile info
            - Limited to ~3 most recent entries per user (icity restriction)

        Authenticated (email + password):
            - Read ALL entries with pagination (per_page up to 200)
            - Post new diary entries
            - Post comments on entries
            - Like/unlike entries
            - Read individual entry details with comments

    Example:
        # Anonymous
        client = ICityClient()
        profile = client.get_profile("some_user")
        entries = client.get_entries("some_user")

        # Authenticated
        client = ICityClient(email="me@example.com", password="pass")
        all_entries = client.get_all_entries("some_user")
        client.post_entry("Hello world!")
    """

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Create a new icity client.

        Args:
            email: icity.ly login email. Omit for anonymous read-only mode.
            password: icity.ly login password.
            timeout: HTTP request timeout in seconds.
        """
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        self.timeout = timeout
        self.authenticated = False
        self._username: Optional[str] = None  # logged-in user's username
        self._user_hash: Optional[str] = None  # internal user hash for re_id
        self._csrf_token: Optional[str] = None

        if email and password:
            self._login(email, password)

    # ──────────────────────────────────────────────
    #  Authentication
    # ──────────────────────────────────────────────

    def _login(self, email: str, password: str) -> None:
        """Log into icity.ly and store the session cookies."""
        # GET the login page to grab the CSRF token
        resp = self.session.get(
            f"{BASE_URL}/welcome", timeout=self.timeout
        )
        resp.raise_for_status()
        self._csrf_token = self._extract_csrf(resp.text)

        if not self._csrf_token:
            raise LoginError("Could not find CSRF token on login page.")

        # POST login form to the actual sign-in endpoint
        login_data = {
            "utf8": "✓",
            "authenticity_token": self._csrf_token,
            "icty_user[login]": email,
            "icty_user[password]": password,
            "icty_user[remember_me]": "0",
            "commit": "登入",
        }
        resp = self.session.post(
            f"{BASE_URL}/users/sign_in",
            data=login_data,
            timeout=self.timeout,
            allow_redirects=True,
        )

        # If we're still on /welcome or /sign_in, login failed
        if "/welcome" in resp.url or "sign_in" in resp.url:
            raise LoginError(
                "Login failed. Check your email and password."
            )

        self.authenticated = True
        # Try to extract username from the page
        self._username = self._extract_my_username(resp.text)
        # Extract the internal user hash (needed for posting)
        self._user_hash = self._extract_user_hash(resp.text)
        # Refresh CSRF token from the authenticated page
        self._csrf_token = self._extract_csrf(resp.text)

    def _require_auth(self) -> None:
        """Raise if not authenticated."""
        if not self.authenticated:
            raise NotAuthenticatedError(
                "This operation requires login. "
                "Create the client with email and password."
            )

    @property
    def username(self) -> Optional[str]:
        """The logged-in user's username, or None if anonymous."""
        return self._username

    # ──────────────────────────────────────────────
    #  Reading: Profile
    # ──────────────────────────────────────────────

    def get_profile(self, username: str) -> UserProfile:
        """
        Get a user's public profile information.

        Works in both anonymous and authenticated mode.

        Args:
            username: The icity username (without @).

        Returns:
            UserProfile with nickname, bio, avatar, stats.
        """
        resp = self.session.get(
            f"{BASE_URL}/u/{username}", timeout=self.timeout
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        profile = UserProfile(username=username)

        # Nickname
        nick_el = soup.select_one("#user-header .nickname")
        if nick_el:
            profile.nickname = nick_el.get_text(strip=True)

        # Bio
        bio_el = soup.select_one("#user-header .bio")
        if bio_el:
            profile.bio = bio_el.get_text(strip=True).strip('" "')

        # Avatar
        avatar_el = soup.select_one("#user-header img.avatar")
        if avatar_el and avatar_el.get("src"):
            profile.avatar_url = avatar_el["src"]

        # Stats
        for li in soup.select(".nav-stats li"):
            link = li.find("a")
            count_el = li.select_one("span.c")
            if not link or not count_el:
                continue
            href = link.get("href", "")
            count = int(count_el.get_text(strip=True).replace(",", "") or 0)
            if "/posts" in href:
                profile.diary_count = count
            elif "/photos" in href:
                profile.photo_count = count
            elif "/followers" in href:
                profile.follower_count = count
            elif "/followings" in href:
                profile.following_count = count

        return profile

    # ──────────────────────────────────────────────
    #  Reading: Entries
    # ──────────────────────────────────────────────

    def get_entries(
        self,
        username: str,
        page: int = 1,
        per_page: int = 200,
    ) -> list[DiaryEntry]:
        """
        Get diary entries for a user.

        Anonymous mode: Returns ~3 most recent entries from the profile page.
            The page/per_page parameters are ignored (icity restriction).

        Authenticated mode: Returns up to `per_page` entries from the given
            page. Use per_page=200 (max) for efficiency.

        Args:
            username: The icity username.
            page: Page number (1-based). Authenticated only.
            per_page: Entries per page, max ~200. Authenticated only.

        Returns:
            List of DiaryEntry objects.
        """
        if self.authenticated:
            return self._fetch_entries_authenticated(username, page, per_page)
        else:
            return self._fetch_entries_anonymous(username)

    def get_all_entries(
        self,
        username: str,
        per_page: int = 200,
        progress: bool = True,
    ) -> list[DiaryEntry]:
        """
        Fetch ALL diary entries for a user. Requires authentication.

        Automatically paginates through all pages until no more entries.

        Args:
            username: The icity username.
            per_page: Entries per page (default 200, max ~200).
            progress: If True, print progress to stdout.

        Returns:
            List of all DiaryEntry objects, newest first.
        """
        self._require_auth()

        all_entries: list[DiaryEntry] = []
        seen_last_content: Optional[str] = None

        for pg in range(1, 500):  # safety limit
            if progress:
                print(f"  Fetching page {pg}...", end=" ", flush=True)

            entries = self._fetch_entries_authenticated(
                username, page=pg, per_page=per_page
            )

            if not entries:
                if progress:
                    print("empty page, done.")
                break

            # Detect duplicate pages (icity returns last page for out-of-range)
            last_sig = entries[-1].content[-50:] if entries[-1].content else ""
            if last_sig == seen_last_content:
                if progress:
                    print("duplicate of previous page, done.")
                break
            seen_last_content = last_sig

            all_entries.extend(entries)
            img_count = sum(1 for e in entries if e.images)
            if progress:
                print(f"{len(entries)} entries ({img_count} with images)")

        return all_entries

    def get_entry_comments(self, entry_id: str) -> list[Comment]:
        """
        Get comments on a specific entry.

        Requires authentication — individual entry pages need login.

        Args:
            entry_id: The entry's short ID (e.g. 'aihy1u3').

        Returns:
            List of Comment objects.
        """
        self._require_auth()

        resp = self.session.get(
            f"{BASE_URL}/a/{entry_id}/expand",
            timeout=self.timeout,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        if resp.status_code == 404:
            raise EntryNotFoundError(f"Entry '{entry_id}' not found.")
        resp.raise_for_status()

        comments: list[Comment] = []
        soup = BeautifulSoup(resp.text, "html.parser")

        for reply in soup.select(".reply"):
            c = Comment()
            author_el = reply.select_one(".author a")
            if author_el:
                c.author = author_el.get_text(strip=True)
            content_el = reply.select_one(".content, .comment-body")
            if content_el:
                c.content = content_el.get_text(strip=True)
            time_el = reply.select_one("time")
            if time_el:
                c.datetime_iso = time_el.get("datetime", "")
            comments.append(c)

        return comments

    # ──────────────────────────────────────────────
    #  Writing: Post entry
    # ──────────────────────────────────────────────

    def post_entry(
        self,
        content: str,
        title: str = "",
        privacy: int = 1,
    ) -> str:
        """
        Post a new diary entry.

        Requires authentication.

        Args:
            content: The text content of the diary entry.
            title: Optional title (icity supports untitled entries).
            privacy: 1 = public, 2 = friends only, 3 = private.

        Returns:
            The activity token (short ID) of the new entry.
        """
        self._require_auth()
        self._refresh_csrf()

        if not self._user_hash:
            raise ICityError(
                "Could not determine user hash. Try logging in again."
            )

        post_data = {
            "authenticity_token": self._csrf_token,
            "activity[content]": content,
        }
        if title:
            post_data["activity[title]"] = title

        resp = self.session.post(
            f"{BASE_URL}/activities",
            params={
                "act_id": "301",
                "re_id": f"icty+user+{self._user_hash}",
            },
            data=post_data,
            timeout=self.timeout,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("success"):
                    return data.get("activity_token", "")
            except (ValueError, KeyError):
                pass

        raise ICityError(
            f"Failed to post entry. Status: {resp.status_code}"
        )

    # ──────────────────────────────────────────────
    #  Writing: Comments
    # ──────────────────────────────────────────────

    def post_comment(self, entry_id: str, content: str) -> str:
        """
        Post a comment on a diary entry.

        Requires authentication.

        Args:
            entry_id: The entry's short ID (e.g. 'aihy1u3').
            content: The comment text.

        Returns:
            The activity token (short ID) of the new comment.
        """
        self._require_auth()
        self._refresh_csrf()

        post_data = {
            "authenticity_token": self._csrf_token,
            "activity[content]": content,
        }

        resp = self.session.post(
            f"{BASE_URL}/activities",
            params={
                "act_id": "101",
                "re_id": f"icty+activity+{entry_id}",
            },
            data=post_data,
            timeout=self.timeout,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("success"):
                    return data.get("activity_token", "")
            except (ValueError, KeyError):
                pass

        raise ICityError(
            f"Failed to post comment. Status: {resp.status_code}"
        )

    # ──────────────────────────────────────────────
    #  Writing: Like
    # ──────────────────────────────────────────────

    def like_entry(self, entry_id: str) -> bool:
        """
        Like a diary entry.

        Requires authentication. Note: icity's like endpoint returns
        HTTP 500 due to a server-side response rendering bug, but the
        like IS recorded successfully. We verify by checking the entry
        page afterward.

        Args:
            entry_id: The entry's short ID (e.g. 'aihy1u3').

        Returns:
            True if the like was recorded.
        """
        self._require_auth()
        self._refresh_csrf()

        # POST to the like endpoint — icity records the like even
        # though the server returns 500 (response rendering bug)
        self.session.post(
            f"{BASE_URL}/a/{entry_id}/like",
            data={"authenticity_token": self._csrf_token},
            timeout=self.timeout,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-Token": self._csrf_token,
            },
        )

        # Verify the like was recorded by checking the entry page
        resp = self.session.get(
            f"{BASE_URL}/a/{entry_id}/expand",
            timeout=self.timeout,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            unlike_link = soup.select_one(f'a[href="/a/{entry_id}/unlike"]')
            if unlike_link:
                return True

        raise ICityError(
            f"Failed to like entry '{entry_id}'. "
            "The entry may not exist or you may have already liked it."
        )

    def unlike_entry(self, entry_id: str) -> bool:
        """
        Unlike (remove like from) a diary entry.

        Requires authentication.

        Args:
            entry_id: The entry's short ID (e.g. 'aihy1u3').

        Returns:
            True if the unlike was recorded.
        """
        self._require_auth()
        self._refresh_csrf()

        self.session.delete(
            f"{BASE_URL}/a/{entry_id}/unlike",
            data={"authenticity_token": self._csrf_token},
            timeout=self.timeout,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-Token": self._csrf_token,
            },
        )

        # Verify
        resp = self.session.get(
            f"{BASE_URL}/a/{entry_id}/expand",
            timeout=self.timeout,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            like_link = soup.select_one(f'a[href="/a/{entry_id}/like"]')
            if like_link:
                return True

        raise ICityError(
            f"Failed to unlike entry '{entry_id}'."
        )

    # ──────────────────────────────────────────────
    #  Export (backward-compatible with v1)
    # ──────────────────────────────────────────────

    def export_json(
        self, username: str, output_path: str = "icity_diary.json"
    ) -> str:
        """
        Export all entries for a user as a JSON file.

        Requires authentication for full export.

        Args:
            username: The icity username.
            output_path: Path for the output JSON file.

        Returns:
            The output file path.
        """
        entries = self.get_all_entries(username)
        data = [e.to_dict() for e in entries]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Exported {len(entries)} entries to {output_path}")
        return output_path

    def export_txt(
        self, username: str, output_path: str = "icity_diary.txt"
    ) -> str:
        """
        Export all entries for a user as a plain text file.

        Requires authentication for full export.

        Args:
            username: The icity username.
            output_path: Path for the output text file.

        Returns:
            The output file path.
        """
        entries = self.get_all_entries(username)

        with open(output_path, "w", encoding="utf-8") as f:
            current_date = ""
            for entry in entries:
                if entry.date != current_date:
                    current_date = entry.date
                    f.write(f"\n{'=' * 40}\n")
                    f.write(f"  {current_date}\n")
                    f.write(f"{'=' * 40}\n\n")
                f.write(f"[{entry.time}]")
                if entry.likes:
                    f.write(f" ♡{entry.likes}")
                if entry.comments_count:
                    f.write(f" 💬{entry.comments_count}")
                f.write("\n")
                f.write(f"{entry.content}\n")
                if entry.images:
                    f.write(f"  📷 {len(entry.images)} image(s):\n")
                    for img_url in entry.images:
                        f.write(f"    {img_url}\n")
                f.write("\n")

        print(f"Exported {len(entries)} entries to {output_path}")
        return output_path

    # ──────────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────────

    def _extract_csrf(self, html: str) -> Optional[str]:
        """Extract CSRF token from HTML meta tag."""
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", attrs={"name": "csrf-token"})
        if meta and meta.get("content"):
            return meta["content"]
        return None

    def _extract_my_username(self, html: str) -> Optional[str]:
        """Extract the logged-in user's username from a page."""
        soup = BeautifulSoup(html, "html.parser")
        link = soup.select_one('a[href*="/u/"]')
        if link and link.get("href"):
            match = re.search(r"/u/([^/]+)", link["href"])
            if match:
                return match.group(1)
        return None

    def _extract_user_hash(self, html: str) -> Optional[str]:
        """
        Extract the internal user hash from the compose widget.

        The hash appears in the submit button's data-url attribute:
            data-url="/activities?act_id=301&re_id=icty%2Buser%2B{HASH}"
        It's also embedded in the avatar URL path.
        """
        # Method 1: from compose submit button
        match = re.search(
            r're_id=icty%2Buser%2B(\w+)', html
        )
        if match:
            return match.group(1)

        # Method 2: from avatar image URL
        match = re.search(
            r'/user/avatar/\w+/\w+?(\w{7,})\.jpg', html
        )
        if match:
            return match.group(1)

        return None

    def _refresh_csrf(self) -> None:
        """Refresh the CSRF token from any authenticated page."""
        resp = self.session.get(f"{BASE_URL}/", timeout=self.timeout)
        token = self._extract_csrf(resp.text)
        if token:
            self._csrf_token = token

    def _fetch_entries_anonymous(self, username: str) -> list[DiaryEntry]:
        """Fetch entries from the public profile page (no login needed)."""
        resp = self.session.get(
            f"{BASE_URL}/u/{username}", timeout=self.timeout
        )
        resp.raise_for_status()
        return self._parse_entries_html(resp.text)

    def _fetch_entries_authenticated(
        self, username: str, page: int = 1, per_page: int = 200
    ) -> list[DiaryEntry]:
        """Fetch entries from the posts page (login required)."""
        resp = self.session.get(
            f"{BASE_URL}/u/{username}/posts",
            params={"page": page, "per_page": per_page},
            timeout=self.timeout,
        )
        if resp.status_code == 302 or "/welcome" in resp.url:
            raise NotAuthenticatedError(
                "Session expired or not authenticated."
            )
        resp.raise_for_status()
        return self._parse_entries_html(resp.text)

    def _parse_entries_html(self, html: str) -> list[DiaryEntry]:
        """Parse diary entries from an icity HTML page."""
        soup = BeautifulSoup(html, "html.parser")
        entries: list[DiaryEntry] = []
        current_date = ""

        posts_list = soup.select_one(".posts-list")
        if not posts_list:
            return entries

        for li in posts_list.find_all("li", recursive=False):
            # Date separator
            if "day-cut" in li.get("class", []):
                # Extract date text, cleaning out icon elements
                for icon in li.find_all("i"):
                    icon.decompose()
                current_date = li.get_text(strip=True)
                continue

            # Diary entry
            if "diary" not in li.get("class", []):
                continue

            entry = DiaryEntry(content="", date=current_date)

            # Text content — the main .comment div (not the comment link)
            comment_div = li.select_one(".comment:not([data-expand-to])")
            if comment_div:
                entry.content = comment_div.get_text(strip=True)

            # Title (some entries have an h4 title)
            h4 = li.select_one("h4 a")
            if h4:
                title = h4.get_text(strip=True)
                if title and title != entry.content:
                    entry.content = title + "\n" + entry.content

            # Time
            time_el = li.select_one("time")
            if time_el:
                entry.time = time_el.get_text(strip=True)
                entry.datetime_iso = time_el.get("datetime", "")

            # Entry ID and permalink
            timeago = li.select_one(".timeago")
            if timeago and timeago.get("href"):
                href = timeago["href"]
                entry.permalink = f"{BASE_URL}{href}"
                # Extract ID from /a/XXXXX
                id_match = re.search(r"/a/([^/]+)", href)
                if id_match:
                    entry.entry_id = id_match.group(1)

            # Images
            for img in li.select(".photos img"):
                src = img.get("src", "")
                # Upgrade to higher resolution
                src = re.sub(r"/\d+x\d+$", "/1280x1280", src)
                if src:
                    entry.images.append(src)

            # Likes
            like_count_el = li.select_one(".like span")
            if like_count_el:
                try:
                    entry.likes = int(like_count_el.get_text(strip=True))
                except ValueError:
                    pass
            if entry.likes == 0 and li.select_one(".like.liked"):
                entry.likes = 1

            # Comments count
            comment_count_el = li.select_one(
                "a.comment[data-expand-to] span"
            )
            if comment_count_el:
                try:
                    entry.comments_count = int(
                        comment_count_el.get_text(strip=True)
                    )
                except ValueError:
                    pass

            # Source
            via_el = li.select_one(".via")
            if via_el:
                entry.source = via_el.get_text(strip=True)

            # Only include entries with content or images
            if entry.content or entry.images:
                entries.append(entry)

        return entries
