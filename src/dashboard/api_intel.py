"""Market intelligence routes: the intel page and competitor/domain data."""

from flask import Blueprint, render_template, jsonify

from src.dashboard.helpers import ROOT, validate_client, load_config, get_db

bp = Blueprint("intel", __name__)


@bp.route("/<client_name>/intel")
def intel_view(client_name):
    """Market Intelligence page."""
    validate_client(client_name)
    return render_template("intel.html", client_name=client_name)


@bp.route("/api/<client_name>/intel/market")
def api_market_intel(client_name):
    """Aggregate competitor intel and domain monitoring data."""
    validate_client(client_name)

    # 1. Load Competitor JSON
    config = load_config()
    data_dir = ROOT / config.get("data_dir", "data")
    report_path = data_dir / "clients" / client_name / "reports" / "competitor_intel.json"
    intel = {}
    if report_path.exists():
        import json
        with open(report_path) as f:
            intel = json.load(f)

    # 2. Get Domain Monitoring Stats
    db = get_db(client_name)
    # Using LegacySessionWrapper mappings() for Postgres compatibility
    domain_stats = db.execute("""
        SELECT c.name as channel_name, COUNT(*) as post_count, MAX(m.timestamp) as last_post
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        WHERE c.name LIKE 'domain:%' AND m.client_id = :client_id
        GROUP BY c.name
        ORDER BY post_count DESC
    """).fetchall()  # Result will be mappings if LegacySessionWrapper detected SELECT
    db.close()

    return jsonify({
        "competitors": intel,
        "domains": [dict(d) for d in domain_stats]
    })
