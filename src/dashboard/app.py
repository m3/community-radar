"""
CommunityRadar Flask Dashboard
Real-time community intelligence with time-series sentiment charts.
"""

from flask import Flask, render_template, jsonify, request, current_app
import sqlite3
from pathlib import Path
import json
from datetime import datetime, timedelta
from collections import defaultdict
import sys

app = Flask(__name__)

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.db.models import get_db as _get_db

def get_db():
    """Get database connection with row factory."""
    client_name = current_app.config.get('CLIENT_NAME')
    if not client_name:
        raise ValueError("CLIENT_NAME is not set")
    return _get_db(client_name)


def load_report():
    """Load latest sentiment analysis report."""
    client_name = current_app.config.get('CLIENT_NAME')
    if not client_name:
        raise ValueError("CLIENT_NAME is not set")
    report_path = ROOT / "data" / "clients" / client_name / "reports" / "community-sentiment-analysis.json"
    if report_path.exists():
        with open(report_path) as f:
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


# ─── Cuebot Engagement Scoring API ──────────────────────────────────────

@app.route("/api/cuebot/engagement/score")
def api_cuebot_engagement_score():
    """Get engagement scores for all users across platforms.
    
    Returns a ranked list of users with composite engagement scores
    based on message count, reactions, replies, sentiment, and recency.
    """
    db = get_db()

    # Calculate engagement scores
    # Components: message_count, reactions_received, reply_count, sentiment_score, recency
    rows = db.execute("""
        SELECT 
            u.id as user_id,
            u.display_name,
            u.username,
            u.messages as total_messages,
            u.reactions_received,
            u.last_seen,
            COALESCE(u.sentiment, 0) as sentiment_score,
            (SELECT platform FROM messages WHERE user_id = u.id LIMIT 1) as platform,
            (SELECT COUNT(*) FROM messages WHERE reply_to IN 
                (SELECT message_id FROM messages WHERE user_id = u.id)
            ) as reply_count
        FROM users u
        WHERE u.messages > 0
    """).fetchall()

    scores = []
    now = datetime.now()
    for r in rows:
        # Recency score (0-1, 1 = active today)
        last_active = r["last_seen"]
        recency = 0
        if last_active:
            try:
                last_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                days_ago = (now - last_dt).days
                recency = max(0, 1 - days_ago / 90)  # Decay over 90 days
            except:
                recency = 0

        # Composite engagement score
        # Weights: messages 30%, reactions 25%, replies 20%, sentiment 15%, recency 10%
        msg_score = min(r["total_messages"] / 500, 1) * 30  # Cap at 500 messages
        reaction_score = min(r["reactions_received"] / 200, 1) * 25  # Cap at 200 reactions
        reply_score = min(r["reply_count"] / 100, 1) * 20  # Cap at 100 replies
        sent_score = (r["sentiment_score"] + 1) / 2 * 15  # -1 to 1 → 0 to 15
        recency_score = recency * 10

        total_score = msg_score + reaction_score + reply_score + sent_score + recency_score

        scores.append({
            "user_id": r["user_id"],
            "display_name": r["display_name"],
            "username": r["username"],
            "platform": r["platform"],
            "total_messages": r["total_messages"],
            "reactions_received": r["reactions_received"],
            "reply_count": r["reply_count"],
            "sentiment_score": round(r["sentiment_score"], 3),
            "last_active": r["last_seen"],
            "engagement_score": round(total_score, 2),
            "score_breakdown": {
                "messages": round(msg_score, 2),
                "reactions": round(reaction_score, 2),
                "replies": round(reply_score, 2),
                "sentiment": round(sent_score, 2),
                "recency": round(recency_score, 2)
            }
        })

    # Sort by engagement score descending
    scores.sort(key=lambda x: x["engagement_score"], reverse=True)

    db.close()

    return jsonify({
        "scores": scores,
        "total_users": len(scores),
        "generated_at": now.isoformat()
    })


