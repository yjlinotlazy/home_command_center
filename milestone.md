# 家用命令台 Milestones

Track progress for the first useful version of 家用命令台.

## Milestone 0: Scope Locked

Status: Done

Goal: Define 家用命令台 as a household web app directory, not a process manager.

Done when:

- [x] Requirements describe a config-driven app directory
- [x] Start / stop / port assignment are out of MVP scope
- [x] HTTPS LAN access is documented as the expected setup

## Milestone 1: Project Skeleton

Status: Done

Goal: Create the minimal runnable application.

Done when:

- [x] A web server can start locally
- [x] A dashboard page is served
- [x] Static assets can be served
- [x] A sample app YAML file exists
- [x] Basic run instructions are documented

## Milestone 2: App Registry

Status: Done

Goal: Load configured apps from YAML files.

Done when:

- [x] App config files are loaded from `~/.config/home_command_center/apps/*.yaml`
- [x] Required fields are validated: `id`, `name`, `url`
- [x] Optional fields are supported: `thumbnail`, `description`, `tags`, `health_url`
- [x] Duplicate app IDs are reported clearly
- [x] Invalid config produces a useful error

## Milestone 3: Dashboard MVP

Status: Done

Goal: Show the configured apps in a usable dashboard.

Done when:

- [x] All configured apps appear on the dashboard
- [x] Each app shows name, URL or hostname, description, tags, and thumbnail when present
- [x] Each app has an Open action
- [x] Missing thumbnails have a clean fallback
- [x] Layout works on desktop and mobile

## Milestone 4: Filtering

Status: Done

Goal: Make the app list easy to scan.

Done when:

- [x] User can search by app name
- [x] User can filter by tag
- [x] Empty states are clear
- [x] Filters work without reloading the page

## Milestone 5: Optional Health Status

Status: Done

Goal: Show best-effort app availability without blocking app access.

Done when:

- [x] Apps with `health_url` are checked from the server
- [x] Status can be online, offline, or unknown
- [x] Health checks have a timeout
- [x] Health results are cached briefly
- [x] Apps can still be opened regardless of health status

## Milestone 6: LAN HTTPS Documentation

Status: Done

Goal: Document the household deployment path.

Done when:

- [x] Caddy + mkcert setup is documented
- [x] Example Caddyfile includes the dashboard and at least one app
- [x] Client certificate trust steps are documented
- [x] Local-only / trusted-LAN assumptions are explicit

## Milestone 7: First Release Polish

Status: In progress

Goal: Make the MVP comfortable enough for daily household use.

Done when:

- [x] README matches the simplified product scope
- [x] Requirements and milestone docs agree
- [x] Error states are visible and understandable
- [x] The app has a small set of representative sample configs
- [ ] Manual test checklist passes on desktop and mobile

## Milestone 8: Repo-Owned Command Tools

Status: Done

Goal: Expose approved command line tools from this repo through web forms.

Done when:

- [x] Command tools are registered in repo code, not user config
- [x] CLI scripts live under `cli_tools/`
- [x] Dashboard lists command tools
- [x] Each command tool has a generated form page
- [x] Frontend trims and constrains submitted args
- [x] Backend validates args server-side
- [x] Backend runs tools without a shell
- [x] Backend returns stdout, stderr, exit code, success state, and generated file links
- [x] Workbook tool uses workbook_go's default filename pattern
- [x] Workbook tool allows output directory override
- [x] Default output directory is read from `~/.config/home_command_center/apps/workbook_go.yaml`
- [x] Docs describe the wrapper model

## Milestone 9: Eat What Tool

Status: Done

Goal: Expose the non-interactive `eat_what` menu planner through 家用命令台.

Done when:

- [x] `吃啥` appears as a command tool
- [x] User can generate a menu
- [x] User can list recipes
- [x] User can choose recipe CSV path
- [x] Interactive recipe editing/picking is left out of scope

## Milestone 10: Daka Tool

Status: Done

Goal: Expose the new year resolution tracker as a one-click check-in page.

Done when:

- [x] `daka` appears as a command tool
- [x] The tool page loads all resolutions and tasks at once
- [x] The tool page includes a date picker defaulted to today
- [x] Each task has its own one-click check-in button
- [x] The tool page can generate task-level and resolution-level reports
- [x] Reports keep the resolution color categories and show web-friendly progress bars
- [x] Rename/add flows stay in the original CLI
- [x] The backend records check-ins through the existing `daka` data files

## Later

Ideas deliberately outside the first release:

* Caddy config generation
* Favorites or grouping
* Authentication
* Importing app definitions from other systems
* Read-only diagnostics for local services
