"""Reddit home feed and subreddit feed."""

from __future__ import annotations

import json
import logging
import time

from .bridge import BridgePage
from .errors import NoPostsError
from .human import sleep_random
from .selectors import POST_CONTAINER
from .types import Post
from .urls import HOME_URL, make_subreddit_url

logger = logging.getLogger(__name__)

_EXTRACT_POSTS_JS = """
(() => {
    const posts = [];
    document.querySelectorAll('shreddit-post').forEach(el => {
        try {
            const title = el.getAttribute('post-title') || '';
            if (!title) return;
            const bodyEl = el.querySelector('[slot="text-body"]');
            const selftext = bodyEl ? bodyEl.innerText.trim() : '';
            // Extract timestamp from <time> element
            let createdUtc = 0;
            const timeEl = el.querySelector('time[datetime]');
            if (timeEl) {
                const dt = timeEl.getAttribute('datetime');
                if (dt) {
                    createdUtc = new Date(dt).getTime() / 1000;
                }
            }
            posts.push({
                id: el.id || '',
                title: title,
                subreddit: el.getAttribute('subreddit-name') || '',
                author: { name: el.getAttribute('author') || '' },
                permalink: el.getAttribute('permalink') || '',
                postType: el.getAttribute('post-type') || '',
                selftext: selftext,
                createdUtc: createdUtc,
                stats: {
                    score: parseInt(el.getAttribute('score') || '0', 10) || 0,
                    numComments: parseInt(el.getAttribute('comment-count') || '0', 10) || 0,
                },
            });
        } catch (e) {}
    });
    return JSON.stringify(posts);
})()
"""


def home_feed(page: BridgePage) -> list[Post]:
    """Get posts from the home feed."""
    page.navigate(HOME_URL)
    page.wait_for_load()
    page.wait_dom_stable()
    sleep_random(500, 1000)

    return _extract_posts(page)


def subreddit_feed(
    page: BridgePage,
    subreddit: str,
    sort: str = "hot",
    max_posts: int = 100,
    max_scrolls: int = 30,
) -> list[Post]:
    """Get posts from a specific subreddit, scrolling to load more."""
    url = make_subreddit_url(subreddit, sort)
    page.navigate(url)
    page.wait_for_load()
    page.wait_dom_stable()
    sleep_random(500, 1000)

    return _extract_posts_scroll(page, max_posts=max_posts, max_scrolls=max_scrolls)


def _extract_posts(page: BridgePage) -> list[Post]:
    """Extract post data from the current page (no scroll)."""
    _wait_for_posts(page)

    result = page.evaluate(_EXTRACT_POSTS_JS)
    if not result:
        raise NoPostsError()

    posts_data = json.loads(result)
    if not posts_data:
        raise NoPostsError()

    return [Post.from_dict(p) for p in posts_data]


def _extract_posts_scroll(
    page: BridgePage,
    max_posts: int = 100,
    max_scrolls: int = 30,
) -> list[Post]:
    """Extract posts by scrolling the page to load more.

    Reddit uses infinite scroll — only ~3-5 posts are in the DOM at a time.
    This scrolls down, waits for new posts to render, and accumulates unique posts.
    """
    _wait_for_posts(page)

    seen_ids: set[str] = set()
    all_posts: list[Post] = []

    for scroll_num in range(max_scrolls):
        result = page.evaluate(_EXTRACT_POSTS_JS)
        if result:
            posts_data = json.loads(result)
            new_count = 0
            for p in posts_data:
                pid = p.get("id", "")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_posts.append(Post.from_dict(p))
                    new_count += 1

            if len(all_posts) >= max_posts:
                logger.info("Reached max_posts (%d), stopping scroll", max_posts)
                break

            if new_count == 0:
                # No new posts this scroll — try once more after a longer wait
                logger.info("No new posts at scroll %d (total: %d), waiting...", scroll_num + 1, len(all_posts))
                sleep_random(1500, 2500)
                result2 = page.evaluate(_EXTRACT_POSTS_JS)
                if result2:
                    posts_data2 = json.loads(result2)
                    new2 = 0
                    for p in posts_data2:
                        pid = p.get("id", "")
                        if pid and pid not in seen_ids:
                            seen_ids.add(pid)
                            all_posts.append(Post.from_dict(p))
                            new2 += 1
                    if new2 == 0:
                        logger.info("Still no new posts after wait, stopping (total: %d)", len(all_posts))
                        break

        # Scroll down — use a human-like amount
        page.scroll_by(0, 600 + (scroll_num % 3) * 200)
        sleep_random(800, 1500)

    if not all_posts:
        raise NoPostsError()

    logger.info("Scrolled %d times, collected %d unique posts", scroll_num + 1, len(all_posts))
    return all_posts

_WAIT_TIMEOUT = 15.0


def _wait_for_posts(page: BridgePage, timeout: float = 15.0) -> None:
    """Wait for posts to appear on the page."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        count = page.get_elements_count(POST_CONTAINER)
        if count > 0:
            return
        time.sleep(0.5)
    logger.warning("Timeout waiting for posts to load")
