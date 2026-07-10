# 家用命令台 Requirements

Serve as a household dashboard for local web apps and repo-owned command tools on the same trusted LAN.

## Goal

家用命令台 is a local web app and command tool directory.

It helps the user:

* See all registered local web apps
* Open a registered app from one dashboard
* Use approved command line tools through web forms
* Organize apps with names, thumbnails, descriptions, and tags
* Optionally see whether an app appears online

It does **not** start, stop, supervise, or configure external apps.
Each registered app must already be running as a web app at a known URL.
Command tools must be coded and registered in this repo. They are not loaded from user config.

## Use Case

I have several local web apps on my home server.

I run those apps myself using systemd, shell scripts, Docker, terminals, or any other mechanism I choose.
Each app is exposed on the household LAN through HTTPS, usually with Caddy and a locally trusted certificate.

I want a single household dashboard where I can find and open these apps from any device on the same local network.
I also want small repo-owned command line tools to be usable from phones or tablets through simple forms.

## Requirements

### App List

The dashboard should show all registered apps.

User can filter or search apps by:

* Name
* Tag
* Online / offline / unknown status, if health checks are enabled

Each app card should show:

* App name
* Thumbnail if provided
* Description if provided
* Tags if provided
* URL or hostname
* Status if health checks are enabled
* Open button

Command tool cards should show:

* Tool name
* Description
* Tags if provided
* Use button

Clicking a command tool opens a web form for that tool.

The `daka` tool is a special case:

* It loads the full resolution/task tree at once
* It shows a date picker defaulted to today
* Each task has its own one-click check-in button
* Rename and add flows stay outside the web UI

## App Configuration

Each app is configured by the user in `~/.config/home_command_center/apps/*.yaml`.

Example:

```yaml
id: inspire
name: Inspire
url: "https://192.168.0.0:8001"
thumbnail: ./thumb.png
description: Inspiration browser
tags:
  - writing
  - local
health_url: "http://127.0.0.1:7001/"
health_verify_tls: false
```

### Required Fields

```yaml
id: inspire
name: Inspire
url: "https://192.168.0.0:8001"
```

### Optional Fields

```yaml
thumbnail: ./thumb.png
description: Inspiration browser
tags:
  - writing
  - local
health_url: "http://127.0.0.1:7001/"
health_verify_tls: false
```

### Field Notes

* `id` is a stable unique identifier used by 家用命令台.
* `name` is the user-facing display name.
* `url` is the URL opened by household devices.
* `thumbnail` is resolved relative to the YAML file unless absolute.
* `health_url` is used by 家用命令台 only to extract the host and port to probe. It may be different from `url` and should point at the local backend port.
* Health checks are TCP port checks, not HTTP requests.
* `health_verify_tls` is retained for config compatibility, but it is ignored by the current port-based health check.

## Health Checks

Health checks are optional.

If `health_url` is provided, 家用命令台 may periodically probe the host and port and show:

* Online
* Offline
* Unknown

Health checks should be best-effort only.
An app can still be opened even if its health status is offline or unknown.

## Command Tool Wrappers

Command tools are coded in this repo under `cli_tools/` and registered in `command_tools.py`.

Each registered command tool defines:

* Stable id
* Display name
* Description
* Script path under `cli_tools/`
* Accepted arguments
* Tags

The frontend should:

* Render a form based on the registered argument schema
* Use suitable controls such as text inputs, textareas, and selects
* Trim and constrain user input before submitting
* Send JSON to the backend
* Display stdout, stderr, and errors clearly

The backend must:

* Run only registered repo-owned scripts
* Never run arbitrary commands from user config
* Never invoke a shell
* Validate every argument again server-side
* Enforce input length and allowed choices
* Enforce a command timeout
* Return stdout, stderr, exit code, and success state
* Return generated file links when a tool creates files under the configured output directory

### Chinese Practice PDF Tool

The first real command tool wraps the workbook generator from `<workbook_go_repo>`.

It should generate Chinese handwriting practice PDFs from:

* Characters
* Cells per row
* Paper size: `us_letter` or `a4`
* Practice mode: `1`, `2`, or `3`
* Copy count

