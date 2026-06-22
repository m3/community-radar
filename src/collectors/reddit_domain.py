import json
import time
from datetime import datetime, timezone
from pathlib import Path

from src.db.models import get_db, upsert_server, upsert_channel, upsert_user, log_export
from src.collectors.utils import get_config_value, run_cli


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
        import sys
        print(f"Error fetching proxy from BWS: {e}", file=sys.stderr)
        return None


def build_domain_json_url(domain: str, sort: str = "new", limit: int = 100, after: str = None) -> str:
    url = f"https://www.reddit.com/domain/{domain}/{sort}.json?limit={limit}"
    if after:
        url += f"&after={after}"
    return url


def fetch_domain_posts_via_json(domain, sort="new", limit=100, max_pages=3, client_cfg=None):
    """Fetch posts for a domain using the Chrome bridge CLI."""
    all_posts = []
    after = ""

    for page_num in range(max_pages):
        result = run_cli([
            "json-url",
            "--url", build_domain_json_url(domain, sort, limit, after if after else None),
        ], timeout=30, client_cfg=client_cfg)

        if not result:
            print(f"  ✗ No response from json-url at page {page_num + 1}")
            break

        # result is the raw Reddit JSON
        data = result
        children = data.get("data", {}).get("children", [])
        if not children:
            print(f"  No more posts at page {page_num + 1}")
            break

        posts = []
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
            posts.append(post)

        all_posts.extend(posts)
        after = data.get("data", {}).get("after")
        
        print(f"  Page {page_num + 1}: {len(posts)} posts (total: {len(all_posts)})")
        if not after:
            break
        
        time.sleep(1)

    return all_posts


def fetch_domain_posts_via_json_in_process(page, domain, sort="new", limit=100, max_pages=3):
    """Fetch posts for a domain in-process via PlaywrightPage."""
    all_posts = []
    after = ""

    for page_num in range(max_pages):
        url = build_domain_json_url(domain, sort, limit, after if after else None)
        print(f"    Navigating to {url}...")
        page.navigate(url)
        page.wait_for_load()
        time.sleep(1)

        text = page.evaluate("document.body.innerText")
        if not text:
            break

        try:
            data = json.loads(text.strip())
        except Exception:
            try:
                pre_text = page.evaluate("document.querySelector('pre')?.innerText")
                if pre_text:
                    data = json.loads(pre_text.strip())
                else:
                    break
            except Exception:
                break

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        posts = []
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
            posts.append(post)

        all_posts.extend(posts)
        after = data.get("data", {}).get("after")
        print(f"    Page {page_num + 1}: {len(posts)} posts (total: {len(all_posts)})")
        if not after:
            break

        time.sleep(1.5)

    return all_posts


