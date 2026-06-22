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

# Register custom JSON provider to serialize datetime/date objects as ISO strings
from datetime import date, datetime
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

try:
    from flask.json.provider import DefaultJSONProvider
    class CustomJSONProvider(DefaultJSONProvider):
        def dumps(self, obj, **kwargs):
            return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)
        def loads(self, s, **kwargs):
            return json.loads(s, **kwargs)
    app.json = CustomJSONProvider(app)
except ImportError:
    app.json_encoder = CustomJSONEncoder

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


import secrets

@app.context_processor
def inject_clients():
    """Inject available clients into all templates."""
    try:
        config = load_config()
        return dict(clients=config.get("clients", {}))
    except Exception:
        return dict(clients={})


@app.before_request
def csrf_protect():
    if app.config.get("TESTING"):
        return
    if request.method in ["POST", "PUT", "DELETE"]:
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            return jsonify({"success": False, "error": "CSRF Token missing or invalid"}), 403


@app.after_request
def set_csrf_cookie(response):
    if app.config.get("TESTING"):
        return response
    if not request.cookies.get("csrf_token"):
        token = secrets.token_urlsafe(32)
        response.set_cookie("csrf_token", token, httponly=False, samesite="Lax")
    return response


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

    # Convert row objects to dictionaries for JSON serialization
    p_stats = {r["platform"]: r["count"] for r in platform_stats}
    
    # Report metadata
    report = load_report(client_name)
    report_meta = report.get("meta", {})
    if report.get("sentiment", {}).get("overall"):
        report_meta["sentiment_ratio"] = report["sentiment"]["overall"].get("sentiment_ratio", 0)
        report_meta["generated_at"] = report["meta"].get("generated_at")

    return jsonify({
        "platforms": p_stats,
        "date_range": {"from": str(date_range["min_ts"])[:10] if date_range and date_range["min_ts"] else "N/A",
                       "to": str(date_range["max_ts"])[:10] if date_range and date_range["max_ts"] else "N/A"},
        "channels": channels,
        "users": users,
        "report_meta": report_meta
    })


@app.route("/api/<client_name>/sentiment/timeseries")
def api_sentiment_timeseries(client_name):
    """Time-series sentiment data for charts using actual lexicon model."""
    validate_client(client_name)
    db = get_db(client_name)

    rows = db.execute("""
        SELECT m.timestamp, m.platform, m.content
        FROM messages m
        WHERE m.client_id = :client_id AND m.timestamp IS NOT NULL AND m.content IS NOT NULL AND m.content != ''
        ORDER BY m.timestamp ASC
    """).fetchall()

    db.close()

    from src.analysis.sentiment import classify_sentiment

    # Build time series by platform
    series = defaultdict(lambda: defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0}))

    for r in rows:
        ts = r["timestamp"]
        if isinstance(ts, str):
            day = ts[:10]
        else:
            day = ts.strftime("%Y-%m-%d")
            
        platform = r["platform"]
        content = r["content"]
        
        _, label = classify_sentiment(content)
        
        series[platform][day][label] += 1
        series[platform][day]["total"] += 1

    report = load_report(client_name)

    return jsonify({
        "series": {p: dict(d) for p, d in series.items()},
        "report_sentiment": report.get("sentiment", {})
    })


@app.route("/api/<client_name>/sentiment/by_channel")
def api_sentiment_by_channel(client_name):
    """Sentiment breakdown by channel with ownership metadata."""
    validate_client(client_name)
    report = load_report(client_name)
    channel_data = report.get("sentiment", {}).get("by_channel", {})
    
    # Enrich with ownership info
    config = load_config()
    client_config = config.get("clients", {}).get(client_name, {})
    reddit_config = client_config.get("reddit", {}).get("subreddits", {})
    
    # Subreddits are 'owned' if they are explicitly marked as owned
    owned_subreddits = [s.lower() for s, conf in reddit_config.items() if conf.get("owned")]
    
    enriched = {}
    for ch, data in channel_data.items():
        is_owned = False
        if ch.startswith("reddit-"):
            # Format: reddit-SubName-sort
            parts = ch.split("-")
            if len(parts) > 1 and parts[1].lower() in owned_subreddits:
                is_owned = True
        elif not ch.startswith("reddit"):
            # Discord is always owned
            is_owned = True
            
        enriched[ch] = {**data, "is_owned": is_owned}
        
    return jsonify(enriched)