@app.route("/api/cuebot/engagement/leaderboard")
def api_cuebot_leaderboard():
    """Get top N users by engagement score."""
    limit = min(int(request.args.get("limit", 50)), 200)
    platform = request.args.get("platform")

    db = get_db()

    query = """
        SELECT 
            u.id as user_id,
            u.display_name,
            u.username,
            u.messages as total_messages,
            u.reactions_received,
            u.last_seen,
            COALESCE(u.sentiment, 0) as sentiment_score,
            (SELECT platform FROM messages WHERE user_id = u.id LIMIT 1) as platform,
            (SELECT COUNT(*) FROM messages WHERE reply_to IN 
                (SELECT message_id FROM messages WHERE user_id = u.id)
            ) as reply_count
        FROM users u
        WHERE u.messages > 0
    """
    params = []

    if platform:
        query += " AND u.platform = ?"
        params.append(platform)

    rows = db.execute(query, params).fetchall()

    now = datetime.now()
    scores = []
    for r in rows:
        last_active = r["last_seen"]
        recency = 0
        if last_active:
            try:
                last_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                days_ago = (now - last_dt).days
                recency = max(0, 1 - days_ago / 90)
            except:
                recency = 0

        msg_score = min(r["total_messages"] / 500, 1) * 30
        reaction_score = min(r["reactions_received"] / 200, 1) * 25
        reply_score = min(r["reply_count"] / 100, 1) * 20
        sent_score = (r["sentiment_score"] + 1) / 2 * 15
        recency_score = recency * 10

        total_score = msg_score + reaction_score + reply_score + sent_score + recency_score

        scores.append({
            "user_id": r["user_id"],
            "display_name": r["display_name"],
            "username": r["username"],
            "platform": r["platform"],
            "engagement_score": round(total_score, 2),
            "total_messages": r["total_messages"],
            "reactions_received": r["reactions_received"],
            "reply_count": r["reply_count"]
        })

    scores.sort(key=lambda x: x["engagement_score"], reverse=True)
    db.close()

    return jsonify({
        "leaderboard": scores[:limit],
        "limit": limit,
        "platform_filter": platform
    })


@app.route("/api/cuebot/engagement/user/<user_id>")
def api_cuebot_user_profile(user_id):
    """Get detailed engagement profile for a specific user."""
    db = get_db()

    user = db.execute("""
        SELECT u.*, 
            (SELECT COUNT(*) FROM messages WHERE reply_to IN 
                (SELECT message_id FROM messages WHERE user_id = u.id)
            ) as reply_count
        FROM users u
        WHERE u.id = ?
    """, (user_id,)).fetchone()

    if not user:
        db.close()
        return jsonify({"error": "User not found"}), 404

    # Get user's messages with sentiment
    messages = db.execute("""
        SELECT m.content, m.timestamp, m.reactions, m.platform, m.channel_id,
               c.name as channel_name,
               CASE 
                   WHEN m.reactions > 2 THEN 'positive'
                   WHEN m.reactions < 0 THEN 'negative'
                   ELSE 'neutral'
               END as sentiment_proxy
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        WHERE m.user_id = ? AND m.content IS NOT NULL AND m.content != ''
        ORDER BY m.timestamp DESC
        LIMIT 100
    """, (user_id,)).fetchall()

    # Channel activity
    channel_activity = db.execute("""
        SELECT c.name as channel_name, m.platform, COUNT(*) as msg_count
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        WHERE m.user_id = ?
        GROUP BY c.id, m.platform
        ORDER BY msg_count DESC
    """, (user_id,)).fetchall()

    # Cross-platform presence
    platforms = db.execute("""
        SELECT DISTINCT platform FROM messages WHERE user_id = ?
    """, (user_id,)).fetchall()

    db.close()

    return jsonify({
        "user_id": user["id"],
        "display_name": user["display_name"],
        "username": user["username"],
        "total_messages": user["messages"],
        "reactions_received": user["reactions_received"],
        "reply_count": user["reply_count"],
        "sentiment_score": user["sentiment"] if user["sentiment"] else 0,
        "last_active": user["last_seen"],
        "platforms": [p["platform"] for p in platforms],
        "channel_activity": [dict(c) for c in channel_activity],
        "recent_messages": [dict(m) for m in messages]
    })


@app.route("/api/cuebot/engagement/crossref")
def api_cuebot_crossref():
    """Get cross-references between Discord and Reddit users."""
    db = get_db()

    rows = db.execute("""
        SELECT cr.*, 
            u1.display_name as discord_name, u1.username as discord_username,
            u2.display_name as reddit_name, u2.username as reddit_username
        FROM cross_references cr
        LEFT JOIN users u1 ON cr.username1 = u1.username
        LEFT JOIN users u2 ON cr.username2 = u2.username
    """).fetchall()

    db.close()

    return jsonify({
        "cross_references": [dict(r) for r in rows],
        "total": len(rows)
    })


def run_dashboard(client_name):
    app.config['CLIENT_NAME'] = client_name
    app.run(host="0.0.0.0", port=5001, debug=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--client", required=True, help="Client name")
    args = parser.parse_args()
    run_dashboard(args.client)