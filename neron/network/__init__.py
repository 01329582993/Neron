"""Neron network and online integration subsystem."""

from neron.network.browser import PageContent, WebReader
from neron.network.observer import (
    EVENT_NETWORK_CHANGED,
    NetworkObserver,
)
from neron.network.search import (
    DuckDuckGoProvider,
    MockSearchProvider,
    SearchEngineRouter,
    SearchProvider,
    SearchResult,
    SearXNGProvider,
)

__all__ = [
    "DuckDuckGoProvider",
    "EVENT_NETWORK_CHANGED",
    "MockSearchProvider",
    "NetworkObserver",
    "PageContent",
    "SearchEngineRouter",
    "SearchProvider",
    "SearchResult",
    "SearXNGProvider",
    "WebReader",
]
