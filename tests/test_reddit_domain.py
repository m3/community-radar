import pytest
from src.collectors.reddit_domain import build_domain_json_url

def test_build_domain_json_url():
    # Reddit's legacy /domain/<d>/new.json endpoint 404s, so we use the
    # search API with the site: operator instead.
    url = build_domain_json_url("example.com", limit=50)
    assert url == "https://www.reddit.com/search.json?q=site:example.com&sort=new&limit=50"

def test_build_domain_json_url_with_after():
    url = build_domain_json_url("example.com", after="t3_xyz")
    # Should include both limit (default 100) and after
    assert "after=t3_xyz" in url
    assert "limit=100" in url
