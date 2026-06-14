"""
CommunityRadar Flask Dashboard
Real-time community intelligence with time-series sentiment charts.
"""

from flask import Flask, render_template, jsonify, request, current_app, abort
import sqlite3
from pathlib import Path
import json
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import yaml
import functools

app = Flask(__name__)

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.db.models import get_db as _get_db
from src.dashboard.config_manager import ConfigManager

config_mgr = ConfigManager(ROOT / "config.yaml")

@functools.lru_cache()
def load_config():
    """Load configuration from config.yaml."""
    config_path = ROOT / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

def validate_client(client_name):
    """Validate client name against config to prevent path traversal.
    
    Raises 404 if client not found.
    """
    config = load_config()
    if client_name not in config.get("clients", {}):
        abort(404)

def get_db(client_name):
    """Get database connection for a specific client."""
    return _get_db(client_name)


def load_report(client_name):
    """Load latest sentiment analysis report for a specific client."""
    report_path = ROOT / "data" / "clients" / client_name / "reports" / "community-sentiment-analysis.json"
    if report_path.exists():
        with open(report_path) as f:
            return json.load(f)
    return {}


@app.context_processor
def inject_clients():
    """Inject available clients into all templates."""
    try:
        config = load_config()
        return dict(clients=config.get("clients", {}))
    except Exception:
        return dict(clients={})


@app.route("/")
def hub():
    """Client selection hub."""
    return render_template("hub.html")


@app.route("/<client_name>/dashboard")
def index(client_name):
    """Main dashboard page."""
    validate_client(client_name)
    report = load_report(client_name)
    return render_template("index.html", client_name=client_name, report=report)


@app.route("/<client_name>/leaderboard")
def leaderboard(client_name):
    """Engagement leaderboard page."""
    validate_client(client_name)
    return render_template("leaderboard.html", client_name=client_name)


@app.route("/<client_name>/user/<user_id>")
def user_profile(client_name, user_id):
    """User profile page."""
    validate_client(client_name)
    return render_template("user_profile.html", client_name=client_name, user_id=user_id)


@app.route("/api/<client_name>/overview")
def api_overview(client_name):
    """High-level stats for dashboard cards."""
    validate_client(client_name)
    db = get_db(client_name)

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
        "report_meta": report.get("meta", {}) if (report := load_report(client_name)) else {}
    })


@app.route("/api/<client_name>/sentiment/timeseries")
def api_sentiment_timeseries(client_name):
    """Time-series sentiment data for charts."""
    validate_client(client_name)
    db = get_db(client_name)

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
    report = load_report(client_name)

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


@app.route("/api/<client_name>/sentiment/by_channel")
def api_sentiment_by_channel(client_name):
    """Sentiment breakdown by channel."""
    validate_client(client_name)
    report = load_report(client_name)
    return jsonify(report.get("sentiment", {}).get("by_channel", {}))


@app.route("/api/<client_name>/topics")
def api_topics(client_name):
    """Topic-level sentiment."""
    validate_client(client_name)
    report = load_report(client_name)
    return jsonify(report.get("topic_sentiment", {}))


@app.route("/api/<client_name>/power_words")
def api_power_words(client_name):
    """Community power words."""
    validate_client(client_name)
    report = load_report(client_name)
    return jsonify(report.get("power_words", {}))


@app.route("/api/<client_name>/engagement")
def api_engagement(client_name):
    """Engagement metrics."""
    validate_client(client_name)
    report = load_report(client_name)
    return jsonify(report.get("engagement", {}))


@app.route("/api/<client_name>/contributors")
def api_contributors(client_name):
    """Top contributors."""
    validate_client(client_name)
    report = load_report(client_name)
    return jsonify(report.get("top_contributors", []))


@app.route("/api/<client_name>/negative_messages")
def api_negative_messages(client_name):
    """Top negative messages."""
    validate_client(client_name)
    report = load_report(client_name)
    return jsonify(report.get("top_negative", []))


@app.route("/api/<client_name>/positive_messages")
def api_positive_messages(client_name):
    """Top positive messages."""
    validate_client(client_name)
    report = load_report(client_name)
    return jsonify(report.get("top_positive", []))


@app.route("/api/<client_name>/purpose")
def api_purpose(client_name):
    """Purpose classification."""
    validate_client(client_name)
    report = load_report(client_name)
    return jsonify(report.get("purpose", {}))


