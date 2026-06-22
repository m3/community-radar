"""
Sentiment analysis runner that bypasses the ORM's client_id injection.
Directly uses the SQLite database at data/community_radar.db.
"""
import sqlite3
import json
import sys
import os

# Add project root to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Import the analysis functions from the real script
from src.analysis.sentiment import (
    run_analysis as original_run_analysis,
    classify_sentiment,
    classify_purpose,
    extract_power_words,
    deduplicate_reddit,
    compute_weekly_trends,
    detect_anomalies,
)

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import statistics

WEEKS_IN_TREND = 8
ANOMALY_THRESHOLD = 2.0


class DirectSQLiteDB:
    """Direct SQLite connection that mimics the LegacySessionWrapper interface."""
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def execute(self, sql, params=None):
        # Remove client_id filtering — the SQLite DB doesn't have this column
        # Strip any client_id WHERE conditions
        sql_clean = re.sub(
            r'\s*(?:AND\s+)?(?:[\w.]+\.)?client_id\s*=\s*(?::\w+|\?)\s*',
            ' ',
            sql,
            flags=re.IGNORECASE
        )
        # Also remove client_id from JOIN conditions
        sql_clean = re.sub(
            r'\s*(?:AND\s+)?(?:[\w.]+\.)?client_id\s*=\s*(?::\w+|\?)\s*',
            ' ',
            sql_clean,
            flags=re.IGNORECASE
        )

        if params is None:
            params = {}

        # Remove client_id from params if present
        params_clean = {k: v for k, v in params.items() if k != 'client_id'}

        cur = self.conn.execute(sql_clean, params_clean)
        return cur.fetchall()

    def close(self):
        self.conn.close()


def main():
    db_path = os.path.join("/Users/mathias/Development/Projects/community-radar", "data", "community_radar.db")
    output_dir = Path(os.path.join("/Users/mathias/Development/Projects/community-radar", "docs"))
    output_dir.mkdir(parents=True, exist_ok=True)

    db = DirectSQLiteDB(db_path)
    print(f"Connected to SQLite DB: {db_path}")

    # Import and run the analysis with our direct DB
    # We need to call a modified version that doesn't filter by client_id
    report = run_analysis_direct(db, output_dir)

    db.close()
    if report:
        print("\n✅ Analysis complete.")