Generated PDFs should be written under `generated/workbooks/` and opened from the result page.
The wrapper should not pass `--output`; workbook_go should use its default filename pattern.
The user can override the output directory from the form.
The default output directory is read from `~/.config/home_command_center/apps/workbook_go.yaml`.

Example command center config:

```yaml
type: command_tool
chinese_chars:
  output_dir: <home_command_center_output_dir>
```

### Eat What Tool

The second command tool wraps `<eat_what_repo>`.

It should support:

* Generating a weekly menu and shopping list
* Listing all recipes
* Custom recipe CSV path
* Time, overlap, veg, spicy, and seed options

It should not wrap the interactive `eat-what-recipe` or `eat-what-pick` flows until those have dedicated web form designs.

### New Year Resolution Tool

The `daka` tool wraps `<new_year_resolution_tracker_repo>`.

It should:

* Render all resolutions and tasks on one page
* Let the user choose a date from a calendar input, defaulting to today
* Let the user check in any task with a single button click
* Generate both task-level and resolution-level reports
* Show report colors, labels, and progress in a web-friendly way
* Keep rename/add flows in the original CLI, not in the web UI

## Opening Apps

The dashboard should provide an Open button for every configured app.

For MVP, apps are expected to use their own HTTPS ports:

```text
https://192.168.0.0:8000   # 家用命令台
https://192.168.0.0:8001   # App 1
https://192.168.0.0:8002   # App 2
```

This is simpler and more reliable than path-based routing.

## Local Network Access

The app is intended for trusted household LAN usage.

Recommended setup:

* Install Caddy
* Install mkcert
* Generate a local certificate for the server IP
* Serve 家用命令台 over HTTPS
* Serve each registered app over HTTPS
* Trust the mkcert root certificate on household client devices

Example:

```bash
mkcert -install
mkcert 192.168.0.0
```

This generates:

```text
192.168.0.0.pem
192.168.0.0-key.pem
```

Example Caddyfile:

```caddy
{
    auto_https off
}

https://192.168.0.0:8000 {
    bind 0.0.0.0
    tls /path/to/192.168.0.0.pem /path/to/192.168.0.0-key.pem
    reverse_proxy 127.0.0.1:7000
}

https://192.168.0.0:8001 {
    bind 0.0.0.0
    tls /path/to/192.168.0.0.pem /path/to/192.168.0.0-key.pem
    reverse_proxy 127.0.0.1:7001
}

https://192.168.0.0:8002 {
    bind 0.0.0.0
    tls /path/to/192.168.0.0.pem /path/to/192.168.0.0-key.pem
    reverse_proxy 127.0.0.1:7002
}
```

Apps may listen on localhost while Caddy exposes them over LAN HTTPS.

Format Caddyfile:

```bash
caddy fmt --overwrite Caddyfile
```

Run Caddy:

```bash
sudo caddy run --config Caddyfile
```

## Client Device Certificate Trust

To avoid browser certificate warnings on household devices:

```bash
mkcert -CAROOT
```

Copy `rootCA.pem` to the client device.

Do **not** copy the root CA key file.

Install and trust the certificate on each client device.
The exact method depends on the device and operating system.

## Non-Goals

家用命令台 does not:

* Convert arbitrary CLI tools into web apps
* Start apps
* Stop apps
* Assign ports
* Track process IDs
* Capture app logs
* Generate Caddy config in MVP
* Provide authentication in MVP
* Expose apps to the public internet
* Manage Docker containers in MVP
* Rewrite app code
* Guarantee app-level security
* Handle multi-user permissions

## MVP Scope

The first version should include:

* `~/.config/home_command_center/apps/*.yaml` app registry
* Repo-owned command tool registry
* Dashboard UI
* Search and tag filtering
* Open app links
* Command tool form pages
* Thumbnail support
* Optional health status
* LAN HTTPS setup documentation

## Future Ideas

Possible future features:

* Caddy config generation
* App grouping or favorites
* App icons and richer metadata
* Basic password protection
* Mobile-friendly dashboard polish
* Import from existing service definitions
* Read-only diagnostics for known local services
