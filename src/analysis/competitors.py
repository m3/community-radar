"""
Competitor & Opportunity Analyzer
Scans r/billiards, r/snooker, and other niche subreddits for:
1. Pure Pool / Ripstone mentions (opportunity leads)
2. Competitor game mentions (market intelligence)
3. Unmet needs / feature requests
4. Sentiment around cue sports simulation
"""

import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import argparse
import yaml

from src.db.models import get_db

ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = ROOT / "config.yaml"
with open(CONFIG_PATH, "r") as f:
    CONFIG = yaml.safe_load(f)
DATA_DIR = ROOT / CONFIG.get("data_dir", "data")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f) or {}

# Brand & product names to track (multi-word phrases first to avoid false matches)
BRAND_KEYWORDS = {
    "pure_pool": ["pure pool", "purepoolpro", "ripstone"],
    "competitor_games": [
        "virtual pool", "pool of eight", "side pocket", "snooker 19", "snooker 20",
        "wsc real", "matchroom pool", "8 ball pool", "miniclip", "foosball", "foos",
        "carom 3d", "vr pool", "pool vr", "killer pool", "archona", "snooker club",
    ],
    "cue_sports_general": [
        "billiards", "snooker", "8 ball", "9 ball", "10 ball", "carom",
        "straight pool", "one pocket", "bank pool", "trick shot", "trickshot",
    ],
    "game_features": [
        "physics", "realistic", "simulation", "tutorial", "training mode", "practice mode",
        "online multiplayer", "ranked", "matchmaking", "replay system", "match replay",
    ],
    "pain_points": [
        "pay to win", "microtransactions", "ads", "laggy", "abandoned",
        "no updates", "no support", "cheaters", "hackers", "toxic community",
    ],
}


def search_keywords(text, keywords):
    """Return list of keywords found in text (with word boundary check)"""
    text_lower = text.lower()
    found = []
    for kw in keywords:
        # Use word boundaries to avoid false positives (e.g., "ads" in "pads")
        pattern = r'\b' + re.escape(kw.lower()) + r'\b'
        if re.search(pattern, text_lower):
            found.append(kw)
    return found


def classify_message(text):
    """Classify message into opportunity/competitor/neutral"""
    brand_hits = search_keywords(text, BRAND_KEYWORDS["pure_pool"])
    competitor_hits = search_keywords(text, BRAND_KEYWORDS["competitor_games"])

    if brand_hits:
        return "pure_pool_mention", brand_hits
    elif competitor_hits:
        return "competitor_mention", competitor_hits
    return None, []


def extract_quote(text, keyword, context=200):
    """Extract quote around keyword"""
    text_lower = text.lower()
    idx = text_lower.find(keyword.lower())
    if idx == -1:
        return text[:300]

    start = max(0, idx - context)
    end = min(len(text), idx + len(keyword) + context)
    quote = text[start:end].strip()

    if start > 0:
        quote = "..." + quote
    if end < len(text):
        quote = quote + "..."
    return quote


