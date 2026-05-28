"""Tests for export_opml in src.feed_import."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from src.feed_import import export_opml
from src.models import Feed


class TestExportOpml:
    def test_empty_feed_list_produces_valid_xml(self, tmp_path):
        out = tmp_path / "empty.opml"
        export_opml([], str(out))
        assert out.exists()
        tree = ET.parse(out)
        root = tree.getroot()
        assert root.tag == "opml"
        assert root.get("version") == "2.0"
        body = root.find("body")
        assert body is not None
        assert list(body) == []

    def test_empty_feed_list_has_head_with_title(self, tmp_path):
        out = tmp_path / "empty.opml"
        export_opml([], str(out))
        tree = ET.parse(out)
        root = tree.getroot()
        head = root.find("head")
        assert head is not None
        title = head.find("title")
        assert title is not None
        assert title.text == "Jinkies Feed Export"

    def test_single_feed_outline_attributes(self, tmp_path):
        feed = Feed(url="https://example.com/feed.atom", name="Example Feed")
        out = tmp_path / "single.opml"
        export_opml([feed], str(out))
        tree = ET.parse(out)
        root = tree.getroot()
        body = root.find("body")
        outlines = list(body)
        assert len(outlines) == 1
        o = outlines[0]
        assert o.tag == "outline"
        assert o.get("text") == "Example Feed"
        assert o.get("title") == "Example Feed"
        assert o.get("type") == "rss"
        assert o.get("xmlUrl") == "https://example.com/feed.atom"

    def test_multiple_feeds_all_exported(self, tmp_path):
        feeds = [
            Feed(url="https://a.com/feed", name="Feed A"),
            Feed(url="https://b.com/rss", name="Feed B"),
            Feed(url="https://c.com/atom", name="Feed C"),
        ]
        out = tmp_path / "multi.opml"
        export_opml(feeds, str(out))
        tree = ET.parse(out)
        root = tree.getroot()
        body = root.find("body")
        outlines = list(body)
        assert len(outlines) == 3
        urls = {o.get("xmlUrl") for o in outlines}
        assert urls == {"https://a.com/feed", "https://b.com/rss", "https://c.com/atom"}
        names = {o.get("title") for o in outlines}
        assert names == {"Feed A", "Feed B", "Feed C"}

    def test_xml_declaration_present(self, tmp_path):
        out = tmp_path / "decl.opml"
        export_opml([], str(out))
        content = out.read_bytes()
        assert content.startswith(b"<?xml")

    def test_date_created_element_present(self, tmp_path):
        out = tmp_path / "dated.opml"
        export_opml([], str(out))
        tree = ET.parse(out)
        root = tree.getroot()
        head = root.find("head")
        assert head is not None
        date_el = head.find("dateCreated")
        assert date_el is not None
        assert date_el.text  # non-empty date string

    def test_all_outline_types_are_rss(self, tmp_path):
        feeds = [
            Feed(url="https://x.com/feed", name="X"),
            Feed(url="https://y.com/feed", name="Y"),
        ]
        out = tmp_path / "types.opml"
        export_opml(feeds, str(out))
        tree = ET.parse(out)
        root = tree.getroot()
        body = root.find("body")
        for outline in body:
            assert outline.get("type") == "rss"

    def test_output_is_parseable_by_import_opml(self, tmp_path):
        """Round-trip: export then import recovers the same feeds."""
        from src.feed_import import import_opml

        original = [
            Feed(url="https://alpha.com/feed", name="Alpha"),
            Feed(url="https://beta.com/rss", name="Beta"),
        ]
        out = tmp_path / "roundtrip.opml"
        export_opml(original, str(out))
        recovered = import_opml(out)
        assert len(recovered) == 2
        recovered_urls = {f.url for f in recovered}
        assert recovered_urls == {"https://alpha.com/feed", "https://beta.com/rss"}
