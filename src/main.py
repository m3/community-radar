"""CommunityRadar — CLI entry point"""

import sys
import json
import argparse
import yaml
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Ensure we can import from src
sys.path.insert(0, str(ROOT))

def load_config():
    CONFIG_PATH = ROOT / "config.yaml"
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def get_available_clients(config):
    return list(config.get("clients", {}).keys())

def status(args):
    """Show current scan status"""
    from src.db.models import get_db
    db = get_db(args.client)
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


def topics(args):
    """Show top topics from message analysis"""
    from src.db.models import get_db
    db = get_db(args.client)
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


def xref(args):
    """Show cross-platform user matches"""
    from src.db.models import get_db
    db = get_db(args.client)
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


def collect(args):
    """Run all collectors for a specific client"""
    config = load_config()
    if args.client not in config.get("clients", {}):
        print(f"Error: Client '{args.client}' not found in config.")
        return

    client_cfg = config["clients"][args.client]
    client_cfg["_client_name"] = args.client
    
    # Run Discord export if configured
    if "discord" in client_cfg:
        from src.collectors.discord import export_all_channels
        print(f"Running Discord collector for {args.client}...")
        export_all_channels(client_cfg=client_cfg)

    # Run Reddit export if configured
    if "reddit" in client_cfg:
        from src.collectors.reddit import export_all
        print(f"Running Reddit collector for {args.client}...")
        export_all(client_cfg=client_cfg)

        # Run Reddit Domain Monitoring if enabled
        if "domain_monitoring" in client_cfg["reddit"]:
            from src.collectors.reddit_domain import export_all_domains
            print(f"Running Reddit Domain Monitoring for {args.client}...")
            export_all_domains(client_cfg=client_cfg)


def export_discord(args):
    """Run Discord export for a specific client"""
    config = load_config()
    client_cfg = config["clients"].get(args.client)
    if not client_cfg or "discord" not in client_cfg:
        print(f"Error: Discord config not found for client '{args.client}'")
        return
    client_cfg["_client_name"] = args.client
    from src.collectors.discord import export_all_channels
    export_all_channels(client_cfg=client_cfg)


def export_reddit(args):
    """Export Reddit data for a specific client"""
    config = load_config()
    client_cfg = config["clients"].get(args.client)
    if not client_cfg or "reddit" not in client_cfg:
        print(f"Error: Reddit config not found for client '{args.client}'")
        return
    client_cfg["_client_name"] = args.client
    from src.collectors.reddit import export_all
    print(f"Running Reddit collector for {args.client}...")
    export_all(client_cfg=client_cfg)

    # Run Reddit Domain Monitoring if enabled
    if "domain_monitoring" in client_cfg["reddit"]:
        from src.collectors.reddit_domain import export_all_domains
        print(f"Running Reddit Domain Monitoring for {args.client}...")
        export_all_domains(client_cfg=client_cfg)


def search(args):
    """Search message content"""
    term = args.term
    from src.db.models import get_db
    db = get_db(args.client)
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


def report(args):
    """Generate HTML report from current data"""
    from src.dashboard.report import generate_report
    generate_report(client_name=args.client)


def dashboard(args):
    """Launch web dashboard"""
    from src.dashboard.app import run_dashboard
    run_dashboard(args.client)


def migrate_dbs(args):
    """Run database migrations for all clients or a specific client"""
    from src.db.models import get_db
    config = load_config()
    
    clients_to_migrate = [args.client] if args.client else get_available_clients(config)
    
    for client in clients_to_migrate:
        print(f"\nMigrating database for {client}...")
        # get_db automatically applies migrations
        db = get_db(client)
        db.close()
        print(f"✅ {client} migration complete.")


def import_data(args):
    """Import data from cuebot research JSON files"""
    from src.collectors.importer import import_all
    import_all()


def show_config(args):
    """Show current configuration"""
    config = load_config()
    if args.client:
        if args.client in config.get("clients", {}):
            print(yaml.dump(config["clients"][args.client], default_flow_style=False, sort_keys=False))
        else:
            print(f"Client '{args.client}' not found.")
    else:
        print(yaml.dump(config, default_flow_style=False, sort_keys=False))


