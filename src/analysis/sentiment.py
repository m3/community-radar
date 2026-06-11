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
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timedelta
import statistics

DB_PATH = Path("/Users/mathias/Development/Projects/community-radar/data/community_radar.db")
RESEARCH_DIR = Path("/Users/mathias/Development/DiscordBot/cuebot/docs/research")
OUTPUT_DIR = Path("/Users/mathias/Development/Projects/community-radar/docs")

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
    "missing", "lacking", "lacks", "need", "needs", "want", "wanted", "wish",
    "wished", "hope", "hoped", "please", "pls", "plz", "request", "requested",
    "suggestion", "suggestions", "feature", "features", "add", "adding",
    "include", "including", "implement", "implementation", "update", "updates",
    "patch", "patches", "fix", "fixes", "fixed", "fixing",
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

# Community purpose indicators
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
    """Return a single sparkline glyph representing this value's relative magnitude.
    
    Normalises the value against the min/max of all_values to pick one of 8 block elements.
    Returns ▁ for minimum, █ for maximum, with intermediate levels in between.
    """
    if not all_values:
        return "▁"
    lo, hi = min(all_values), max(all_values)
    if hi == lo:
        return "▄"  # All values equal
    normalised = (value - lo) / (hi - lo)  # 0..1
    idx = int(normalised * (len(SPARKLINE_GLYPHS) - 1))
    return SPARKLINE_GLYPHS[idx]


def deduplicate_reddit(messages):
    """Remove cross-posted Reddit content that appears in multiple sorts.
    
    Reddit posts appear in new, hot, top?t=month, top?t=year, top?t=all.
    We identify duplicates by content hash and keep only the first occurrence
    (chronologically earliest) per unique post.
    """
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
    # Group by week
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
        
        # ISO week
        week_key = dt.strftime("%Y-W%U")
        score, label = classify_sentiment(msg["content"])
        
        weekly[week_key]["total"] += 1
        weekly[week_key][label[:3]] += 1
        
        platform = "discord" if not msg["channel_name"].startswith("reddit-") else "reddit"
        weekly[week_key][f"{platform}_total"] += 1
        weekly[week_key][f"{platform}_{label[:3]}"] += 1
    
    # Sort weeks and take last N
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
    """Detect sentiment anomalies using rolling statistics (2σ).
    
    Returns list of anomaly dicts with week, metric, value, expected, severity.
    """
    if len(trends) < 3:
        return []
    
    anomalies = []
    
    # Extract time series for each metric
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
        
        # Rolling mean/std (excluding current week for detection)
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
    
    # Sort by severity (z_score desc)
    anomalies.sort(key=lambda x: -x["z_score"])
    return anomalies


