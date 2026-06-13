"""HTML report generator"""

from pathlib import Path
import sys

# Ensure we can import from src
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import json
from src.db.models import get_db

DATA_DIR = ROOT / "data"

def generate_report(client_name=None, output_path=None):
    """Generate HTML report from current DB state and analysis data"""
    if output_path is None:
        if client_name:
            output_dir = DATA_DIR / "clients" / client_name / "reports"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "community-report.html"
            analysis_path = output_dir / "community-sentiment-analysis.json"
        else:
            output_path = DATA_DIR / "community-report.html"
            analysis_path = DATA_DIR / "community-sentiment-analysis.json"

    # Load rich analysis if available
    analysis = None
    if analysis_path.exists():
        with open(analysis_path) as f:
            analysis = json.load(f)

    db = get_db(client_name)

    # Gather data
    servers = db.execute("SELECT * FROM servers ORDER BY id").fetchall()
    total_users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    total_msgs = db.execute("SELECT SUM(message_count) as c FROM channels").fetchone()["c"] or 0
    
    # Use accurate counts from analysis meta if available
    if analysis:
        total_msgs = analysis["meta"]["total_messages_analyzed"]
        total_channels = analysis["meta"]["channels"]
    else:
        total_channels = len(servers)

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

    # Sentiment distribution
    overall_sent = analysis["sentiment"]["overall"] if analysis else None

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CommunityRadar Report - {client_name or 'Global'}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #0f0f13; color: #e8e8f0; line-height: 1.6; padding: 40px 24px; max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 2.5rem; font-weight: 700; background: linear-gradient(135deg, #6c5ce7, #00cec9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }}
  .subtitle {{ color: #8888a0; font-size: 1rem; margin-bottom: 40px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 40px; }}
  .stat-card {{ background: #1a1a24; border: 1px solid #2a2a3a; border-radius: 12px; padding: 24px; text-align: center; position: relative; overflow: hidden; }}
  .stat-value {{ font-size: 2.2rem; font-weight: 700; color: #6c5ce7; }}
  .stat-label {{ font-size: 0.8rem; color: #8888a0; text-transform: uppercase; letter-spacing: 0.05em; }}
  .stat-sub {{ font-size: 0.75rem; color: #555570; margin-top: 4px; }}
  
  .sentiment-bar {{ height: 8px; background: #22222e; border-radius: 4px; display: flex; overflow: hidden; margin: 12px 0; }}
  .sent-pos {{ background: #00b894; height: 100%; }}
  .sent-neg {{ background: #ff7675; height: 100%; }}
  .sent-neu {{ background: #8888a0; height: 100%; }}
  
  h2 {{ font-size: 1.5rem; margin: 48px 0 20px; border-bottom: 2px solid #6c5ce7; padding-bottom: 10px; }}
  h3 {{ font-size: 1.1rem; color: #6c5ce7; margin: 32px 0 16px; text-transform: uppercase; letter-spacing: 0.05em; }}
  
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }}
  
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th {{ text-align: left; padding: 12px 16px; background: #22222e; border-bottom: 2px solid #2a2a3a; font-size: 0.75rem; text-transform: uppercase; color: #8888a0; }}
  td {{ padding: 12px 16px; border-bottom: 1px solid #2a2a3a; font-size: 0.85rem; }}
  tr:hover td {{ background: #1a1a24; }}
  
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; }}
  .role-team {{ background: rgba(108,92,231,0.2); color: #6c5ce7; }}
  .role-mod {{ background: rgba(0,206,201,0.2); color: #00cec9; }}
  .role-power {{ background: rgba(0,184,148,0.2); color: #00b894; }}
  
  .sent-pill {{ padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }}
  .pill-pos {{ background: rgba(0,184,148,0.15); color: #00b894; }}
  .pill-neg {{ background: rgba(255,118,117,0.15); color: #ff7675; }}
  .pill-neu {{ background: rgba(136,136,160,0.15); color: #8888a0; }}
  
  .anomaly-card {{ border-left: 4px solid #ff7675; background: rgba(255,118,117,0.05); padding: 16px; border-radius: 0 8px 8px 0; margin-bottom: 12px; }}
  .anomaly-sev-critical {{ border-left-color: #d63031; background: rgba(214,48,49,0.1); }}
  
  .sparkline {{ font-family: monospace; color: #6c5ce7; font-size: 1.2rem; line-height: 1; }}
  
  @media (max-width: 900px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  @media (max-width: 600px) {{ .stats-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  .footer {{ text-align: center; color: #8888a0; font-size: 0.8rem; margin-top: 64px; border-top: 1px solid #2a2a3a; padding-top: 32px; }}
</style>
</head>
<body>
<h1>🎯 CommunityRadar {f' - {client_name}' if client_name else ''}</h1>
<div class="subtitle">Community Intelligence Report · {__import__('datetime').datetime.now().strftime('%B %d, %Y')}</div>

<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-value">{total_users}</div>
    <div class="stat-label">Total Users</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{total_msgs}</div>
    <div class="stat-label">Total Messages</div>
    {f'<div class="stat-sub">{analysis["meta"]["deduped_messages"]} unique</div>' if analysis else ''}
  </div>
  <div class="stat-card">
    <div class="stat-value">{total_channels}</div>
    <div class="stat-label">Channels</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{overall_sent['sentiment_ratio'] if overall_sent else 'N/A'}</div>
    <div class="stat-label">Sentiment Ratio</div>
    {f'<div class="sentiment-bar"><div class="sent-pos" style="width: {overall_sent["positive"]["pct"]}%"></div><div class="sent-neg" style="width: {overall_sent["negative"]["pct"]}%"></div><div class="sent-neu" style="width: {overall_sent["neutral"]["pct"]}%"></div></div>' if overall_sent else ''}
  </div>
</div>
"""

    if analysis:
        # Weekly Trends
        if "weekly_trends" in analysis:
            trends = analysis["weekly_trends"]
            pos_pcts = [t["pos_pct"] for t in trends]
            neg_pcts = [t["neg_pct"] for t in trends]
            
            def get_spark(val, vals):
                if not vals: return "▁"
                lo, hi = min(vals), max(vals)
                if hi == lo: return "▅"
                idx = int((val - lo) / (hi - lo) * 7)
                glyphs = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
                return glyphs[min(7, idx)]

            html += "<h2>Weekly Sentiment Trends</h2>\n<table>\n<thead><tr><th>Week</th><th>Volume</th><th>Positive %</th><th>Negative %</th><th>Pos Trend</th><th>Neg Trend</th></tr></thead>\n<tbody>\n"
            for t in trends:
                pos_spark = get_spark(t['pos_pct'], pos_pcts)
                neg_spark = get_spark(t['neg_pct'], neg_pcts)
                html += f"""<tr>
                    <td>{t['week']}</td>
                    <td>{t['total']}</td>
                    <td><span class="sent-pill pill-pos">{t['pos_pct']}%</span></td>
                    <td><span class="sent-pill pill-neg">{t['neg_pct']}%</span></td>
                    <td class="sparkline">{pos_spark}</td>
                    <td class="sparkline">{neg_spark}</td>
                </tr>"""
            html += "</tbody>\n</table>\n"

        # Anomalies
        if analysis.get("anomalies"):
            html += "<h2>🚨 Sentiment Anomalies</h2>\n"
            for anom in analysis["anomalies"]:
                sev_class = "anomaly-sev-critical" if "CRITICAL" in anom["severity"] else ""
                html += f"""<div class="anomaly-card {sev_class}">
                    <strong>{anom['severity']}</strong>: {anom['metric']} spike in {anom['week']}<br/>
                    <small>Value: {anom['value']}% (Expected: {anom['expected']}%, Z-Score: {anom['z_score']})</small>
                </div>"""

        # Topics
        if "topic_sentiment" in analysis:
            html += "<h2>Topic Analysis</h2>\n<table>\n<thead><tr><th>Topic</th><th>Mentions</th><th>Positive %</th><th>Negative %</th><th>Net Sentiment</th></tr></thead>\n<tbody>\n"
            # Sort topics by net sentiment
            sorted_topics = sorted(analysis["topic_sentiment"].items(), key=lambda x: -x[1]["net_sentiment"])
            for topic, data in sorted_topics[:20]:
                net = data["net_sentiment"]
                indicator = "🟢" if net > 10 else ("🔴" if net < -10 else "🟡")
                html += f"""<tr>
                    <td><strong>{topic}</strong></td>
                    <td>{data['total']}</td>
                    <td>{data['pos_pct']}%</td>
                    <td>{data['neg_pct']}%</td>
                    <td>{indicator} {net:+.0f}</td>
                </tr>"""
            html += "</tbody>\n</table>\n"

    html += """<div class="grid-2">"""
    
    # Channel breakdown
    if channels:
        html += "<div><h2>Channels Scanned</h2>\n<table>\n<thead><tr><th>Channel</th><th>Messages</th><th>Last Scan</th></tr></thead>\n<tbody>\n"
        for c in channels:
            html += f"<tr><td><small>{c['server_name']}</small><br/>#{c['name']}</td><td>{c['message_count'] or 0}</td><td>{c['last_scan'][:10] if c['last_scan'] else 'never'}</td></tr>\n"
        html += "</tbody>\n</table></div>\n"

    # Top users
    if top_users:
        html += "<div><h2>Top Contributors</h2>\n<table>\n<thead><tr><th>User</th><th>Role</th><th>Messages</th></tr></thead>\n<tbody>\n"
        for u in top_users:
            role_class = {"riipstone_team": "team", "moderator": "mod", "power_user": "power"}.get(u["role"], "")
            role_label = {"riipstone_team": "Team", "moderator": "Mod", "power_user": "Power", "active_user": "Active", "casual": "Casual"}.get(u["role"], u["role"] or "Unknown")
            html += f"<tr><td><strong>{u['display_name'] or u['username'] or 'Unknown'}</strong></td>"
            html += f"<td><span class='badge role-{role_class}'>{role_label}</span></td>"
            html += f"<td>{u['messages']}</td></tr>\n"
        html += "</tbody>\n</table></div>\n"

    html += "</div>"

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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--client", help="Client name")
    args = parser.parse_args()
    generate_report(client_name=args.client)
