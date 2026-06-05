"""
CommunityRadar Flask Dashboard
Real-time community intelligence with time-series sentiment charts.
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
from pathlib import Path
import json
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)

DB_PATH = Path("/Users/mathias/Development/community-radar/data/community_radar.db")
REPORT_PATH = Path("/Users/mathias/Development/community-radar/docs/community-sentiment-analysis.json")


def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_report():
    """Load latest sentiment analysis report."""
    if REPORT_PATH.exists():
        with open(REPORT_PATH) as f:
            return json.load(f)
    return {}


@app.route("/")
def index():
    """Main dashboard page."""
    report = load_report()
    return render_template("index.html", report=report)


@app.route("/api/overview")
def api_overview():
    """High-level stats for dashboard cards."""
    db = get_db()

    # Total messages by platform
    platform_stats = db.execute("""
        SELECT platform, COUNT(*) as count
        FROM messages
        GROUP BY platform
    """).fetchall()

    # Date range
    date_range = db.execute("""
        SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
        FROM messages
        WHERE timestamp IS NOT NULL
    """).fetchone()

    # Channels
    channels = db.execute("SELECT COUNT(*) as c FROM channels").fetchone()["c"]
    users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]

    db.close()

    return jsonify({
        "platforms": {r["platform"]: r["count"] for r in platform_stats},
        "date_range": {"from": date_range["min_ts"][:10] if date_range["min_ts"] else "N/A",
                       "to": date_range["max_ts"][:10] if date_range["max_ts"] else "N/A"},
        "channels": channels,
        "users": users,
        "report_meta": report.get("meta", {}) if (report := load_report()) else {}
    })


@app.route("/api/sentiment/timeseries")
def api_sentiment_timeseries():
    """Time-series sentiment data for charts."""
    db = get_db()

    # Get messages with sentiment - we'll compute on the fly
    # For performance, we use pre-computed daily aggregates
    rows = db.execute("""
        SELECT date(timestamp) as day, platform,
               SUM(CASE WHEN reactions > 0 THEN 1 ELSE 0 END) as positive_proxy,
               SUM(CASE WHEN reactions < 0 THEN 1 ELSE 0 END) as negative_proxy,
               COUNT(*) as total
        FROM messages
        WHERE timestamp IS NOT NULL
        GROUP BY day, platform
        ORDER BY day
    """).fetchall()

    db.close()

    # Also get actual sentiment from report if available
    report = load_report()

    # Build time series by platform
    series = defaultdict(lambda: defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0}))

    for r in rows:
        day = r["day"]
        platform = r["platform"]
        series[platform][day] = {
            "positive": r["positive_proxy"],  # Using reactions as proxy
            "negative": r["negative_proxy"],
            "neutral": r["total"] - r["positive_proxy"] - r["negative_proxy"],
            "total": r["total"]
        }

    return jsonify({
        "series": {p: dict(d) for p, d in series.items()},
        "report_sentiment": report.get("sentiment", {})
    })


@app.route("/api/sentiment/by_channel")
def api_sentiment_by_channel():
    """Sentiment breakdown by channel."""
    report = load_report()
    return jsonify(report.get("sentiment", {}).get("by_channel", {}))


@app.route("/api/topics")
def api_topics():
    """Topic-level sentiment."""
    report = load_report()
    return jsonify(report.get("topic_sentiment", {}))


@app.route("/api/power_words")
def api_power_words():
    """Community power words."""
    report = load_report()
    return jsonify(report.get("power_words", {}))


@app.route("/api/engagement")
def api_engagement():
    """Engagement metrics."""
    report = load_report()
    return jsonify(report.get("engagement", {}))


@app.route("/api/contributors")
def api_contributors():
    """Top contributors."""
    report = load_report()
    return jsonify(report.get("top_contributors", []))


@app.route("/api/negative_messages")
def api_negative_messages():
    """Top negative messages."""
    report = load_report()
    return jsonify(report.get("top_negative", []))


@app.route("/api/positive_messages")
def api_positive_messages():
    """Top positive messages."""
    report = load_report()
    return jsonify(report.get("top_positive", []))


@app.route("/api/purpose")
def api_purpose():
    """Purpose classification."""
    report = load_report()
    return jsonify(report.get("purpose", {}))


@app.route("/api/reddit/comparison")
def api_reddit_comparison():
    """Reddit vs Discord comparison."""
    report = load_report()
    return jsonify(report.get("sentiment", {}).get("reddit_comparison", {}))


@app.route("/api/raw_messages")
def api_raw_messages():
    """Raw messages for detailed view with filters."""
    db = get_db()

    platform = request.args.get("platform")
    channel = request.args.get("channel")
    sentiment = request.args.get("sentiment")  # positive, negative, neutral
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    query = """
        SELECT m.message_id, m.content, m.timestamp, m.reactions, m.channel_id,
               m.platform, m.reply_to,
               c.name as channel_name,
               u.display_name, u.role
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        LEFT JOIN users u ON m.user_id = u.id
        WHERE m.content IS NOT NULL AND m.content != ''
    """
    params = []

    if platform:
        query += " AND m.platform = ?"
        params.append(platform)
    if channel:
        query += " AND c.name = ?"
        params.append(channel)

    query += " ORDER BY m.timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(query, params).fetchall()
    db.close()

    return jsonify([dict(r) for r in rows])


@app.route("/api/channels")
def api_channels():
    """List all channels with stats."""
    db = get_db()

    rows = db.execute("""
        SELECT c.id, c.name, c.server_id, c.message_count, c.last_scan,
               s.name as server_name
        FROM channels c
        LEFT JOIN servers s ON c.server_id = s.id
        ORDER BY c.message_count DESC
    """).fetchall()
    db.close()

    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)