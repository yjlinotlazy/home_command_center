# Home Command Center Design

This file is the short architectural reference for the repo. It is meant to explain how the pieces fit together, not to restate every implementation detail.

## System Model

Home Command Center is a dashboard for two kinds of things:

1. User-managed web apps listed from `~/.config/home_command_center/apps/*.yaml`
2. Repo-owned command tools registered in `command_tools.py`

The dashboard itself does not start or supervise external services.

## Ports And Routing

The repo uses two port ranges:

1. Local app processes listen on `7***`
2. Caddy-facing public bindings use `8***`

Example:

```text
public URL:   https://192.168.0.0:8001
local backend: http://127.0.0.1:7001
```

The `url` field in app YAML is the address opened by users.
The `health_url` field is only used for health probing and should point at the local backend port.

## Health Checks

Health checks are best-effort and optional.

Current behavior:

1. The dashboard reads `health_url`
2. It extracts the host and port
3. It checks whether that port is listening with a TCP connect

This means:

1. `health_url` does not need to be fetchable over HTTP
2. `health_verify_tls` is retained for config compatibility, but it is ignored by the current checker
3. An app can still be opened even if its status is offline or unknown

## Web App Cards

Configured web apps are shown as dashboard cards.

Each card shows:

1. Name
2. URL/hostname
3. Description
4. Tags
5. Status, when health checks are configured

Clicking the card is sufficient to open the app.

## Command Tools

Command tools are repo-owned CLI wrappers exposed through web forms.

The flow is:

1. `server.py` lists tools from `command_tools.py`
2. The browser opens `/tools/<tool-id>`
3. The tool page fetches the tool schema from the backend
4. The frontend renders controls from that schema
5. The backend validates the submitted JSON again and runs the registered script without a shell

Current tool pages live in the existing files under `cli_tools/`.
Shared shell helpers live in `cli_tools/util.py`.

## Frontend Split

The front page is rendered by `static/app.js`.
Tool pages are rendered by `static/tool.js`, with per-tool special cases when needed.

Important current special cases:

1. `chinese-practice` has its own page shell, CSS, and JS
2. `eat-what` has its own page shell for its layout
3. `daka` is a special web-first tool with its own interaction model

## Repo Layout

Useful files:

1. `server.py` - dashboard server, app registry, health checks, and tool routing
2. `command_tools.py` - tool registry and tool schema definitions
3. `cli_tools/` - command tool wrappers and shared tool page helpers
4. `static/` - dashboard and tool frontend assets
5. `README.md` - user-facing setup and usage
6. `Requirements.md` - behavioral requirements and conventions

## Conventions

1. Keep app config YAMLs small and explicit
2. Keep command tools non-interactive and bounded
3. Prefer short, local health probes over browser-dependent checks
4. Keep public URL examples and local backend examples clearly separated
