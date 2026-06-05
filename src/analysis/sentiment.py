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
from collections import Counter, defaultdict
from pathlib import Path

DB_PATH = Path("/Users/mathias/Development/community-radar/data/community_radar.db")
RESEARCH_DIR = Path("/Users/mathias/Development/DiscordBot/cuebot/docs/research")
OUTPUT_DIR = Path("/Users/mathias/Development/community-radar/docs")

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

    # ─── 2. Topic-level sentiment ───────────────────────────────────────
    print("[2/6] Topic-level sentiment...")
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

    # ─── 4. Reddit comparison ───────────────────────────────────────────
    print("[4/6] Loading Reddit data...")
    reddit_posts = []
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
                reddit_posts.extend(data)
            elif isinstance(data, dict) and "posts" in data:
                reddit_posts.extend(data["posts"])

    reddit_sentiment = Counter()
    for post in reddit_posts:
        title = post.get("title", "")
        body = post.get("selftext", post.get("body", ""))
        text = f"{title} {body}"
        _, label = classify_sentiment(text)
        reddit_sentiment[label] += 1

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
    pos_pct = sentiment_dist["positive"] / total * 100
    neg_pct = sentiment_dist["negative"] / total * 100
    neu_pct = sentiment_dist["neutral"] / total * 100

    report = {
        "meta": {
            "total_messages_analyzed": total,
            "channels": len(sentiment_by_channel),
            "date_range": {
                "from": messages[0]["timestamp"][:10] if messages else "N/A",
                "to": messages[-1]["timestamp"][:10] if messages else "N/A",
            },
            "reddit_posts_analyzed": len(reddit_posts),
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
                "pos_pct": round(reddit_sentiment["positive"] / max(len(reddit_posts), 1) * 100, 1),
                "neg_pct": round(reddit_sentiment["negative"] / max(len(reddit_posts), 1) * 100, 1),
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
    lines.append(f"\n*Generated from {a['meta']['total_messages_analyzed']} Discord messages + {a['meta']['reddit_posts_analyzed']} Reddit posts*")
    lines.append(f"*Date range: {a['meta']['date_range']['from']} → {a['meta']['date_range']['to']}*")

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

    # ── Top Negatives ──
    lines.append("\n\n## Top Negative Messages")
    for msg in a["top_negative"][:10]:
        lines.append(f"\n> **{msg['author']}** ({msg['channel']}, {msg['timestamp']}) [{msg['score']}]")
        lines.append(f"> {msg['content']}")

    # ── Top Positives ──
    lines.append("\n\n## Top Positive Messages")
    for msg in a["top_positive"][:10]:
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
