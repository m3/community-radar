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
    users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()
    print(f"Total unique users profiled: {users['c']}")


def export():
    """Run Discord export for all tracked channels"""
    from src.collectors.discord import export_all_channels
    export_all_channels()


def export_reddit():
    """Export Reddit data from tracked subreddits"""
    from src.collectors.reddit import export_all
    export_all()


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
  report     Generate HTML report
  dashboard  Launch web dashboard
  import     Import existing data from cuebot research files
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
        "report": report,
        "dashboard": dashboard,
        "import": import_data,
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