# Design Spec: Headless Playwright Backend & Residential Proxies

## Overview
To scale Community Radar for hundreds of clients on `superchargedbym3.com` and prevent Reddit IP bans, the system will evolve from a local Chrome Extension bridge to a native Playwright-based automation backend. This backend will support residential proxies and utilize Bitwarden Secrets Manager (BWS) for secure credential management.

## Goals
- **Scalability:** Run multiple browser instances in parallel (across different queue workers in the future) without a single-extension bottleneck.
- **Resilience:** Bypass Reddit rate limits and IP bans using rotating residential proxies.
- **Security:** Use Bitwarden Secrets Manager (BWS) to store and retrieve sensitive proxy URLs and Reddit authentication tokens.
- **Abstraction:** Provide a common interface so existing collectors can work with either the legacy "Bridge" or the new "Playwright" backend.

## Architecture

### 1. Pluggable Browser Backend
We will introduce a `BrowserPage` abstraction in the `scripts/reddit/` directory.

- **BridgeBackend:** (Existing) Connects to the local Chrome extension via WebSocket.
- **PlaywrightBackend:** (New) Launches a native Chromium instance using the `playwright` library.

### 2. Configuration & Secrets (`config.yaml` + BWS)
The global and client-specific configurations will be updated to support backend selection.

```yaml
reddit_global:
  backend: "playwright" # 'bridge' or 'playwright'
  headless: true
  # Global fallback proxy
  proxy_secret_id: "7890-global-proxy-uuid"

clients:
  pure-pool-pro:
    reddit:
      # Optional client-specific proxy (overrides global)
      proxy_secret_id: "1234-client-proxy-uuid"
```

### 3. Proxy & BWS Logic
The system will use the existing `bws` CLI integration to fetch secrets:
1. Lookup the `proxy_secret_id`.
2. Fetch the JSON secret from BWS.
3. Parse the secret (expected format: `http://user:pass@proxy.provider:port`).
4. Pass the proxy configuration directly to the Playwright `browser.new_context()` method.

### 4. Headless Execution
- By default, all background tasks (triggered via the queue) will run in **headless** mode.
- A `--headed` flag will be added to the CLI for manual debugging.

## Key Benefits
- **Zero Login Bias:** Playwright instances can start with fresh or specifically curated cookie sets, preventing the "Single-Profile Bias" of the Chrome extension.
- **Infrastructure Ready:** This architecture is ready for deployment to headless Linux servers (Docker/Cloud), where a Chrome extension bridge would be impossible to maintain.
- **Location Spoofing:** Residential proxies allow for geographic-specific analysis.

## Security
- **No Secrets in Config:** Only UUIDs for BWS secrets are stored in `config.yaml`.
- **Credential Protection:** Proxy and Reddit credentials are never logged or stored in the SQLite silos.