def run_analysis():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    print("Loading messages...")
    messages = db.execute("""
        SELECT m.message_id, m.content, m.timestamp, m.reactions, m.channel_id,
               c.name as channel_name, u.display_name, u.role
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        LEFT JOIN users u ON m.user_id = u.id
        WHERE m.content IS NOT NULL AND m.content != ''
    """).fetchall()
    print(f"  {len(messages)} messages loaded")

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

        month = msg["timestamp"][:7] if msg["timestamp"] else "unknown"
        sentiment_by_month[month][label] += 1

        if label == "negative" and score <= -2:
            negative_messages.append({
                "channel": msg["channel_name"],
                "author": msg["display_name"] or "unknown",
                "content": msg["content"][:200],
                "score": score,
                "timestamp": msg["timestamp"][:10],
            })
        elif label == "positive" and score >= 2:
            positive_messages.append({
                "channel": msg["channel_name"],
                "author": msg["display_name"] or "unknown",
                "content": msg["content"][:200],
                "score": score,
                "timestamp": msg["timestamp"][:10],
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

    # Use existing topic keywords from the DB
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
    user_sentiment = defaultdict(lambda: {"pos": 0, "neg": 0, "neu": 0, "total": 0})

    for msg in messages:
        score, label = classify_sentiment(msg["content"])
        uid = msg["display_name"] or "unknown"
        user_sentiment[uid]["total"] += 1
        user_sentiment[uid][label[:3]] += 1

    # ─── 4. Reddit comparison (from DB) ──────────────────────────────────
    print("[4/6] Reddit data from DB...")
    reddit_messages = db.execute("""
        SELECT m.content, m.reactions, m.timestamp, c.name as channel_name
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        WHERE m.platform = 'reddit' AND m.content IS NOT NULL AND m.content != ''
    """).fetchall()

    reddit_sentiment = Counter()
    reddit_by_channel = defaultdict(Counter)
    for msg in reddit_messages:
        text = msg["content"]
        _, label = classify_sentiment(text)
        reddit_sentiment[label] += 1
        reddit_by_channel[msg["channel_name"]][label] += 1

    # Legacy Reddit JSON files (keep for backward compat)
    reddit_posts_legacy = []
    reddit_files = [
        RESEARCH_DIR / "reddit-top-posts.json",
        RESEARCH_DIR / "reddit-new-posts.json",
        RESEARCH_DIR / "reddit-hot-posts.json",
    ]
    for rf in reddit_files:
        if rf.exists():
            with open(rf) as f:
                data = json.load(f)
            if isinstance(data, list):
                reddit_posts_legacy.extend(data)
            elif isinstance(data, dict) and "posts" in data:
                reddit_posts_legacy.extend(data["posts"])

    # Also load new full export JSONs
    reddit_export_dir = Path("/Users/mathias/Development/Projects/community-radar/data/reddit-exports")
    for jf in reddit_export_dir.glob("*-full.json"):
        with open(jf) as f:
            data = json.load(f)
        if isinstance(data, list):
            for post in data:
                title = post.get("title", "")
                body = post.get("selftext", "")
                text = f"{title} {body}"
                _, label = classify_sentiment(text)
                reddit_sentiment[label] += 1
                reddit_posts_legacy.append(post)

    total_reddit = len(reddit_messages) + len(reddit_posts_legacy)

    # ─── 5. Engagement metrics ──────────────────────────────────────────
    print("[5/6] Engagement metrics...")
    total_reactions = db.execute("SELECT SUM(reactions) as s FROM messages").fetchone()["s"] or 0
    avg_reactions = total_reactions / len(messages) if messages else 0

    # Reply chains
    reply_count = db.execute("SELECT COUNT(*) as c FROM messages WHERE reply_to IS NOT NULL").fetchone()["c"]

    # Active users (5+ messages)
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

    # Compute true date range from DB (not from messages list which may be unsorted)
    date_range = db.execute("""
        SELECT MIN(timestamp), MAX(timestamp) FROM messages
        WHERE content IS NOT NULL AND content != ''
    """).fetchone()
    true_from = date_range[0][:10] if date_range[0] else "N/A"
    true_to = date_range[1][:10] if date_range[1] else "N/A"

    report = {
        "meta": {
            "total_messages_analyzed": total,
            "deduped_messages": deduped_total,
            "duplicates_removed": duplicates_removed,
            "channels": len(sentiment_by_channel),
            "date_range": {
                "from": true_from,
                "to": true_to,
            },
            "reddit_posts_analyzed": total_reddit,
            "reddit_messages_in_db": len(reddit_messages),
            "reddit_posts_in_json": len(reddit_posts_legacy),
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
                "pos_pct": round(reddit_sentiment["positive"] / max(total_reddit, 1) * 100, 1),
                "neg_pct": round(reddit_sentiment["negative"] / max(total_reddit, 1) * 100, 1),
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
    output_path = OUTPUT_DIR / "community-sentiment-analysis.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  JSON saved: {output_path}")

    # Generate Markdown report
    md = generate_markdown_report(report)
    md_path = OUTPUT_DIR / "community-sentiment-report.md"
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Markdown saved: {md_path}")

    db.close()
    return report


def generate_markdown_report(r):
    lines = []
    a = r  # shorthand

    lines.append("# Community Sentiment & Classification Analysis")
    lines.append(f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append(f"\n*Generated from {a['meta']['total_messages_analyzed']} Discord messages + {a['meta']['reddit_messages_in_db']} Reddit messages (DB) + {a['meta']['reddit_posts_in_json']} Reddit posts (JSON)*")
    lines.append(f"*Deduplicated: {a['meta']['deduped_messages']} unique messages ({a['meta']['duplicates_removed']} cross-post duplicates removed)*")
    lines.append(f"*Data date range: {a['meta']['date_range']['from']} → {a['meta']['date_range']['to']}*")

    # ── Platform Breakdown ──
    lines.append("\n\n## Platform Overview")
    lines.append(f"| Platform | Messages |")
    lines.append(f"|----------|----------|")
    lines.append(f"| Discord | {a['meta']['total_messages_analyzed']} |")
    lines.append(f"| Reddit | {a['meta']['reddit_messages_in_db'] + a['meta']['reddit_posts_in_json']} |")
    lines.append(f"| **Total (raw)** | **{a['meta']['total_messages_analyzed'] + a['meta']['reddit_messages_in_db'] + a['meta']['reddit_posts_in_json']}** |")
    lines.append(f"| **Total (deduped)** | **{a['meta']['deduped_messages']}** |")

    # ── WEEKLY SENTIMENT TRENDS ──
    lines.append("\n\n## Weekly Sentiment Trends (Last 8 Weeks)")
    # Compute sparkline data for overall neg% across the 8-week window
    neg_pcts = [t["neg_pct"] for t in a.get("weekly_trends", [])]
    pos_pcts = [t["pos_pct"] for t in a.get("weekly_trends", [])]
    lines.append("\n| Week | Total | Pos% | Neg% | Neu% | Discord Pos% | Discord Neg% | Reddit Pos% | Reddit Neg% | Pos Trend | Neg Trend |")
    lines.append("|------|-------|------|------|------|--------------|--------------|-------------|-------------|-----------|-----------|")
    for t in a.get("weekly_trends", []):
        # Sparkline glyphs (▁▂▃▄▅▆▇█) — use simple text representation
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

    # Community feel
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

    # Build decision cards from anomalies and gap analysis
    decisions = []

    # From anomalies
    for anom in anomalies[:3]:
        if "neg" in anom["metric"].lower() and anom["direction"] == "↑ spike":
            decisions.append({
                "priority": "🔴 HIGH",
                "issue": f"{anom['platform']} negative sentiment spike",
                "evidence": f"{anom['metric']} {anom['value']}% (expected {anom['expected']}%, z={anom['z_score']})",
                "action": "Investigate root cause; prepare comms response if patch/bug related",
                "owner": "Dev Lead + CM"
            })
        elif "pos" in anom["metric"].lower() and anom["direction"] == "↓ drop":
            decisions.append({
                "priority": "🟡 MED",
                "issue": f"{anom['platform']} positive sentiment drop",
                "evidence": f"{anom['metric']} {anom['value']}% (expected {anom['expected']}%, z={anom['z_score']})",
                "action": "Review recent changes; amplify positive content",
                "owner": "CM"
            })

    # From gap analysis
    neg_topic = min(a["topic_sentiment"].items(), key=lambda x: x[1]["net_sentiment"]) if a["topic_sentiment"] else None
    if neg_topic and neg_topic[1]["neg_pct"] > 40:
        decisions.append({
            "priority": "🔴 HIGH",
            "issue": f"'{neg_topic[0]}' pain point",
            "evidence": f"{neg_topic[1]['neg_pct']}% negative sentiment, net {neg_topic[1]['net_sentiment']:+.0f}%",
            "action": "Dedicate dev resources; communicate fix timeline",
            "owner": "Dev Lead"
        })

    feedback_pct = a["purpose"]["distribution"].get("feedback", {}).get("pct", 0)
    if feedback_pct > 15:
        decisions.append({
            "priority": "🟡 MED",
            "issue": "High feedback volume",
            "evidence": f"{feedback_pct}% of messages are feedback/feature requests",
            "action": "Implement structured feedback pipeline (voting, roadmap visibility)",
            "owner": "PM"
        })

    support_pct = a["purpose"]["distribution"].get("support", {}).get("pct", 0)
    if support_pct > 10:
        decisions.append({
            "priority": "🟡 MED",
            "issue": "High support needs",
            "evidence": f"{support_pct}% of messages are support/questions",
            "action": "Create FAQ/pinned guides; consider bot auto-responses",
            "owner": "CM"
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
    lines.append(f"| Discord | {ds['positive']['pct']}% | {ds['negative']['pct']}% | {ds['neutral']['pct']}% |")
    lines.append(f"| Reddit | {rs['pos_pct']}% | {rs['neg_pct']}% | {round(100 - rs['pos_pct'] - rs['neg_pct'], 1)}% |")

    if rs["neg_pct"] > ds["negative"]["pct"] + 10:
        lines.append("\n> ⚠️ Reddit sentiment is significantly more negative than Discord. Reddit serves as the complaint/venting outlet while Discord is more constructive.")
    elif ds["negative"]["pct"] > rs["neg_pct"] + 10:
        lines.append("\n> ⚠️ Discord sentiment is more negative than Reddit — unusual, suggests in-game frustration is being voiced directly in community channels.")
    else:
        lines.append("\n> Sentiment is broadly similar across platforms.")

    # ── Purpose Analysis ──
    lines.append("\n\n## What Are They Trying to Achieve?")
    lines.append("\nMessage purpose classification:\n")
    lines.append("| Purpose | Count | % |")
    lines.append("|---------|-------|---|")
    for purpose, data in a["purpose"]["distribution"].items():
        lines.append(f"| {purpose} | {data['count']} | {data['pct']}% |")

    lines.append("\n### Purpose by Channel")
    for ch, purposes in a["purpose"]["by_channel"].items():
        top = ", ".join(f"{k} ({v})" for k, v in purposes.items())
        lines.append(f"- **{ch}**: {top}")

    # ── Power Words ──
    lines.append("\n\n## Community Identity: Power Words")
    lines.append("\nMost frequently used community-specific terms:\n")
    lines.append("| Word/Phrase | Mentions |")
    lines.append("|-------------|----------|")
    for word, count in list(a["power_words"].items())[:30]:
        lines.append(f"| {word} | {count} |")

    # ── Topic Sentiment ──
    lines.append("\n\n## Topic-Level Sentiment")
    lines.append("\nWhat drives positivity vs negativity:\n")
    lines.append("| Topic | Mentions | Pos% | Neg% | Net Sentiment |")
    lines.append("|-------|----------|------|------|---------------|")
    for topic, data in list(a["topic_sentiment"].items())[:20]:
        net = data["net_sentiment"]
        indicator = "🟢" if net > 10 else ("🔴" if net < -10 else "🟡")
        lines.append(f"| {topic} | {data['total']} | {data['pos_pct']}% | {data['neg_pct']}% | {indicator} {net:+.0f} |")

    # ── Top Negatives (deduplicated) ──
    lines.append("\n\n## Top Negative Messages")
    seen_content = set()
    neg_count = 0
    for msg in a["top_negative"]:
        content_key = msg["content"][:100]
        if content_key in seen_content:
            continue
        seen_content.add(content_key)
        neg_count += 1
        if neg_count > 10:
            break
        lines.append(f"\n> **{msg['author']}** ({msg['channel']}, {msg['timestamp']}) [{msg['score']}]")
        lines.append(f"> {msg['content']}")

    # ── Top Positives (deduplicated) ──
    lines.append("\n\n## Top Positive Messages")
    seen_content = set()
    pos_count = 0
    for msg in a["top_positive"]:
        content_key = msg["content"][:100]
        if content_key in seen_content:
            continue
        seen_content.add(content_key)
        pos_count += 1
        if pos_count > 10:
            break
        lines.append(f"\n> **{msg['author']}** ({msg['channel']}, {msg['timestamp']}) [+{msg['score']}]")
        lines.append(f"> {msg['content']}")

    # ── Engagement ──
    lines.append("\n\n## Engagement Metrics")
    e = a["engagement"]
    lines.append(f"- Total reactions: {e['total_reactions']}")
    lines.append(f"- Avg reactions/message: {e['avg_reactions_per_message']}")
    lines.append(f"- Reply rate: {e['reply_rate']}% ({e['reply_count']} replies)")
    lines.append(f"- Active users (5+ msgs): {e['active_users_5plus']}")

    lines.append("\n### Top Contributors")
    lines.append("\n| User | Messages | Reactions Received |")
    lines.append("|------|----------|-------------------|")
    for u in a["top_contributors"]:
        lines.append(f"| {u['name']} | {u['messages']} | {u['reactions_received']} |")

    # ── Gap Analysis ──
    lines.append("\n\n## Gap Analysis: Purpose vs Reality")

    top_purpose = list(a["purpose"]["distribution"].keys())[0] if a["purpose"]["distribution"] else "unknown"
    neg_topic = min(a["topic_sentiment"].items(), key=lambda x: x[1]["net_sentiment"]) if a["topic_sentiment"] else None
    pos_topic = max(a["topic_sentiment"].items(), key=lambda x: x[1]["net_sentiment"]) if a["topic_sentiment"] else None

    lines.append(f"\n### What the community wants: {top_purpose}")
    lines.append(f"### What's working: {pos_topic[0] if pos_topic else 'N/A'} (net sentiment: {pos_topic[1]['net_sentiment']:+.0f}%)" if pos_topic else "")
    lines.append(f"### What's broken: {neg_topic[0] if neg_topic else 'N/A'} (net sentiment: {neg_topic[1]['net_sentiment']:+.0f}%)" if neg_topic else "")

    lines.append("\n### Identified Gaps")

    # Auto-detect gaps from data
    feedback_pct = a["purpose"]["distribution"].get("feedback", {}).get("pct", 0)
    support_pct = a["purpose"]["distribution"].get("support", {}).get("pct", 0)
    social_pct = a["purpose"]["distribution"].get("social", {}).get("pct", 0)
    competition_pct = a["purpose"]["distribution"].get("competition", {}).get("pct", 0)

    if feedback_pct > 15:
        lines.append(f"- **High feedback volume ({feedback_pct}%)**: Community is actively requesting features/changes. Need structured feedback pipeline.")
    if support_pct > 10:
        lines.append(f"- **High support needs ({support_pct}%)**: Many questions going unanswered. Consider FAQ or pinned guides.")
    if social_pct > 20:
        lines.append(f"- **Strong social drive ({social_pct}%)**: Community wants to connect. Matchmaking features or events would resonate.")
    if competition_pct > 10:
        lines.append(f"- **Competition interest ({competition_pct}%)**: Tournament/league demand exists. Formal competition structure needed.")

    if neg_topic and neg_topic[1]["neg_pct"] > 40:
        lines.append(f"- **'{neg_topic[0]}' is a pain point**: {neg_topic[1]['neg_pct']}% negative sentiment. Needs immediate attention.")

    bug_neg = a["topic_sentiment"].get("bug", {}).get("neg_pct", 0)
    if bug_neg > 30:
        lines.append(f"- **Bug frustration high**: Bug-related messages are {bug_neg}% negative. Communication about fixes needed.")

    lines.append("\n### Recommendations")
    lines.append("1. **Address the top negative topic** — dedicate dev resources to the highest-negativity area")
    lines.append("2. **Amplify what works** — double down on the highest-positivity topics in marketing and community management")
    lines.append("3. **Close the feedback loop** — when bugs are fixed, announce it. When features are added, credit the community.")
    lines.append("4. **Cross-platform monitoring** — Reddit is where people vent. Monitor it for early warning signs.")
    lines.append("5. **Engage top contributors** — the top 15 users drive disproportionate engagement. Recognize and empower them.")

    return "\n".join(lines)


if __name__ == "__main__":
    report = run_analysis()
    print("\n✅ Analysis complete.")
