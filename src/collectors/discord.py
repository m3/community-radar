"""Discord collector — uses DiscordChatExporter for unlimited message exports"""

import subprocess
import json
import time
import os
from pathlib import Path
from datetime import datetime

from src.db.models import get_db, upsert_server, upsert_channel, upsert_user, log_export

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DCE_BIN = os.path.expanduser("~/tools/discordchatexporter/cli/DiscordChatExporter.Cli")
BWS_SECRET_ID = "70909217-9e02-452b-b933-b45f00c17fee"  # DISCORD_USER_TOKEN_M3


# Tracked servers and channels
SERVERS = {
    "203428322082816001": {
        "name": "Ripstone - Pure Pool Pro",
        "channels": {
            "1362333099089727488": "chat-pure-pool-pro",
            "1427915258147766303": "questions-and-suggestions-pure-pool-pro",
        }
    }
}


def get_token():
    """Get Discord token from BWS"""
    result = subprocess.run(
        ["bws", "secret", "get", BWS_SECRET_ID, "--output", "json"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    return data["value"]


def parse_dce_export(filepath):
    """Parse a DCE JSON export and return messages"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = []
    for msg in data:
        # DCE exports can be a list of messages or wrapped in a "messages" key
        if isinstance(data, dict) and "messages" in data:
            msg_list = data["messages"]
        else:
            msg_list = data

        for m in msg_list:
            author = m.get("author", {})
            if isinstance(author, dict):
                user_id = str(author.get("id", ""))
                display_name = author.get("nickname", author.get("name", ""))
                username = author.get("name", "")
            else:
                user_id = ""
                display_name = str(author)
                username = str(author)

            messages.append({
                "message_id": str(m.get("id", "")),
                "user_id": user_id,
                "display_name": display_name,
                "username": username,
                "content": m.get("content", ""),
                "timestamp": m.get("timestamp", ""),
                "reply_to": str(m.get("referencedMessageId", "")),
                "reactions": len(m.get("reactions", [])),
            })
        break  # Only process the first list
    return messages


def export_channel(server_id, server_name, channel_id, channel_name):
    """Export a single Discord channel incrementally"""
    db = get_db()

    # Get last export timestamp for this channel
    row = db.execute(
        "SELECT last_message_ts FROM channels WHERE id = ?", (channel_id,)
    ).fetchone()
    last_ts = row["last_message_ts"] if row else None

    # Ensure server + channel exist
    upsert_server(db, server_id, server_name)
    upsert_channel(db, channel_id, server_id, channel_name)

    # Build DCE command
    token = get_token()
    output_dir = DATA_DIR / "dce-exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / f"{channel_name}.json")

    cmd = [DCE_BIN, "export", "--token", token, "--channel", channel_id,
           "--format", "Json", "--output", output_path]

    if last_ts:
        # Only get messages after last export
        cmd.extend(["--after", last_ts[:10]])

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    duration = time.time() - t0

    if result.returncode != 0:
        print(f"  ✗ Export failed: {result.stderr[:200]}")
        log_export(db, server_id, channel_id, 0, 0, duration, "failed", result.stderr[:200])
        return

    # Parse and import messages
    if not os.path.exists(output_path):
        print(f"  ✗ No output file: {output_path}")
        return

    messages = parse_dce_export(output_path)
    print(f"  📥 {len(messages)} messages from #{channel_name}")

    # Find last message timestamp
    new_last_ts = last_ts
    new_users = 0
    for msg in messages:
        if msg["timestamp"] and (not new_last_ts or msg["timestamp"] > new_last_ts):
            new_last_ts = msg["timestamp"]

        # Upsert user
        if msg["user_id"]:
            existing = db.execute("SELECT id FROM users WHERE id = ?", (msg["user_id"],)).fetchone()
            if not existing:
                new_users += 1
            upsert_user(db, msg["user_id"],
                        display_name=msg["display_name"],
                        username=msg["username"])

    # Update channel state
    if new_last_ts:
        db.execute("UPDATE channels SET last_message_ts=?, message_count=message_count+?, updated_at=datetime('now') WHERE id=?",
                   (new_last_ts, len(messages), channel_id))

    # Update server totals
    db.execute("UPDATE servers SET total_messages=total_messages+?, last_scan=datetime('now') WHERE id=?",
               (len(messages), server_id))

    db.execute("UPDATE servers SET total_users=(SELECT COUNT(*) FROM users) WHERE id=?", (server_id,))

    log_export(db, server_id, channel_id, len(messages), new_users, duration)
    print(f"  ✅ {len(messages)} msgs, {new_users} new users, {duration:.1f}s")
    db.close()


def export_all_channels():
    """Export all configured Discord channels"""
    for server_id, server_info in SERVERS.items():
        print(f"\n📡 {server_info['name']}")
        for channel_id, channel_name in server_info["channels"].items():
            print(f"\n  📺 #{channel_name} ({channel_id})")
            export_channel(server_id, server_info["name"], channel_id, channel_name)


if __name__ == "__main__":
    export_all_channels()