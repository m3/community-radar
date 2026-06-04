"""HTML report generator"""

from pathlib import Path
from src.db.models import get_db

DATA_DIR = Path(__file__).parent.parent.parent / "data"

def generate_report(output_path=None):
    """Generate HTML report from current DB state"""
    if output_path is None:
        output_path = DATA_DIR / "community-report.html"

    db = get_db()

    # Gather data
    servers = db.execute("SELECT * FROM servers ORDER BY id").fetchall()
    total_users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    total_msgs = db.execute("SELECT SUM(message_count) as c FROM channels").fetchone()["c"] or 0
    total_channels = len(servers)  # approximate

    # Top users
    top_users = db.execute(
        "SELECT display_name, username, role, messages, reactions_received "
        "FROM users ORDER BY messages DESC LIMIT 15"
    ).fetchall()

    # Channel stats
    channels = db.execute(
        "SELECT c.name, c.message_count, c.last_scan, s.name as server_name "
        "FROM channels c JOIN servers s ON c.server_id = s.id "
        "ORDER BY c.message_count DESC"
    ).fetchall()

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CommunityRadar Report</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #0f0f13; color: #e8e8f0; line-height: 1.6; padding: 40px 24px; max-width: 1000px; margin: 0 auto; }}
  h1 {{ font-size: 2.5rem; font-weight: 700; background: linear-gradient(135deg, #6c5ce7, #00cec9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }}
  .subtitle {{ color: #8888a0; font-size: 1rem; margin-bottom: 40px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 40px; }}
  .stat-card {{ background: #1a1a24; border: 1px solid #2a2a3a; border-radius: 12px; padding: 24px; text-align: center; }}
  .stat-value {{ font-size: 2.2rem; font-weight: 700; color: #6c5ce7; }}
  .stat-label {{ font-size: 0.8rem; color: #8888a0; text-transform: uppercase; letter-spacing: 0.05em; }}
  h2 {{ font-size: 1.3rem; margin: 32px 0 16px; border-bottom: 2px solid #6c5ce7; padding-bottom: 8px; display: inline-block; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th {{ text-align: left; padding: 10px 14px; background: #22222e; border-bottom: 2px solid #2a2a3a; font-size: 0.75rem; text-transform: uppercase; color: #8888a0; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #2a2a3a; font-size: 0.85rem; }}
  tr:hover td {{ background: #1a1a24; }}
  .role {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; }}
  .role-team {{ background: rgba(108,92,231,0.2); color: #6c5ce7; }}
  .role-mod {{ background: rgba(0,206,201,0.2); color: #00cec9; }}
  .role-power {{ background: rgba(0,184,148,0.2); color: #00b894; }}
  @media (max-width: 600px) {{ .stats-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  .footer {{ text-align: center; color: #8888a0; font-size: 0.8rem; margin-top: 48px; border-top: 1px solid #2a2a3a; padding-top: 24px; }}
</style>
</head>
<body>
<h1>🎯 CommunityRadar</h1>
<div class="subtitle">Community Intelligence Report · {__import__('datetime').datetime.now().strftime('%B %d, %Y')}</div>

<div class="stats-grid">
  <div class="stat-card"><div class="stat-value">{total_users}</div><div class="stat-label">Users</div></div>
  <div class="stat-card"><div class="stat-value">{total_msgs}</div><div class="stat-label">Messages</div></div>
  <div class="stat-card"><div class="stat-value">{len(channels)}</div><div class="stat-label">Channels</div></div>
  <div class="stat-card"><div class="stat-value">{len(servers)}</div><div class="stat-label">Servers</div></div>
</div>
"""

    # Channel breakdown
    if channels:
        html += "<h2>Channels Scanned</h2>\n<table>\n<thead><tr><th>Server</th><th>Channel</th><th>Messages</th><th>Last Scan</th></tr></thead>\n<tbody>\n"
        for c in channels:
            html += f"<tr><td>{c['server_name']}</td><td>#{c['name']}</td><td>{c['message_count'] or 0}</td><td>{c['last_scan'] or 'never'}</td></tr>\n"
        html += "</tbody>\n</table>\n"

    # Top users
    if top_users:
        html += "<h2>Top Users</h2>\n<table>\n<thead><tr><th>User</th><th>Role</th><th>Messages</th><th>Reactions</th></tr></thead>\n<tbody>\n"
        for u in top_users:
            role_class = {"riipstone_team": "team", "moderator": "mod", "power_user": "power"}.get(u["role"], "")
            role_label = {"riipstone_team": "Team", "moderator": "Mod", "power_user": "Power", "active_user": "Active", "casual": "Casual"}.get(u["role"], u["role"] or "Unknown")
            html += f"<tr><td><strong>{u['display_name'] or u['username'] or 'Unknown'}</strong></td>"
            html += f"<td><span class='role role-{role_class}'>{role_label}</span></td>"
            html += f"<td>{u['messages']}</td><td>{u['reactions_received']}</td></tr>\n"
        html += "</tbody>\n</table>\n"

    html += f"""
<div class="footer">
Generated by CommunityRadar · {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
</div>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    print(f"  Report generated: {output_path}")
    db.close()
    return output_path