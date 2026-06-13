"""Unified CLI entry point (Extension Bridge version)

Connects to the user's browser via the Reddit Bridge extension.
Start bridge_server.py first, install the Reddit Bridge extension in Chrome, then run this CLI.

Output: JSON (ensure_ascii=False)
Exit codes: 0=success, 1=not logged in, 2=error
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

def get_proxy_from_bws(secret_id: str) -> str | None:
    import subprocess
    import json
    if not secret_id:
        return None
    try:
        result = subprocess.run(
            ["bws", "secret", "get", secret_id, "--output", "json"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        return data.get("value")
    except Exception as e:
        print(f"Error fetching proxy from BWS: {e}")
        return None

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("reddit-cli")


def _output(data: dict, exit_code: int = 0) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


class _DummyBrowser:
    def close(self) -> None:
        pass

    def close_page(self, page) -> None:
        pass


def _ensure_bridge_ready(bridge_url: str) -> None:
    """Ensure bridge server is running and extension is connected."""
    import subprocess
    import time
    from pathlib import Path

    from reddit.bridge import BridgePage

    page = BridgePage(bridge_url)

    if not page.is_server_running():
        logger.info("Bridge server not running, starting...")
        scripts_dir = Path(__file__).parent
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen(
            [sys.executable, str(scripts_dir / "bridge_server.py")],
            **kwargs,
        )
        for _ in range(10):
            time.sleep(1)
            if page.is_server_running():
                logger.info("Bridge server started")
                break
        else:
            logger.warning("Bridge server start timeout. Please run bridge_server.py manually.")
            return

    if page.is_extension_connected():
        return

    logger.info("Browser extension not connected, opening Chrome...")
    _open_chrome()

    for _ in range(20):
        time.sleep(1)
        if page.is_extension_connected():
            logger.info("Browser extension connected")
            return
    logger.warning(
        "Extension connection timeout. "
        "Please ensure Chrome has the Reddit Bridge extension installed and enabled."
    )


def _open_chrome() -> None:
    """Try to launch Chrome browser."""
    import subprocess

    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            subprocess.Popen([path])
            return
    for cmd in [["open", "-a", "Google Chrome"], ["google-chrome"], ["chromium-browser"]]:
        try:
            subprocess.Popen(cmd)
            return
        except FileNotFoundError:
            continue
    logger.warning("Chrome not found. Please open your browser manually.")


def _connect(args: argparse.Namespace):
    backend = getattr(args, "backend", "bridge")
    if backend == "playwright":
        from reddit.playwright_backend import PlaywrightPage
        proxy = get_proxy_from_bws(args.proxy_secret_id) if getattr(args, "proxy_secret_id", None) else None
        page = PlaywrightPage(headless=not getattr(args, "headed", False), proxy=proxy)
        return page, page
    else:
        from reddit.bridge import BridgePage
        bridge_url = getattr(args, "bridge_url", "ws://localhost:9334")
        _ensure_bridge_ready(bridge_url)
        return _DummyBrowser(), BridgePage(bridge_url)


# ─── Subcommand implementations ──────────────────────────────────


def cmd_check_login(args: argparse.Namespace) -> None:
    from reddit.login import check_login_status, get_current_username

    browser, page = _connect(args)
    try:
        logged_in = check_login_status(page)
        if logged_in:
            username = get_current_username(page)
            _output({"logged_in": True, "username": username})
        else:
            _output(
                {
                    "logged_in": False,
                    "hint": "Not logged in. Please log in to Reddit in your browser.",
                },
                exit_code=1,
            )
    finally:
        browser.close()


def cmd_delete_cookies(args: argparse.Namespace) -> None:
    from reddit.login import logout

    browser, page = _connect(args)
    try:
        logged_out = logout(page)
        msg = "Logged out successfully" if logged_out else "Not logged in"
        _output({"success": True, "message": msg})
    finally:
        browser.close()


def cmd_home_feed(args: argparse.Namespace) -> None:
    from reddit.feeds import home_feed

    browser, page = _connect(args)
    try:
        posts = home_feed(page)
        _output({"posts": [p.to_dict() for p in posts], "count": len(posts)})
    finally:
        browser.close()


def cmd_subreddit_feed(args: argparse.Namespace) -> None:
    from reddit.feeds import subreddit_feed

    browser, page = _connect(args)
    try:
        posts = subreddit_feed(page, args.subreddit, args.sort)
        _output({"posts": [p.to_dict() for p in posts], "count": len(posts)})
    finally:
        browser.close()


def cmd_json_feed(args: argparse.Namespace) -> None:
    """Fetch Reddit's .json API for bulk post extraction with timestamps."""
    from reddit.human import sleep_random

    browser, page = _connect(args)
    try:
        all_posts = []
        after = args.after or None

        for page_num in range(args.max_pages):
            # 'top' sort requires a time filter (t=all|year|month|week|day)
            # If sort contains '?t=' it's already a top+time combo
            base_sort = args.sort.split("?")[0]
            url = f"https://www.reddit.com/r/{args.subreddit}/{base_sort}.json?limit={args.limit}"
            if "?" in args.sort:
                url += "&" + args.sort.split("?", 1)[1]
            if after:
                url += f"&after={after}"

            page.navigate(url)
            page.wait_for_load()
            sleep_random(500, 1000)

            text = page.evaluate("document.body.innerText")
            if not text:
                break

            data = json.loads(text)
            children = data.get("data", {}).get("children", [])

            if not children:
                break

            for c in children:
                d = c.get("data", {})
                post = {
                    "id": d.get("id", ""),
                    "title": d.get("title", ""),
                    "subreddit": d.get("subreddit", ""),
                    "author": {"name": d.get("author", "[deleted]")},
                    "permalink": d.get("permalink", ""),
                    "postType": "text" if d.get("is_self") else "link",
                    "selftext": d.get("selftext", ""),
                    "createdUtc": d.get("created_utc", 0),
                    "stats": {
                        "score": d.get("score", 0),
                        "numComments": d.get("num_comments", 0),
                        "upvoteRatio": d.get("upvote_ratio", 0),
                    },
                    "flair": d.get("link_flair_text", ""),
                    "domain": d.get("domain", ""),
                    "url": d.get("url", ""),
                }
                all_posts.append(post)

            after = data.get("data", {}).get("after")
            if not after:
                break

            sleep_random(1000, 2000)

        _output({"posts": all_posts, "count": len(all_posts), "after": after})
    finally:
        browser.close()


