from __future__ import annotations

import html
import json


def render_tool_arg_html(arg: dict[str, object]) -> str:
    attrs = [
        f'name="{html.escape(str(arg["name"]))}"',
        f'data-kind="{html.escape(str(arg["kind"]))}"',
        f'maxlength="{int(arg.get("max_length") or 200)}"',
    ]
    if arg.get("required", True):
        attrs.append("required")
    if arg.get("placeholder"):
        attrs.append(f'placeholder="{html.escape(str(arg["placeholder"]))}"')
    if arg.get("pattern"):
        attrs.append(f'pattern="{html.escape(str(arg["pattern"]))}"')

    kind = str(arg["kind"])
    default = html.escape(str(arg.get("default") or ""))
    label = html.escape(str(arg["label"]))
    help_text = str(arg.get("help") or "")

    if kind == "textarea":
        control = f"<textarea {' '.join(attrs)}>{default}</textarea>"
    elif kind == "date":
        control = f'<input type="date" value="{default}" {" ".join(attrs)}>'
    elif kind == "select":
        options = []
        for choice in arg.get("choices") or ():
            choice_text = html.escape(str(choice))
            selected = " selected" if choice == arg.get("default") else ""
            options.append(f'<option value="{choice_text}"{selected}>{choice_text}</option>')
        control = f"<select {' '.join(attrs)}>{''.join(options)}</select>"
    else:
        control = f'<input type="text" value="{default}" {" ".join(attrs)}>'

    help_html = f"<small>{html.escape(help_text)}</small>" if help_text else ""
    return f"""<label class="tool-field">
    <span>{label}</span>
    {control}
    {help_html}
</label>"""


def render_tool_page_shell(
    tool_id: str,
    tool_name: str,
    tool_description: str,
    *,
    body_html: str | None = None,
    extra_stylesheets: tuple[str, ...] = (),
    extra_head: str = "",
    script_src: str = "/static/tool.js",
    script_type: str | None = None,
) -> str:
    title = f"{tool_name} - 家用命令台"
    if body_html is None:
        body_html = """<form class="tool-panel" data-tool-form>
      <div class="tool-fields" data-tool-fields></div>
      <button class="open tool-submit" type="submit" data-tool-submit>生成</button>
    </form>

    <section class="notice" data-tool-status hidden></section>
    <section class="notice" data-tool-error hidden></section>
    <section class="tool-daka" data-tool-daka hidden></section>
    <section class="generated-files" data-tool-files></section>
    <pre class="tool-output" data-tool-output></pre>"""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/static/styles.css">
  {"".join(f'<link rel="stylesheet" href="{html.escape(sheet)}">' for sheet in extra_stylesheets)}
  {extra_head}
  <script>window.__COMMAND_TOOL_ID__ = {json.dumps(tool_id)};</script>
  <script src="{html.escape(script_src)}"{' type="' + html.escape(script_type) + '"' if script_type else ""} defer></script>
</head>
<body>
  <main class="shell tool-shell">
    <header class="topbar">
      <div>
        <h1 data-tool-title>{html.escape(tool_name)}</h1>
        <p data-tool-description>{html.escape(tool_description)}</p>
      </div>
      <a class="back" href="/">返回命令台</a>
    </header>
    {body_html}
  </main>
</body>
</html>
"""