def run_analysis(client_name):
    db = get_db(client_name)
    config = load_config()
    client_config = config.get("clients", {}).get(client_name, {})
    reddit_config = client_config.get("reddit", {}).get("subreddits", {})

    external_channels = []
    for sub, conf in reddit_config.items():
        if conf.get("track_keywords"): # Only scan external channels for intel
            external_channels.append(f"reddit_{sub.lower()}_%")

    if not external_channels:
        print("No external channels configured for intelligence scanning.")
        return

    channel_filters = " OR ".join(["c.name LIKE ?" for _ in external_channels])
    query = f"""
        SELECT m.message_id, m.content, m.timestamp, m.reactions, m.platform,
               c.name as channel_name
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        WHERE m.client_id = :client_id AND ({channel_filters})
          AND m.content IS NOT NULL AND m.content != ''
        ORDER BY m.timestamp DESC
    """
    messages = db.execute(query, external_channels).all()

    print(f"  {len(messages)} messages loaded")

    # Categorize
    pure_pool_mentions = []
    competitor_mentions = defaultdict(list)
    feature_requests = []
    pain_points = []
    sentiment_indicators = {"positive": 0, "negative": 0, "neutral": 0}

    for msg in messages:
        content = msg["content"]
        classification, hits = classify_message(content)

        def fmt_ts(ts):
            if not ts: return "unknown"
            if isinstance(ts, str): return ts[:10]
            return ts.strftime("%Y-%m-%d")

        # Track Pure Pool mentions
        if classification == "pure_pool_mention":
            for hit in hits:
                pure_pool_mentions.append({
                    "channel": msg["channel_name"],
                    "timestamp": fmt_ts(msg["timestamp"]),
                    "score": msg["reactions"] or 0,
                    "quote": extract_quote(content, hit),
                })
        # Track competitor mentions
        elif classification == "competitor_mention":
            for hit in hits:
                competitor_mentions[hit].append({
                    "channel": msg["channel_name"],
                    "timestamp": fmt_ts(msg["timestamp"]),
                    "score": msg["reactions"] or 0,
                    "quote": extract_quote(content, hit),
                })

        # Feature requests
        feature_hits = search_keywords(content, BRAND_KEYWORDS["game_features"])
        if "suggestion" in content.lower() or "feature" in content.lower() or "wish" in content.lower() or "would be nice" in content.lower():
            if feature_hits:
                feature_requests.append({
                    "features": feature_hits,
                    "channel": msg["channel_name"],
                    "timestamp": fmt_ts(msg["timestamp"]),
                    "quote": extract_quote(content, "suggestion" if "suggestion" in content.lower() else "feature"),
                })

        # Pain points
        pain_hits = search_keywords(content, BRAND_KEYWORDS["pain_points"])
        if pain_hits:
            pain_points.append({
                "pains": pain_hits,
                "channel": msg["channel_name"],
                "timestamp": fmt_ts(msg["timestamp"]),
                "quote": extract_quote(content, pain_hits[0]),
                "score": msg["reactions"] or 0,
            })

        # Simple sentiment
        content_lower = content.lower()
        pos_words = ["love", "great", "amazing", "best", "awesome", "perfect", "recommend"]
        neg_words = ["hate", "terrible", "worst", "garbage", "trash", "awful", "disappointed"]
        if any(w in content_lower for w in pos_words):
            sentiment_indicators["positive"] += 1
        elif any(w in content_lower for w in neg_words):
            sentiment_indicators["negative"] += 1
        else:
            sentiment_indicators["neutral"] += 1

    db.close()

    # Generate report
    # Deduplicate Pure Pool mentions by quote hash
    seen_quotes = set()
    deduped_pp_mentions = []
    for m in sorted(pure_pool_mentions, key=lambda x: -x["score"]):
        quote_hash = hash(m["quote"][:100])
        if quote_hash in seen_quotes:
            continue
        seen_quotes.add(quote_hash)
        deduped_pp_mentions.append(m)
    pure_pool_mentions = deduped_pp_mentions[:25]

    report = {
        "meta": {
            "total_messages_scanned": len(messages),
            "pure_pool_mentions": len(pure_pool_mentions),
            "competitor_mentions": sum(len(v) for v in competitor_mentions.values()),
            "unique_competitors": len(competitor_mentions),
            "feature_requests": len(feature_requests),
            "pain_points_flagged": len(pain_points),
        },
        "pure_pool_mentions": pure_pool_mentions,
        "competitor_mentions": {
            comp: sorted(items, key=lambda x: -x["score"])[:5]
            for comp, items in sorted(competitor_mentions.items(), key=lambda x: -len(x[1]))[:10]
        },
        "feature_requests": feature_requests[:15],
        "pain_points": sorted(pain_points, key=lambda x: -x["score"])[:15],
        "sentiment_indicators": sentiment_indicators,
    }

    # Save JSON
    json_path = DATA_DIR / "clients" / client_name / "reports" / "competitor_intel.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  JSON saved: {json_path}")

    # Generate Markdown
    md = generate_markdown(report)
    md_path = json_path.with_suffix(".md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Markdown saved: {md_path}")

    return report


