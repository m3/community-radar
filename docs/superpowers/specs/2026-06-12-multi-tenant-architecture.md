# Design Spec: Multi-Tenant Architecture (Database Isolation)

## Overview
To support multiple "Analysis Objects" or "Clients" (e.g., for superchargedbym3.com), Community Radar will move from a single-tenant global configuration to a multi-tenant architecture. This design uses **Database-Level Isolation**, where every client has its own dedicated SQLite database file and configuration scope.

## Goals
- **Data Isolation:** Ensure Client A's data never mixes with Client B's data.
- **Portability:** Make it easy to backup, move, or delete a single client's entire history by handling one file.
- **API Readiness:** Provide a clean interface for web platforms (like superchargedbym3.com) to trigger scoped analysis via CLI flags or API calls.
- **Scalability:** Prevent the global database from becoming a performance bottleneck as the number of clients grows.

## Architecture

### 1. Client-Centric Configuration
The `config.yaml` is restructured to move subreddits, domains, and discord servers under a `clients` key.

```yaml
clients:
  pure-pool-pro:
    name: "Pure Pool Pro"
    reddit:
      subreddits:
        PurePoolPro: { sorts: ["new", "hot"] }
      domain_monitoring:
        domains: ["purepoolpro.com"]
    discord:
      servers:
        "203428322082816001": ["chat-pure-pool-pro"]

  competitor-x:
    name: "Competitor Intelligence"
    reddit:
      domain_monitoring:
        domains: ["competitor-x.com"]
```

### 2. Isolated Storage
Instead of a single `data/community_radar.db`, the system will generate and use client-specific databases:
- `data/clients/pure-pool-pro.db`
- `data/clients/competitor-x.db`

All exports and raw JSON files will also be organized by client:
- `data/reddit-exports/pure-pool-pro/`
- `data/reddit-exports/competitor-x/`

### 3. CLI & Command Interface
The tool will enforce a `--client` (or `-c`) flag for all operations.

**Commands:**
- `uv run python src/main.py collect --client pure-pool-pro`
- `uv run python src/main.py analyze --client pure-pool-pro`
- `uv run python src/main.py report --client pure-pool-pro`

### 4. Integration Logic (The "Supercharged" Bridge)
When an API call comes from `superchargedbym3.com`:
1. The backend identifies the client ID.
2. It invokes the Community Radar CLI with the corresponding `--client` flag.
3. Community Radar looks up the client's configuration, opens the correct `.db` file, and executes the requested operation.
4. Results are returned in a client-scoped JSON/Markdown file.

## Key Benefits
- **Security:** A bug in a query cannot leak data between clients because they are physically in different files.
- **Simplicity:** No need for complex `WHERE client_id = ...` logic on every database query.
- **Customization:** Each client can have different collection frequencies, domain monitoring lists, and discord server targets without affecting others.
- **Maintenance:** You can vacuum or repair one client's database without taking down the analysis for others.
