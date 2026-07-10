# 家用命令台

家用命令台 is a household dashboard for local web apps and repo-owned command tools on the same trusted LAN.

It does not start, stop, or supervise external services. You run your web apps yourself, expose them over LAN HTTPS, and list them in `~/.config/home_command_center/apps/*.yaml`.

Command tools are different: they are small CLI scripts coded in this repo and exposed through controlled web forms. 家用命令台 does not run arbitrary commands from user config.

## Run

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Start the dashboard:

```bash
python3 server.py --host 127.0.0.1 --port 7000
```

Open:

```text
http://127.0.0.1:7000
```

For household devices, serve the dashboard through Caddy over HTTPS.

By default, app config is loaded from:

```text
~/.config/home_command_center/apps/*.yaml
```

The workbook tool has app-specific settings in:

```text
~/.config/home_command_center/apps/workbook_go.yaml
```

Current workbook setting:

```yaml
type: command_tool
chinese_chars:
  output_dir: /home/yli/.config/home_command_center/output
```

For development, you can point at another config directory:

```bash
python3 server.py --apps-dir ./apps
```

## App Config

Create one YAML file per app in `~/.config/home_command_center/apps/`.

```yaml
id: inspire
name: Inspire
url: "https://192.168.4.35:8001"
thumbnail: ./thumb.png
description: Inspiration browser
tags:
  - writing
  - local
health_url: "http://127.0.0.1:8001/"
health_verify_tls: false
```

Required fields:

* `id`
* `name`
* `url`

Optional fields:

* `thumbnail`
* `description`
* `tags`
* `health_url`
* `health_verify_tls`

`thumbnail` paths are resolved relative to the YAML file.

`health_verify_tls` defaults to `true`. Set it to `false` for local HTTPS health checks when the app is reachable but Python does not trust the local mkcert CA.

## Command Tools

Repo-owned command tools live in `cli_tools/` and are registered in `command_tools.py`.

The dashboard automatically lists registered command tools alongside configured web apps. Clicking a command tool opens a form page such as:

```text
/tools/slugify
```

The frontend constrains fields using the registered schema. The backend validates the same inputs again, builds an argv list, and runs the registered script without a shell.

Current tool:

* `chinese-practice`: generates printable Chinese handwriting practice PDFs using the workbook generator from `/home/yli/e/Dropbox/github/workbook_go`
* `eat-what`: generates a weekly menu or lists recipes using `/home/yli/e/Dropbox/github/eat_what`
* `daka`: shows all existing new year resolutions and tasks from `/home/yli/e/Dropbox/github/new_year_resolution_tracker` and lets you check them off one by one by date

`eat-what` currently exposes the non-interactive planner and recipe-list modes. The interactive `eat-what-recipe` and `eat-what-pick` commands are not wrapped yet.

`daka` is web-first: the page loads the full resolution tree, includes a date picker defaulted to today, each task gets its own check-in button, and the page can generate task or resolution reports. Rename/add flows stay in the original CLI.

To add a command tool:

* Add a CLI script under `cli_tools/`
* Register it in `command_tools.py`
* Define each accepted argument with `ToolArg`
* Keep the CLI script non-interactive and bounded
* If the tool generates files, write them under its configured output directory

For `chinese-practice`, the output directory field defaults to `chinese_chars.output_dir` from `~/.config/home_command_center/apps/workbook_go.yaml`. The user may override it in the form for a single run. The wrapper does not pass a PDF filename to workbook_go; it changes into the chosen output directory and lets workbook_go use its default filename pattern, such as `practice_20260710.pdf`.

## LAN HTTPS

Recommended setup:

* Install Caddy
* Install mkcert
* Generate a local certificate for the server IP
* Trust the mkcert root certificate on household client devices
* Run each app on localhost
* Let Caddy expose the dashboard and apps over HTTPS

Example:

```bash
mkcert -install
mkcert 192.168.4.35
```

Example Caddyfile:

```caddy
{
    auto_https off
}

https://192.168.4.35:7000 {
    bind 192.168.4.35
    tls /path/to/192.168.4.35.pem /path/to/192.168.4.35-key.pem
    reverse_proxy 127.0.0.1:7000
}

https://192.168.4.35:8001 {
    bind 192.168.4.35
    tls /path/to/192.168.4.35.pem /path/to/192.168.4.35-key.pem
    reverse_proxy 127.0.0.1:8001
}
```

Format and run Caddy:

```bash
caddy fmt --overwrite Caddyfile
sudo caddy run --config Caddyfile
```

To trust the local CA on client devices:

```bash
mkcert -CAROOT
```

Copy `rootCA.pem` to each client device. Do not copy the root CA key file.
