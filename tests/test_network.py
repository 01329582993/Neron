"""Test suite for Neron Stage 11 Modular Online Integrations."""

import pytest

from neron.core.events.bus import EventBus
from neron.core.planner.dag_planner import DAGPlanner
from neron.core.state.models import TaskState
from neron.network.browser import PageContent, WebReader
from neron.network.observer import EVENT_NETWORK_CHANGED, NetworkObserver
from neron.network.search import (
    MockSearchProvider,
    SearchEngineRouter,
    SearchResult,
)
from neron.security.permissions import Capability
from neron.tools import create_default_registry
from neron.tools.network.tools import (
    NetworkFetchPageTool,
    NetworkSearchTool,
    NetworkStatusTool,
)


# ── Network Observer Tests ──────────────────────────────────────────────────

class TestNetworkObserver:
    def test_mock_status_online_and_offline(self):
        observer = NetworkObserver()

        observer.set_mock_status(True)
        assert observer.is_online is True

        observer.set_mock_status(False)
        assert observer.is_online is False

    def test_network_event_on_transition(self):
        bus = EventBus()
        events = []
        bus.subscribe(EVENT_NETWORK_CHANGED, lambda e: events.append(e))

        observer = NetworkObserver(event_bus=bus)
        observer.set_mock_status(None) # Clear mock

        # Simulate transitions
        observer._is_online = False
        observer.check_connection(force=True)

        # Transition to online
        observer._is_online = False
        observer._mock_online = True
        observer.check_connection(force=True)

        assert len(events) >= 1
        assert events[-1].payload["online"] is True

    def test_cached_read_within_ttl(self):
        observer = NetworkObserver(cache_ttl_seconds=60.0)
        observer.set_mock_status(True)

        r1 = observer.check_connection()
        r2 = observer.check_connection()
        assert r2["cached"] is True


# ── Search Engine Tests ─────────────────────────────────────────────────────

class TestSearchEngine:
    def test_mock_search_provider(self):
        provider = MockSearchProvider()
        results = provider.search("python fast-api", max_results=2)

        assert len(results) == 2
        assert "python fast-api" in results[0].title
        assert "https://" in results[0].url

    def test_search_router_fallback(self):
        class FailingSearch(MockSearchProvider):
            def search(self, query: str, max_results: int = 5):
                return []

        fallback = MockSearchProvider([
            SearchResult(title="Fallback Hit", url="https://fallback.org", snippet="Backup text")
        ])
        router = SearchEngineRouter(primary=FailingSearch(), fallback=fallback)

        res = router.search("anything")
        assert len(res) == 1
        assert res[0].title == "Fallback Hit"


# ── Web Reader Tests ────────────────────────────────────────────────────────

class TestWebReader:
    def test_mock_web_reader(self):
        reader = WebReader()
        mock_page = PageContent(
            url="https://test.local/doc",
            title="Test Doc",
            text="Clean extracted text from article.",
            links=[{"text": "Home", "href": "https://test.local"}],
            status_code=200,
        )
        reader.set_mock_page("https://test.local/doc", mock_page)

        page = reader.fetch("https://test.local/doc")
        assert page.title == "Test Doc"
        assert "Clean extracted" in page.text
        assert len(page.links) == 1

    def test_html_cleaning_logic(self):
        reader = WebReader()
        # Mock HTML parsing without real HTTP request
        from bs4 import BeautifulSoup
        html = """
        <html>
            <head><title>Clean Me</title><script>alert('bad')</script></head>
            <body>
                <nav>Menu 1 Menu 2</nav>
                <article>
                    <h1>Real Heading</h1>
                    <p>Real paragraph text here.</p>
                </article>
                <footer>Copyright 2026</footer>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        assert "alert" not in text
        assert "Menu 1" not in text
        assert "Copyright" not in text
        assert "Real paragraph text here." in text


# ── Network Tools Tests ─────────────────────────────────────────────────────

class TestNetworkTools:
    def test_network_tools_registered_in_default_registry(self):
        registry = create_default_registry()
        assert registry.has("network.status")
        assert registry.has("network.search")
        assert registry.has("network.fetch_page")

    def test_network_status_tool_execution(self):
        observer = NetworkObserver()
        observer.set_mock_status(True)
        tool = NetworkStatusTool(observer=observer)

        res = tool.execute({})
        assert res.success is True
        assert res.output["online"] is True

    def test_network_search_tool_execution(self):
        mock_provider = MockSearchProvider([
            SearchResult(title="Pytest Guide", url="https://pytest.org", snippet="Testing in Python")
        ])
        router = SearchEngineRouter(primary=mock_provider)
        tool = NetworkSearchTool(router=router)

        res = tool.execute({"query": "pytest"})
        assert res.success is True
        assert res.output["count"] == 1
        assert res.output["results"][0]["title"] == "Pytest Guide"

    def test_network_fetch_page_tool_execution(self):
        reader = WebReader()
        reader.set_mock_page(
            "https://mytest.org",
            PageContent(
                url="https://mytest.org",
                title="My Test",
                text="Article content here",
                status_code=200,
            ),
        )
        tool = NetworkFetchPageTool(reader=reader)

        res = tool.execute({"url": "https://mytest.org"})
        assert res.success is True
        assert res.output["title"] == "My Test"
        assert res.output["text"] == "Article content here"


# ── DAG Planner Network Goals Tests ─────────────────────────────────────────

class TestDAGPlannerNetworkGoals:
    def test_search_web_goal(self):
        planner = DAGPlanner()
        plan = planner.plan("search the web for machine learning news", {}, [])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "network.search"
        assert plan.steps[0].arguments["query"] == "machine learning news"
        assert plan.state == TaskState.PENDING

    def test_read_webpage_goal(self):
        planner = DAGPlanner()
        plan = planner.plan("read webpage https://docs.python.org", {}, [])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "network.fetch_page"
        assert plan.steps[0].arguments["url"] == "https://docs.python.org"

    def test_check_internet_goal(self):
        planner = DAGPlanner()
        plan = planner.plan("check internet connection", {}, [])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "network.status"