def cmd_json_url(args: argparse.Namespace) -> None:
    """Fetch any URL as JSON via bridge."""
    browser, page = _connect(args)
    try:
        page.navigate(args.url)
        page.wait_for_load()
        sleep_random(500, 1000)
        text = page.evaluate("document.body.innerText")
        if not text or not text.strip():
            _output({"error": "Empty response from browser", "url": args.url}, exit_code=2)
        
        try:
            data = json.loads(text.strip())
            _output(data)
        except json.JSONDecodeError:
            # Some browsers might wrap JSON in <pre> or similar
            # Attempt to extract text content
            _output({"error": "Failed to parse JSON from body", "raw": text[:200]}, exit_code=2)
    finally:
        browser.close()


def cmd_search(args: argparse.Namespace) -> None:
    from reddit.search import search_posts
    from reddit.types import SearchFilter

    filter_opt = SearchFilter(
        sort=args.sort or "relevance",
        time=args.time or "all",
    )

    browser, page = _connect(args)
    try:
        posts = search_posts(page, args.query, filter_opt)
        _output({"posts": [p.to_dict() for p in posts], "count": len(posts)})
    finally:
        browser.close()


def cmd_get_post_detail(args: argparse.Namespace) -> None:
    from reddit.post_detail import get_post_detail

    browser, page = _connect(args)
    try:
        detail = get_post_detail(
            page,
            args.post_url,
            load_all_comments=args.load_all_comments,
        )
        _output(detail.to_dict())
    finally:
        browser.close()


