#!/usr/bin/env python3
"""Compare Instagram followers and following from saved HTML files."""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


USERNAME_RE = re.compile(r"^[a-z0-9._]{1,30}$")
JSON_USERNAME_RE = re.compile(r'"username"\s*:\s*"([^"]+)"')

RESERVED_PATHS = {
    "about",
    "accounts",
    "api",
    "archive",
    "challenge",
    "create",
    "developer",
    "direct",
    "explore",
    "graphql",
    "legal",
    "oauth",
    "p",
    "privacy",
    "reel",
    "reels",
    "stories",
    "terms",
    "tv",
}


@dataclass(frozen=True)
class ExtractionResult:
    usernames: set[str]
    source: str
    dialog_count: int
    href_count: int
    json_count: int


class InstagramDialogParser(HTMLParser):
    """Collect links and text only from role=dialog regions."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.dialog_depth: int | None = None
        self.dialog_count = 0
        self.dialog_hrefs: list[str] = []
        self.dialog_text: list[str] = []
        self.all_hrefs: list[str] = []
        self.all_text: list[str] = []

    @property
    def in_dialog(self) -> bool:
        return self.dialog_depth is not None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        role = attr_map.get("role", "").lower()

        if self.in_dialog:
            self.dialog_depth = (self.dialog_depth or 0) + 1
        elif role == "dialog":
            self.dialog_depth = 1
            self.dialog_count += 1

        href = attr_map.get("href")
        if href:
            self.all_hrefs.append(href)
            if self.in_dialog:
                self.dialog_hrefs.append(href)

    def handle_endtag(self, tag: str) -> None:
        if self.in_dialog:
            next_depth = (self.dialog_depth or 1) - 1
            self.dialog_depth = next_depth if next_depth > 0 else None

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.all_text.append(data)
            if self.in_dialog:
                self.dialog_text.append(data)


def normalize_username(value: str) -> str | None:
    username = html.unescape(value).strip().strip("@").lower()
    if not USERNAME_RE.fullmatch(username):
        return None
    if username in RESERVED_PATHS:
        return None
    return username


def username_from_href(href: str) -> str | None:
    href = html.unescape(href)
    parsed = urlparse(href)

    if parsed.netloc and not parsed.netloc.endswith("instagram.com"):
        return None

    path = unquote(parsed.path).strip("/")
    if not path:
        return None

    first_segment = path.split("/", 1)[0]
    return normalize_username(first_segment)


def usernames_from_hrefs(hrefs: list[str]) -> set[str]:
    usernames: set[str] = set()
    for href in hrefs:
        username = username_from_href(href)
        if username:
            usernames.add(username)
    return usernames


def usernames_from_text(text_parts: list[str]) -> set[str]:
    text = html.unescape("\n".join(text_parts))
    usernames: set[str] = set()
    for match in JSON_USERNAME_RE.finditer(text):
        username = normalize_username(match.group(1))
        if username:
            usernames.add(username)
    return usernames


def extract_usernames(path: Path) -> ExtractionResult:
    try:
        document = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SystemExit(f"Could not read {path}: {exc}") from exc

    parser = InstagramDialogParser()
    parser.feed(document)

    dialog_hrefs = usernames_from_hrefs(parser.dialog_hrefs)
    dialog_json = usernames_from_text(parser.dialog_text)
    dialog_usernames = dialog_hrefs | dialog_json

    if dialog_usernames:
        return ExtractionResult(
            usernames=dialog_usernames,
            source="dialog",
            dialog_count=parser.dialog_count,
            href_count=len(dialog_hrefs),
            json_count=len(dialog_json),
        )

    all_hrefs = usernames_from_hrefs(parser.all_hrefs)
    all_json = usernames_from_text(parser.all_text)
    whole_page_candidates = all_hrefs | all_json

    details = [
        f"No usernames were found inside an Instagram modal/dialog in {path}.",
        "Save the page while the Followers or Following modal is open and fully scrolled.",
    ]
    if parser.dialog_count:
        details.append(
            f"{parser.dialog_count} dialog region(s) were found, but none contained extractable usernames."
        )
    elif whole_page_candidates:
        details.append(
            f"The whole page contains {len(whole_page_candidates)} username-like value(s), "
            "but those may include feed authors, suggestions, and navigation data."
        )
    else:
        details.append("The file did not contain any username-like Instagram profile links or JSON values.")

    raise SystemExit("\n".join(details))


def write_lines(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare saved Instagram followers/following HTML and list accounts that do not follow back."
    )
    parser.add_argument("followers_html", type=Path, help="Saved HTML with the Followers modal open.")
    parser.add_argument("following_html", type=Path, help="Saved HTML with the Following modal open.")
    parser.add_argument("--out-dir", type=Path, default=Path("output"), help="Directory for output text files.")
    parser.add_argument(
        "--show-counts",
        action="store_true",
        help="Print extraction source details in addition to the default summary.",
    )
    parser.add_argument(
        "--debug-samples",
        action="store_true",
        help="Print a few extracted usernames from each input for sanity checking.",
    )
    return parser.parse_args(argv)


def print_samples(label: str, usernames: set[str]) -> None:
    sample = ", ".join(sorted(usernames)[:10])
    print(f"{label} sample: {sample or '(none)'}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    followers = extract_usernames(args.followers_html)
    following = extract_usernames(args.following_html)

    follower_names = sorted(followers.usernames)
    following_names = sorted(following.usernames)
    not_following_back = sorted(following.usernames - followers.usernames)

    write_lines(args.out_dir / "followers.txt", follower_names)
    write_lines(args.out_dir / "following.txt", following_names)
    write_lines(args.out_dir / "not_following_back.txt", not_following_back)

    print(f"Followers: {len(follower_names)}")
    print(f"Following: {len(following_names)}")
    print(f"Not following back: {len(not_following_back)}")
    print(f"Wrote results to {args.out_dir}")

    if args.show_counts:
        print(
            f"Followers source: {followers.source} "
            f"({followers.dialog_count} dialog(s), {followers.href_count} href usernames, "
            f"{followers.json_count} JSON usernames)"
        )
        print(
            f"Following source: {following.source} "
            f"({following.dialog_count} dialog(s), {following.href_count} href usernames, "
            f"{following.json_count} JSON usernames)"
        )

    if args.debug_samples:
        print_samples("Followers", followers.usernames)
        print_samples("Following", following.usernames)
        print_samples("Not following back", set(not_following_back))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
