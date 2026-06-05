"""Import existing research data from cuebot project into CommunityRadar DB"""

import json
from pathlib import Path
from src.db.models import get_db, upsert_server, upsert_channel, upsert_user, log_export

CUEBOT_RESEARCH = Path("/Users/mathias/Development/DiscordBot/cuebot/docs/research")


def find_dce_dir():
    """Find DCE exports directory -- check CommunityRadar data dir first, then cuebot"""
    data_dir = Path(__file__).parent.parent.parent / "data" / "dce-exports"
    if data_dir.exists():
        return data_dir
    cuebot_dir = CUEBOT_RESEARCH / "dce-exports"
    if cuebot_dir.exists():
        return cuebot_dir
    return None


def import_dce_exports():
    """Import from DCE-exported JSON files"""
    db = get_db()

    dce_dir = find_dce_dir()
    if not dce_dir:
        print("No DCE exports directory found")
        return

    total_msgs = 0

    for f in sorted(dce_dir.glob("*.json")):
        print(f"  Importing {f.name}...")
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        if isinstance(data, dict) and "messages" in data:
            msg_list = data["messages"]
        elif isinstance(data, list):
            msg_list = data
        else:
            print(f"  ✗ Unknown format: {f.name}")
            continue

        # Parse channel info from filename AND from export metadata
        fname = f.stem
        channel_id = None
        server_id = None
        channel_name = fname
        server_name = "Unknown Server"

        # DCE exports contain channel/guild metadata at the top level
        if isinstance(data, dict):
            ch_meta = data.get("channel", {})
            g_meta = data.get("guild", {})
            if ch_meta.get("id"):
                channel_id = str(ch_meta["id"])
                channel_name = ch_meta.get("name", fname)
            if g_meta.get("id"):
                server_id = str(g_meta["id"])
                server_name = g_meta.get("name", "Unknown Server")

        # Fallback: parse from filename if metadata didn't have it
        if not channel_id and "[" in fname and "]" in fname:
            channel_id = fname.split("[")[-1].rstrip("]")

        if channel_id and not channel_name:
            base = fname.split(f"[{channel_id}]")[0].strip().rstrip(" -").strip()
            parts = base.split(" - ")
            channel_name = parts[-1].strip() if len(parts) > 1 else base

        # Determine server from filename if not in metadata
        if not server_id:
            if "Ripstone" in fname:
                server_id = "203428322082816001"
                server_name = "Ripstone - Pure Pool Pro"
            else:
                server_id = "unknown"
                server_name = "Unknown Server"

        if not channel_id:
            channel_id = "unknown"

        upsert_server(db, server_id, server_name)
        upsert_channel(db, channel_id, server_id, channel_name)

        # Find the last timestamp and process users
        last_ts = None
        new_users = 0
        message_rows = []
        seen_msg_ids = set()
        for msg in msg_list:
            msg_id = str(msg.get("id", ""))
            if msg_id in seen_msg_ids:
                continue
            seen_msg_ids.add(msg_id)

            author = msg.get("author", {})
            if isinstance(author, dict):
                user_id = str(author.get("id", ""))
                display_name = author.get("nickname", author.get("name", ""))
                username = author.get("name", "")
            else:
                user_id = ""
                display_name = str(author)
                username = str(author)

            ts = msg.get("timestamp", "")
            if ts and (not last_ts or ts > last_ts):
                last_ts = ts

            if user_id:
                existing = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
                if not existing:
                    upsert_user(db, user_id,
                                display_name=display_name,
                                username=username,
                                first_seen=ts[:10] if ts else None,
                                last_seen=ts[:10] if ts else None)
                    new_users += 1

            # Collect message row for batch insert
            content = msg.get("content", "")
            reply_to = str(msg.get("referencedMessageId", ""))
            reactions = len(msg.get("reactions", []))
            message_rows.append((msg_id, channel_id, user_id, content, ts, reply_to, reactions))

        # Batch insert messages
        batch_size = 500
        inserted_msgs = 0
        for i in range(0, len(message_rows), batch_size):
            batch = message_rows[i:i+batch_size]
            db.executemany("""
                INSERT OR IGNORE INTO messages
                    (message_id, channel_id, user_id, content, timestamp, reply_to, reactions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, batch)
            inserted_msgs += len(batch)

        # Update channel
        msg_count = inserted_msgs
        db.execute("UPDATE channels SET last_message_ts=?, message_count=?, updated_at=datetime('now') WHERE id=?",
                   (last_ts, msg_count, channel_id))

        # Update server totals
        total = db.execute("SELECT COALESCE(SUM(message_count),0) as t FROM channels WHERE server_id=?",
                          (server_id,)).fetchone()["t"]
        db.execute("UPDATE servers SET last_scan=datetime('now'), total_messages=?, total_users=(SELECT COUNT(*) FROM users) WHERE id=?",
                   (total, server_id))

        log_export(db, server_id, channel_id, msg_count, new_users, 0, "imported")
        total_msgs += msg_count

        print(f"    📥 {msg_count} msgs, {new_users} new users")

    print(f"\n  Total: {total_msgs} messages imported")
    db.commit()
    db.close()


def import_user_profiles():
    """Import user profiles from existing JSON"""
    db = get_db()

    profile_file = CUEBOT_RESEARCH / "discord-community-profiles.json"
    if not profile_file.exists():
        print("No user profiles file found")
        return

    print(f"  Importing user profiles from {profile_file.name}...")
    with open(profile_file, "r") as f:
        data = json.load(f)

    users = data.get("users", [])
    imported = 0
    for u in users:
        user_id = str(u.get("user_id", ""))
        if not user_id:
            continue
        upsert_user(db, user_id,
                    display_name=u.get("display_name"),
                    username=u.get("username"),
                    role=u.get("role", "unknown"),
                    messages=u.get("messages", 0),
                    reactions_given=u.get("reactions_given", 0),
                    reactions_received=u.get("reactions_received", 0),
                    first_seen=u.get("first_seen"),
                    last_seen=u.get("last_seen"))
        imported += 1

    print(f"    {imported} user profiles imported")
    db.commit()
    db.close()


def import_cross_references():
    """Import Reddit↔Discord cross-references from existing JSON"""
    db = get_db()

    xref_file = CUEBOT_RESEARCH / "reddit-discord-crossref.json"
    if not xref_file.exists():
        print("No cross-reference file found")
        return

    print(f"  Importing cross-references from {xref_file.name}...")
    with open(xref_file, "r") as f:
        data = json.load(f)

    matched = data.get("matched", [])
    unmatched = data.get("unmatched_reddit", [])

    inserted = 0
    for m in matched:
        reddit_name = m.get("reddit_name", "")
        discord_name = m.get("discord_display_name", "")
        match_type = m.get("match_type", "partial")

        # Find the Discord user ID by display name
        row = db.execute(
            "SELECT id FROM users WHERE display_name = ? OR username = ?",
            (discord_name, discord_name)
        ).fetchone()
        user_id = row["id"] if row else f"unknown_{discord_name}"

        db.execute("""
            INSERT OR IGNORE INTO cross_references (user_id, platform1, username1, platform2, username2, match_type, confidence)
            VALUES (?, 'reddit', ?, 'discord', ?, ?, ?)
        """, (user_id, reddit_name, discord_name, match_type, 0.8 if match_type == "exact" else 0.5))
        inserted += 1

    # Also store unmatched Reddit-only users as cross-ref entries with null discord side
    for u in unmatched:
        reddit_name = u.get("reddit_name", "")
        db.execute("""
            INSERT OR IGNORE INTO cross_references (user_id, platform1, username1, platform2, username2, match_type, confidence)
            VALUES (?, 'reddit', ?, 'discord', NULL, 'unmatched', 0.0)
        """, (f"reddit_{reddit_name}", reddit_name))
        inserted += 1

    print(f"    {inserted} cross-references imported ({len(matched)} matched, {len(unmatched)} reddit-only)")
    db.commit()
    db.close()


def extract_topics():
    """Extract topics from message content using keyword matching"""
    db = get_db()

    print("  Extracting topics from message content...")

    # Define topic keywords
    TOPIC_KEYWORDS = {
        # Bugs & Issues
        "bug": "bug", "crash": "bug", "glitch": "bug", "broken": "bug",
        "fix": "bug", "issue": "bug", "problem": "bug", "error": "bug",
        # Features
        "feature": "feature_request", "add": "feature_request", "wish": "feature_request",
        "would be nice": "feature_request", "suggestion": "feature_request",
        "request": "feature_request", "please add": "feature_request",
        # Gameplay
        "gameplay": "gameplay", "physics": "gameplay", "mechanics": "gameplay",
        "controls": "gameplay", "aiming": "gameplay", "shot": "gameplay",
        # Multiplayer
        "multiplayer": "multiplayer", "online": "multiplayer", "matchmaking": "multiplayer",
        "lobby": "multiplayer", "ranked": "multiplayer", "tournament": "multiplayer",
        # Cross-play
        "crossplay": "cross_play", "cross-play": "cross_play", "cross play": "cross_play",
        "steam": "cross_play", "playstation": "cross_play", "xbox": "cross_play",
        "switch": "cross_play", "ps5": "cross_play", "ps4": "cross_play",
        # Store/Pricing
        "price": "pricing", "cost": "pricing", "buy": "pricing", "purchase": "pricing",
        "steam sale": "pricing", "discount": "pricing", "worth": "pricing",
        # General
        "update": "update", "patch": "update", "version": "update",
        "dev": "development", "developer": "development", "roadmap": "development",
        "release": "release", "launch": "release", "early access": "release",
    }

    # Scan all messages for topic keywords
    messages = db.execute("SELECT content, timestamp FROM messages WHERE content != ''").fetchall()

    topic_counts = {}
    topic_first_seen = {}
    topic_last_seen = {}

    for msg in messages:
        content = (msg["content"] or "").lower()
        ts = msg["timestamp"] or ""
        for keyword, category in TOPIC_KEYWORDS.items():
            if keyword in content:
                topic_counts[keyword] = topic_counts.get(keyword, 0) + 1
                if keyword not in topic_first_seen or (ts and ts < topic_first_seen[keyword]):
                    topic_first_seen[keyword] = ts
                if keyword not in topic_last_seen or (ts and ts > topic_last_seen[keyword]):
                    topic_last_seen[keyword] = ts

    # Upsert topics
    inserted = 0
    for name, count in topic_counts.items():
        category = TOPIC_KEYWORDS[name]
        db.execute("""
            INSERT INTO topics (name, category, mention_count, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                mention_count = mention_count + excluded.mention_count,
                last_seen = MAX(last_seen, excluded.last_seen)
        """, (name, category, count, topic_first_seen.get(name), topic_last_seen.get(name)))
        inserted += 1

    print(f"    {inserted} topics extracted from {len(messages)} messages")
    db.commit()
    db.close()


def import_all():
    """Import all available data"""
    print("Importing existing data into CommunityRadar DB...\n")

    print("[1/4] DCE exports:")
    import_dce_exports()

    print(f"\n[2/4] User profiles:")
    import_user_profiles()

    print(f"\n[3/4] Cross-references:")
    import_cross_references()

    print(f"\n[4/4] Topic extraction:")
    extract_topics()

    print("\nDone. Run 'python src/main.py status' to verify.")


if __name__ == "__main__":
    import_all()