def analyze(args):
    """Run sentiment + community analysis"""
    import subprocess
    cmd = [sys.executable, str(ROOT / "src" / "analysis" / "sentiment.py")]
    if args.client:
        cmd.extend(["--client", args.client])
        
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode == 0:
        print("\nAnalysis complete.")


def queue_mgmt(args):
    """Manage execution queue"""
    from src.db.queue import get_queue_db
    db = get_queue_db()
    
    if args.action == "status":
        rows = db.execute("SELECT status, COUNT(*) as count FROM tasks GROUP BY status").fetchall()
        for r in rows:
            print(f"{r['status'].capitalize()}: {r['count']}")
            
    elif args.action == "list":
        rows = db.execute("SELECT id, client_name, command, status, created_at FROM tasks ORDER BY id DESC LIMIT 20").fetchall()
        print(f"{'ID':<4} {'Client':<20} {'Command':<15} {'Status':<10} {'Created'}")
        for r in rows:
            client = r['client_name'] or 'global'
            print(f"{r['id']:<4} {client:<20} {r['command']:<15} {r['status']:<10} {r['created_at']}")
            
    elif args.action == "retry":
        if not args.task_id:
            print("Error: task_id required for retry")
            return
        db.execute("UPDATE tasks SET status='pending', error_log=NULL, started_at=NULL, finished_at=NULL WHERE id=?", (args.task_id,))
        db.commit()
        print(f"Task {args.task_id} reset to pending.")
        
    elif args.action == "clear":
        db.execute("DELETE FROM tasks WHERE status IN ('completed', 'failed')")
        db.commit()
        print("Cleared completed/failed tasks.")
        
    db.close()


commands = {
    "status": status,
    "collect": collect,
    "export": export_discord,
    "reddit": export_reddit,
    "import": import_data,
    "search": search,
    "topics": topics,
    "xref": xref,
    "config": show_config,
    "analyze": analyze,
    "report": report,
    "dashboard": dashboard,
    "migrate": migrate_dbs,
    "queue": queue_mgmt,
}


def cli():
    """Main CLI dispatcher"""
    parser = argparse.ArgumentParser(description="CommunityRadar — Community Intelligence Tool")
    parser.add_argument("-c", "--client", help="Client name to work on")
    parser.add_argument("--async", dest="async_mode", action="store_true", help="Run command asynchronously via queue")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("status", help="Show scan status and summary")
    subparsers.add_parser("collect", help="Run all collectors for a client")
    subparsers.add_parser("export", help="Run Discord export for a client")
    subparsers.add_parser("reddit", help="Export Reddit data for a client")
    subparsers.add_parser("import", help="Import existing data from cuebot research files")
    
    search_parser = subparsers.add_parser("search", help="Search message content")
    search_parser.add_argument("term", help="Search term")
    
    subparsers.add_parser("topics", help="Show top topics from message analysis")
    subparsers.add_parser("xref", help="Show cross-platform user matches")
    subparsers.add_parser("analyze", help="Run sentiment + community analysis")
    subparsers.add_parser("config", help="Show current configuration")
    subparsers.add_parser("report", help="Generate HTML report")
    subparsers.add_parser("dashboard", help="Launch web dashboard")
    subparsers.add_parser("migrate", help="Run database migrations (can be scoped with --client)")

    q_parser = subparsers.add_parser("queue", help="Manage execution queue")
    q_parser.add_argument("action", choices=["status", "list", "retry", "clear"])
    q_parser.add_argument("--task-id", type=int, help="Task ID for retry action")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Commands that require --client
    client_required_cmds = ["status", "collect", "export", "reddit", "search", "topics", "xref", "analyze", "report"]
    if args.command in client_required_cmds and not args.client:
        config = load_config()
        available = get_available_clients(config)
        print(f"Error: --client is required for '{args.command}'")
        print(f"Available clients: {', '.join(available)}")
        sys.exit(1)

    if args.command in commands:
        if getattr(args, "async_mode", False):
            from src.db.queue import enqueue_task
            # Strip internal argparse fields
            task_args = vars(args).copy()
            task_args.pop("async_mode", None)
            task_args.pop("command", None)
            task_args.pop("client", None)
            
            enqueue_task(args.client, args.command, task_args)
            target = f"client '{args.client}'" if args.client else "global"
            print(f"✅ Task '{args.command}' for {target} enqueued.")
            return
            
        commands[args.command](args)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    cli()