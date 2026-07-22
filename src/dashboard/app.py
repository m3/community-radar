"""
CommunityRadar Flask Dashboard
Real-time community intelligence with time-series sentiment charts.
"""

from flask import Flask, render_template, jsonify, request, abort
import os
from pathlib import Path
import json
from datetime import datetime
from collections import defaultdict, Counter
import sys
import re

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

from src.dashboard.helpers import (
    ROOT,
    config_mgr,
    load_config,
    validate_client,
    get_db,
    int_arg,
    is_channel_owned,
    segment_filter,
    get_channel_segmentation,
    load_report,
    get_friendly_field_name,
    _calculate_engagement_score,
)

sys.path.insert(0, str(ROOT))


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
    segment = request.args.get("segment", "all")
    db = get_db(client_name)

    owned_ids, external_ids = get_channel_segmentation(client_name)

    # Determine message filter. This query has no table alias, so the column
    # is unqualified and the fragment leads with WHERE.
    msg_filter, msg_params = segment_filter(
        segment, owned_ids, external_ids, connector="WHERE", column="channel_id"
    )

    # Total messages by platform
    if msg_filter:
        platform_stats = db.execute(f"""
            SELECT platform, COUNT(*) as count
            FROM messages
            {msg_filter}
            GROUP BY platform
        """, msg_params).fetchall()
    else:
        platform_stats = db.execute("""
            SELECT platform, COUNT(*) as count
            FROM messages
            GROUP BY platform
        """).fetchall()

    # Date range
    date_range_query = "SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM messages"
    if msg_filter:
        date_range_query += msg_filter + " AND timestamp IS NOT NULL"
        date_range = db.execute(date_range_query, msg_params).fetchone()
    else:
        date_range = db.execute(date_range_query + " WHERE timestamp IS NOT NULL").fetchone()

    # Channels
    if segment == "owned":
        channels = len(owned_ids)
    elif segment == "external":
        channels = len(external_ids)
    else:
        channels = db.execute("SELECT COUNT(*) as c FROM channels").fetchone()["c"]

    # Users
    if msg_filter:
        users = db.execute(f"SELECT COUNT(DISTINCT user_id) as c FROM messages {msg_filter}", msg_params).fetchone()["c"]
    else:
        users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]

    db.close()

    # Convert row objects to dictionaries for JSON serialization
    p_stats = {r["platform"]: r["count"] for r in platform_stats}
    
    # Report metadata
    report = load_report(client_name)
    report_meta = report.get("meta", {})
    if report.get("sentiment", {}).get("overall"):
        if segment != "all":
            # Compute dynamic sentiment ratio
            from src.analysis.sentiment import classify_sentiment
            db = get_db(client_name)
            msg_query = f"SELECT content FROM messages {msg_filter} AND content IS NOT NULL AND content != ''"
            msgs = db.execute(msg_query, msg_params).fetchall()
            db.close()
            
            pos, neg = 0, 0
            for m in msgs:
                _, label = classify_sentiment(m["content"])
                if label == "positive":
                    pos += 1
                elif label == "negative":
                    neg += 1
            report_meta = {**report_meta}
            report_meta["sentiment_ratio"] = round(pos / max(neg, 1), 2)
        else:
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
    segment = request.args.get("segment", "all")
    db = get_db(client_name)

    owned_ids, external_ids = get_channel_segmentation(client_name)

    query = """
        SELECT m.timestamp, m.platform, m.content
        FROM messages m
        WHERE m.client_id = :client_id AND m.timestamp IS NOT NULL AND m.content IS NOT NULL AND m.content != ''
    """
    params = []
    seg_frag, seg_params = segment_filter(segment, owned_ids, external_ids)
    query += seg_frag
    params.extend(seg_params)

    query += " ORDER BY m.timestamp ASC"
    rows = db.execute(query, params).fetchall()
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
    report_sentiment = report.get("sentiment", {})
    if segment != "all" and "by_channel" in report_sentiment:
        config = load_config()
        client_config = config.get("clients", {}).get(client_name, {})
        reddit_config = client_config.get("reddit", {}).get("subreddits", {})
        owned_subreddits = [s.lower() for s, conf in reddit_config.items() if conf.get("owned")]
        
        filtered_by_channel = {}
        for ch, data in report_sentiment["by_channel"].items():
            owned = is_channel_owned(ch, owned_subreddits)
            if (segment == "owned" and owned) or (segment == "external" and not owned):
                filtered_by_channel[ch] = data
        report_sentiment = {**report_sentiment, "by_channel": filtered_by_channel}

    return jsonify({
        "series": {p: dict(d) for p, d in series.items()},
        "report_sentiment": report_sentiment
    })


