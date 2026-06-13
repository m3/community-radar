"""Discord collector — uses DiscordChatExporter for unlimited message exports"""

import subprocess
import json
import time
from pathlib import Path

from src.db.models import get_db, upsert_server, upsert_channel, upsert_user, log_export
from src.collectors.utils import get_config_value, CONFIG

DATA_DIR = Path(__file__).parent.parent.parent / CONFIG.get("data_dir", "data")

def get_token(client_cfg=None):
    """Get Discord token from BWS"""
    bws_secret_id = get_config_value(client_cfg, "discord", "bws_secret_id")
    if not bws_secret_id:
        raise ValueError("discord.bws_secret_id not found in config")

    result = subprocess.run(
        ["bws", "secret", "get", bws_secret_id, "--output", "json"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    return data["value"]


def parse_dce_export(filepath):
    """Parse a DCE JSON export and return messages list"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # DCE wraps messages in a dict with guild/channel metadata
    msg_list = data.get("messages", data) if isinstance(data, dict) else data
    if not isinstance(msg_list, list):
        print(f"  ⚠ Unexpected format in {filepath}")
        return []

    messages = []
    for m in msg_list:
        author = m.get("author", {})
        if isinstance(author, dict):
            user_id = str(author.get("id", ""))
            display_name = author.get("nick", author.get("globalName", author.get("name", "")))
            username = author.get("name", "")
        else:
            user_id = str(author) if author else ""
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
    return messages


def process_export_file(channel_id, channel_name, db, server_id):
    """Parse a DCE export file and update DB"""
    output_dir = DATA_DIR / "dce-exports"
    output_path = output_dir / f"{channel_name}.json"

    if not output_path.exists():
        print(f"  ✗ No export file found for #{channel_name}")
        return 0, 0

    messages = parse_dce_export(str(output_path))
    if not messages:
        return 0, 0

    print(f"  📥 {len(messages)} new messages from #{channel_name}")

    new_last_ts = None
    new_users = 0
    message_rows = []
    for msg in messages:
        ts = msg["timestamp"]
        if ts and (not new_last_ts or ts > new_last_ts):
            new_last_ts = ts

        if msg["user_id"]:
            existing = db.execute("SELECT id FROM users WHERE id = ?", (msg["user_id"],)).fetchone()
            if not existing:
                new_users += 1
            upsert_user(db, msg["user_id"],
                        display_name=msg["display_name"],
                        username=msg["username"])

        message_rows.append((
            msg["message_id"], channel_id, msg["user_id"],
            msg["content"], msg["timestamp"], msg["reply_to"], msg["reactions"]
        ))

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

    # Update channel state
    msg_count = inserted_msgs
    if new_last_ts:
        db.execute("UPDATE channels SET last_message_ts=?, message_count=message_count+?, updated_at=datetime('now') WHERE id=?",
                   (new_last_ts, msg_count, channel_id))

    # Update server totals
    db.execute("UPDATE servers SET total_messages=total_messages+?, last_scan=datetime('now') WHERE id=?",
               (msg_count, server_id))
    db.execute("UPDATE servers SET total_users=(SELECT COUNT(*) FROM users) WHERE id=?", (server_id,))

    return msg_count, new_users


def export_channel(server_id, server_name, channel_id, channel_name, client_cfg=None):
    """Export a single Discord channel incrementally"""
    client_name = client_cfg.get("_client_name") if client_cfg else None
    db = get_db(client_name=client_name)

    # Ensure server + channel exist
    upsert_server(db, server_id, server_name)
    upsert_channel(db, channel_id, server_id, channel_name)

    # Get last export timestamp
    row = db.execute(
        "SELECT last_message_ts FROM channels WHERE id = ?", (channel_id,)
    ).fetchone()
    last_ts = row["last_message_ts"] if row else None

    # Build DCE command
    token = get_token(client_cfg)
    dce_bin = get_config_value(client_cfg, "discord", "dce_bin")
    if not dce_bin:
        raise ValueError("discord.dce_bin not found in config")

    output_dir = DATA_DIR / "dce-exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / f"{channel_name}.json")

    cmd = [dce_bin, "export", "--token", token, "--channel", channel_id,
           "--format", "Json", "--output", output_path]

    if last_ts:
        # Only get messages after last export
        cmd.extend(["--after", last_ts[:10]])
        print(f"  Incremental export since {last_ts[:10]}")
    else:
        print(f"  Full export (no prior scan data)")

    t0 = time.time()
    dce_timeout = get_config_value(client_cfg, "discord", "dce_timeout", 1200)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=dce_timeout)
    duration = time.time() - t0

    if result.returncode != 0:
        print(f"  ✗ Export failed: {result.stderr[:200]}")
        log_export(db, server_id, channel_id, 0, 0, duration, "failed", result.stderr[:200])
        db.commit()
        db.close()
        return

    # Process the exported file
    msg_count, new_users = process_export_file(channel_id, channel_name, db, server_id)
    log_export(db, server_id, channel_id, msg_count, new_users, duration)

    status = "✅" if msg_count > 0 else "⏭"
    print(f"  {status} {msg_count} msgs, {new_users} new users, {duration:.1f}s")
    db.commit()
    db.close()


def export_all_channels(client_cfg=None):
    """Export all configured Discord channels"""
    servers = get_config_value(client_cfg, "discord", "servers", {})
    
    for server_id, server_info in servers.items():
        print(f"\n📡 {server_info['name']}")
        for channel_id, channel_name in server_info["channels"].items():
            print(f"\n  📺 #{channel_name} ({channel_id})")
            export_channel(server_id, server_info["name"], channel_id, channel_name, client_cfg=client_cfg)


if __name__ == "__main__":
    export_all_channels()