def cmd_user_profile(args: argparse.Namespace) -> None:
    from reddit.user_profile import get_user_profile

    browser, page = _connect(args)
    try:
        result = get_user_profile(page, args.username)
        _output(result)
    finally:
        browser.close()


def cmd_post_comment(args: argparse.Namespace) -> None:
    from reddit.comment import post_comment

    browser, page = _connect(args)
    try:
        post_comment(page, args.post_url, args.content)
        _output({"success": True, "message": "Comment posted successfully"})
    finally:
        browser.close()


def cmd_reply_comment(args: argparse.Namespace) -> None:
    from reddit.comment import reply_comment

    browser, page = _connect(args)
    try:
        reply_comment(page, args.post_url, args.content, comment_id=args.comment_id or "")
        _output({"success": True, "message": "Reply posted successfully"})
    finally:
        browser.close()


def cmd_upvote(args: argparse.Namespace) -> None:
    from reddit.vote import upvote_post

    browser, page = _connect(args)
    try:
        result = upvote_post(page, args.post_url)
        _output(result.to_dict())
    finally:
        browser.close()


def cmd_downvote(args: argparse.Namespace) -> None:
    from reddit.vote import downvote_post

    browser, page = _connect(args)
    try:
        result = downvote_post(page, args.post_url)
        _output(result.to_dict())
    finally:
        browser.close()


def cmd_save_post(args: argparse.Namespace) -> None:
    from reddit.vote import save_post

    browser, page = _connect(args)
    try:
        result = save_post(page, args.post_url, unsave=args.unsave)
        _output(result.to_dict())
    finally:
        browser.close()


def cmd_subreddit_rules(args: argparse.Namespace) -> None:
    from reddit.publish import get_submit_flairs, get_subreddit_rules

    browser, page = _connect(args)
    try:
        rules_data = get_subreddit_rules(page, args.subreddit)
        flairs = get_submit_flairs(page, args.subreddit)
        _output({
            "subreddit": args.subreddit,
            "rules": rules_data.get("rules", []),
            "availableFlairs": flairs,
            "requiresFlair": any(
                "flair" in r.lower() for r in rules_data.get("rules", [])
            ),
        })
    finally:
        browser.close()


def cmd_submit_text(args: argparse.Namespace) -> None:
    from reddit.publish import submit_text_post
    from reddit.types import SubmitTextContent

    with open(args.title_file, encoding="utf-8") as f:
        title = f.read().strip()
    body = ""
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read().strip()

    browser, page = _connect(args)
    try:
        submit_text_post(
            page,
            SubmitTextContent(
                subreddit=args.subreddit,
                title=title,
                body=body,
                flair_id=getattr(args, "flair", ""),
                nsfw=args.nsfw,
                spoiler=args.spoiler,
            ),
        )
        _output(
            {
                "success": True,
                "subreddit": args.subreddit,
                "title": title,
                "status": "Published",
            }
        )
    finally:
        browser.close()


def cmd_submit_link(args: argparse.Namespace) -> None:
    from reddit.publish import submit_link_post
    from reddit.types import SubmitLinkContent

    with open(args.title_file, encoding="utf-8") as f:
        title = f.read().strip()

    browser, page = _connect(args)
    try:
        submit_link_post(
            page,
            SubmitLinkContent(
                subreddit=args.subreddit,
                title=title,
                url=args.url,
                flair_id=getattr(args, "flair", ""),
                nsfw=args.nsfw,
                spoiler=args.spoiler,
            ),
        )
        _output(
            {
                "success": True,
                "subreddit": args.subreddit,
                "title": title,
                "url": args.url,
                "status": "Published",
            }
        )
    finally:
        browser.close()


