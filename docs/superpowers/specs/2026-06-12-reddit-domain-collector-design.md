# Design Spec: Reddit Domain Collector

## Overview
The Reddit Domain Collector is a new component for CommunityRadar designed to track mentions and shared links of specific domains across the entire Reddit platform (via `reddit.com/domain/<domain>`). This provides broader visibility beyond specific monitored subreddits, capturing organic reach and competitor activity.

## Goals
- Discover where and how specific domains are being shared on Reddit.
- Integrate this data into the existing sentiment analysis and reporting pipeline.
- Allow configuration-driven monitoring of multiple domains.
- Maintain separation between "Subreddit Monitoring" and "Domain Discovery" while using unified storage.

## Architecture & Data Flow

### 1. Configuration (`config.yaml`)
A new section `reddit_domain_monitoring` will be added to the configuration.

```yaml
reddit:
  domain_monitoring:
    enabled: true
    domains:
      - "purepoolpro.com"
      - "competitor-a.io"
    max_pages: 3
    sort: "new"
```

### 2. Collection Logic (`src/collectors/reddit_domain.py`)
- **Isolation:** A dedicated script will handle domain-based collection.
- **Mechanism:** Utilizes the existing Chrome-extension bridge and the `json-feed` command to fetch `https://www.reddit.com/domain/<domain>/.json`.
- **Pagination:** Supports multi-page fetching via the `after` token.

### 3. Data Integration (Tagged Unified Storage)
To keep the database schema simple while allowing for clear data separation:

- **Server ID:** All domain search results will be grouped under the server ID `reddit_domain_monitoring`.
- **Channel ID:** Each domain will be treated as a "virtual channel" with the ID format `domain:<domain_name>` (e.g., `domain:purepoolpro.com`).
- **Table:** Data is stored in the standard `messages` table.
- **Platform:** Marked as `reddit`.

### 4. Analysis Integration
The existing analysis scripts (`src/analysis/sentiment.py`, `src/analysis/competitors.py`) will recognize the `domain:` prefix in `channel_id` to:
- Generate specific "External Reach" or "Domain Mention" reports.
- Filter domain results out of standard "Subreddit Health" metrics if needed.

## Testing Strategy
- **Unit Tests:** Verify URL generation for various domain formats.
- **Integration Tests:** Run the collector against a test domain (e.g., `github.com`) and verify that posts are correctly upserted into the SQLite database with the `domain:` tag.
- **Schema Validation:** Ensure no collisions with existing subreddit message IDs.

## Security & Rate Limiting
- **Rate Limits:** The collector will respect existing sleep intervals between pages to avoid Reddit API/Bridge throttling.
- **Privacy:** Only public post data is collected.
