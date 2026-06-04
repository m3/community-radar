"""Flask dashboard for CommunityRadar"""

import os
from src.db.models import get_db

try:
    from flask import Flask, render_template_string, jsonify
except ImportError:
    print("Flask not installed. Run: pip install flask")
    raise

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CommunityRadar Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; background: #0f0f13; color: #e8e8f0; line-height: 1.6; }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }

  .header { padding: 32px 0 24px; border-bottom: 1px solid #2a2a3a; margin-bottom: 32px; }
  .header h1 { font-size: 2rem; background: linear-gradient(135deg, #6c5ce7, #00cec9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .stat { background: #1a1a24; border: 1px solid #2a2a3a; border-radius: 10px; padding: 20px; text-align: center; }
  .stat .value { font-size: 2rem; font-weight: 700; color: #6c5ce7; }
  .stat .label { font-size: 0.8rem; color: #8888a0; text-transform: uppercase; margin-top: 4px; }

  .section { margin-bottom: 32px; }
  .section h2 { font-size: 1.2rem; margin-bottom: 16px; border-bottom: 2px solid #6c5ce7; padding-bottom: 8px; display: inline-block; }

  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 10px 14px; background: #22222e; border-bottom: 2px solid #2a2a3a; font-size: 0.75rem; text-transform: uppercase; color: #8888a0; }
  td { padding: 10px 14px; border-bottom: 1px solid #2a2a3a; font-size: 0.85rem; }
  tr:hover td { background: rgba(108,92,231,0.05); }

  .nav { display: flex; gap: 12px; margin-bottom: 24px; }
  .nav a { color: #6c5ce7; text-decoration: none; padding: 8px 16px; border-radius: 6px; background: #1a1a24; border: 1px solid #2a2a3a; font-size: 0.85rem; }
  .nav a:hover { border-color: #6c5ce7; }
  .nav a.active { background: #6c5ce7; color: white; border-color: #6c5ce7; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🎯 CommunityRadar</h1>
    <div style="color: #8888a0; margin-top: 4px;">Community Intelligence Dashboard</div>
  </div>

  <div class="nav">
    <a href="/" class="active">Overview</a>
    <a href="/users">Users</a>
    <a href="/servers">Servers</a>
  </div>

  <div class="stats">
    <div class="stat"><div class="value">{{ stats.total_users }}</div><div class="label">Users</div></div>
    <div class="stat"><div class="value">{{ stats.total_messages }}</div><div class="label">Messages</div></div>
    <div class="stat"><div class="value">{{ stats.total_channels }}</div><div class="label">Channels</div></div>
    <div class="stat"><div class="value">{{ stats.total_servers }}</div><div class="label">Servers</div></div>
  </div>

  <div class="section">
    <h2>Top Users</h2>
    <table>
      <thead><tr><th>User</th><th>Role</th><th>Messages</th><th>Reactions</th><th>Last Seen</th></tr></thead>
      <tbody>
      {% for u in top_users %}
      <tr>
        <td><strong>{{ u.display_name or u.username or 'Unknown' }}</strong></td>
        <td><span style="color:#6c5ce7">{{ u.role }}</span></td>
        <td>{{ u.messages }}</td><td>{{ u.reactions_received }}</td>
        <td>{{ u.last_seen or '' }}</td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
</body>
</html>"""

app = Flask(__name__)


@app.route("/")
def overview():
    db = get_db()
    stats = {
        "total_users": db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"],
        "total_messages": db.execute("SELECT COALESCE(SUM(message_count),0) as c FROM channels").fetchone()["c"],
        "total_channels": db.execute("SELECT COUNT(*) as c FROM channels").fetchone()["c"],
        "total_servers": db.execute("SELECT COUNT(*) as c FROM servers").fetchone()["c"],
    }
    top_users = db.execute(
        "SELECT display_name, username, role, messages, reactions_received, last_seen "
        "FROM users ORDER BY COALESCE(messages,0) DESC LIMIT 20"
    ).fetchall()
    db.close()
    return render_template_string(TEMPLATE, stats=stats, top_users=top_users)


@app.route("/users")
def users():
    db = get_db()
    users = db.execute(
        "SELECT display_name, username, role, messages, reactions_received, reactions_given, first_seen, last_seen "
        "FROM users ORDER BY COALESCE(messages,0) DESC"
    ).fetchall()
    db.close()
    rows = "".join(
        f"<tr><td><strong>{u['display_name'] or u['username'] or 'Unknown'}</strong></td>"
        f"<td>{u['role']}</td><td>{u['messages']}</td><td>{u['reactions_received']}</td>"
        f"<td>{u['reactions_given']}</td><td>{u['first_seen'] or ''}</td><td>{u['last_seen'] or ''}</td></tr>"
        for u in users
    )
    return render_template_string("""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Users — CommunityRadar</title><style>
        body{font-family:-apple-system,system-ui,sans-serif;background:#0f0f13;color:#e8e8f0;padding:24px;max-width:1200px;margin:0 auto}
        h1{background:linear-gradient(135deg,#6c5ce7,#00cec9);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        a{color:#6c5ce7;text-decoration:none}
        table{width:100%;border-collapse:collapse;margin-top:16px}
        th{text-align:left;padding:10px;background:#22222e;border-bottom:2px solid #2a2a3a;font-size:0.75rem;text-transform:uppercase;color:#8888a0}
        td{padding:10px;border-bottom:1px solid #2a2a3a;font-size:0.85rem}
        tr:hover td{background:#1a1a24}
        .count{color:#8888a0;margin:8px 0}
    </style></head><body>
    <a href="/">← Back</a><h1>Users</h1>
    <div class="count">{{ users|length }} users</div>
    <table><thead><tr><th>User</th><th>Role</th><th>Msgs</th><th>Reacts Given</th><th>Reacts Received</th><th>First Seen</th><th>Last Seen</th></tr></thead>
    <tbody>""" + rows + "</tbody></table></body></html>", users=users)


@app.route("/servers")
def servers():
    db = get_db()
    servers = db.execute(
        "SELECT id, name, total_messages, total_users, first_scan, last_scan "
        "FROM servers ORDER BY name"
    ).fetchall()
    rows = ""
    for s in servers:
        channels = db.execute(
            "SELECT name, message_count, last_scan FROM channels WHERE server_id=? ORDER BY name",
            (s["id"],)
        ).fetchall()
        chan_info = "".join(
            f"<div style='font-size:0.8rem;color:#8888a0;margin-left:20px'>📺 #{c['name']}: {c['message_count']} msgs</div>"
            for c in channels
        )
        rows += f"<tr><td><strong>{s['name']}</strong>{chan_info}</td><td>{s['total_messages'] or 0}</td><td>{s['total_users'] or 0}</td><td>{s['last_scan'] or 'never'}</td></tr>"
    db.close()
    return render_template_string("""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Servers — CommunityRadar</title><style>
        body{font-family:-apple-system,system-ui,sans-serif;background:#0f0f13;color:#e8e8f0;padding:24px;max-width:1200px;margin:0 auto}
        h1{background:linear-gradient(135deg,#6c5ce7,#00cec9);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        a{color:#6c5ce7;text-decoration:none}
        table{width:100%;border-collapse:collapse;margin-top:16px}
        th{text-align:left;padding:10px;background:#22222e;border-bottom:2px solid #2a2a3a;font-size:0.75rem;text-transform:uppercase;color:#8888a0}
        td{padding:10px;border-bottom:1px solid #2a2a3a;font-size:0.85rem}
        tr:hover td{background:#1a1a24}
    </style></head><body>
    <a href="/">← Back</a><h1>Servers</h1>
    <table><thead><tr><th>Server</th><th>Messages</th><th>Users</th><th>Last Scan</th></tr></thead>
    <tbody>""" + rows + "</tbody></table></body></html>")


def run_dashboard(host="0.0.0.0", port=5050):
    print(f"  Dashboard starting at http://localhost:{port}")
    print(f"  Press Ctrl+C to stop")
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    run_dashboard()