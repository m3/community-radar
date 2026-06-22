"""
Community Sentiment & Classification Analysis
Analyzes all Discord + Reddit content for:
1. Sentiment distribution (positive/negative/neutral)
2. Topic-level sentiment (what drives negativity vs positivity)
3. Community classification (power words, engagement patterns)
4. Gap analysis (what they want vs what they get)
5. Cross-platform comparison (Discord vs Reddit)
"""

import sqlite3
import json
import re
import hashlib
import argparse
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timedelta
import statistics
import sys

# Ensure we can import from src
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.db.models import get_db

# ─── Config ───────────────────────────────────────────────────────────────
WEEKS_IN_TREND = 8
ANOMALY_THRESHOLD = 2.0  # Standard deviations

# ─── Sentiment Lexicon (gaming/community-specific) ───────────────────────────

POSITIVE_WORDS = {
    # Achievement / skill
    "good", "great", "awesome", "amazing", "excellent", "fantastic", "brilliant",
    "love", "loved", "like", "enjoy", "enjoyed", "fun", "nice", "cool", "solid",
    "impressive", "beautiful", "smooth", "clean", "perfect", "best", "better",
    "improved", "improvement", "progress", "win", "won", "winner", "winning",
    "congrats", "congratulations", "well done", "gg", "nice shot", "clean shot",
    # Community
    "thanks", "thank", "appreciate", "helpful", "welcome", "friendly", "active",
    "engaged", "supportive", "recommended", "recommend", "addictive", "addicted",
    # Game-specific positive
    "realistic", "physics", "authentic", "immersive", "satisfying", "responsive",
    "intuitive", "polished", "refined", "balanced", "fair", "competitive",
    "rewarding", "challenging", "depth", "detailed", "quality", "premium",
    # Emoji sentiment (text equivalents)
    "lol", "lmao", "haha", "😂", "👍", "🔥", "💪", "🎯", "⭐", "❤️", "🙌", "👏",
}

NEGATIVE_WORDS = {
    # Bugs / issues
    "bug", "bugs", "buggy", "glitch", "glitches", "broken", "crash", "crashes",
    "crashing", "freeze", "freezes", "freezing", "lag", "laggy", "lags", "latency",
    "stutter", "stuttering", "desync", "desyncs", "disconnect", "disconnects",
    "disconnected", "dc", "error", "errors", "fail", "failed", "failing",
    "issue", "issues", "problem", "problems", "wrong", "incorrect", "unfair",
    # Frustration
    "bad", "terrible", "horrible", "awful", "worst", "worse", "hate", "hated",
    "annoying", "annoyed", "frustrating", "frustrated", "frustration", "angry",
    "disappointed", "disappointing", "disappointment", "sad", "sorry", "unfortunate",
    "unfortunately", "ridiculous", "pathetic", "useless", "garbage", "trash",
    "waste", "wasted", "dead", "dying", "abandoned", "neglected", "forgotten",
    # Gameplay complaints
    "unbalanced", "overpowered", "underpowered", "cheap", "cheesy", "exploit",
    "exploiting", "hacker", "hacking", "cheating", "cheater", "toxic", "grief",
    "griefing", "camping", "camping", "spam", "spamming", "afk", "leaver",
    "leaving", "quit", "quitting", "ragequit",
    # Missing / lacking
    "missing", "lacking", "lacks",
    # Negative emoji
    "😤", "😡", "🤬", "💀", "😢", "😭", "😞", "😔", "😟", "😠", "👎", "🤦",
}

# Power words that indicate community identity / passion
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

# Community purpose signals
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


def classify_sentiment(text):
    """Simple lexicon-based sentiment scoring"""
    if not text:
        return 0, "neutral"

    text_lower = text.lower()
    words = re.findall(r'\b\w+\b', text_lower)

    pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
    neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)

    # Also check multi-word phrases
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


def classify_purpose(text):
    """Classify what the message is trying to achieve"""
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


def extract_power_words(text):
    """Extract community-specific power words"""
    if not text:
        return []

    text_lower = text.lower()
    found = []
    for phrase in POWER_WORDS:
        if phrase in text_lower:
            found.append(phrase)
    return found


def content_hash(text):
    """Generate hash for deduplication"""
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]


# Unicode block elements for sparklines (low to high)
SPARKLINE_GLYPHS = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


def sparkline_for_value(value, all_values):
    """Return a single sparkline glyph representing this value's relative magnitude."""
    if not all_values:
        return "▁"
    lo, hi = min(all_values), max(all_values)
    if hi == lo:
        return "▄"  # All values equal
    normalised = (value - lo) / (hi - lo)  # 0..1
    idx = int(normalised * (len(SPARKLINE_GLYPHS) - 1))
    return SPARKLINE_GLYPHS[idx]


