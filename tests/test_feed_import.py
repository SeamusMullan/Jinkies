"""Tests for src.feed_import module."""

from __future__ import annotations

import pytest

import feedparser

from src.feed_import import (
    _build_feed_url,
    _extract_job_feeds,
    import_local_feed,
    import_opml,
)

SAMPLE_OPML = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>My Feeds</title></head>
  <body>
    <outline text="Tech" title="Tech">
      <outline type="rss" text="Feed A" title="Feed A"
               xmlUrl="https://a.com/feed.atom"
               htmlUrl="https://a.com"/>
      <outline type="rss" text="Feed B" title="Feed B"
               xmlUrl="https://b.com/rss.xml"
               htmlUrl="https://b.com"/>
    </outline>
    <outline type="rss" text="Feed C"
             xmlUrl="https://c.com/feed"
             htmlUrl="https://c.com"/>
  </body>
</opml>
"""

SAMPLE_ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Feed</title>
  <link href="https://example.com/feed.atom" rel="self" type="application/atom+xml"/>
  <link href="https://example.com" rel="alternate" type="text/html"/>
  <entry>
    <title>Entry 1</title>
    <id>urn:uuid:entry-1</id>
    <link href="https://example.com/1"/>
    <updated>2024-01-01T00:00:00Z</updated>
  </entry>
</feed>
"""

SAMPLE_ATOM_NO_SELF_LINK = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>No Self Link Feed</title>
  <link href="https://example.com" rel="alternate" type="text/html"/>
  <entry>
    <title>Entry 1</title>
    <id>urn:uuid:entry-1</id>
    <link href="https://example.com/1"/>
  </entry>
</feed>
"""


class TestImportOpml:
    def test_parses_all_feeds(self, tmp_path):
        opml_file = tmp_path / "subs.opml"
        opml_file.write_text(SAMPLE_OPML)
        feeds = import_opml(opml_file)
        assert len(feeds) == 3

    def test_extracts_urls(self, tmp_path):
        opml_file = tmp_path / "subs.opml"
        opml_file.write_text(SAMPLE_OPML)
        feeds = import_opml(opml_file)
        urls = {f.url for f in feeds}
        assert "https://a.com/feed.atom" in urls
        assert "https://b.com/rss.xml" in urls
        assert "https://c.com/feed" in urls

    def test_extracts_names(self, tmp_path):
        opml_file = tmp_path / "subs.opml"
        opml_file.write_text(SAMPLE_OPML)
        feeds = import_opml(opml_file)
        names = {f.name for f in feeds}
        assert "Feed A" in names
        assert "Feed B" in names
        assert "Feed C" in names

    def test_invalid_xml_raises(self, tmp_path):
        bad_file = tmp_path / "bad.opml"
        bad_file.write_text("this is not xml")
        with pytest.raises(ValueError, match="Invalid OPML"):
            import_opml(bad_file)

    def test_xxe_payload_is_rejected(self, tmp_path):
        xxe_file = tmp_path / "xxe.opml"
        xxe_file.write_text("""\
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///nonexistent">]>
<opml><body><outline xmlUrl="https://a.com/feed" text="&xxe;"/></body></opml>
""")
        with pytest.raises(ValueError, match="Invalid OPML"):
            import_opml(xxe_file)

    def test_empty_opml(self, tmp_path):
        opml_file = tmp_path / "empty.opml"
        opml_file.write_text(
            '<?xml version="1.0"?><opml><head/><body/></opml>'
        )
        feeds = import_opml(opml_file)
        assert feeds == []

    def test_uses_text_when_no_title(self, tmp_path):
        opml_file = tmp_path / "text_only.opml"
        opml_file.write_text("""\
<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline type="rss" text="Text Name"
             xmlUrl="https://example.com/feed"/>
  </body>
