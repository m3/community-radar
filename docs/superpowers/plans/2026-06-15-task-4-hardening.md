# Task 4 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve security and usability of the client configuration system through validation, duplicate detection, and better UI feedback.

**Architecture:** 
- Add a global Toast notification system to the layout.
- Implement client-side validation (regex, uniqueness) in the config editor.
- Implement server-side schema validation in the Flask API.

**Tech Stack:** Python/Flask, JavaScript, Tailwind CSS.

---

### Task 1: UI Feedback - Toast System

**Files:**
- Modify: `src/dashboard/templates/layout.html`

- [ ] **Step 1: Add Toast container and logic to layout**

```html
<!-- Add this to src/dashboard/templates/layout.html before </body> -->
<div id="toastContainer" class="fixed bottom-8 right-8 z-[100] flex flex-col gap-3"></div>

<script>
    function showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        const bg = type === 'success' ? 'bg-emerald-500' : type === 'error' ? 'bg-red-500' : 'bg-sky-500';
        const icon = type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle';
        
        toast.className = `${bg} text-white px-6 py-3 rounded-lg shadow-xl flex items-center gap-3 transform transition-all duration-300 translate-y-10 opacity-0`;
        toast.innerHTML = `
            <i class="fas ${icon}"></i>
            <span class="font-medium">${message}</span>
        `;
        
        container.appendChild(toast);
        
        // Animate in
        setTimeout(() => {
            toast.classList.remove('translate-y-10', 'opacity-0');
        }, 10);
        
        // Auto remove
        setTimeout(() => {
            toast.classList.add('opacity-0');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
</script>
```

- [ ] **Step 2: Commit layout changes**

```bash
git add src/dashboard/templates/layout.html
git commit -m "feat(ui): add global toast notification system"
```

### Task 2: UI Hardening - Client-Side Validation

**Files:**
- Modify: `src/dashboard/templates/client_edit.html`

- [ ] **Step 1: Update saveConfig to include validation**

```javascript
    async function saveConfig() {
        const client_id = "{{ client_name }}";
        const displayName = document.getElementById('clientDisplayName').value.trim();
        
        if (!displayName) {
            showToast('Client display name is required', 'error');
            return;
        }

        // Build payload
        const payload = {
            name: displayName,
            reddit: {
                subreddits: {},
                domain_monitoring: {
                    enabled: document.getElementById('domainEnabled').checked,
                    domains: document.getElementById('targetDomains').value.split('\n').map(d => d.trim()).filter(d => d),
                    max_pages: parseInt(document.getElementById('domainMaxPages').value) || 1,
                    sort: document.getElementById('domainSort').value
                }
            },
            discord: {
                servers: {}
            }
        };

        // Parse Reddit Subreddits with uniqueness check and regex
        const redditNames = new Set();
        let redditError = null;
        const redditRegex = /^[a-zA-Z0-9_]+$/;

        document.querySelectorAll('.reddit-target').forEach(el => {
            if (redditError) return;
            const name = el.querySelector('.sub-name').value.trim();
            if (!name) return;
            
            if (!redditRegex.test(name)) {
                redditError = `Invalid subreddit name: ${name} (alphanumeric only)`;
                return;
            }
            if (redditNames.has(name.toLowerCase())) {
                redditError = `Duplicate subreddit: ${name}`;
                return;
            }
            redditNames.add(name.toLowerCase());
            
            const sorts = Array.from(el.querySelectorAll('.sort-check:checked')).map(c => c.value);
            const keywords = el.querySelector('.track-keywords').value.split(',').map(k => k.trim()).filter(k => k);
            
            payload.reddit.subreddits[name] = {
                sorts: sorts,
                track_keywords: keywords.length > 0 ? keywords : undefined
            };
        });

        if (redditError) {
            showToast(redditError, 'error');
            return;
        }

        // Parse Discord Servers with uniqueness check and regex
        const discordIds = new Set();
        let discordError = null;
        const discordRegex = /^\d+$/;

        document.querySelectorAll('.discord-server').forEach(el => {
            if (discordError) return;
            const sid = el.querySelector('.server-id').value.trim();
            const sname = el.querySelector('.server-name').value.trim();
            if (!sid) return;

            if (!discordRegex.test(sid)) {
                discordError = `Invalid Discord server ID: ${sid} (numeric only)`;
                return;
            }
            if (discordIds.has(sid)) {
                discordError = `Duplicate Discord server ID: ${sid}`;
                return;
            }
            discordIds.add(sid);

            const channels = {};
            const channelIds = new Set();
            el.querySelectorAll('.channel-row').forEach(ch => {
                if (discordError) return;
                const chid = ch.querySelector('.channel-id').value.trim();
                const chname = ch.querySelector('.channel-name').value.trim();
                if (!chid) return;

                if (!discordRegex.test(chid)) {
                    discordError = `Invalid channel ID: ${chid} (numeric only)`;
                    return;
                }
                if (channelIds.has(chid)) {
                    discordError = `Duplicate channel ID: ${chid} in server ${sid}`;
                    return;
                }
                channelIds.add(chid);
                channels[chid] = chname;
            });

            payload.discord.servers[sid] = {
                name: sname,
                channels: channels
            };
        });

        if (discordError) {
            showToast(discordError, 'error');
            return;
        }

        try {
            const res = await fetch(`/api/clients/${client_id}/update`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast('Configuration updated successfully!', 'success');
            } else {
                showToast('Error: ' + (data.error || 'Unknown error occurred'), 'error');
            }
        } catch (e) {
            showToast('Network error: ' + e.message, 'error');
        }
    }
```

