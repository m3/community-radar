"""
Reddit collector v4 — uses Reddit's .json API for bulk post extraction
(with full timestamps, scores, pagination) and Chrome bridge for comment threads.
"""

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

DATA_DIR = Path(__file__).parent.parent.parent / CONFIG.get("data_dir", "data")


def run_cli(args, timeout=60, client_cfg=None):
    """Run reddit-skills CLI and return parsed output"""
    import subprocess
    reddit_skills_dir = get_config_value(client_cfg, "skills_dir")
    if not reddit_skills_dir:
        raise ValueError("reddit.skills_dir not found in config")
        
    full_args = [
        "uv", "run",
        "--directory", str(reddit_skills_dir),
        "python", "cli.py",
    ] + args

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


def fetch_posts_via_json(subreddit, sort="new", limit=100, max_pages=5, client_cfg=None):
    """Fetch posts using Reddit's .json API via the Chrome bridge CLI.
    
    This bypasses the DOM virtualization issue — the .json endpoint returns
    up to 100 posts per page with full metadata including timestamps.
    Uses the `json-feed` CLI command (cmd_json_feed) to go through the bridge.
    """
    all_posts = []
    after = ""

    for page_num in range(max_pages):
        result = run_cli([
            "json-feed",
            "--subreddit", subreddit,
            "--sort", sort,
            "--limit", str(limit),
            "--max-pages", "1",
            "--after", after,
        ], timeout=30, client_cfg=client_cfg)

        if not result:
            print(f"  ✗ No response from json-feed at page {page_num + 1}")
            break

        posts = result.get("posts", [])
        if not posts:
            print(f"  No more posts at page {page_num + 1}")
            break

        all_posts.extend(posts)
        after = result.get("after", "")
        if not after:
            print(f"  No more pages")
            break

        print(f"  Page {page_num + 1}: {len(posts)} posts (total: {len(all_posts)}, after={after[:20]}...)")
        time.sleep(1)  # Rate limit between pages

    return all_posts


def fetch_comments_for_post(permalink, client_cfg=None):
    """Fetch comments for a post using the Chrome bridge."""
    detail = run_cli(["get-post-detail", "--post-url", f"https://www.reddit.com{permalink}"], timeout=30, client_cfg=client_cfg)
    if detail:
        return detail.get("comments", [])
    return []


