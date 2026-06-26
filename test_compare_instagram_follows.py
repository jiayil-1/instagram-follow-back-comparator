import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from compare_instagram_follows import (
    extract_usernames,
    main,
    normalize_username,
    username_from_href,
)


class InstagramFollowComparatorTests(unittest.TestCase):
    def write_tmp(self, directory: Path, name: str, content: str) -> Path:
        path = directory / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_normalizes_and_rejects_reserved_or_invalid_names(self) -> None:
        self.assertEqual(normalize_username("@Some.User_1"), "some.user_1")
        self.assertIsNone(normalize_username("explore"))
        self.assertIsNone(normalize_username("has spaces"))

    def test_extracts_profile_username_from_href(self) -> None:
        self.assertEqual(username_from_href("https://www.instagram.com/Some.User_1/?hl=en"), "some.user_1")
        self.assertEqual(username_from_href("/another_user/"), "another_user")
        self.assertIsNone(username_from_href("https://example.com/not_instagram/"))
        self.assertIsNone(username_from_href("/reels/"))

    def test_extracts_usernames_from_dialog_links_and_json(self) -> None:
        document = """
        <html>
          <a href="/feed_author/">outside dialog</a>
          <div role="dialog">
            <a href="/Alice.Example/">Alice</a>
            <a href="https://www.instagram.com/bob_2/">Bob</a>
            <script>{"username":"Carol.Three","username":"bob_2"}</script>
            <a href="/explore/">Explore</a>
          </div>
        </html>
        """

        with tempfile.TemporaryDirectory() as tmp:
            result = extract_usernames(self.write_tmp(Path(tmp), "followers.html", document))

        self.assertEqual(result.usernames, {"alice.example", "bob_2", "carol.three"})
        self.assertEqual(result.source, "dialog")

    def test_fails_when_only_whole_page_usernames_exist(self) -> None:
        document = '<html><a href="/feed_author/">Feed author</a><script>{"username":"suggested"}</script></html>'

        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_tmp(Path(tmp), "homepage.html", document)
            with self.assertRaises(SystemExit) as raised:
                extract_usernames(path)

        self.assertIn("No usernames were found inside an Instagram modal/dialog", str(raised.exception))
        self.assertIn("whole page contains 2 username-like", str(raised.exception))

    def test_main_writes_sorted_comparison_outputs(self) -> None:
        followers_html = """
        <div role="dialog">
          <a href="/alice/">Alice</a>
          <a href="/bob/">Bob</a>
        </div>
        """
        following_html = """
        <div role="dialog">
          <a href="/bob/">Bob</a>
          <a href="/charlie/">Charlie</a>
          <script>{"username":"DANA"}</script>
        </div>
        """

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            followers_path = self.write_tmp(root, "followers.html", followers_html)
            following_path = self.write_tmp(root, "following.html", following_html)
            out_dir = root / "output"

            with redirect_stdout(StringIO()):
                exit_code = main([str(followers_path), str(following_path), "--out-dir", str(out_dir)])

            self.assertEqual(exit_code, 0)
            self.assertEqual((out_dir / "followers.txt").read_text(encoding="utf-8"), "alice\nbob\n")
            self.assertEqual((out_dir / "following.txt").read_text(encoding="utf-8"), "bob\ncharlie\ndana\n")
            self.assertEqual((out_dir / "not_following_back.txt").read_text(encoding="utf-8"), "charlie\ndana\n")


if __name__ == "__main__":
    unittest.main()