</opml>
""")
        feeds = import_opml(opml_file)
        assert feeds[0].name == "Text Name"

    @pytest.mark.parametrize("bad_url", [
        "file:///etc/passwd",
        "file:///home/user/.ssh/id_rsa",
        "ftp://example.com/feed.xml",
        "data:text/xml,feed",
        "javascript:alert(1)",
    ])
    def test_rejects_non_http_scheme(self, tmp_path, bad_url):
        opml_file = tmp_path / "bad_scheme.opml"
        opml_file.write_text(f"""\
<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline type="rss" text="Bad Feed" xmlUrl="{bad_url}"/>
  </body>
</opml>
""")
        feeds = import_opml(opml_file)
        assert feeds == []

    def test_filters_invalid_schemes_from_mixed_opml(self, tmp_path):
        opml_file = tmp_path / "mixed.opml"
        opml_file.write_text("""\
<?xml version="1.0"?>
<opml version="2.0">
  <body>
    <outline type="rss" text="Valid Feed"
             xmlUrl="https://example.com/feed"/>
    <outline type="rss" text="Local File"
             xmlUrl="file:///etc/passwd"/>
    <outline type="rss" text="FTP Feed"
             xmlUrl="ftp://example.com/feed.xml"/>
  </body>
</opml>
""")
        feeds = import_opml(opml_file)
        assert len(feeds) == 1
        assert feeds[0].url == "https://example.com/feed"


class TestImportLocalFeed:
    def test_parses_atom_feed(self, tmp_path):
        atom_file = tmp_path / "feed.atom"
        atom_file.write_text(SAMPLE_ATOM)
        feeds = import_local_feed(atom_file)
        assert feeds[0].name == "Example Feed"
        assert feeds[0].url == "https://example.com/feed.atom"

    def test_uses_alternate_link_when_no_self(self, tmp_path):
        atom_file = tmp_path / "feed.atom"
        atom_file.write_text(SAMPLE_ATOM_NO_SELF_LINK)
        feeds = import_local_feed(atom_file)
        assert feeds[0].name == "No Self Link Feed"
        assert feeds[0].url == "https://example.com/feed"

    def test_invalid_file_raises(self, tmp_path):
        bad_file = tmp_path / "bad.xml"
        bad_file.write_text("this is not a feed")
        with pytest.raises(ValueError, match="Cannot parse feed"):
            import_local_feed(bad_file)

    def test_feeds_default_enabled(self, tmp_path):
        atom_file = tmp_path / "feed.atom"
        atom_file.write_text(SAMPLE_ATOM)
        feeds = import_local_feed(atom_file)
        assert feeds[0].enabled is True


SAMPLE_JENKINS_ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Jenkins:All (all builds)</title>
  <link rel="alternate" type="text/html" href="http://localhost:8080/"/>
  <entry>
    <title>MyProject &raquo; Backend #5 (stable)</title>
    <link rel="alternate" type="text/html"
          href="http://localhost:8080/job/MyProject/job/Backend/5/"/>
    <id>tag:hudson.dev.java.net,2026:MyProject/Backend:5</id>
    <published>2026-01-15T10:00:00Z</published>
  </entry>
  <entry>
    <title>MyProject &raquo; Frontend #3 (broken)</title>
    <link rel="alternate" type="text/html"
          href="http://localhost:8080/job/MyProject/job/Frontend/3/"/>
    <id>tag:hudson.dev.java.net,2026:MyProject/Frontend:3</id>
    <published>2026-01-15T09:00:00Z</published>
  </entry>
  <entry>
    <title>External &raquo; Library #2 (stable)</title>
    <link rel="alternate" type="text/html"
          href="http://localhost:8080/job/External/job/Library/2/"/>
    <id>tag:hudson.dev.java.net,2026:External/Library:2</id>
    <published>2026-01-15T08:00:00Z</published>
  </entry>
</feed>
"""