@app.route("/api/<client_name>/ecosystem")
def api_ecosystem_summary(client_name):
    """Aggregate stats and generate insights for Owned vs External channels."""
    validate_client(client_name)
    report = load_report(client_name)
    config = load_config()
    
    channel_data = report.get("sentiment", {}).get("by_channel", {})
    client_config = config.get("clients", {}).get(client_name, {})
    reddit_config = client_config.get("reddit", {}).get("subreddits", {})
    
    owned_subreddits = [s.lower() for s, conf in reddit_config.items() if conf.get("owned")]
    
    owned = {"total": 0, "positive": 0, "negative": 0}
    external = {"total": 0, "positive": 0, "negative": 0}
    
    for ch, data in channel_data.items():
        is_owned = False
        if ch.startswith("reddit-"):
            parts = ch.split("-")
            if len(parts) > 1 and parts[1].lower() in owned_subreddits:
                is_owned = True
        elif not ch.startswith("reddit"):
            is_owned = True
            
        target = owned if is_owned else external
        target["total"] += data.get("total", 0)
        target["positive"] += data.get("positive", 0)
        target["negative"] += data.get("negative", 0)
        
    owned["ratio"] = round(owned["positive"] / max(owned["negative"], 1), 2)
    external["ratio"] = round(external["positive"] / max(external["negative"], 1), 2)
    
    # Auto-Learnings Engine
    insights = []
    if external["total"] > (owned["total"] * 3):
        insights.append("External conversation volume dwarfs owned channels. Significant opportunity to convert broader market discussion into owned community members.")
    
    if owned["ratio"] > (external["ratio"] + 1.0):
        insights.append(f"Core community sentiment ({owned['ratio']}) outpaces external market ({external['ratio']}). Strong retention, but potential struggle with initial market perception.")
    elif external["ratio"] > (owned["ratio"] + 0.5) and owned["ratio"] < 4.0:
        insights.append("External sentiment is noticeably higher than owned channels. Core players may be experiencing burnout or specific live-ops friction.")
        
    if not insights:
        insights.append("Ecosystem is balanced. Core and external sentiment are relatively aligned.")

    return jsonify({
        "owned": owned,
        "external": external,
        "insight": insights[0] # Pick the most prominent insight
    })


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


@app.route("/api/<client_name>/help_data")
def api_help_data(client_name):
    """Provide specific metadata for the help page."""
    validate_client(client_name)
    config = load_config()
    client_config = config.get("clients", {}).get(client_name, {})
    report = load_report(client_name)
    
    return jsonify({
        "client_name": client_name,
        "client_config": client_config,
        "report_meta": report.get("meta", {}),
        "db_status": "Connected (Postgres)"
    })

@app.route("/<client_name>/help")
def help_guide(client_name):
    """Serve the Mission Control Guide with client-specific context."""
    validate_client(client_name)
    return render_template("help.html", client_name=client_name)


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


def get_friendly_field_name(loc):
    if not loc:
        return "Configuration"
    
    parts = []
    i = 0
    while i < len(loc):
        key = str(loc[i])
        if key == "name" and len(loc) == 1:
            parts.append("Client Display Name")
        elif key == "reddit":
            parts.append("Reddit")
            if i + 1 < len(loc) and str(loc[i+1]) == "subreddits":
                parts.append("Subreddits")
                if i + 2 < len(loc):
                    parts.append(f'"{loc[i+2]}"')
                    i += 2
                i += 1
            elif i + 1 < len(loc) and str(loc[i+1]) == "domain_monitoring":
                parts.append("Domain Monitoring")
                if i + 2 < len(loc):
                    field = str(loc[i+2]).replace("_", " ").title()
                    parts.append(field)
                    i += 2
                i += 1
        elif key == "discord":
            parts.append("Discord")
            if i + 1 < len(loc) and str(loc[i+1]) == "servers":
                parts.append("Servers")
                if i + 2 < len(loc):
                    parts.append(f'Server "{loc[i+2]}"')
                    if i + 3 < len(loc) and str(loc[i+3]) == "channels":
                        parts.append("Channels")
                        if i + 4 < len(loc):
                            parts.append(f'Channel "{loc[i+4]}"')
                            i += 4
                        i += 3
                    i += 2
                i += 1
        else:
            parts.append(key.replace("_", " ").title())
        i += 1
    
    return " -> ".join(parts)


