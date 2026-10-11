"""Pure parsing helpers (HTML, DuckDuckGo results, arXiv Atom). Stdlib only, easy to test."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------- readable text from HTML

_SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form", "iframe", "template"}
_BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0:
            self.parts.append(data)


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, readable_text)."""
    p = _TextExtractor()
    try:
        p.feed(html)
        p.close()
    except Exception:  # malformed HTML: use what we have
        pass
    raw = "".join(p.parts)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in raw.split("\n")]
    text = "\n".join(ln for ln in lines if ln)
    return re.sub(r"\s+", " ", p.title).strip(), text


# ---------------------------------------------------------------- DuckDuckGo HTML results


def _unwrap_ddg(href: str) -> str:
    if "uddg=" in href:
        q = parse_qs(urlparse(href).query).get("uddg")
        if q:
            return q[0]
    if href.startswith("//"):
        return "https:" + href
    return href


class _DDGParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict] = []
        self._cur: dict | None = None
        self._mode: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if "result__a" in classes:
            self._cur = {"title": "", "url": _unwrap_ddg(a.get("href") or ""), "snippet": ""}
            self.results.append(self._cur)
            self._mode = "title"
        elif "result__snippet" in classes and self._cur is not None:
            self._mode = "snippet"

    def handle_endtag(self, tag):
        if tag == "a":
            self._mode = None

    def handle_data(self, data):
        if self._cur is not None and self._mode:
            self._cur[self._mode] += data


def parse_ddg_html(html: str, limit: int = 5) -> list[dict]:
    p = _DDGParser()
    p.feed(html)
    out = []
    for r in p.results:
        url = r["url"]
        if not url.startswith("http") or "duckduckgo.com/y.js" in url:  # skip ads / junk
            continue
        out.append(
            {
                "title": re.sub(r"\s+", " ", r["title"]).strip(),
                "url": url,
                "snippet": re.sub(r"\s+", " ", r["snippet"]).strip()[:400],
            }
        )
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- arXiv Atom feed

_NS = {"a": "http://www.w3.org/2005/Atom"}


def parse_arxiv_atom(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall("a:entry", _NS):
        title = " ".join((e.findtext("a:title", "", _NS) or "").split())
        if not title or title.lower() == "error":
            continue
        out.append(
            {
                "title": title,
                "authors": [n for n in (a.findtext("a:name", "", _NS) for a in e.findall("a:author", _NS)) if n][:4],
                "published": (e.findtext("a:published", "", _NS) or "")[:10],
                "summary": " ".join((e.findtext("a:summary", "", _NS) or "").split())[:600],
                "url": (e.findtext("a:id", "", _NS) or "").replace("http://", "https://"),
            }
        )
    return out
