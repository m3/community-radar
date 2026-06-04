"""Import existing research data from cuebot project into CommunityRadar DB"""

import json
import os
from pathlib import Path
from datetime import datetime

from src.db.models import get_db, upsert_server, upsert_channel, upsert_user, log_export

CUEBOT_RESEARCH = Path(os.path.expanduser("~/Development/DiscordBot/cuebot/docs/research"))


def import_dce_exports():
    """Import from DCE-exported JSON files"""
    db = get_db()

    dce_dir = CUEBOT_RESEARCH / "dce-exports"
    if not dce_dir.exists():
        print("No DCE exports directory found")
        return

    total_msgs = 0
    total_new_users = 0

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

        # Extract channel name from filename
        fname = f.stem
        # Parse out server and channel info
        channel_id = None
        server_id = None
        channel_name = fname

        if "[" in fname and "]" in fname:
            channel_id = fname.split("[")[-1].rstrip("]")
            # Try to get channel name from before [id]
            raw_name = fname.split("[")[0].strip().rstrip("- ").strip()
            # Extract the actual channel name (last part after space)
            parts = raw_name.split(" - ")
            if len(parts) >= 2:
                channel_name = parts[1].strip()

        # Determine server
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

        # Find the last timestamp
        last_ts = None
        for msg in msg_list:
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

        # Update channel
        chan_row = db.execute("SELECT message_count FROM channels WHERE id = ?", (channel_id,)).fetchone()
        msg_count = len(msg_list)
        if chan_row and chan_row["message_count"] < msg_count:
            db.execute("UPDATE channels SET last_message_ts=?, message_count=?, updated_at=datetime('now') WHERE id=?",
                       (last_ts, msg_count, channel_id))

        db.execute("UPDATE servers SET last_scan=datetime('now'), total_messages=total_messages+? WHERE id=?",
                   (msg_count, server_id))
        db.execute("UPDATE servers SET total_users=(SELECT COUNT(*) FROM users) WHERE id=?", (server_id,))

        log_export(db, server_id, channel_id, msg_count, 0, 0, "imported")
        total_msgs += msg_count

        # Print summary
        server_total = db.execute("SELECT total_messages, total_users FROM servers WHERE id=?", (server_id,)).fetchone()
        print(f"    📥 {msg_count} msgs imported")
        print(f"    Server: {server_total['total_messages']} msgs, {server_total['total_users']} users")

    print(f"\n  Total: {total_msgs} messages imported across {len(list(dce_dir.glob('*.json')))} files")
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
    db.close()


def import_all():
    """Import all available data"""
    print("Importing existing data into CommunityRadar DB...\n")

    print("[1/2] DCE exports:")
    import_dce_exports()

    print(f"\n[2/2] User profiles:")
    import_user_profiles()

    print("\nDone. Run 'python src/main.py status' to verify.")


if __name__ == "__main__":
    import_all()