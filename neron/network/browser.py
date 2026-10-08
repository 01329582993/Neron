"""Lightweight webpage fetcher and content extractor using requests and BeautifulSoup."""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional
import urllib.parse

from bs4 import BeautifulSoup
import requests

from neron.network.search import DEFAULT_USER_AGENT
from neron.utils.logger import get_logger

logger = get_logger("network.browser")


@dataclass
class PageContent:
    """Extracted text, metadata, and links from a fetched webpage."""
    url: str
    title: str
    text: str
    links: List[Dict[str, str]] = field(default_factory=list)
    status_code: int = 200

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "links": self.links,
            "status_code": self.status_code,
        }


class WebReader:
    """
    HTTP web page reader that cleans HTML boilerplate, navigations, and scripts
    to produce clean, token-efficient text for AI processing.
    """

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self._mock_pages: Dict[str, PageContent] = {}

    def set_mock_page(self, url: str, content: PageContent) -> None:
        """Inject mock page content for offline testing."""
        self._mock_pages[url] = content

    def fetch(self, url: str, max_length: int = 5000) -> PageContent:
        """
        Fetch and parse a webpage. Extracts title, clean body text, and top links.
        """
        clean_url = url.strip()
        if clean_url in self._mock_pages:
            return self._mock_pages[clean_url]

        parsed = urllib.parse.urlparse(clean_url)
        if not parsed.scheme:
            clean_url = "https://" + clean_url

        try:
            resp = requests.get(clean_url, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract Title
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else parsed.netloc

            # Remove non-content tags
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"]):
                tag.decompose()

            # Extract links
            links: List[Dict[str, str]] = []
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(strip=True)
                if href.startswith("http") and text and len(text) > 2:
                    links.append({"text": text, "href": href})
                    if len(links) >= 10:
                        break

            # Extract clean main text
            text = soup.get_text(separator="\n", strip=True)
            # Collapse multiple empty lines
            text = re.sub(r"\n\s*\n+", "\n\n", text)

            if len(text) > max_length:
                text = text[:max_length] + "\n\n[...content truncated for brevity...]"

            return PageContent(
                url=clean_url,
                title=title,
                text=text,
                links=links,
                status_code=resp.status_code,
            )

        except Exception as e:
            logger.error(f"Failed to fetch webpage '{clean_url}': {e}")
            return PageContent(
                url=clean_url,
                title="Error",
                text=f"Failed to fetch content: {e}",
                status_code=500,
            )
