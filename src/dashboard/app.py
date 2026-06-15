"""
CommunityRadar Flask Dashboard
Real-time community intelligence with time-series sentiment charts.
"""

from flask import Flask, render_template, jsonify, request, abort
import os
from pathlib import Path
import json
from datetime import datetime
from collections import defaultdict
import sys

app = Flask(__name__)

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.db.models import get_db as _get_db
from src.dashboard.config_manager import ConfigManager

# Allow overriding config path for tests
CONFIG_PATH = os.environ.get("COMMUNITY_RADAR_CONFIG", str(ROOT / "config.yaml"))
config_mgr = ConfigManager(CONFIG_PATH)

def load_config():
    """Load configuration via config_mgr."""
    return config_mgr.load()

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


@app.route("/clients")
def clients_hub():
    """Client management overview."""
    return render_template("clients.html")


@app.route("/clients/<client_name>/edit")
def client_edit(client_name):
    """Form-based configuration editor for a specific client."""
    validate_client(client_name)
    config = load_config()
    client_config = config["clients"][client_name]
    return render_template("client_edit.html", client_name=client_name, config=client_config)


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
    return jsonify({"success": True})


@app.route("/api/clients/<client_name>/update", methods=["POST"])
def api_update_client_config(client_name):
    """Update an existing client's configuration with basic validation."""
    validate_client(client_name)
    data = request.json
    
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid payload format"}), 400
        
    # Basic structure check
    if "name" not in data or not data["name"]:
        return jsonify({"success": False, "error": "Client name is required"}), 400
        
    if "reddit" not in data or not isinstance(data["reddit"], dict):
        return jsonify({"success": False, "error": "Missing or invalid reddit config"}), 400
        
    if "discord" not in data or not isinstance(data["discord"], dict):
        return jsonify({"success": False, "error": "Missing or invalid discord config"}), 400

    # Ensure subreddits and servers are dicts
    if not isinstance(data["reddit"].get("subreddits"), dict):
        return jsonify({"success": False, "error": "Invalid subreddits format"}), 400
    if not isinstance(data["discord"].get("servers"), dict):
        return jsonify({"success": False, "error": "Invalid discord servers format"}), 400

    config = config_mgr.load()
    config["clients"][client_name] = data
    config_mgr.save(config)
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

    # Flag external mentions
    config = config_mgr.load()
    client_config = config.get("clients", {}).get(client_name, {})
    keywords = []
    external_prefixes = []
    subreddits_config = client_config.get("reddit", {}).get("subreddits", {})
    for sub, sub_conf in subreddits_config.items():
        if "track_keywords" in sub_conf and sub_conf["track_keywords"]:
            keywords.extend(sub_conf["track_keywords"])
            external_prefixes.append(f"reddit_{sub.lower()}")
            
    keywords = list(set([k.lower() for k in keywords]))
    
    result_rows = []
    for r in rows:
        r_dict = dict(r)
        r_dict["is_external_mention"] = False
        
        channel_name = (r_dict.get("channel_name") or "").lower()
        if any(channel_name.startswith(p) for p in external_prefixes):
            content_lower = (r_dict.get("content") or "").lower()
            if any(kw in content_lower for kw in keywords):
                r_dict["is_external_mention"] = True
                
        result_rows.append(r_dict)

    return jsonify(result_rows)


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


@app.route("/api/<client_name>/market/awareness")
def api_market_awareness(client_name):
    """Calculate Market Penetration and volume stats."""
    validate_client(client_name)
    config = config_mgr.load()
    client_config = config.get("clients", {}).get(client_name, {})
    
    # 1. Gather keywords and identify external subreddits
    keywords = []
    subreddits_config = client_config.get("reddit", {}).get("subreddits", {})
    external_channels = []
    for sub, sub_conf in subreddits_config.items():
        if "track_keywords" in sub_conf and sub_conf["track_keywords"]:
            keywords.extend(sub_conf["track_keywords"])
            # Channel name format in DB is like reddit_billiards_hot
            external_channels.append(f"reddit_{sub.lower()}_%")
    
    keywords = list(set(keywords)) # Deduplicate
    db = get_db(client_name)
    
    total_external = 0
    external_mentions = 0
    
    if external_channels:
        channel_filters = " OR ".join(["c.name LIKE ?" for _ in external_channels])
        
        # Total External Volume
        total_external = db.execute(f"""
            SELECT COUNT(*) FROM messages m
            JOIN channels c ON m.channel_id = c.id
            WHERE {channel_filters}
        """, external_channels).fetchone()[0]
        
        # External Mentions (Brand Blips)
        if keywords:
            kw_filters = " OR ".join(["m.content LIKE ?" for _ in keywords])
            params = external_channels + [f"%{k}%" for k in keywords]
            external_mentions = db.execute(f"""
                SELECT COUNT(*) FROM messages m
                JOIN channels c ON m.channel_id = c.id
                WHERE ({channel_filters}) AND ({kw_filters})
            """, params).fetchone()[0]

    # 2. Total Owned Volume (Everything else)
    if external_channels:
        not_channel_filters = " AND ".join(["c.name NOT LIKE ?" for _ in external_channels])
        total_owned = db.execute(f"""
            SELECT COUNT(*) FROM messages m
            JOIN channels c ON m.channel_id = c.id
            WHERE {not_channel_filters}
        """, external_channels).fetchone()[0]
    else:
        total_owned = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    db.close()
    
    penetration_score = (external_mentions / max(total_external, 1)) * 100
    
    return jsonify({
        "market_volume": total_external,
        "external_mentions": external_mentions,
        "penetration_score": round(penetration_score, 2),
        "owned_volume": total_owned
    })


