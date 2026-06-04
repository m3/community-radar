"""CommunityRadar — CLI entry point"""

import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Ensure we can import from src
sys.path.insert(0, str(ROOT))

def status():
    """Show current scan status"""
    from src.db.models import get_db
    db = get_db()
    row = db.execute("SELECT id, name, last_scan, total_messages, total_users FROM servers ORDER BY id").fetchall()
    if not row:
        print("No servers scanned yet.")
        return
    for r in row:
        print(f"  {r['name']}")
        print(f"    Last scan: {r['last_scan'] or 'never'}")
        print(f"    Messages:  {r['total_messages']}")
        print(f"    Users:     {r['total_users']}")
        chans = db.execute(
            "SELECT id, name, last_scan, message_count FROM channels WHERE server_id = ? ORDER BY id",
            (r['id'],)
        ).fetchall()
        for c in chans:
            print(f"    📺 #{c['name']}: {c['message_count']} msgs (last scan: {c['last_scan'] or 'never'})")
    print()

    # Messages in DB
    msgs = db.execute("SELECT COUNT(*) as c FROM messages").fetchone()
    print(f"Messages stored: {msgs['c']}")

    # Cross-refs
    xrefs = db.execute("SELECT COUNT(*) as c FROM cross_references").fetchone()
    matched = db.execute("SELECT COUNT(*) as c FROM cross_references WHERE match_type != 'unmatched'").fetchone()
    print(f"Cross-references: {xrefs['c']} ({matched['c']} matched)")

    # Topics
    topics = db.execute("SELECT COUNT(*) as c FROM topics").fetchone()
    print(f"Topics extracted: {topics['c']}")

    # Users
    users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()
    print(f"Total unique users profiled: {users['c']}")
    db.close()


def topics():
    """Show top topics from message analysis"""
    from src.db.models import get_db
    db = get_db()
    rows = db.execute("""
        SELECT name, category, mention_count, first_seen, last_seen
        FROM topics ORDER BY mention_count DESC LIMIT 30
    """).fetchall()
    if not rows:
        print("No topics extracted yet. Run 'python src/main.py import' first.")
        return
    print(f"Top {len(rows)} topics:\n")
    for r in rows:
        print(f"  {r['name']:20s} ({r['category']:15s}) {r['mention_count']:4d} mentions  [{r['first_seen'][:10] if r['first_seen'] else '?'} → {r['last_seen'][:10] if r['last_seen'] else '?'}]")
    db.close()


def xref():
    """Show cross-platform user matches"""
    from src.db.models import get_db
    db = get_db()
    rows = db.execute("""
        SELECT platform1, username1, platform2, username2, match_type, confidence
        FROM cross_references ORDER BY confidence DESC
    """).fetchall()
    if not rows:
        print("No cross-references yet. Run 'python src/main.py import' first.")
        return
    print(f"Cross-platform matches ({len(rows)}):\n")
    for r in rows:
        u2 = r['username2'] or '(unmatched)'
        print(f"  {r['username1']:25s} ↔ {u2:25s}  [{r['match_type']}] (conf: {r['confidence']:.1f})")
    db.close()


def export():
    """Run Discord export for all tracked channels"""
    from src.collectors.discord import export_all_channels
    export_all_channels()


def export_reddit():
    """Export Reddit data from tracked subreddits"""
    from src.collectors.reddit import export_all
    export_all()


def search():
    """Search message content"""
    import sys
    term = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
    if not term:
        print("Usage: python src/main.py search <term>")
        return
    from src.db.models import get_db
    db = get_db()
    rows = db.execute("""
        SELECT m.timestamp, m.content, u.display_name, c.name as channel
        FROM messages m
        JOIN users u ON m.user_id = u.id
        JOIN channels c ON m.channel_id = c.id
        WHERE m.content LIKE ? ESCAPE '\\'
        ORDER BY m.timestamp DESC
        LIMIT 30
    """, (f"%{term}%",)).fetchall()
    print(f"Found {len(rows)} messages containing '{term}':\n")
    for r in rows:
        print(f"  [{r['timestamp'][:19]}] {r['display_name'] or '?'} in #{r['channel']}")
        print(f"  {r['content'][:200]}")
        print()
    db.close()


def report():
    """Generate HTML report from current data"""
    from src.dashboard.report import generate_report
    generate_report()


def dashboard():
    """Launch web dashboard"""
    from src.dashboard.app import run_dashboard
    run_dashboard()


def import_data():
    """Import data from cuebot research JSON files"""
    from src.collectors.importer import import_all
    import_all()


def help_cmd():
    print("""CommunityRadar — Community Intelligence Tool

Commands:
  status     Show scan status and summary
  export     Run Discord export for tracked channels
  reddit     Export Reddit data from tracked subreddits
  import     Import existing data from cuebot research files
  search     Search message content (usage: search <term>)
  topics     Show top topics from message analysis
  xref       Show cross-platform user matches
  report     Generate HTML report
  dashboard  Launch web dashboard
  help       Show this message
""")


def cli():
    """Main CLI dispatcher"""
    args = sys.argv[1:] if len(sys.argv) > 1 else ["help"]
    cmd = args[0]

    commands = {
        "status": status,
        "export": export,
        "reddit": export_reddit,
        "import": import_data,
        "search": search,
        "topics": topics,
        "xref": xref,
        "report": report,
        "dashboard": dashboard,
        "help": help_cmd,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        help_cmd()
        sys.exit(1)


if __name__ == "__main__":
    cli()