def cmd_submit_image(args: argparse.Namespace) -> None:
    from image_downloader import process_images

    from reddit.publish import submit_image_post
    from reddit.types import SubmitImageContent

    with open(args.title_file, encoding="utf-8") as f:
        title = f.read().strip()

    image_paths = process_images(args.images) if args.images else []
    if not image_paths:
        _output({"success": False, "error": "No valid images provided"}, exit_code=2)

    browser, page = _connect(args)
    try:
        submit_image_post(
            page,
            SubmitImageContent(
                subreddit=args.subreddit,
                title=title,
                image_paths=image_paths,
                flair_id=getattr(args, "flair", ""),
                nsfw=args.nsfw,
                spoiler=args.spoiler,
            ),
        )
        _output(
            {
                "success": True,
                "subreddit": args.subreddit,
                "title": title,
                "images": len(image_paths),
                "status": "Published",
            }
        )
    finally:
        browser.close()


# ─── Argument parsing ──────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reddit-cli",
        description="Reddit Automation CLI (Extension Bridge or Playwright)",
    )
    parser.add_argument(
        "--bridge-url",
        default="ws://localhost:9334",
        help="Bridge server WebSocket URL (default: ws://localhost:9334)",
    )
    parser.add_argument(
        "--backend",
        choices=["bridge", "playwright"],
        default="bridge",
        help="Backend to use (default: bridge)",
    )
    parser.add_argument(
        "--proxy-secret-id",
        help="BWS Secret ID for proxy string (format: http://user:pass@host:port)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode (Playwright only)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # check-login
    sub = subparsers.add_parser("check-login", help="Check login status")
    sub.set_defaults(func=cmd_check_login)

    # delete-cookies
    sub = subparsers.add_parser("delete-cookies", help="Log out")
    sub.set_defaults(func=cmd_delete_cookies)

    # home-feed
    sub = subparsers.add_parser("home-feed", help="Get home feed posts")
    sub.set_defaults(func=cmd_home_feed)

    # subreddit-feed
    sub = subparsers.add_parser("subreddit-feed", help="Get subreddit posts")
    sub.add_argument("--subreddit", required=True, help="Subreddit name (without r/)")
    sub.add_argument("--sort", default="hot", help="Sort: hot|new|top|rising (default: hot)")
    sub.set_defaults(func=cmd_subreddit_feed)

    # json-feed — fetch Reddit's .json API for bulk post extraction
    sub = subparsers.add_parser("json-feed", help="Fetch subreddit .json API (bulk posts with timestamps)")
    sub.add_argument("--subreddit", required=True, help="Subreddit name (without r/)")
    sub.add_argument("--sort", default="new", help="Sort: hot|new|top|rising (default: new)")
    sub.add_argument("--limit", type=int, default=100, help="Posts per page (max 100, default 100)")
    sub.add_argument("--after", default="", help="Pagination token (from previous response)")
    sub.add_argument("--max-pages", type=int, default=5, help="Max pages to fetch (default 5)")
    sub.set_defaults(func=cmd_json_feed)

    # json-url
    sub = subparsers.add_parser("json-url", help="Fetch any URL as JSON via bridge")
    sub.add_argument("--url", required=True, help="Full URL to fetch")
    sub.set_defaults(func=cmd_json_url)

    # search
    sub = subparsers.add_parser("search", help="Search Reddit")
    sub.add_argument("--query", required=True, help="Search query")
    sub.add_argument("--sort", help="Sort: relevance|hot|top|new|comments")
    sub.add_argument("--time", help="Time filter: hour|day|week|month|year|all")
    sub.set_defaults(func=cmd_search)

    # get-post-detail
    sub = subparsers.add_parser("get-post-detail", help="Get post detail")
    sub.add_argument("--post-url", required=True, help="Full post URL or permalink")
    sub.add_argument("--load-all-comments", action="store_true", help="Scroll to load all comments")
    sub.set_defaults(func=cmd_get_post_detail)

    # user-profile
    sub = subparsers.add_parser("user-profile", help="Get user profile")
    sub.add_argument("--username", required=True, help="Reddit username")
    sub.set_defaults(func=cmd_user_profile)

    # post-comment
    sub = subparsers.add_parser("post-comment", help="Post a comment")
    sub.add_argument("--post-url", required=True, help="Full post URL or permalink")
    sub.add_argument("--content", required=True, help="Comment text")
    sub.set_defaults(func=cmd_post_comment)

    # reply-comment
    sub = subparsers.add_parser("reply-comment", help="Reply to a comment")
    sub.add_argument("--post-url", required=True, help="Full post URL or permalink")
    sub.add_argument("--content", required=True, help="Reply text")
    sub.add_argument("--comment-id", help="Comment ID to reply to")
    sub.set_defaults(func=cmd_reply_comment)

    # upvote
    sub = subparsers.add_parser("upvote", help="Upvote a post")
    sub.add_argument("--post-url", required=True, help="Full post URL or permalink")
    sub.set_defaults(func=cmd_upvote)

    # downvote
    sub = subparsers.add_parser("downvote", help="Downvote a post")
    sub.add_argument("--post-url", required=True, help="Full post URL or permalink")
    sub.set_defaults(func=cmd_downvote)

    # save-post
    sub = subparsers.add_parser("save-post", help="Save or unsave a post")
    sub.add_argument("--post-url", required=True, help="Full post URL or permalink")
    sub.add_argument("--unsave", action="store_true", help="Unsave instead of save")
    sub.set_defaults(func=cmd_save_post)

    # subreddit-rules
    sub = subparsers.add_parser("subreddit-rules", help="Get subreddit rules and flairs")
    sub.add_argument("--subreddit", required=True, help="Subreddit name (without r/)")
    sub.set_defaults(func=cmd_subreddit_rules)

    # submit-text
    sub = subparsers.add_parser("submit-text", help="Submit a text post")
    sub.add_argument("--subreddit", required=True, help="Target subreddit (without r/)")
    sub.add_argument("--title-file", required=True, help="Title file path")
    sub.add_argument("--body-file", help="Body text file path")
    sub.add_argument("--flair", default="", help="Post flair text (matched by substring)")
    sub.add_argument("--nsfw", action="store_true", help="Mark as NSFW")
    sub.add_argument("--spoiler", action="store_true", help="Mark as spoiler")
    sub.set_defaults(func=cmd_submit_text)

    # submit-link
    sub = subparsers.add_parser("submit-link", help="Submit a link post")
    sub.add_argument("--subreddit", required=True, help="Target subreddit (without r/)")
    sub.add_argument("--title-file", required=True, help="Title file path")
    sub.add_argument("--url", required=True, help="Link URL")
    sub.add_argument("--flair", default="", help="Post flair text (matched by substring)")
    sub.add_argument("--nsfw", action="store_true", help="Mark as NSFW")
    sub.add_argument("--spoiler", action="store_true", help="Mark as spoiler")
    sub.set_defaults(func=cmd_submit_link)

    # submit-image
    sub = subparsers.add_parser("submit-image", help="Submit an image post")
    sub.add_argument("--subreddit", required=True, help="Target subreddit (without r/)")
    sub.add_argument("--title-file", required=True, help="Title file path")
    sub.add_argument("--images", nargs="+", required=True, help="Image file paths or URLs")
    sub.add_argument("--flair", default="", help="Post flair text (matched by substring)")
    sub.add_argument("--nsfw", action="store_true", help="Mark as NSFW")
    sub.add_argument("--spoiler", action="store_true", help="Mark as spoiler")
    sub.set_defaults(func=cmd_submit_image)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except Exception as e:
        logger.error("Execution failed: %s", e, exc_info=True)
        _output({"success": False, "error": str(e)}, exit_code=2)


if __name__ == "__main__":
    main()