# ─── Cuebot Engagement Scoring Logic ────────────────────────────────────

def _calculate_engagement_score(row, now):
    """Internal helper to calculate engagement score for a user row.
    
    Weights: messages 30%, reactions 25%, replies 20%, sentiment 15%, recency 10%
    """
    last_active = row["last_seen"]
    recency = 0
    if last_active:
        try:
            last_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
            days_ago = (now - last_dt).days
            recency = max(0, 1 - days_ago / 90)  # Decay over 90 days
        except Exception:
            recency = 0

    msg_score = min(row["total_messages"] / 500, 1) * 30  # Cap at 500 messages
    reaction_score = min(row["reactions_received"] / 200, 1) * 25  # Cap at 200 reactions
    reply_score = min(row["reply_count"] / 100, 1) * 20  # Cap at 100 replies
    sent_score = (row["sentiment_score"] + 1) / 2 * 15  # -1 to 1 → 0 to 15
    recency_score = recency * 10

    total_score = msg_score + reaction_score + reply_score + sent_score + recency_score
    
    return {
        "engagement_score": round(total_score, 2),
        "score_breakdown": {
            "messages": round(msg_score, 2),
            "reactions": round(reaction_score, 2),
            "replies": round(reply_score, 2),
            "sentiment": round(sent_score, 2),
            "recency": round(recency_score, 2)
        }
    }


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
        calc = _calculate_engagement_score(r, now)
        
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
            "engagement_score": calc["engagement_score"],
            "score_breakdown": calc["score_breakdown"]
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
    """Get top N users by engagement score with optimized aggregation."""
    validate_client(client_name)
    limit = min(int(request.args.get("limit", 50)), 200)
    platform = request.args.get("platform")

    db = get_db(client_name)

    # 1. Aggregate message stats first to avoid slow subqueries
    query = """
        WITH user_stats AS (
            SELECT 
                user_id,
                COUNT(*) as msg_count,
                platform
            FROM messages
            GROUP BY user_id
        ),
        reply_counts AS (
            SELECT m1.user_id, COUNT(*) as count
            FROM messages m1
            JOIN messages m2 ON m1.message_id = m2.reply_to
            GROUP BY m1.user_id
        )
        SELECT 
            u.id as user_id,
            u.display_name,
            u.username,
            us.msg_count as total_messages,
            u.reactions_received,
            u.last_seen,
            COALESCE(u.sentiment, 0) as sentiment_score,
            us.platform,
            COALESCE(rc.count, 0) as reply_count
        FROM users u
        JOIN user_stats us ON u.id = us.user_id
        LEFT JOIN reply_counts rc ON u.id = rc.user_id
        WHERE us.msg_count > 0
    """
    params = []

    if platform:
        query += " AND us.platform = ?"
        params.append(platform)

    rows = db.execute(query, params).fetchall()

    now = datetime.now()
    scores = []
    for r in rows:
        calc = _calculate_engagement_score(r, now)

        scores.append({
            "user_id": r["user_id"],
            "display_name": r["display_name"],
            "username": r["username"],
            "platform": r["platform"],
            "engagement_score": calc["engagement_score"],
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

    # Linked identities (Heuristic Engine)
    linked = db.execute("""
        SELECT cr.*, u2.display_name as other_name
        FROM cross_references cr
        LEFT JOIN users u2 ON (cr.user_id != ? AND (cr.username1 = u2.username OR cr.username2 = u2.username))
        WHERE cr.user_id = ? OR cr.username1 = ? OR cr.username2 = ?
    """, (user_id, user_id, user["username"], user["username"], user["username"])).fetchall()

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
        "recent_messages": [dict(m) for m in messages],
        "linked_identities": [dict(l) for l in linked]
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