@app.route("/api/clients")
def api_get_clients():
    """Return all clients."""
    config = config_mgr.load()
    return jsonify({"clients": config.get("clients", {})})


@app.route("/api/clients", methods=["POST"])
def api_create_client():
    """Create a new client."""
    data = request.json
    client_id = data.get("client_id")
    name = data.get("name")

    if not client_id or not all(c.isalnum() or c in "-_" for c in client_id):
        return jsonify({"success": False, "error": "Invalid client_id"}), 400

    config = config_mgr.load()
    if client_id in config.get("clients", {}):
        return jsonify({"success": False, "error": "Client already exists"}), 400

    config.setdefault("clients", {})[client_id] = {
        "name": name,
        "reddit": {"subreddits": {}},
        "discord": {"servers": {}}
    }
    config_mgr.save(config)
    load_config.cache_clear()
    return jsonify({"success": True})


@app.route("/api/clients/<client_name>/update", methods=["POST"])
def api_update_client_config(client_name):
    """Update an existing client's configuration."""
    validate_client(client_name)
    new_client_config = request.json

    config = config_mgr.load()
    config["clients"][client_name] = new_client_config
    config_mgr.save(config)
    load_config.cache_clear()
    return jsonify({"success": True})


@app.route("/api/<client_name>/reddit/comparison")
def api_reddit_comparison(client_name):
    """Reddit vs Discord comparison."""
    validate_client(client_name)
    report = load_report(client_name)
    return jsonify(report.get("sentiment", {}).get("reddit_comparison", {}))


@app.route("/api/<client_name>/raw_messages")
def api_raw_messages(client_name):
    """Raw messages for detailed view with filters."""
    validate_client(client_name)
    db = get_db(client_name)

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


@app.route("/api/<client_name>/channels")
def api_channels(client_name):
    """List all channels with stats."""
    validate_client(client_name)
    db = get_db(client_name)

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

@app.route("/api/<client_name>/cuebot/engagement/score")
def api_cuebot_engagement_score(client_name):
    """Get engagement scores for all users across platforms.
    
    Returns a ranked list of users with composite engagement scores
    based on message count, reactions, replies, sentiment, and recency.
    """
    validate_client(client_name)
    db = get_db(client_name)

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


@app.route("/api/<client_name>/cuebot/engagement/leaderboard")
def api_cuebot_leaderboard(client_name):
    """Get top N users by engagement score."""
    validate_client(client_name)
    limit = min(int(request.args.get("limit", 50)), 200)
    platform = request.args.get("platform")

    db = get_db(client_name)

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


@app.route("/api/<client_name>/cuebot/engagement/user/<user_id>")
def api_cuebot_user_profile(client_name, user_id):
    """Get detailed engagement profile for a specific user."""
    validate_client(client_name)
    db = get_db(client_name)

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


@app.route("/api/<client_name>/cuebot/engagement/crossref")
def api_cuebot_crossref(client_name):
    """Get cross-references between Discord and Reddit users."""
    validate_client(client_name)
    db = get_db(client_name)

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


@app.route("/api/<client_name>/trigger/<command>", methods=["POST"])
def api_trigger_task(client_name, command):
    """Trigger a background task for a client."""
    validate_client(client_name)
    if command not in ["collect", "analyze", "report"]:
        return jsonify({"success": False, "error": "Invalid command"}), 400

    from src.db.queue import enqueue_task
    # Enqueue with standard args
    enqueue_task(client_name, command, {"client": client_name})
    return jsonify({"success": True})


@app.route("/queue")
def queue_view():
    return render_template("queue.html", client_name=None)


@app.route("/api/queue/status")
def api_queue_status():
    from src.db.queue import get_queue_db
    db = get_queue_db()
    tasks = db.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT 50").fetchall()
    db.close()
    return jsonify([dict(t) for t in tasks])


@app.route("/api/queue/retry/<int:task_id>", methods=["POST"])
def api_queue_retry(task_id):
    try:
        from src.db.queue import get_queue_db
        db = get_queue_db()
        db.execute("UPDATE tasks SET status='pending', error_log=NULL, started_at=NULL, finished_at=NULL WHERE id=?", (task_id,))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def run_dashboard(client_name=None):
    app.run(host="0.0.0.0", port=5001, debug=True)

if __name__ == "__main__":
    run_dashboard()