class TestImportJenkinsFeed:
    def test_reconstructs_feed_url_from_filename(self, tmp_path):
        atom_file = tmp_path / "rssAll.atom"
        atom_file.write_text(SAMPLE_JENKINS_ATOM)
        feeds = import_local_feed(atom_file)
        assert feeds[0].url == "http://localhost:8080/rssAll"
        assert feeds[0].name == "Jenkins:All (all builds)"

    def test_extracts_per_job_feeds(self, tmp_path):
        atom_file = tmp_path / "rssAll.atom"
        atom_file.write_text(SAMPLE_JENKINS_ATOM)
        feeds = import_local_feed(atom_file)
        # First feed is the main one, rest are per-job
        job_feeds = feeds[1:]
        assert len(job_feeds) == 3
        job_urls = {f.url for f in job_feeds}
        assert "http://localhost:8080/job/MyProject/job/Backend/rssAll" in job_urls
        assert "http://localhost:8080/job/MyProject/job/Frontend/rssAll" in job_urls
        assert "http://localhost:8080/job/External/job/Library/rssAll" in job_urls

    def test_handles_rssLatest_filename(self, tmp_path):
        atom_file = tmp_path / "rssLatest.atom"
        atom_file.write_text(SAMPLE_JENKINS_ATOM)
        feeds = import_local_feed(atom_file)
        assert feeds[0].url == "http://localhost:8080/rssLatest"

    def test_handles_numbered_filename(self, tmp_path):
        atom_file = tmp_path / "rssAll(3).atom"
        atom_file.write_text(SAMPLE_JENKINS_ATOM)
        feeds = import_local_feed(atom_file)
        assert feeds[0].url == "http://localhost:8080/rssAll"


# ---------------------------------------------------------------------------
# Helpers for building minimal feedparser dicts used by the unit tests below.
# ---------------------------------------------------------------------------

def _make_parsed(entries: list[dict], links: list[dict] | None = None) -> feedparser.FeedParserDict:
    """Return a minimal feedparser-style dict with the given entries and links.

    Args:
        entries: List of entry dicts, each with at least a ``link`` key.
        links: Optional list of link dicts for ``parsed.feed.links``.

    Returns:
        A ``feedparser.FeedParserDict`` suitable for passing to private helpers.
    """
    raw: dict = {
        "feed": {"links": links or [], "title": "Test Feed"},
        "entries": [feedparser.FeedParserDict(e) for e in entries],
        "bozo": False,
    }
    return feedparser.FeedParserDict(raw)


# ---------------------------------------------------------------------------
# Edge-case tests for _build_feed_url
# ---------------------------------------------------------------------------

class TestBuildFeedUrlEdgeCases:
    """Unit tests for _build_feed_url covering non-happy-path scenarios."""

    def test_empty_base_url_no_self_link_returns_path(self, tmp_path):
        """When base_url is empty and there is no self link, fall back to str(path)."""
        path = tmp_path / "myfeed.atom"
        parsed = _make_parsed([], links=[])
        result = _build_feed_url(parsed, base_url="", path=path)
        assert result == str(path)

    def test_self_link_takes_priority_over_base_url(self, tmp_path):
        """An explicit self link should always win over base_url reconstruction."""
        path = tmp_path / "rssAll.atom"
        links = [{"rel": "self", "href": "https://ci.example.com/rssAll"}]
        parsed = _make_parsed([], links=links)
        result = _build_feed_url(parsed, base_url="http://localhost:8080", path=path)
        assert result == "https://ci.example.com/rssAll"

    def test_base_url_with_known_stem_is_reconstructed(self, tmp_path):
        """Without a self link, base_url + stem should be reconstructed correctly."""
        path = tmp_path / "rssLatest.atom"
        parsed = _make_parsed([], links=[{"rel": "alternate", "href": "http://ci.local/"}])
        result = _build_feed_url(parsed, base_url="http://ci.local", path=path)
        assert result == "http://ci.local/rssLatest"

    def test_numbered_stem_is_normalised(self, tmp_path):
        """Filenames like ``rssAll(2)`` should be normalised to ``rssAll``."""
        path = tmp_path / "rssAll(2).atom"
        parsed = _make_parsed([])
        result = _build_feed_url(parsed, base_url="http://ci.local", path=path)
        assert result == "http://ci.local/rssAll"


