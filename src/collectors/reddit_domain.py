import json
import time
from datetime import datetime, timezone
from pathlib import Path
import yaml
from src.db.models import get_db, upsert_server, upsert_channel, upsert_user, log_export

# Load config
CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

def get_config_value(client_cfg, key, default=None):
    """Helper to get config value from client_cfg or global CONFIG"""
    # Check client-specific reddit section first
    if client_cfg and "reddit" in client_cfg:
        if key in client_cfg["reddit"]:
            return client_cfg["reddit"][key]
    
    # Check global reddit_global section
    if "reddit_global" in CONFIG:
        if key in CONFIG["reddit_global"]:
            return CONFIG["reddit_global"][key]
            
    # Fallback to old global reddit section if it exists
    if "reddit" in CONFIG:
        if key in CONFIG["reddit"]:
            return CONFIG["reddit"][key]
            
    return default

def build_domain_json_url(domain: str, sort: str = "new", limit: int = 100, after: str = None) -> str:
    url = f"https://www.reddit.com/domain/{domain}/{sort}.json?limit={limit}"
    if after:
        url += f"&after={after}"
    return url

def run_cli(args, timeout=60, client_cfg=None):
    """Run reddit-skills CLI and return parsed output"""
    import subprocess
    reddit_skills_dir = get_config_value(client_cfg, "skills_dir")
    if not reddit_skills_dir:
        # Fallback to old path if not in global/client config
        reddit_skills_dir = Path(__file__).parent.parent.parent / "scripts"
        
    backend = get_config_value(client_cfg, "backend")
    proxy_secret_id = get_config_value(client_cfg, "proxy_secret_id")
    headless = get_config_value(client_cfg, "headless", True)

    full_args = [
        "uv", "run",
        "--directory", str(reddit_skills_dir),
        "python", "cli.py",
    ]
    
    if backend:
        full_args += ["--backend", backend]
    if proxy_secret_id:
        full_args += ["--proxy-secret-id", proxy_secret_id]
    if not headless:
        full_args += ["--headed"]
        
    full_args += args

    result = subprocess.run(full_args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        print(f"  ✗ reddit-skills error: {result.stderr[:200]}")
        return None

    try:
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except json.JSONDecodeError:
        print(f"  ⚠ Could not parse output: {result.stdout[:200]}")
        return None

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

def export_domain(domain, sort="new", max_pages=3, client_cfg=None):
    """Fetch and store domain posts in DB."""
    print(f"  📥 domain/{domain} ({sort})...")
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
    domain_cfg = get_config_value(client_cfg, "domain_monitoring", {})
    if not domain_cfg.get("enabled", False):
        print("  ⚠ Domain monitoring is disabled for this client")
        return

    domains = domain_cfg.get("domains", [])
    sort = domain_cfg.get("sort", "new")
    max_pages = domain_cfg.get("max_pages", 3)
    
    total_msgs = 0
    for domain in domains:
        total_msgs += export_domain(domain, sort=sort, max_pages=max_pages, client_cfg=client_cfg)
    print(f"\n✅ Total Domain Messages: {total_msgs}")

if __name__ == "__main__":
    export_all_domains()
