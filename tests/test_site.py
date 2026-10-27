"""Static checks for the HTML pages deployed to S3."""
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted(REPO_ROOT.glob("*.html"))

# Elements that never have a closing tag
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "source", "track", "wbr",
}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.doctype = None
        self.stack = []
        self.errors = []
        self.html_attrs = {}
        self.metas = []
        self.title = ""
        self.in_title = False
        self.links = []
        self.scripts = []
        self.anchors = []

    def handle_decl(self, decl):
        self.doctype = decl

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.html_attrs = attrs
        elif tag == "meta":
            self.metas.append(attrs)
        elif tag == "title":
            self.in_title = True
        elif tag == "link":
            self.links.append(attrs)
        elif tag == "script":
            self.scripts.append(attrs)
        elif tag == "a" and attrs.get("href"):
            self.anchors.append(attrs["href"])
        if tag not in VOID_ELEMENTS:
            self.stack.append((tag, self.getpos()))

    def handle_startendtag(self, tag, attrs):
        # Self-closing syntax (<br />): record attributes without pushing onto the stack
        if tag in VOID_ELEMENTS:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in VOID_ELEMENTS:
            return
        if not self.stack or self.stack[-1][0] != tag:
            expected = self.stack[-1][0] if self.stack else "nothing"
            self.errors.append(f"line {self.getpos()[0]}: </{tag}> closes <{expected}>")
            return
        self.stack.pop()

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def parse(page: Path) -> PageParser:
    parser = PageParser()
    parser.feed(page.read_text(encoding="utf-8"))
    parser.close()
    return parser


def test_pages_found():
    assert PAGES, "No HTML pages found at the repository root"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
class TestPage:
    def test_html5_doctype(self, page):
        assert (parse(page).doctype or "").lower() == "doctype html"

    def test_tags_balanced(self, page):
        parser = parse(page)
        assert not parser.errors, parser.errors
        unclosed = [f"<{tag}> at line {pos[0]}" for tag, pos in parser.stack]
        assert not unclosed, f"Unclosed tags: {unclosed}"

    def test_language_declared(self, page):
        assert parse(page).html_attrs.get("lang")

    def test_utf8_charset(self, page):
        charsets = [m.get("charset", "").lower() for m in parse(page).metas]
        assert "utf-8" in charsets

    def test_viewport_meta(self, page):
        assert any(m.get("name") == "viewport" for m in parse(page).metas)

    def test_description_meta(self, page):
        assert any(m.get("name") == "description" and m.get("content") for m in parse(page).metas)

    def test_title_present(self, page):
        assert parse(page).title.strip()

    def test_external_resources_use_https_and_sri(self, page):
        parser = parse(page)
        resources = [(a.get("href"), a) for a in parser.links] + [(a.get("src"), a) for a in parser.scripts]
        for url, attrs in resources:
            if not url or not url.startswith(("http:", "https:", "//")):
                continue
            assert url.startswith("https://"), f"Insecure resource URL: {url}"
            assert attrs.get("integrity"), f"Missing Subresource Integrity hash: {url}"
            assert attrs.get("crossorigin") == "anonymous", f"SRI requires crossorigin=anonymous: {url}"

    def test_internal_links_resolve(self, page):
        for href in parse(page).anchors:
            if href.startswith(("http:", "https:", "mailto:", "tel:", "#")):
                continue
            assert (REPO_ROOT / href.split("#")[0]).is_file(), f"Broken link: {href}"
