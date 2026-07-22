"""Shared helpers for the dashboard blueprints.

Pure request/config/DB helpers with no route registration, imported by the
blueprint modules and re-exported from app.py for backwards compatibility.
"""

import os
import json
from pathlib import Path
from datetime import datetime

from flask import request, abort

from src.db.models import get_db as _get_db
from src.dashboard.config_manager import ConfigManager

ROOT = Path(__file__).parent.parent.parent

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


def int_arg(name, default, maximum=None, minimum=0):
    """Read a non-negative integer query parameter.

    Bare int() on request.args raises ValueError on anything non-numeric,
    which surfaces as an unhandled 500. Anything the caller controls should
    fail as a 400 instead.
    """
    raw = request.args.get(name)
    if raw is None or raw == "":
        value = default
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            abort(400, f"{name} must be an integer")
    if value < minimum:
        abort(400, f"{name} must be >= {minimum}")
    if maximum is not None:
        value = min(value, maximum)
    return value


def is_channel_owned(ch_name, owned_subreddits):
    ch_name_lower = ch_name.lower()
    if ch_name_lower.startswith("reddit-"):
        parts = ch_name_lower.split("-")
        if len(parts) > 1 and parts[1].lower() in owned_subreddits:
            return True
        return False
    elif ch_name_lower.startswith("reddit_"):
        parts = ch_name_lower.split("_")
        if len(parts) > 1 and parts[1].lower() in owned_subreddits:
            return True
        return False
    elif not ch_name_lower.startswith("reddit"):
        return True
    return False


def segment_filter(segment, owned_ids, external_ids, connector="AND", column="m.channel_id"):
    """SQL fragment + params restricting rows to a client's owned/external channels.

    Returns ("", []) for the 'all' segment (or any unrecognised value). An empty
    id list becomes '<connector> 1=0' so the segment deliberately matches no rows
    rather than silently matching everything.
    """
    if segment == "owned":
        ids = owned_ids
    elif segment == "external":
        ids = external_ids
    else:
        return "", []
    if not ids:
        return f" {connector} 1=0", []
    placeholders = ", ".join("?" for _ in ids)
    return f" {connector} {column} IN ({placeholders})", list(ids)


def get_channel_segmentation(client_name):
    """
    Returns (owned_channel_ids, external_channel_ids) for the client.
    """
    config = load_config()
    client_config = config.get("clients", {}).get(client_name, {})
    reddit_config = client_config.get("reddit", {}).get("subreddits", {})
    owned_subreddits = [s.lower() for s, conf in reddit_config.items() if conf.get("owned")]

    db = get_db(client_name)
    rows = db.execute("SELECT id, name FROM channels").fetchall()
    db.close()

    owned_ids = []
    external_ids = []

    for r in rows:
        # Support fallback keys to be resilient to mock DB connections in unit tests
        ch_id = r.get("id") or r.get("channel_id")
        ch_name = r.get("name") or r.get("channel_name")
        if not ch_id or not ch_name:
            continue

        if is_channel_owned(ch_name, owned_subreddits):
            owned_ids.append(ch_id)
        else:
            external_ids.append(ch_id)

    return owned_ids, external_ids


def load_report(client_name):
    """Load latest sentiment analysis report for a specific client."""
    report_path = ROOT / "data" / "clients" / client_name / "reports" / "community-sentiment-analysis.json"
    if report_path.exists():
        with open(report_path) as f:
            return json.load(f)
    return {}


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
