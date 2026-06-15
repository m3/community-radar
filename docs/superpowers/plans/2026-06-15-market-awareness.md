# Market Awareness Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Market Awareness section to the dashboard to visualize "Market Blips" (direct product mentions in external subreddits) and calculate a Market Penetration Score.

**Architecture:** A new API endpoint will calculate aggregate stats for external vs owned channels. The existing `api_raw_messages` endpoint will be enhanced to flag messages that qualify as external mentions. The frontend will render a new summary card and highlight these messages in the feed.

**Tech Stack:** Python, Flask, SQLite, JavaScript, TailwindCSS.

---

### Task 1: Add Market Awareness API Endpoint

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Add helper for market stats in `app.py`**

```python
@app.route("/api/<client_name>/market/awareness")
def api_market_awareness(client_name):
    """Calculate Market Penetration and volume stats."""
    validate_client(client_name)
    config = config_mgr.load()
    client_config = config.get("clients", {}).get(client_name, {})
    
    # We need keywords
    keywords = []
    subreddits_config = client_config.get("reddit", {}).get("subreddits", {})
    for sub, sub_conf in subreddits_config.items():
        if "track_keywords" in sub_conf:
            keywords.extend(sub_conf["track_keywords"])
    
    keywords = list(set(keywords)) # Deduplicate
    
    db = get_db(client_name)
    
    # 1. Total External Volume
    external_channels = []
    for sub, sub_conf in subreddits_config.items():
        if "track_keywords" in sub_conf and sub_conf["track_keywords"]:
             external_channels.append(f"reddit_{sub.lower()}_%")
             
    total_external = 0
    external_mentions = 0
    
    if external_channels:
        channel_filters = " OR ".join(["c.name LIKE ?" for _ in external_channels])
        
        total_external = db.execute(f"""
            SELECT COUNT(*) FROM messages m
            JOIN channels c ON m.channel_id = c.id
            WHERE {channel_filters}
        """, external_channels).fetchone()[0]
        
        if keywords:
            kw_filters = " OR ".join(["m.content LIKE ?" for _ in keywords])
            params = external_channels + [f"%{k}%" for k in keywords]
            external_mentions = db.execute(f"""
                SELECT COUNT(*) FROM messages m
                JOIN channels c ON m.channel_id = c.id
                WHERE ({channel_filters}) AND ({kw_filters})
            """, params).fetchone()[0]

    # 2. Total Owned Volume
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
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/app.py
git commit -m "feat(api): add market awareness statistics endpoint"
```

---

### Task 2: Highlight External Mentions in Raw Messages API

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Update `api_raw_messages` to return `is_external_mention`**

```python
    # Logic in api_raw_messages before jsonify:
    
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
        
        channel_name = r_dict["channel_name"].lower()
        if any(channel_name.startswith(p) for p in external_prefixes):
            content_lower = (r_dict.get("content") or "").lower()
            if any(kw in content_lower for kw in keywords):
                r_dict["is_external_mention"] = True
                
        result_rows.append(r_dict)

    return jsonify(result_rows)
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/app.py
git commit -m "feat(api): flag external mentions in raw messages feed"
```

---

### Task 3: Render Market Awareness UI

**Files:**
- Modify: `src/dashboard/templates/index.html`

- [ ] **Step 1: Add Market Awareness Card**

```html
<!-- Market Awareness Card -->
<div class="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-xl relative overflow-hidden group">
    <div class="absolute -right-6 -top-6 w-32 h-32 bg-fuchsia-500/10 rounded-full blur-2xl group-hover:bg-fuchsia-500/20 transition-all"></div>
    <div class="flex justify-between items-start mb-4 relative z-10">
        <div>
            <p class="text-sm font-medium text-slate-400">Market Penetration</p>
            <h3 class="text-3xl font-bold text-white mt-1" id="stat-penetration">--%</h3>
        </div>
        <div class="p-2 bg-fuchsia-500/10 rounded-lg">
            <i class="fas fa-bullseye text-fuchsia-400 text-xl"></i>
        </div>
    </div>
    <div class="flex items-center text-sm text-slate-400 relative z-10 space-x-4">
        <div>
            <span class="text-white font-medium" id="stat-market-volume">--</span>
            <span class="text-slate-500 text-xs ml-1">Market Vol</span>
        </div>
        <div>
            <span class="text-fuchsia-400 font-medium" id="stat-external-mentions">--</span>
            <span class="text-slate-500 text-xs ml-1">Brand Blips</span>
        </div>
    </div>
</div>
```

- [ ] **Step 2: Fetch and bind data in index.html script**

- [ ] **Step 3: Update renderMessage in index.html to show badge**

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/templates/index.html
git commit -m "feat(ui): visualize market awareness and external mentions"
```
