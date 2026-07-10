export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function fieldHtml(arg) {
  const attrs = [
    `name="${escapeHtml(arg.name)}"`,
    `data-kind="${escapeHtml(arg.kind)}"`,
    `maxlength="${Number(arg.max_length) || 200}"`,
  ];
  if (arg.required) attrs.push("required");
  if (arg.placeholder) attrs.push(`placeholder="${escapeHtml(arg.placeholder)}"`);
  if (arg.pattern) attrs.push(`pattern="${escapeHtml(arg.pattern)}"`);

  let control = "";
  if (arg.kind === "textarea") {
    control = `<textarea ${attrs.join(" ")}>${escapeHtml(arg.default || "")}</textarea>`;
  } else if (arg.kind === "date") {
    control = `<input type="date" value="${escapeHtml(arg.default || "")}" ${attrs.join(" ")}>`;
  } else if (arg.kind === "select") {
    const options = arg.choices
      .map((choice) => {
        const selected = choice === arg.default ? " selected" : "";
        return `<option value="${escapeHtml(choice)}"${selected}>${escapeHtml(choice)}</option>`;
      })
      .join("");
    control = `<select ${attrs.join(" ")}>${options}</select>`;
  } else {
    control = `<input type="text" value="${escapeHtml(arg.default || "")}" ${attrs.join(" ")}>`;
  }

  return `<label class="tool-field">
    <span>${escapeHtml(arg.label)}</span>
    ${control}
    ${arg.help ? `<small>${escapeHtml(arg.help)}</small>` : ""}
  </label>`;
}