@app.route("/api/clients/<client_name>/update", methods=["POST"])
def api_update_client_config(client_name):
    """Update an existing client's configuration with basic validation."""
    validate_client(client_name)
    data = request.json
    
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid payload format"}), 400
        
    from pydantic import ValidationError
    from src.dashboard.validation import ClientConfigSchema
    
    # 1. Load old config to preserve existing 'owned' flags
    old_config = config_mgr.load()
    old_client_config = old_config.get("clients", {}).get(client_name, {})
    old_subreddits = old_client_config.get("reddit", {}).get("subreddits", {})
    
    # 2. Inject existing 'owned' flags into the new data before validating
    if "reddit" in data and isinstance(data["reddit"], dict) and "subreddits" in data["reddit"] and isinstance(data["reddit"]["subreddits"], dict):
        for sub_name, sub_conf in data["reddit"]["subreddits"].items():
            if isinstance(sub_conf, dict) and sub_name in old_subreddits:
                sub_conf["owned"] = old_subreddits[sub_name].get("owned", False)
                
    try:
        # 3. Perform Pydantic validation
        validated_data = ClientConfigSchema.model_validate(data)
    except ValidationError as e:
        details = []
        for err in e.errors():
            details.append({
                "field": get_friendly_field_name(err["loc"]),
                "message": err["msg"]
            })
        return jsonify({
            "success": False,
            "error": "Validation failed",
            "details": details
        }), 400

    config = config_mgr.load()
    config["clients"][client_name] = validated_data.model_dump()
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
        LEFT JOIN users u ON (m.user_id = u.id AND m.client_id = u.client_id)
        WHERE m.client_id = :client_id AND m.content IS NOT NULL AND m.content != ''
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
    subreddits_config = client_config.get("reddit", {}).get("subreddits", {})
    
    # Map external subreddit name (lowercase) to its specific track_keywords
    subreddit_keywords = {}
    for sub, sub_conf in subreddits_config.items():
        if not sub_conf.get("owned"):
            if "track_keywords" in sub_conf and sub_conf["track_keywords"]:
                kws = [k.lower() for k in sub_conf["track_keywords"]]
                subreddit_keywords[sub.lower()] = kws
            
    result_rows = []
    for r in rows:
        r_dict = dict(r)
        r_dict["is_external_mention"] = False
        
        channel_name = (r_dict.get("channel_name") or "").lower()
        sub_name = None
        if channel_name.startswith("reddit-"):
            parts = channel_name.split("-")
            if len(parts) > 1:
                sub_name = parts[1]
        elif channel_name.startswith("reddit_"):
            parts = channel_name.split("_")
            if len(parts) > 1:
                sub_name = parts[1]
                
        if sub_name and sub_name in subreddit_keywords:
            content_lower = (r_dict.get("content") or "").lower()
            kws = subreddit_keywords[sub_name]
            if any(kw in content_lower for kw in kws):
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
    
    # 1. Identify external subreddits and their specific keywords
    subreddits_config = client_config.get("reddit", {}).get("subreddits", {})
    external_subs = {}
    for sub, sub_conf in subreddits_config.items():
        if not sub_conf.get("owned"):
            kws = sub_conf.get("track_keywords") or []
            external_subs[sub.lower()] = [k.lower() for k in kws]
            
    db = get_db(client_name)
    
    total_external = 0
    external_mentions = 0
    
    if external_subs:
        channel_likes = [f"reddit%{sub}%" for sub in external_subs.keys()]
        channel_filters = " OR ".join(["LOWER(c.name) LIKE ?" for _ in channel_likes])
        
        # Total External Volume
        total_external_row = db.execute(f"""
            SELECT COUNT(*) as count FROM messages m
            JOIN channels c ON m.channel_id = c.id
            WHERE m.client_id = :client_id AND ({channel_filters})
        """, channel_likes).fetchone()
        total_external = total_external_row["count"] if total_external_row else 0
        
        # External Mentions (Brand Blips)
        mention_clauses = []
        mention_params = []
        for sub, kws in external_subs.items():
            if kws:
                kw_likes = [f"%{k}%" for k in kws]
                kw_or = " OR ".join(["LOWER(m.content) LIKE ?" for _ in kw_likes])
                mention_clauses.append(f"(LOWER(c.name) LIKE ? AND ({kw_or}))")
                mention_params.append(f"reddit%{sub}%")
                mention_params.extend(kw_likes)
                
        if mention_clauses:
            mentions_filter = " OR ".join(mention_clauses)
            external_mentions_row = db.execute(f"""
                SELECT COUNT(*) as count FROM messages m
                JOIN channels c ON m.channel_id = c.id
                WHERE m.client_id = :client_id AND ({mentions_filter})
            """, mention_params).fetchone()
            external_mentions = external_mentions_row["count"] if external_mentions_row else 0

    # 2. Total Owned Volume (Everything else)
    if external_subs:
        channel_likes = [f"reddit%{sub}%" for sub in external_subs.keys()]
        not_channel_filters = " AND ".join(["LOWER(c.name) NOT LIKE ?" for _ in channel_likes])
        total_owned_row = db.execute(f"""
            SELECT COUNT(*) as count FROM messages m
            JOIN channels c ON m.channel_id = c.id
            WHERE m.client_id = :client_id AND ({not_channel_filters})
        """, channel_likes).fetchone()
        total_owned = total_owned_row["count"] if total_owned_row else 0
    else:
        total_owned_row = db.execute("SELECT COUNT(*) as count FROM messages WHERE client_id = :client_id").fetchone()
        total_owned = total_owned_row["count"] if total_owned_row else 0

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
            if isinstance(last_active, str):
                last_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
            else:
                last_dt = last_active
                
            days_ago = (now - last_dt).days
            recency = max(0, 1 - days_ago / 90)  # Decay over 90 days
        except Exception:
            recency = 0

    msg_score = min(row["total_messages"] / 500, 1) * 30  # Cap at 500 messages
    reaction_score = min(row["reactions_received"] / 200, 1) * 25  # Cap at 200 reactions
    reply_score = min(row["reply_count"] / 100, 1) * 20  # Cap at 100 replies
    
    # Handle potentially string or null sentiment
    raw_sent = row["sentiment_score"]
    try:
        sent_val = float(raw_sent) if raw_sent is not None else 0
    except (ValueError, TypeError):
        sent_val = 0
        
    sent_score = (sent_val + 1) / 2 * 15  # -1 to 1 → 0 to 15
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
            COALESCE(NULLIF(u.sentiment, '')::numeric, 0) as sentiment_score,
            (SELECT platform FROM messages WHERE user_id = u.id AND client_id = :client_id LIMIT 1) as platform,
            (SELECT COUNT(*) FROM messages WHERE reply_to IN 
                (SELECT message_id FROM messages WHERE user_id = u.id AND client_id = :client_id)
                AND client_id = :client_id
            ) as reply_count
        FROM users u
        WHERE u.messages > 0 AND u.client_id = :client_id
    """).fetchall()

    scores = []
    now = datetime.now()
    for r in rows:
        # Robustly ensure sentiment_score is a float for _calculate_engagement_score
        r_dict = dict(r)
        try:
            r_dict["sentiment_score"] = float(r_dict["sentiment_score"])
        except (ValueError, TypeError):
            r_dict["sentiment_score"] = 0.0
            
        calc = _calculate_engagement_score(r_dict, now)
        
        scores.append({
            "user_id": r_dict["user_id"],
            "display_name": r_dict["display_name"],
            "username": r_dict["username"],
            "platform": r_dict["platform"],
            "total_messages": r_dict["total_messages"],
            "reactions_received": r_dict["reactions_received"],
            "reply_count": r_dict["reply_count"],
            "sentiment_score": round(r_dict["sentiment_score"], 3),
            "last_active": r_dict["last_seen"],
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


@app.route("/<client_name>/intel")
def intel_view(client_name):
    """Market Intelligence page."""
    validate_client(client_name)
    return render_template("intel.html", client_name=client_name)


@app.route("/api/<client_name>/intel/market")
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
    """).fetchall() # Result will be mappings if LegacySessionWrapper detected SELECT
    db.close()
    
    return jsonify({
        "competitors": intel,
        "domains": [dict(d) for d in domain_stats]
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
                MAX(platform) as platform
            FROM messages
            WHERE client_id = :client_id
            GROUP BY user_id
        ),
        reply_counts AS (
            SELECT m1.user_id, COUNT(*) as count
            FROM messages m1
            JOIN messages m2 ON m1.message_id = m2.reply_to
            WHERE m1.client_id = :client_id AND m2.client_id = :client_id
            GROUP BY m1.user_id
        )
        SELECT 
            u.id as user_id,
            u.display_name,
            u.username,
            us.msg_count as total_messages,
            u.reactions_received,
            u.last_seen,
            COALESCE(NULLIF(u.sentiment, '')::numeric, 0) as sentiment_score,
            us.platform,
            COALESCE(rc.count, 0) as reply_count
        FROM users u
        JOIN user_stats us ON (u.id = us.user_id AND u.client_id = :client_id)
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
        r_dict = dict(r)
        try:
            r_dict["sentiment_score"] = float(r_dict["sentiment_score"])
        except (ValueError, TypeError):
            r_dict["sentiment_score"] = 0.0
            
        calc = _calculate_engagement_score(r_dict, now)

        scores.append({
            "user_id": r_dict["user_id"],
            "display_name": r_dict["display_name"],
            "username": r_dict["username"],
            "platform": r_dict["platform"],
            "engagement_score": calc["engagement_score"],
            "total_messages": r_dict["total_messages"],
            "reactions_received": r_dict["reactions_received"],
            "reply_count": r_dict["reply_count"],
            "sentiment_score": round(r_dict["sentiment_score"], 3),
            "last_active": r_dict["last_seen"]
        })

    scores.sort(key=lambda x: x["engagement_score"], reverse=True)
    db.close()

    return jsonify({
        "leaderboard": scores[:limit],
        "total_users": len(scores),
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
            (SELECT COUNT(*) FROM messages WHERE client_id = :client_id AND reply_to IN 
                (SELECT message_id FROM messages WHERE client_id = :client_id AND user_id = u.id)
            ) as reply_count
        FROM users u
        WHERE u.client_id = :client_id AND u.id = ?
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
         WHERE m.client_id = :client_id AND m.user_id = ? AND m.content IS NOT NULL AND m.content != ''
         ORDER BY m.timestamp DESC
         LIMIT 100
    """, (user_id,)).fetchall()

    # Channel activity
    channel_activity = db.execute("""
        SELECT c.name as channel_name, m.platform, COUNT(*) as msg_count
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        WHERE m.client_id = :client_id AND m.user_id = ?
        GROUP BY c.name, m.platform
        ORDER BY msg_count DESC
    """, (user_id,)).fetchall()

    # Cross-platform presence
    platforms = db.execute("""
        SELECT DISTINCT platform FROM messages WHERE client_id = :client_id AND user_id = ?
    """, (user_id,)).fetchall()

    # Linked identities (Heuristic Engine)
    linked = db.execute("""
        SELECT cr.*, u2.display_name as other_name
        FROM cross_references cr
        LEFT JOIN users u2 ON (u2.client_id = :client_id AND cr.user_id != ? AND (cr.username1 = u2.username OR cr.username2 = u2.username))
        WHERE cr.client_id = :client_id AND (cr.user_id = ? OR cr.username1 = ? OR cr.username2 = ?)
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
        LEFT JOIN users u1 ON (cr.client_id = u1.client_id AND cr.username1 = u1.username)
        LEFT JOIN users u2 ON (cr.client_id = u2.client_id AND cr.username2 = u2.username)
        WHERE cr.client_id = :client_id
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
    # Explicitly use text() to avoid wrapper issues if using LegacySessionWrapper
    from sqlalchemy import text
    tasks = db.session.execute(text("SELECT * FROM tasks ORDER BY id DESC LIMIT 50")).mappings().all()
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