# ---------------------------------------------------------------------------
# Edge-case tests for _extract_job_feeds
# ---------------------------------------------------------------------------

# Parametrize the "link does not contribute a job" scenarios in one table so
# that adding a new corner-case is just adding a row.
_SKIPPED_ENTRY_CASES = [
    pytest.param(
        "",
        id="empty_link",
    ),
    pytest.param(
        "http://localhost:8080/view/All/",
        id="no_job_segment",
    ),
    pytest.param(
        # Different host – removeprefix won't strip the base_url prefix,
        # leaving the full URL as `after_base`; the first part won't be "job".
        "https://other-host.example.com/job/SomeName/42/",
        id="link_different_host",
    ),
    pytest.param(
        # Same host but no /job/ anywhere in the link.
        "http://localhost:8080/search?q=test",
        id="link_no_job_slash",
    ),
]


class TestExtractJobFeedsEdgeCases:
    """Unit tests for _extract_job_feeds covering edge cases."""

    def test_empty_base_url_returns_no_feeds(self):
        """_extract_job_feeds must return an empty list when base_url is empty."""
        parsed = _make_parsed([{"link": "http://localhost:8080/job/Foo/1/"}])
        result = _extract_job_feeds(parsed, base_url="")
        assert result == []

    @pytest.mark.parametrize("link", _SKIPPED_ENTRY_CASES)
    def test_non_contributing_entry_is_skipped(self, link: str):
        """Entries that cannot yield a valid job path must be silently skipped."""
        parsed = _make_parsed([{"link": link, "title": "Irrelevant #1"}])
        result = _extract_job_feeds(parsed, base_url="http://localhost:8080")
        assert result == [], f"Expected no job feeds for link={link!r}"

    def test_deeply_nested_job_path(self):
        """Three levels of /job/Name nesting should all be captured in the feed URL."""
        entries = [
            {
                "link": "http://localhost:8080/job/Org/job/Team/job/Service/7/",
                "title": "Org » Team » Service #7 (stable)",
            }
        ]
        parsed = _make_parsed(entries)
        result = _extract_job_feeds(parsed, base_url="http://localhost:8080")
        assert len(result) == 1
        assert result[0].url == "http://localhost:8080/job/Org/job/Team/job/Service/rssAll"

    def test_duplicate_entries_produce_single_feed(self):
        """Multiple builds from the same job should collapse into one feed URL."""
        entries = [
            {"link": "http://localhost:8080/job/Alpha/job/Beta/3/", "title": "Alpha » Beta #3"},
            {"link": "http://localhost:8080/job/Alpha/job/Beta/4/", "title": "Alpha » Beta #4"},
        ]
        parsed = _make_parsed(entries)
        result = _extract_job_feeds(parsed, base_url="http://localhost:8080")
        assert len(result) == 1
        assert result[0].url == "http://localhost:8080/job/Alpha/job/Beta/rssAll"

    def test_mixed_valid_and_invalid_entries(self):
        """Only entries with a valid job path should produce feeds; others are ignored."""
        entries = [
            # Valid job entry
            {"link": "http://localhost:8080/job/MyProject/job/API/10/", "title": "MyProject » API #10"},
            # No /job/ in link
            {"link": "http://localhost:8080/view/All/", "title": "View page #1"},
            # Different host
            {"link": "https://other.example.com/job/Ghost/1/", "title": "Ghost #1"},
            # Empty link
            {"link": "", "title": "Empty #1"},
        ]
        parsed = _make_parsed(entries)
        result = _extract_job_feeds(parsed, base_url="http://localhost:8080")
        assert len(result) == 1
        assert result[0].url == "http://localhost:8080/job/MyProject/job/API/rssAll"