- [ ] **Step 2: Add pattern attributes to inputs for built-in validation**

```html
<!-- Example for reddit name -->
<input type="text" placeholder="e.g. snooker" pattern="[a-zA-Z0-9_]+"
       class="sub-name w-full bg-slate-900 border border-slate-700 rounded-lg py-2 px-3 text-white focus:ring-1 focus:ring-sky-500">

<!-- Example for discord id -->
<input type="text" placeholder="e.g. 203428322082816001" pattern="\d+"
       class="server-id w-full bg-slate-900 border border-slate-700 rounded-lg py-2 px-3 text-white focus:ring-1 focus:ring-sky-500">
```

- [ ] **Step 3: Commit editor changes**

```bash
git add src/dashboard/templates/client_edit.html
git commit -m "feat(ui): add validation and uniqueness checks to config editor"
```

### Task 3: Backend Hardening - API Validation

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Update api_update_client_config with validation**

```python
@app.route("/api/clients/<client_name>/update", methods=["POST"])
def api_update_client_config(client_name):
    """Update an existing client's configuration with basic validation."""
    validate_client(client_name)
    data = request.json
    
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid payload format"}), 400
        
    # Basic structure check
    if "name" not in data or not data["name"]:
        return jsonify({"success": False, "error": "Client name is required"}), 400
        
    if "reddit" not in data or not isinstance(data["reddit"], dict):
        return jsonify({"success": False, "error": "Missing or invalid reddit config"}), 400
        
    if "discord" not in data or not isinstance(data["discord"], dict):
        return jsonify({"success": False, "error": "Missing or invalid discord config"}), 400

    # Ensure subreddits and servers are dicts
    if not isinstance(data["reddit"].get("subreddits"), dict):
        return jsonify({"success": False, "error": "Invalid subreddits format"}), 400
    if not isinstance(data["discord"].get("servers"), dict):
        return jsonify({"success": False, "error": "Invalid discord servers format"}), 400

    config = config_mgr.load()
    config["clients"][client_name] = data
    config_mgr.save(config)
    return jsonify({"success": True})
```

- [ ] **Step 2: Commit backend changes**

```bash
git add src/dashboard/app.py
git commit -m "fix(api): add backend validation for client config updates"
```

### Task 4: Verification

- [ ] **Step 1: Test duplicate subreddits**
- [ ] **Step 2: Test invalid characters in subreddit names**
- [ ] **Step 3: Test numeric validation for Discord IDs**
- [ ] **Step 4: Verify toast notifications appear**
- [ ] **Step 5: Verify backend rejects malformed JSON**