@app.route("/api/<client_name>/sentiment/by_channel")
def api_sentiment_by_channel(client_name):
    """Sentiment breakdown by channel with ownership metadata."""
    validate_client(client_name)
    segment = request.args.get("segment", "all")
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
        is_owned = is_channel_owned(ch, owned_subreddits)
        
        if segment == "owned" and not is_owned:
            continue
        if segment == "external" and is_owned:
            continue
            
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
        is_owned = is_channel_owned(ch, owned_subreddits)
            
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
    segment = request.args.get("segment", "all")
    if segment == "all":
        report = load_report(client_name)
        return jsonify(report.get("topic_sentiment", {}))

    db = get_db(client_name)
    owned_ids, external_ids = get_channel_segmentation(client_name)

    query = """
        SELECT m.content, m.channel_id
        FROM messages m
        WHERE m.client_id = :client_id AND m.content IS NOT NULL AND m.content != ''
    """
    params = []
    seg_frag, seg_params = segment_filter(segment, owned_ids, external_ids)
    query += seg_frag
    params.extend(seg_params)

    rows = db.execute(query, params).fetchall()
    topic_rows = db.execute("SELECT name, category FROM topics").fetchall()
    topic_keywords = {r["name"]: r["category"] for r in topic_rows}
    db.close()

    from src.analysis.sentiment import classify_sentiment

    topic_sentiment = defaultdict(lambda: {"pos": 0, "neg": 0, "neu": 0, "total": 0})
    for r in rows:
        text_lower = r["content"].lower()
        score, label = classify_sentiment(r["content"])
        for topic, category in topic_keywords.items():
            if topic.lower() in text_lower:
                topic_sentiment[topic]["total"] += 1
                topic_sentiment[topic][label[:3]] += 1

    result = {
        topic: {
            "total": data["total"],
            "pos_pct": round(data["pos"] / max(data["total"], 1) * 100, 1),
            "neg_pct": round(data["neg"] / max(data["total"], 1) * 100, 1),
            "net_sentiment": round((data["pos"] - data["neg"]) / max(data["total"], 1) * 100, 1),
        }
        for topic, data in sorted(topic_sentiment.items(), key=lambda x: -x[1]["total"])[:30]
    }
    return jsonify(result)


@app.route("/api/<client_name>/power_words")
def api_power_words(client_name):
    """Community power words."""
    validate_client(client_name)
    segment = request.args.get("segment", "all")
    if segment == "all":
        report = load_report(client_name)
        return jsonify(report.get("power_words", {}))

    db = get_db(client_name)
    owned_ids, external_ids = get_channel_segmentation(client_name)

    query = """
        SELECT m.content
        FROM messages m
        WHERE m.client_id = :client_id AND m.content IS NOT NULL AND m.content != ''
    """
    params = []
    seg_frag, seg_params = segment_filter(segment, owned_ids, external_ids)
    query += seg_frag
    params.extend(seg_params)

    rows = db.execute(query, params).fetchall()
    db.close()

    from src.analysis.sentiment import extract_power_words

    all_power_words = Counter()
    for r in rows:
        pw = extract_power_words(r["content"])
        for w in pw:
            all_power_words[w] += 1

    return jsonify(dict(all_power_words.most_common(40)))


@app.route("/api/<client_name>/engagement")
def api_engagement(client_name):
    """Engagement metrics."""
    validate_client(client_name)
    segment = request.args.get("segment", "all")
    if segment == "all":
        report = load_report(client_name)
        return jsonify(report.get("engagement", {}))

    db = get_db(client_name)
    owned_ids, external_ids = get_channel_segmentation(client_name)

    query_base = """
        FROM messages m
        WHERE m.client_id = :client_id
    """
    params = []
    seg_frag, seg_params = segment_filter(segment, owned_ids, external_ids)
    query_base += seg_frag
    params.extend(seg_params)

    # Total & Avg reactions
    stats = db.execute(f"SELECT COUNT(*) as cnt, COALESCE(SUM(reactions), 0) as total_react {query_base}", params).fetchone()
    total_messages = stats["cnt"] if stats else 0
    total_reactions = stats["total_react"] if stats else 0
    avg_reactions = total_reactions / total_messages if total_messages > 0 else 0

    # Reply count
    reply_stats = db.execute(f"SELECT COUNT(*) as c {query_base} AND m.reply_to IS NOT NULL", params).fetchone()
    reply_count = reply_stats["c"] if reply_stats else 0
    reply_rate = round(reply_count / total_messages * 100, 1) if total_messages > 0 else 0

    # Active users (5+ messages)
    active_users_stats = db.execute(f"""
        SELECT COUNT(*) as c FROM (
            SELECT user_id, COUNT(*) as cnt
            {query_base}
            GROUP BY user_id
            HAVING COUNT(*) >= 5
        ) AS sub
    """, params).fetchone()
    active_users_5plus = active_users_stats["c"] if active_users_stats else 0

    db.close()

    return jsonify({
        "total_reactions": total_reactions,
        "avg_reactions_per_message": round(avg_reactions, 2),
        "reply_count": reply_count,
        "reply_rate": reply_rate,
        "active_users_5plus": active_users_5plus
    })


