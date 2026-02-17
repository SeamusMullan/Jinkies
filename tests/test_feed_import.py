"""Tests for src.feed_import module."""

from __future__ import annotations

import pytest

from src.feed_import import import_local_feed, import_opml

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
