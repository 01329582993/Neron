"""Pluggable web search engine with DuckDuckGo, SearXNG, and mock providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import urllib.parse

from bs4 import BeautifulSoup
import requests

from neron.utils.logger import get_logger

logger = get_logger("network.search")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class SearchResult:
    """Standardized web search result item."""
    title: str
    url: str
    snippet: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
        }


class SearchProvider(ABC):
    """Abstract contract for search engines."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        pass


class DuckDuckGoProvider(SearchProvider):
    """Zero-API-key web search using DuckDuckGo HTML endpoint."""

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        clean_query = query.strip()
        if not clean_query:
            return []

        url = "https://html.duckduckgo.com/html/"
        data = {"q": clean_query}

        try:
            resp = requests.post(url, data=data, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            results: List[SearchResult] = []
            links = soup.find_all("a", class_="result__url")
            titles = soup.find_all("a", class_="result__snippet")

            # Extract result blocks
            for result_div in soup.find_all("div", class_="result"):
                title_elem = result_div.find("a", class_="result__a")
                snippet_elem = result_div.find("a", class_="result__snippet")

                if not title_elem:
                    continue

                raw_url = title_elem.get("href", "")
                # DuckDuckGo wraps URLs in /l/?uddg=<actual_url>
                if "uddg=" in raw_url:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                    target_url = parsed.get("uddg", [raw_url])[0]
                else:
                    target_url = raw_url

                title_text = title_elem.get_text(strip=True)
                snippet_text = snippet_elem.get_text(strip=True) if snippet_elem else ""

                if target_url and title_text:
                    results.append(
                        SearchResult(
                            title=title_text,
                            url=target_url,
                            snippet=snippet_text,
                        )
                    )
                    if len(results) >= max_results:
                        break

            return results
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []


class SearXNGProvider(SearchProvider):
    """Self-hosted privacy-focused metasearch engine integration."""

    def __init__(self, base_url: str = "http://localhost:8080", timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        endpoint = f"{self.base_url}/search"
        params = {"q": query, "format": "json"}

        try:
            resp = requests.get(endpoint, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            raw_results = data.get("results", [])

            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", ""),
                )
                for r in raw_results[:max_results]
            ]
        except Exception as e:
            logger.warning(f"SearXNG search query failed: {e}")
            return []


class MockSearchProvider(SearchProvider):
    """Simulated search provider for tests and completely offline execution."""

    def __init__(self, mock_results: Optional[List[SearchResult]] = None):
        self.mock_results = mock_results or []

    def set_mock_results(self, results: List[SearchResult]) -> None:
        self.mock_results = results

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if self.mock_results:
            return self.mock_results[:max_results]

        # Generate synthetic search results
        return [
            SearchResult(
                title=f"Result 1 for '{query}'",
                url=f"https://example.com/search?q={urllib.parse.quote(query)}",
                snippet=f"Relevant information and overview regarding '{query}'.",
            ),
            SearchResult(
                title=f"Documentation for '{query}'",
                url="https://docs.example.org/guide",
                snippet=f"Official guide and reference documentation for {query}.",
            ),
        ][:max_results]


class SearchEngineRouter:
    """
    Manages search engine providers and executes fallback strategies.
    """

    def __init__(self, primary: Optional[SearchProvider] = None, fallback: Optional[SearchProvider] = None):
        self.primary = primary or DuckDuckGoProvider()
        self.fallback = fallback or MockSearchProvider()

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        results = self.primary.search(query, max_results=max_results)
        if not results and self.fallback:
            logger.info("Primary search provider yielded no results; invoking fallback provider.")
            results = self.fallback.search(query, max_results=max_results)
        return results