def generate_markdown(r):
    lines = []
    a = r
    m = a["meta"]

    lines.append("# Competitor & Opportunity Analysis")
    lines.append(f"\n*Scanned {m['total_messages_scanned']} messages*")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append(f"\n**Key findings:**")
    lines.append(f"- {m['pure_pool_mentions']} brand mentions (opportunity leads)")
    lines.append(f"- {m['competitor_mentions']} mentions of {m['unique_competitors']} competitor games")
    lines.append(f"- {m['feature_requests']} feature requests identified")
    lines.append(f"- {m['pain_points_flagged']} pain point signals")

    # Sentiment
    s = a["sentiment_indicators"]
    total = sum(s.values())
    lines.append(f"\n## Community Sentiment")
    lines.append(f"\n| Sentiment | Count | % |")
    lines.append(f"|-----------|-------|---|")
    for k, v in s.items():
        pct = v / total * 100 if total else 0
        lines.append(f"| {k.title()} | {v} | {pct:.1f}% |")

    # Pure Pool mentions
    lines.append(f"\n## 🎯 Brand Mentions ({m['pure_pool_mentions']})")
    lines.append(f"\n*Highest-priority opportunity leads — people actively looking for/discussing the brand*")
    if a["pure_pool_mentions"]:
        lines.append(f"\n| Date | Channel | Score | Quote |")
        lines.append(f"|------|---------|-------|-------|")
        for mention in a["pure_pool_mentions"][:15]:
            sub = mention["channel"]
            quote = mention["quote"].replace("\n", " ").replace("|", "\\|")[:200]
            lines.append(f"| {mention['timestamp']} | {sub} | {mention['score']} | {quote} |")
    else:
        lines.append(f"\n*No mentions found in scanned messages.*")

    # Competitor mentions
    lines.append(f"\n## 🏆 Competitor Mentions ({m['unique_competitors']} competitors)")
    lines.append(f"\n*Market intelligence — what else are users discussing?*")
    if a["competitor_mentions"]:
        lines.append(f"\n| Competitor | Mentions | Top Quote |")
        lines.append(f"|------------|----------|-----------|")
        for comp, mentions in a["competitor_mentions"].items():
            top = mentions[0] if mentions else None
            if top:
                sub = top["channel"]
                quote = top["quote"].replace("\n", " ").replace("|", "\\|")[:150]
                lines.append(f"| {comp.title()} | {len(mentions)} | {sub}: {quote} |")
    else:
        lines.append(f"\n*No competitor game mentions found.*")

    # Feature requests
    lines.append(f"\n## 💡 Feature Requests ({m['feature_requests']})")
    lines.append(f"\n*What users want — gaps we could fill*")
    if a["feature_requests"]:
        # Group by feature
        feature_counts = Counter()
        for req in a["feature_requests"]:
            for f in req["features"]:
                feature_counts[f] += 1

        lines.append(f"\n### Most Requested Features")
        lines.append(f"\n| Feature | Requests |")
        lines.append(f"|---------|----------|")
        for feat, count in feature_counts.most_common(15):
            lines.append(f"| {feat} | {count} |")

        lines.append(f"\n### Sample Quotes")
        for req in a["feature_requests"][:5]:
            sub = req["channel"]
            quote = req["quote"].replace("\n", " ").replace("|", "\\|")[:200]
            features = ", ".join(req["features"])
            lines.append(f"\n> {sub} ({req['timestamp']}) — *{features}*")
            lines.append(f"> {quote}")
    else:
        lines.append(f"\n*No explicit feature requests captured.*")

    # Pain points
    lines.append(f"\n## 😤 Pain Points ({m['pain_points_flagged']})")
    lines.append(f"\n*What frustrates users about existing games — opportunity for differentiation*")
    if a["pain_points"]:
        pain_counts = Counter()
        for pp in a["pain_points"]:
            for p in pp["pains"]:
                pain_counts[p] += 1

        lines.append(f"\n### Most Common Pain Points")
        lines.append(f"\n| Pain Point | Mentions |")
        lines.append(f"|------------|----------|")
        for pain, count in pain_counts.most_common(10):
            lines.append(f"| {pain} | {count} |")

        lines.append(f"\n### Top Frustrations (by score)")
        for pp in a["pain_points"][:5]:
            sub = pp["channel"]
            quote = pp["quote"].replace("\n", " ").replace("|", "\\|")[:200]
            pains = ", ".join(pp["pains"])
            lines.append(f"\n> {sub} ({pp['timestamp']}, score: {pp['score']}) — *{pains}*")
            lines.append(f"> {quote}")
    else:
        lines.append(f"\n*No pain point signals captured.*")

    # Strategic recommendations
    lines.append(f"\n## 🎯 Strategic Opportunities")
    lines.append(f"\n### Immediate (this week)")
    if a["pure_pool_mentions"]:
        lines.append(f"- **Engage with {len(a['pure_pool_mentions'])} brand mentions** — these are warm leads. Drop a helpful comment, link to relevant content.")
    if a["competitor_mentions"]:
        top_competitor_name, top_competitor_items = max(a["competitor_mentions"].items(), key=lambda x: len(x[1]))
        lines.append(f"- **Monitor '{top_competitor_name.title()}' mentions** ({len(top_competitor_items)} posts) — most-mentioned competitor. Consider what they're doing right/wrong.")

    lines.append(f"\n### Short-term (this month)")
    if a["feature_requests"]:
        top_feature = Counter()
        for req in a["feature_requests"]:
            for f in req["features"]:
                top_feature[f] += 1
        top = top_feature.most_common(1)[0]
        lines.append(f"- **Investigate top requested feature: {top[0]}** ({top[1]} requests) — could be a low-hanging fruit roadmap item.")

    lines.append(f"\n### Long-term (this quarter)")
    if a["pain_points"]:
        top_pain = Counter()
        for pp in a["pain_points"]:
            for p in pp["pains"]:
                top_pain[p] += 1
        top = top_pain.most_common(1)[0]
        lines.append(f"- **Address top pain point: {top[0]}** ({top[1]} mentions) — if you avoid this issue, use it in marketing.")

    lines.append(f"\n### Brand Awareness Gap")
    if m["pure_pool_mentions"] < 5:
        lines.append(f"- **⚠️ Low brand awareness** — only {m['pure_pool_mentions']} mentions vs {m['competitor_mentions']} competitor mentions. Consider cross-posting content, AMAs, or community engagement strategy.")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run competitor analysis.")
    parser.add_argument("--client", required=True, help="Client name to run analysis for")
    args = parser.parse_args()

    report = run_analysis(args.client)
    if report:
        print("\n✅ Competitor analysis complete.")