def export_domain(domain, sort="new", max_pages=3, client_cfg=None, page=None):
    """Fetch and store domain posts in DB."""
    print(f"  📥 domain/{domain} ({sort})...")
    
    used_in_process = False
    if page:
        print("  [In-Process] Fetching domain posts via Playwright...")
        try:
            posts = fetch_domain_posts_via_json_in_process(
                page, domain, sort, limit=100, max_pages=max_pages
            )
            used_in_process = True
        except Exception as e:
            print(f"  ⚠ In-process domain fetching failed: {e}. Falling back to CLI...")
            posts = []

    if not used_in_process:
        # Fallback to CLI subprocess
        posts = fetch_domain_posts_via_json(domain, sort, limit=100, max_pages=max_pages, client_cfg=client_cfg)
    
    if not posts:
        print(f"  ✗ No posts fetched")
        return 0

    client_name = client_cfg.get("_client_name") if client_cfg else None
    db = get_db(client_name=client_name)
    server_id = "reddit_domain_monitoring"
    upsert_server(db, server_id, "Reddit Domain Monitoring")

    channel_id = f"domain:{domain}"
    upsert_channel(db, channel_id, server_id, f"domain:{domain}")

    # Upsert placeholder deleted user
    upsert_user(db, "reddit_[deleted]", display_name="[deleted]", username="[deleted]", role="reddit_user")

    new_users = 0
    msg_count = 0
    for post in posts:
        author = post.get("author", {}).get("name", "[deleted]")
        uid = f"reddit_{author}" if author != "[deleted]" else "reddit_[deleted]"
        if author != "[deleted]":
            if upsert_user(db, uid, display_name=author, username=author, role="reddit_user") == "new":
                new_users += 1
        
        created_utc = post.get("createdUtc", 0)
        created_date = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if created_utc else None
        
        content = f"{post['title']}\n\n{post.get('selftext', '')}" if post.get('selftext') else post['title']
        content += f"\n\nURL: {post.get('url', '')}"
        
        db.execute("""
            INSERT OR IGNORE INTO messages (message_id, channel_id, user_id, content, timestamp, reactions, platform)
            VALUES (?, ?, ?, ?, ?, ?, 'reddit')
        """, (
            post["id"], channel_id, uid, content, created_date, post["stats"]["score"]
        ))
        msg_count += 1

    db.execute("UPDATE channels SET message_count=(SELECT COUNT(*) FROM messages WHERE channel_id=?), last_scan=datetime('now') WHERE id=?", (channel_id, channel_id))
    db.execute("UPDATE servers SET total_messages=total_messages+?, last_scan=datetime('now') WHERE id=?", (msg_count, server_id))
    
    log_export(db, server_id, channel_id, msg_count, new_users, 0, "imported")
    db.commit()
    db.close()
    
    print(f"  ✅ {msg_count} messages, {new_users} new users")
    return msg_count


def export_all_domains(client_cfg=None):
    domain_cfg = get_config_value(client_cfg, "reddit", "domain_monitoring", {})
    if not domain_cfg.get("enabled", False):
        print("  ⚠ Domain monitoring is disabled for this client")
        return

    domains = domain_cfg.get("domains", [])
    sort = domain_cfg.get("sort", "new")
    max_pages = domain_cfg.get("max_pages", 3)
    
    total_msgs = 0
    backend = get_config_value(client_cfg, "reddit", "backend", "playwright")
    
    if backend == "playwright":
        try:
            import sys
            from pathlib import Path
            current_dir = Path(__file__).parent
            scripts_dir = current_dir.parent.parent / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.append(str(scripts_dir))

            from src.collectors.browser_manager import PlaywrightManager
            from reddit.playwright_backend import PlaywrightPage

            headless = get_config_value(client_cfg, "reddit", "headless", True)
            proxy_secret_id = get_config_value(client_cfg, "reddit", "proxy_secret_id")
            proxy = get_proxy_from_bws(proxy_secret_id) if proxy_secret_id else None
            proxy_cfg = {"server": proxy} if proxy else None

            # Get manager and start
            manager = PlaywrightManager.get_instance()
            manager.start(headless=headless)
            context = manager.get_context(proxy_cfg=proxy_cfg)
            page = PlaywrightPage(headless=headless, proxy=proxy, context=context)

            try:
                for domain in domains:
                    total_msgs += export_domain(
                        domain, sort=sort, max_pages=max_pages, client_cfg=client_cfg, page=page
                    )
            finally:
                try:
                    page.close()
                except Exception:
                    pass
                try:
                    context.close()
                except Exception:
                    pass
                try:
                    manager.stop()
                except Exception:
                    pass
        except Exception as e:
            print(f"  ⚠ In-process domain execution failed: {e}. Falling back to CLI subprocess...")
            total_msgs = 0
            for domain in domains:
                total_msgs += export_domain(domain, sort=sort, max_pages=max_pages, client_cfg=client_cfg)
    else:
        for domain in domains:
            total_msgs += export_domain(domain, sort=sort, max_pages=max_pages, client_cfg=client_cfg)
            
    print(f"\n✅ Total Domain Messages: {total_msgs}")


if __name__ == "__main__":
    export_all_domains()