def export_subreddit(subreddit, sort="new", with_comments=True, comment_limit=20, max_post_pages=5, client_cfg=None):
    """Export posts + comments from a subreddit."""
    # Sanitize sort for use in channel ID and filename (remove ? and = from "top?t=month")
    sort_safe = sort.replace("?", "_").replace("=", "_").replace("&", "_")
    print(f"  📥 r/{subreddit} ({sort})...")

    # Fetch posts via .json API
    posts = fetch_posts_via_json(subreddit, sort, limit=100, max_pages=max_post_pages, client_cfg=client_cfg)
    if not posts:
        print(f"  ✗ No posts fetched")
        return 0, 0

    print(f"  Got {len(posts)} posts total")

    # Fetch comments for top posts
    total_comments = 0
    if with_comments:
        # Sort by comment count descending, take top N
        posts_with_comments = sorted(
            [p for p in posts if p["stats"]["numComments"] > 0],
            key=lambda p: p["stats"]["numComments"],
            reverse=True,
        )
        for post in posts_with_comments[:comment_limit]:
            time.sleep(1.5)  # Rate limit
            comments = fetch_comments_for_post(post["permalink"], client_cfg=client_cfg)
            if comments:
                post["comments"] = comments
                total_comments += len(comments)
                print(f"    💬 {post['id']}: {len(comments)} comments")

    # Save raw data
    out_dir = DATA_DIR / "reddit-exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{subreddit}-{sort_safe}-full.json"
    with open(out_path, "w") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {out_path.name}")

    # Store in DB
    db = get_db()
    server_id = f"reddit_{subreddit.lower()}"
    upsert_server(db, server_id, f"Reddit r/{subreddit}")

    channel_id = f"reddit_{subreddit.lower()}_{sort_safe}"
    upsert_channel(db, channel_id, server_id, f"reddit-{subreddit}-{sort}")

    new_users = 0
    msg_count = 0

    # Ensure placeholder user for deleted accounts
    upsert_user(db, "reddit_[deleted]", display_name="[deleted]", username="[deleted]", role="reddit_user")

    for post in posts:
        author_name = post["author"]["name"]
        if author_name and author_name != "[deleted]":
            uid = f"reddit_{author_name}"
            result = upsert_user(db, uid, display_name=author_name, username=author_name, role="reddit_user")
            if result == "new":
                new_users += 1
        else:
            uid = "reddit_[deleted]"

        created_utc = post.get("createdUtc", 0)
        created_date = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if created_utc else None

        content = f"{post['title']}\n\n{post.get('selftext', '')}" if post.get('selftext') else post['title']
        try:
            db.execute("""
                INSERT OR IGNORE INTO messages (message_id, channel_id, user_id, content, timestamp, reactions, platform)
                VALUES (?, ?, ?, ?, ?, ?, 'reddit')
            """, (
                post["id"],
                channel_id,
                uid,
                content,
                created_date,
                post["stats"]["score"],
            ))
        except Exception as e:
            print(f"  ✗ DB insert failed for post {post['id']}: {e}")
            print(f"    channel_id={channel_id}, user_id=reddit_{author_name}")
            raise
        msg_count += 1

        for comment in post.get("comments", []):
            c_author_name = comment.get("author", {}).get("name", "[deleted]")
            if c_author_name and c_author_name != "[deleted]":
                c_uid = f"reddit_{c_author_name}"
                result = upsert_user(db, c_uid, display_name=c_author_name, username=c_author_name, role="reddit_user")
                if result == "new":
                    new_users += 1
            else:
                c_uid = "reddit_[deleted]"

            c_created_utc = comment.get("createdUtc", 0)
            c_created_date = datetime.fromtimestamp(c_created_utc, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if c_created_utc else None

            try:
                db.execute("""
                    INSERT OR IGNORE INTO messages (message_id, channel_id, user_id, content, timestamp, reply_to, reactions, platform)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'reddit')
                """, (
                    comment.get("id", ""),
                    channel_id,
                    c_uid,
                    comment.get("body", ""),
                    c_created_date,
                    post["id"],
                    comment.get("score", 0),
                ))
            except Exception as e:
                print(f"  ✗ DB insert failed for comment {comment.get('id', '')}: {e}")
                print(f"    channel_id={channel_id}, user_id={c_uid}")
                raise
            msg_count += 1

    db.execute("UPDATE channels SET message_count=(SELECT COUNT(*) FROM messages WHERE channel_id=?), last_scan=datetime('now') WHERE id=?",
               (channel_id, channel_id))
    db.execute("UPDATE servers SET total_messages=total_messages+?, last_scan=datetime('now') WHERE id=?",
               (msg_count, server_id))

    log_export(db, server_id, channel_id, msg_count, new_users, 0, "imported")
    db.commit()
    db.close()

    print(f"  ✅ {msg_count} messages ({total_comments} comments), {new_users} new users")
    return msg_count, total_comments


def export_all(client_cfg=None):
    """Export all configured subreddits"""
    total_msgs = 0
    total_comments = 0
    subreddits = get_config_value(client_cfg, "subreddits", {})
    
    for sub, config in subreddits.items():
        print(f"\n📡 r/{sub}")
        for sort in config["sorts"]:
            msgs, comments = export_subreddit(sub, sort, max_post_pages=config.get("max_pages", 3), client_cfg=client_cfg)
            total_msgs += msgs
            total_comments += comments
            time.sleep(2)
    print(f"\n✅ Total: {total_msgs} messages ({total_comments} comments)")
    return total_msgs


if __name__ == "__main__":
    export_all()
