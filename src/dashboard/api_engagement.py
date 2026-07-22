"""Cuebot engagement routes: score, leaderboard, per-user profile, cross-refs."""

from datetime import datetime

from flask import Blueprint, jsonify, request

from src.dashboard.helpers import (
    validate_client,
    get_db,
    int_arg,
    _calculate_engagement_score,
)

bp = Blueprint("engagement", __name__)


@bp.route("/api/<client_name>/cuebot/engagement/score")
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


@bp.route("/api/<client_name>/cuebot/engagement/leaderboard")
def api_cuebot_leaderboard(client_name):
    """Get top N users by engagement score with optimized aggregation."""
    validate_client(client_name)
    limit = int_arg("limit", 50, maximum=200)
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


@bp.route("/api/<client_name>/cuebot/engagement/user/<user_id>")
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


@bp.route("/api/<client_name>/cuebot/engagement/crossref")
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