@app.route("/api/<client_name>/contributors")
def api_contributors(client_name):
    """Top contributors."""
    validate_client(client_name)
    segment = request.args.get("segment", "all")
    if segment == "all":
        report = load_report(client_name)
        return jsonify(report.get("top_contributors", []))

    db = get_db(client_name)
    owned_ids, external_ids = get_channel_segmentation(client_name)

    query = """
        SELECT u.display_name, COUNT(m.id) as messages, COALESCE(SUM(m.reactions), 0) as reactions_received
        FROM messages m
        JOIN users u ON (m.user_id = u.id AND m.client_id = u.client_id)
        WHERE m.client_id = :client_id
    """
    params = []
    seg_frag, seg_params = segment_filter(segment, owned_ids, external_ids)
    query += seg_frag
    params.extend(seg_params)

    query += " GROUP BY u.id, u.display_name ORDER BY messages DESC LIMIT 15"
    rows = db.execute(query, params).fetchall()
    db.close()

    result = [{"name": r["display_name"] or "unknown", "messages": r["messages"], "reactions_received": r["reactions_received"]} for r in rows]
    return jsonify(result)


@app.route("/api/<client_name>/negative_messages")
def api_negative_messages(client_name):
    """Top negative messages."""
    validate_client(client_name)
    segment = request.args.get("segment", "all")
    report = load_report(client_name)
    msgs = report.get("top_negative", [])
    if segment == "all":
        return jsonify(msgs)

    config = load_config()
    client_config = config.get("clients", {}).get(client_name, {})
    reddit_config = client_config.get("reddit", {}).get("subreddits", {})
    owned_subreddits = [s.lower() for s, conf in reddit_config.items() if conf.get("owned")]

    filtered = []
    for msg in msgs:
        ch = msg.get("channel", "")
        if is_channel_owned(ch, owned_subreddits) == (segment == "owned"):
            filtered.append(msg)
    return jsonify(filtered)


@app.route("/api/<client_name>/positive_messages")
def api_positive_messages(client_name):
    """Top positive messages."""
    validate_client(client_name)
    segment = request.args.get("segment", "all")
    report = load_report(client_name)
    msgs = report.get("top_positive", [])
    if segment == "all":
        return jsonify(msgs)

    config = load_config()
    client_config = config.get("clients", {}).get(client_name, {})
    reddit_config = client_config.get("reddit", {}).get("subreddits", {})
    owned_subreddits = [s.lower() for s, conf in reddit_config.items() if conf.get("owned")]

    filtered = []
    for msg in msgs:
        ch = msg.get("channel", "")
        if is_channel_owned(ch, owned_subreddits) == (segment == "owned"):
            filtered.append(msg)
    return jsonify(filtered)


@app.route("/api/<client_name>/purpose")
def api_purpose(client_name):
    """Purpose classification."""
    validate_client(client_name)
    segment = request.args.get("segment", "all")
    if segment == "all":
        report = load_report(client_name)
        return jsonify(report.get("purpose", {}))

    db = get_db(client_name)
    owned_ids, external_ids = get_channel_segmentation(client_name)

    query = """
        SELECT m.content
        FROM messages m
        WHERE m.client_id = :client_id AND m.content IS NOT NULL AND m.content != ''
    """
    params = []
    seg_frag, seg_params = segment_filter(segment, owned_ids, external_ids)
    query += seg_frag
    params.extend(seg_params)

    rows = db.execute(query, params).fetchall()
    db.close()

    from src.analysis.sentiment import classify_purpose

    purpose_dist = Counter()
    for r in rows:
        purpose = classify_purpose(r["content"])
        purpose_dist[purpose] += 1

    total = len(rows)
    distribution = {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in purpose_dist.most_common()} if total > 0 else {}
    return jsonify({
        "distribution": distribution,
        "by_channel": {}
    })


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
    limit = int_arg("limit", 100, maximum=500)
    offset = int_arg("offset", 0)
    segment = request.args.get("segment", "all")

    owned_ids, external_ids = get_channel_segmentation(client_name)

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

    seg_frag, seg_params = segment_filter(segment, owned_ids, external_ids)
    query += seg_frag
    params.extend(seg_params)

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


# ─── Blueprints ─────────────────────────────────────────────────────────
from src.dashboard.api_queue import bp as queue_bp
from src.dashboard.api_intel import bp as intel_bp
from src.dashboard.api_engagement import bp as engagement_bp

app.register_blueprint(queue_bp)
app.register_blueprint(intel_bp)
app.register_blueprint(engagement_bp)


def run_dashboard(client_name=None):
    """Launch the Flask development server.

    Debug mode is off unless FLASK_DEBUG is set — it leaks tracebacks with
    source and local variables to the caller. Deployments serve the `app`
    object under gunicorn instead (see docker-compose.yml).
    """
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes", "on")
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("DASHBOARD_PORT", 5001))
    app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    run_dashboard()