def deduplicate_reddit(messages):
    """Remove cross-posted Reddit content that appears in multiple sorts."""
    seen_hashes = set()
    deduped = []
    dup_count = 0
    
    # Sort by timestamp so we keep earliest
    sorted_msgs = sorted(messages, key=lambda m: m["timestamp"] or "")
    
    for msg in sorted_msgs:
        # Only deduplicate Reddit messages
        if msg["channel_name"].startswith("reddit-"):
            h = content_hash(msg["content"])
            if h in seen_hashes:
                dup_count += 1
                continue
            seen_hashes.add(h)
        deduped.append(msg)
    
    return deduped


def compute_weekly_trends(messages, weeks=WEEKS_IN_TREND):
    """Compute weekly sentiment trends for the last N weeks."""
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
        score, label = classify_sentiment(msg["content"])
        
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


def detect_anomalies(trends, threshold=ANOMALY_THRESHOLD):
    """Detect sentiment anomalies using rolling statistics (2σ)."""
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


def run_analysis(db, output_dir):
    print("Loading messages...")
    messages = db.execute("""
        SELECT m.user_id, m.message_id, m.content, m.timestamp, m.reactions, m.channel_id,
               c.name as channel_name, u.display_name, u.role
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        LEFT JOIN users u ON (m.user_id = u.id AND m.client_id = u.client_id)
        WHERE m.client_id = :client_id AND m.content IS NOT NULL AND m.content != ''
    """).fetchall()
    print(f"  {len(messages)} messages loaded")

    if not messages:
        print("No messages found in database.")
        return None

    # ─── 1. Overall Sentiment ────────────────────────────────────────────
    print("\n[1/6] Sentiment analysis...")
    sentiment_dist = Counter()
    sentiment_by_channel = defaultdict(Counter)
    sentiment_by_month = defaultdict(Counter)
    negative_messages = []
    positive_messages = []
    all_power_words = Counter()
    purpose_dist = Counter()
    purpose_by_channel = defaultdict(Counter)

    for msg in messages:
        score, label = classify_sentiment(msg["content"])
        sentiment_dist[label] += 1
        sentiment_by_channel[msg["channel_name"]][label] += 1

        ts = msg["timestamp"]
        if ts:
            if isinstance(ts, str):
                month = ts[:7]
                day = ts[:10]
            else:
                month = ts.strftime("%Y-%m")
                day = ts.strftime("%Y-%m-%d")
        else:
            month = "unknown"
            day = "unknown"

        sentiment_by_month[month][label] += 1

        if label == "negative" and score <= -2:
            negative_messages.append({
                "channel": msg["channel_name"],
                "author": msg["display_name"] or "unknown",
                "content": msg["content"][:200],
                "score": score,
                "timestamp": day,
            })
        elif label == "positive" and score >= 2:
            positive_messages.append({
                "channel": msg["channel_name"],
                "author": msg["display_name"] or "unknown",
                "content": msg["content"][:200],
                "score": score,
                "timestamp": day,
            })

        pw = extract_power_words(msg["content"])
        for w in pw:
            all_power_words[w] += 1

        purpose = classify_purpose(msg["content"])
        purpose_dist[purpose] += 1
        purpose_by_channel[msg["channel_name"]][purpose] += 1

    # ─── DEDUP: Remove cross-posted Reddit content ─────────────────────
    print("\n[1.5/7] Deduplicating cross-posted Reddit content...")
    deduped_messages = deduplicate_reddit(messages)
    print(f"  {len(messages)} → {len(deduped_messages)} messages ({len(messages) - len(deduped_messages)} duplicates removed)")

    # ─── WEEKLY TREND: Compute 8-week rolling sentiment ───────────────
    print("\n[2/7] Computing weekly sentiment trends...")
    weekly_trends = compute_weekly_trends(deduped_messages, WEEKS_IN_TREND)
    print(f"  {len(weekly_trends)} weeks of trend data")

    # ─── ANOMALY DETECTION: Find sentiment spikes ─────────────────────
    print("\n[2.5/7] Detecting anomalies...")
    anomalies = detect_anomalies(weekly_trends, ANOMALY_THRESHOLD)
    print(f"  {len(anomalies)} anomalies detected")

    # ─── 2. Topic-level sentiment ───────────────────────────────────────
    print("\n[3/7] Topic-level sentiment...")
    topic_sentiment = defaultdict(lambda: {"pos": 0, "neg": 0, "neu": 0, "total": 0})

    topic_rows = db.execute("SELECT name, category FROM topics").fetchall()
    topic_keywords = {r["name"]: r["category"] for r in topic_rows}

    for msg in messages:
        text_lower = msg["content"].lower()
        score, label = classify_sentiment(msg["content"])
        for topic, category in topic_keywords.items():
            if topic.lower() in text_lower:
                topic_sentiment[topic]["total"] += 1
                topic_sentiment[topic][label[:3]] += 1

    # ─── 3. User sentiment profiles ─────────────────────────────────────
    print("[3/6] User sentiment profiles...")
    user_sentiment = defaultdict(lambda: {"pos": 0, "neg": 0, "neu": 0, "total": 0, "score_sum": 0.0})

    for msg in messages:
        score, label = classify_sentiment(msg["content"])
        uid = msg["user_id"] # Use user_id for DB update
        display_name = msg["display_name"] or "unknown"
        
        user_sentiment[uid]["total"] += 1
        user_sentiment[uid][label[:3]] += 1
        user_sentiment[uid]["score_sum"] += score
        user_sentiment[uid]["display_name"] = display_name

    # Persist user sentiment to DB
    print("  Updating users table...")
    for uid, stats in user_sentiment.items():
        # Normalize sentiment to -1..1 range
        raw_avg = stats["score_sum"] / stats["total"]
        # Simple normalization: tanh or just cap it. 
        # Since we use lexicon, raw_avg is average words difference.
        # Let's use a soft cap at +/- 2.0
        normalized = max(-1.0, min(1.0, raw_avg / 2.0))
        db.execute("UPDATE users SET sentiment = ? WHERE id = ? AND client_id = :client_id", (str(round(normalized, 3)), uid))
    db.commit()

    # ─── 4. Reddit comparison (from DB) ──────────────────────────────────
    print("[4/6] Reddit data from DB...")
    reddit_messages = db.execute("""
        SELECT m.content, m.reactions, m.timestamp, c.name as channel_name
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        WHERE m.client_id = :client_id AND m.platform = 'reddit' AND m.content IS NOT NULL AND m.content != ''
    """).fetchall()

    reddit_sentiment = Counter()
    reddit_by_channel = defaultdict(Counter)
    for msg in reddit_messages:
        text = msg["content"]
        _, label = classify_sentiment(text)
        reddit_sentiment[label] += 1
        reddit_by_channel[msg["channel_name"]][label] += 1

    total_reddit = len(reddit_messages)

    # ─── 5. Engagement metrics ──────────────────────────────────────────
    print("[5/6] Engagement metrics...")
    total_reactions = db.execute("SELECT SUM(reactions) as s FROM messages").fetchone()["s"] or 0
    avg_reactions = total_reactions / len(messages) if messages else 0

    reply_count = db.execute("SELECT COUNT(*) as c FROM messages WHERE reply_to IS NOT NULL").fetchone()["c"]

    active_users = db.execute("""
        SELECT display_name, messages, reactions_received
        FROM users WHERE messages >= 5 ORDER BY messages DESC LIMIT 20
    """).fetchall()

    # ─── 6. Compile report ──────────────────────────────────────────────
    print("[6/6] Compiling report...")

    total = len(messages)
    deduped_total = len(deduped_messages)
    duplicates_removed = total - deduped_total
    pos_pct = sentiment_dist["positive"] / total * 100
    neg_pct = sentiment_dist["negative"] / total * 100
    neu_pct = sentiment_dist["neutral"] / total * 100

    date_range = db.execute("""
        SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM messages
        WHERE client_id = :client_id AND content IS NOT NULL AND content != ''
    """).fetchone()

    def fmt_ts(ts):
        if not ts: return "N/A"
        if isinstance(ts, str): return ts[:10]
        return ts.strftime("%Y-%m-%d")

    true_from = fmt_ts(date_range["min_ts"])
    true_to = fmt_ts(date_range["max_ts"])

    report = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "total_messages_analyzed": total,
            "deduped_messages": deduped_total,
            "duplicates_removed": duplicates_removed,
            "channels": len(sentiment_by_channel),
            "date_range": {
                "from": true_from,
                "to": true_to,
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
            "active_users_5plus": len([u for u in active_users]),
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

    # Generate Markdown report
    md = generate_markdown_report(report)
    md_path = output_dir / "community-sentiment-report.md"
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Markdown saved: {md_path}")

    return report


def generate_markdown_report(r):
    lines = []
    a = r  # shorthand

    lines.append("# Community Sentiment & Classification Analysis")
    lines.append(f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append(f"\n*Generated from {a['meta']['total_messages_analyzed']} Discord messages + {a['meta']['reddit_messages_in_db']} Reddit messages (DB)*")
    lines.append(f"*Deduplicated: {a['meta']['deduped_messages']} unique messages ({a['meta']['duplicates_removed']} cross-post duplicates removed)*")
    lines.append(f"*Data date range: {a['meta']['date_range']['from']} → {a['meta']['date_range']['to']}*")

    # ── Platform Breakdown ──
    lines.append("\n\n## Platform Overview")
    lines.append(f"| Platform | Messages |")
    lines.append(f"|----------|----------|")
    lines.append(f"| Discord | {a['meta']['total_messages_analyzed'] - a['meta']['reddit_messages_in_db']} |")
    lines.append(f"| Reddit | {a['meta']['reddit_messages_in_db']} |")
    lines.append(f"| **Total (raw)** | **{a['meta']['total_messages_analyzed']}** |")
    lines.append(f"| **Total (deduped)** | **{a['meta']['deduped_messages']}** |")

    # ── WEEKLY SENTIMENT TRENDS ──
    lines.append("\n\n## Weekly Sentiment Trends (Last 8 Weeks)")
    neg_pcts = [t["neg_pct"] for t in a.get("weekly_trends", [])]
    pos_pcts = [t["pos_pct"] for t in a.get("weekly_trends", [])]
    lines.append("\n| Week | Total | Pos% | Neg% | Neu% | Discord Pos% | Discord Neg% | Reddit Pos% | Reddit Neg% | Pos Trend | Neg Trend |")
    lines.append("|------|-------|------|------|------|--------------|--------------|-------------|-------------|-----------|-----------|")
    for t in a.get("weekly_trends", []):
        pos_spark = sparkline_for_value(t["pos_pct"], pos_pcts)
        neg_spark = sparkline_for_value(t["neg_pct"], neg_pcts)
        lines.append(f"| {t['week']} | {t['total']} | {t['pos_pct']}% | {t['neg_pct']}% | {t['neu_pct']}% | {t['discord_pos_pct']}% | {t['discord_neg_pct']}% | {t['reddit_pos_pct']}% | {t['reddit_neg_pct']}% | {pos_spark} | {neg_spark} |")

    # ── ANOMALY ALERTS ──
    anomalies = a.get("anomalies", [])
    if anomalies:
        lines.append("\n\n## 🚨 Anomaly Alerts (2σ Detection)")
        lines.append("\n| Week | Platform | Metric | Value | Expected | Z-Score | Severity |")
        lines.append("|------|----------|--------|-------|----------|---------|----------|")
        for anom in anomalies[:10]:
            lines.append(f"| {anom['week']} | {anom['platform']} | {anom['metric']} | {anom['value']}% | {anom['expected']}% | {anom['z_score']} | {anom['severity']} {anom['direction']} |")
    else:
        lines.append("\n\n## 🚨 Anomaly Alerts")
        lines.append("\nNo significant sentiment anomalies detected (all metrics within 2σ of rolling average).")

    # ── Executive Summary ──
    lines.append("\n\n## Executive Summary")
    s = a["sentiment"]["overall"]
    lines.append(f"\n**Overall Sentiment Ratio: {s['sentiment_ratio']}** (positive:negative)")
    lines.append(f"- {s['positive']['pct']}% positive ({s['positive']['count']} messages)")
    lines.append(f"- {s['negative']['pct']}% negative ({s['negative']['count']} messages)")
    lines.append(f"- {s['neutral']['pct']}% neutral ({s['neutral']['count']} messages)")

    if s["sentiment_ratio"] > 2:
        feel = "strongly positive — members are enthusiastic and supportive"
    elif s["sentiment_ratio"] > 1:
        feel = "moderately positive — constructive with some frustrations"
    elif s["sentiment_ratio"] > 0.5:
        feel = "mixed — significant negativity alongside positivity"
    else:
        feel = "predominantly negative — community frustration is high"
    lines.append(f"\n**Community feel: {feel}**")

    # ── DECISION CARD ──
    lines.append("\n\n## 🎯 Decisions Needed This Week")
    lines.append("\n| Priority | Issue | Evidence | Recommended Action | Owner |")
    lines.append("|----------|-------|----------|-------------------|-------|")

    decisions = []
    for anom in anomalies[:3]:
        if "neg" in anom["metric"].lower() and anom["direction"] == "↑ spike":
            decisions.append({
                "priority": "🔴 HIGH",
                "issue": f"{anom['platform']} negative sentiment spike",
                "evidence": f"{anom['metric']} {anom['value']}% (expected {anom['expected']}%, z={anom['z_score']})",
                "action": "Investigate root cause; prepare comms response if patch/bug related",
                "owner": "Dev Lead + CM"
            })

    neg_topic = min(a["topic_sentiment"].items(), key=lambda x: x[1]["net_sentiment"]) if a["topic_sentiment"] else None
    if neg_topic and neg_topic[1]["neg_pct"] > 40:
        decisions.append({
            "priority": "🔴 HIGH",
            "issue": f"'{neg_topic[0]}' pain point",
            "evidence": f"{neg_topic[1]['neg_pct']}% negative sentiment, net {neg_topic[1]['net_sentiment']:+.0f}%",
            "action": "Dedicate dev resources; communicate fix timeline",
            "owner": "Dev Lead"
        })

    if not decisions:
        decisions.append({
            "priority": "🟢 LOW",
            "issue": "No urgent actions",
            "evidence": "Sentiment stable within normal bounds",
            "action": "Continue monitoring",
            "owner": "CM"
        })

    for d in decisions:
        lines.append(f"| {d['priority']} | {d['issue']} | {d['evidence']} | {d['action']} | {d['owner']} |")

    # ── Sentiment by Channel ──
    lines.append("\n\n## Sentiment by Channel")
    lines.append("\n| Channel | Messages | Positive | Negative | Neutral | Pos% | Neg% |")
    lines.append("|---------|----------|----------|----------|---------|------|------|")
    for ch, data in a["sentiment"]["by_channel"].items():
        lines.append(f"| {ch} | {data['total']} | {data['positive']} | {data['negative']} | {data['neutral']} | {data['pos_pct']}% | {data['neg_pct']}% |")

    # ── Reddit Comparison ──
    lines.append("\n\n## Cross-Platform Comparison: Discord vs Reddit")
    rs = a["sentiment"]["reddit_comparison"]
    ds = a["sentiment"]["overall"]
    lines.append(f"\n| Platform | Positive | Negative | Neutral |")
    lines.append(f"|----------|----------|----------|---------|")
    total_reddit = a["meta"]["reddit_messages_in_db"]
    ds_total = ds['positive']['count'] + ds['negative']['count'] + ds['neutral']['count']
    disc_pos = round((ds['positive']['count']-rs['positive'])/(ds_total-total_reddit)*100,1) if ds_total-total_reddit else 0
    disc_neg = round((ds['negative']['count']-rs['negative'])/(ds_total-total_reddit)*100,1) if ds_total-total_reddit else 0
    disc_neu = round(100 - disc_pos - disc_neg, 1)
    lines.append(f"| Discord | {disc_pos}% | {disc_neg}% | {disc_neu}% |")
    lines.append(f"| Reddit | {rs['pos_pct']}% | {rs['neg_pct']}% | {round(100 - rs['pos_pct'] - rs['neg_pct'], 1)}% |")

    # ── Purpose Analysis ──
    lines.append("\n\n## What Are They Trying to Achieve?")
    lines.append("\nMessage purpose classification:\n")
    lines.append("| Purpose | Count | % |")
    lines.append("|---------|-------|---|")
    for purpose, data in a["purpose"]["distribution"].items():
        lines.append(f"| {purpose} | {data['count']} | {data['pct']}% |")

    # ── Topic Sentiment ──
    lines.append("\n\n## Topic-Level Sentiment")
    lines.append("\nWhat drives positivity vs negativity:\n")
    lines.append("| Topic | Mentions | Pos% | Neg% | Net Sentiment |")
    lines.append("|-------|----------|------|------|---------------|")
    for topic, data in list(a["topic_sentiment"].items())[:20]:
        net = data["net_sentiment"]
        indicator = "🟢" if net > 10 else ("🔴" if net < -10 else "🟡")
        lines.append(f"| {topic} | {data['total']} | {data['pos_pct']}% | {data['neg_pct']}% | {indicator} {net:+.0f} |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--client", help="Client name")
    args = parser.parse_args()

    db = get_db(args.client)
    
    # Set output directory based on client
    if args.client:
        output_dir = ROOT / "data" / "clients" / args.client / "reports"
    else:
        output_dir = ROOT / "docs"
        
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running analysis for client: {args.client or 'default'}")
    report = run_analysis(db, output_dir)
    
    db.close()
    if report:
        print("\n✅ Analysis complete.")

if __name__ == "__main__":
    main()