def run_analysis_direct(db, output_dir):
    """Run analysis using direct SQLite connection (no client_id)."""
    import hashlib

    POSITIVE_WORDS = {
        "good", "great", "awesome", "amazing", "excellent", "fantastic", "brilliant",
        "love", "loved", "like", "enjoy", "enjoyed", "fun", "nice", "cool", "solid",
        "impressive", "beautiful", "smooth", "clean", "perfect", "best", "better",
        "improved", "improvement", "progress", "win", "won", "winner", "winning",
        "congrats", "congratulations", "well done", "gg", "nice shot", "clean shot",
        "thanks", "thank", "appreciate", "helpful", "welcome", "friendly", "active",
        "engaged", "supportive", "recommended", "recommend", "addictive", "addicted",
        "realistic", "physics", "authentic", "immersive", "satisfying", "responsive",
        "intuitive", "polished", "refined", "balanced", "fair", "competitive",
        "rewarding", "challenging", "depth", "detailed", "quality", "premium",
        "lol", "lmao", "haha",
    }

    NEGATIVE_WORDS = {
        "bug", "bugs", "buggy", "glitch", "glitches", "broken", "crash", "crashes",
        "crashing", "freeze", "freezes", "freezing", "lag", "laggy", "lags", "latency",
        "stutter", "stuttering", "desync", "desyncs", "disconnect", "disconnects",
        "disconnected", "dc", "error", "errors", "fail", "failed", "failing",
        "issue", "issues", "problem", "problems", "wrong", "incorrect", "unfair",
        "bad", "terrible", "horrible", "awful", "worst", "worse", "hate", "hated",
        "annoying", "annoyed", "frustrating", "frustrated", "frustration", "angry",
        "disappointed", "disappointing", "disappointment", "sad", "sorry", "unfortunate",
        "unfortunately", "ridiculous", "pathetic", "useless", "garbage", "trash",
        "waste", "wasted", "dead", "dying", "abandoned", "neglected", "forgotten",
        "unbalanced", "overpowered", "underpowered", "cheap", "cheesy", "exploit",
        "exploiting", "hacker", "hacking", "cheating", "cheater", "toxic", "grief",
        "griefing", "camping", "spam", "spamming", "afk", "leaver",
        "leaving", "quit", "quitting", "ragequit",
        "missing", "lacking", "lacks",
    }

    POWER_WORDS = {
        "pure pool", "ripstone", "cue", "cueball", "cue ball", "spin", "english",
        "side spin", "top spin", "back spin", "stun", "stun shot", "screw", "screw shot",
        "follow", "follow shot", "draw", "draw shot", "bank", "bank shot", "kick",
        "kick shot", "combination", "combo", "carom", "masse", "jump shot", "jump",
        "trick shot", "trick", "practice", "training", "tutorial", "tips", "advice",
        "improve", "improvement", "skill", "technique", "position", "position play",
        "safety", "safety play", "defense", "defensive", "attack", "aggressive",
        "strategy", "strategic", "tactics", "tactical", "mental", "focus", "concentration",
        "consistency", "consistent", "precision", "accurate", "accuracy", "control",
        "power", "speed", "angle", "angles", "pocket", "pockets", "rail", "rails",
        "table", "cloth", "felt", "tip", "chalk", "bridge", "rest", "mechanical bridge",
        "8-ball", "8 ball", "9-ball", "9 ball", "10-ball", "10 ball", "straight pool",
        "one pocket", "bank pool", "snooker", "billiards", "pool", "pocket billiards",
    }

    PURPOSE_SIGNALS = {
        "competition": ["tournament", "match", "league", "ranking", "rank", "elo", "rating",
                         "compete", "competition", "competitive", "champion", "winner",
                         "final", "finals", "semi-final", "quarter-final", "bracket",
                         "seed", "seeding", "division", "tier", "promotion", "relegation"],
        "social": ["find a game", "lfg", "looking for", "anyone want", "anyone up",
                   "who wants", "who's up", "anyone else", "let's play", "dm me",
                   "add me", "friend", "friends", "group", "team", "clan", "guild",
                   "community", "meet", "meetup", "event", "gathering"],
        "support": ["help", "how do", "how to", "question", "what is", "why does",
                    "can someone", "anyone know", "tutorial", "guide", "tip", "advice",
                    "explain", "understand", "confused", "stuck", "issue", "problem"],
        "feedback": ["suggestion", "feature request", "would be nice", "should add",
                     "could add", "please add", "needs", "missing", "lacking",
                     "improve", "improvement", "update", "patch", "fix", "bug report",
                     "feedback", "opinion", "think", "feel", "prefer", "wish"],
        "showcase": ["clip", "video", "screenshot", "pot", "shot", "trick shot",
                     "amazing", "incredible", "check out", "look at", "watch",
                     "stream", "twitch", "youtube", "tiktok", "share", "posted"],
        "off_topic": ["off topic", "off-topic", "random", "anyone else", "anyone watching",
                      "anyone seen", "anyone heard", "anyone playing", "other game",
                      "different game", "another game", "switch", "moved on"],
    }

    def classify_sentiment_local(text):
        if not text:
            return 0, "neutral"
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
        neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)
        for phrase in ["well done", "nice shot", "clean shot", "good game", "gg",
                       "well played", "nice one", "love it", "great job", "thank you",
                       "thanks for", "looking forward", "can't wait", "well worth"]:
            if phrase in text_lower:
                pos_count += 2
        for phrase in ["waste of", "give up", "fed up", "sick of", "tired of",
                       "not working", "doesn't work", "still broken", "never fixed",
                       "no one", "no response", "no update", "worst game", "unplayable"]:
            if phrase in text_lower:
                neg_count += 2
        score = pos_count - neg_count
        if score > 1:
            return score, "positive"
        elif score < -1:
            return score, "negative"
        else:
            return score, "neutral"

    def classify_purpose_local(text):
        if not text:
            return "unknown"
        text_lower = text.lower()
        scores = {}
        for purpose, keywords in PURPOSE_SIGNALS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[purpose] = score
        if not scores:
            return "general"
        return max(scores, key=scores.get)

    def extract_power_words_local(text):
        if not text:
            return []
        text_lower = text.lower()
        found = []
        for phrase in POWER_WORDS:
            if phrase in text_lower:
                found.append(phrase)
        return found

    def content_hash(text):
        return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]

    def deduplicate_reddit_local(messages):
        seen_hashes = set()
        deduped = []
        dup_count = 0
        sorted_msgs = sorted(messages, key=lambda m: m["timestamp"] or "")
        for msg in sorted_msgs:
            if msg["channel_name"].startswith("reddit-"):
                h = content_hash(msg["content"])
                if h in seen_hashes:
                    dup_count += 1
                    continue
                seen_hashes.add(h)
            deduped.append(msg)
        return deduped

    def compute_weekly_trends_local(messages, weeks=WEEKS_IN_TREND):
        weekly = defaultdict(lambda: {"pos": 0, "neg": 0, "neu": 0, "total": 0,
                                       "discord_pos": 0, "discord_neg": 0, "discord_neu": 0, "discord_total": 0,
                                       "reddit_pos": 0, "reddit_neg": 0, "reddit_neu": 0, "reddit_total": 0})
        for msg in messages:
            if not msg["timestamp"]:
                continue
            try:
                dt = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
            except:
                continue
            week_key = dt.strftime("%Y-W%U")
            score, label = classify_sentiment_local(msg["content"])
            weekly[week_key]["total"] += 1
            weekly[week_key][label[:3]] += 1
            platform = "discord" if not msg["channel_name"].startswith("reddit-") else "reddit"
            weekly[week_key][f"{platform}_total"] += 1
            weekly[week_key][f"{platform}_{label[:3]}"] += 1
        sorted_weeks = sorted(weekly.items())[-weeks:]
        trends = []
        for week_key, data in sorted_weeks:
            total = data["total"]
            if total == 0:
                continue
            pos_pct = data["pos"] / total * 100
            neg_pct = data["neg"] / total * 100
            neu_pct = data["neu"] / total * 100
            d_total = data["discord_total"]
            r_total = data["reddit_total"]
            d_pos_pct = data["discord_pos"] / d_total * 100 if d_total else 0
            d_neg_pct = data["discord_neg"] / d_total * 100 if d_total else 0
            r_pos_pct = data["reddit_pos"] / r_total * 100 if r_total else 0
            r_neg_pct = data["reddit_neg"] / r_total * 100 if r_total else 0
            trends.append({
                "week": week_key,
                "total": total,
                "pos_pct": round(pos_pct, 1),
                "neg_pct": round(neg_pct, 1),
                "neu_pct": round(neu_pct, 1),
                "discord_total": d_total,
                "discord_pos_pct": round(d_pos_pct, 1),
                "discord_neg_pct": round(d_neg_pct, 1),
                "reddit_total": r_total,
                "reddit_pos_pct": round(r_pos_pct, 1),
                "reddit_neg_pct": round(r_neg_pct, 1),
            })
        return trends

    def detect_anomalies_local(trends, threshold=ANOMALY_THRESHOLD):
        if len(trends) < 3:
            return []
        anomalies = []
        metrics = {
            "overall_pos_pct": [t["pos_pct"] for t in trends],
            "overall_neg_pct": [t["neg_pct"] for t in trends],
            "discord_pos_pct": [t["discord_pos_pct"] for t in trends],
            "discord_neg_pct": [t["discord_neg_pct"] for t in trends],
            "reddit_pos_pct": [t["reddit_pos_pct"] for t in trends],
            "reddit_neg_pct": [t["reddit_neg_pct"] for t in trends],
        }
        for metric_name, values in metrics.items():
            if len(values) < 3:
                continue
            for i in range(2, len(values)):
                prior = values[:i]
                mean = statistics.mean(prior)
                stdev = statistics.stdev(prior) if len(prior) > 1 else 0
                if stdev == 0:
                    continue
                current = values[i]
                z_score = abs(current - mean) / stdev
                if z_score >= threshold:
                    severity = "🔴 CRITICAL" if z_score >= 3 else ("🟠 HIGH" if z_score >= 2.5 else "🟡 MEDIUM")
                    direction = "↑ spike" if current > mean else "↓ drop"
                    anomalies.append({
                        "week": trends[i]["week"],
                        "metric": metric_name.replace("_", " ").title(),
                        "value": round(current, 1),
                        "expected": round(mean, 1),
                        "z_score": round(z_score, 2),
                        "severity": severity,
                        "direction": direction,
                        "platform": "Discord" if "discord" in metric_name else ("Reddit" if "reddit" in metric_name else "Overall"),
                    })
        anomalies.sort(key=lambda x: -x["z_score"])
        return anomalies

    # ─── MAIN ANALYSIS ─────────────────────────────────────────────────
    print("Loading messages...")
    rows = db.execute("""
        SELECT m.message_id, m.content, m.timestamp, m.reactions, m.channel_id,
               c.name as channel_name, u.display_name, u.role
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        LEFT JOIN users u ON m.user_id = u.id
        WHERE m.content IS NOT NULL AND m.content != ''
    """)
    messages = [dict(r) for r in rows]
    print(f"  {len(messages)} messages loaded")

    if not messages:
        print("No messages found in database.")
        return None

    print("\n[1/7] Sentiment analysis...")
    sentiment_dist = Counter()
    sentiment_by_channel = defaultdict(Counter)
    sentiment_by_month = defaultdict(Counter)
    negative_messages = []
    positive_messages = []
    all_power_words = Counter()
    purpose_dist = Counter()
    purpose_by_channel = defaultdict(Counter)

    for msg in messages:
        score, label = classify_sentiment_local(msg["content"])
        sentiment_dist[label] += 1
        sentiment_by_channel[msg["channel_name"]][label] += 1
        ts = msg["timestamp"]
        if ts:
            if isinstance(ts, str):
                month = ts[:7]
            else:
                month = ts.strftime("%Y-%m")
        else:
            month = "unknown"
        sentiment_by_month[month][label] += 1
        if label == "negative" and score <= -2:
            negative_messages.append({
                "channel": msg["channel_name"],
                "author": msg["display_name"] or "unknown",
                "content": msg["content"][:200],
                "score": score,
                "timestamp": ts[:10] if ts else "unknown",
            })
        elif label == "positive" and score >= 2:
            positive_messages.append({
                "channel": msg["channel_name"],
                "author": msg["display_name"] or "unknown",
                "content": msg["content"][:200],
                "score": score,
                "timestamp": ts[:10] if ts else "unknown",
            })
        pw = extract_power_words_local(msg["content"])
        for w in pw:
            all_power_words[w] += 1
        purpose = classify_purpose_local(msg["content"])
        purpose_dist[purpose] += 1
        purpose_by_channel[msg["channel_name"]][purpose] += 1

    print("\n[2/7] Deduplicating Reddit cross-posts...")
    deduped_messages = deduplicate_reddit_local(messages)
    print(f"  {len(messages)} → {len(deduped_messages)} messages ({len(messages) - len(deduped_messages)} duplicates removed)")

    print("\n[3/7] Weekly sentiment trends...")
    weekly_trends = compute_weekly_trends_local(deduped_messages, WEEKS_IN_TREND)
    print(f"  {len(weekly_trends)} weeks of trend data")

    print("\n[4/7] Anomaly detection...")
    anomalies = detect_anomalies_local(weekly_trends, ANOMALY_THRESHOLD)
    print(f"  {len(anomalies)} anomalies detected")

    print("\n[5/7] Topic-level sentiment...")
    topic_rows = db.execute("SELECT name, category FROM topics")
    topic_keywords = {r["name"]: r["category"] for r in topic_rows}
    topic_sentiment = defaultdict(lambda: {"pos": 0, "neg": 0, "neu": 0, "total": 0})
    for msg in messages:
        text_lower = msg["content"].lower()
        score, label = classify_sentiment_local(msg["content"])
        for topic, category in topic_keywords.items():
            if topic.lower() in text_lower:
                topic_sentiment[topic]["total"] += 1
                topic_sentiment[topic][label[:3]] += 1

    print("[6/7] User sentiment profiles...")
    user_sentiment = defaultdict(lambda: {"pos": 0, "neg": 0, "neu": 0, "total": 0})
    for msg in messages:
        score, label = classify_sentiment_local(msg["content"])
        uid = msg["display_name"] or "unknown"
        user_sentiment[uid]["total"] += 1
        user_sentiment[uid][label[:3]] += 1

    print("[7/7] Reddit data + engagement...")
    reddit_rows = db.execute("""
        SELECT m.content, m.reactions, m.timestamp, c.name as channel_name
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        WHERE m.platform = 'reddit' AND m.content IS NOT NULL AND m.content != ''
    """)
    reddit_messages = [dict(r) for r in reddit_rows]
    reddit_sentiment = Counter()
    reddit_by_channel = defaultdict(Counter)
    for msg in reddit_messages:
        _, label = classify_sentiment_local(msg["content"])
        reddit_sentiment[label] += 1
        reddit_by_channel[msg["channel_name"]][label] += 1
    total_reddit = len(reddit_messages)

    total_reactions_row = db.execute("SELECT SUM(reactions) as s FROM messages")
    total_reactions = total_reactions_row[0]["s"] if total_reactions_row else 0
    avg_reactions = total_reactions / len(messages) if messages else 0
    reply_row = db.execute("SELECT COUNT(*) as c FROM messages WHERE reply_to IS NOT NULL")
    reply_count = reply_row[0]["c"] if reply_row else 0
    active_users_rows = db.execute("SELECT display_name, messages, reactions_received FROM users WHERE messages >= 5 ORDER BY messages DESC LIMIT 20")
    active_users = [dict(r) for r in active_users_rows]

    # Date range
    date_range_row = db.execute("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM messages WHERE content IS NOT NULL AND content != ''")
    date_range = date_range_row[0] if date_range_row else {"min_ts": None, "max_ts": None}

    def fmt_ts(ts):
        if not ts:
            return "N/A"
        if isinstance(ts, str):
            return ts[:10]
        return ts.strftime("%Y-%m-%d")

    total = len(messages)
    deduped_total = len(deduped_messages)
    duplicates_removed = total - deduped_total
    pos_pct = sentiment_dist["positive"] / total * 100
    neg_pct = sentiment_dist["negative"] / total * 100
    neu_pct = sentiment_dist["neutral"] / total * 100

    report = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "total_messages_analyzed": total,
            "deduped_messages": deduped_total,
            "duplicates_removed": duplicates_removed,
            "channels": len(sentiment_by_channel),
            "date_range": {
                "from": fmt_ts(date_range["min_ts"]),
                "to": fmt_ts(date_range["max_ts"]),
            },
            "reddit_messages_in_db": len(reddit_messages),
        },
        "sentiment": {
            "overall": {
                "positive": {"count": sentiment_dist["positive"], "pct": round(pos_pct, 1)},
                "negative": {"count": sentiment_dist["negative"], "pct": round(neg_pct, 1)},
                "neutral": {"count": sentiment_dist["neutral"], "pct": round(neu_pct, 1)},
                "sentiment_ratio": round(sentiment_dist["positive"] / max(sentiment_dist["negative"], 1), 2),
            },
            "by_channel": {
                ch: {
                    "positive": counts["positive"],
                    "negative": counts["negative"],
                    "neutral": counts["neutral"],
                    "total": sum(counts.values()),
                    "pos_pct": round(counts["positive"] / sum(counts.values()) * 100, 1) if sum(counts.values()) else 0,
                    "neg_pct": round(counts["negative"] / sum(counts.values()) * 100, 1) if sum(counts.values()) else 0,
                }
                for ch, counts in sentiment_by_channel.items()
            },
            "reddit_comparison": {
                "positive": reddit_sentiment["positive"],
                "negative": reddit_sentiment["negative"],
                "neutral": reddit_sentiment["neutral"],
                "pos_pct": round(reddit_sentiment["positive"] / max(total_reddit, 1) * 100, 1) if total_reddit else 0,
                "neg_pct": round(reddit_sentiment["negative"] / max(total_reddit, 1) * 100, 1) if total_reddit else 0,
                "reddit_by_channel": {
                    ch: dict(counts) for ch, counts in reddit_by_channel.items()
                },
            },
        },
        "purpose": {
            "distribution": {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in purpose_dist.most_common()},
            "by_channel": {
                ch: {k: v for k, v in counts.most_common(3)}
                for ch, counts in purpose_by_channel.items()
            },
        },
        "power_words": dict(all_power_words.most_common(40)),
        "topic_sentiment": {
            topic: {
                "total": data["total"],
                "pos_pct": round(data["pos"] / max(data["total"], 1) * 100, 1),
                "neg_pct": round(data["neg"] / max(data["total"], 1) * 100, 1),
                "net_sentiment": round((data["pos"] - data["neg"]) / max(data["total"], 1) * 100, 1),
            }
            for topic, data in sorted(topic_sentiment.items(), key=lambda x: -x[1]["total"])[:30]
        },
        "top_negative": sorted(negative_messages, key=lambda x: x["score"])[:20],
        "top_positive": sorted(positive_messages, key=lambda x: -x["score"])[:20],
        "engagement": {
            "total_reactions": total_reactions,
            "avg_reactions_per_message": round(avg_reactions, 2),
            "reply_count": reply_count,
            "reply_rate": round(reply_count / total * 100, 1),
            "active_users_5plus": len(active_users),
        },
        "top_contributors": [
            {"name": u["display_name"], "messages": u["messages"], "reactions_received": u["reactions_received"]}
            for u in active_users[:15]
        ],
        "weekly_trends": weekly_trends,
        "anomalies": anomalies,
    }

    # Save JSON
    output_path = output_dir / "community-sentiment-analysis.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  JSON saved: {output_path}")

    # Generate Markdown using the original function
    from src.analysis.sentiment import generate_markdown_report
    md = generate_markdown_report(report)
    md_path = output_dir / "community-sentiment-report.md"
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Markdown saved: {md_path}")

    return report


if __name__ == "__main__":
    main()
