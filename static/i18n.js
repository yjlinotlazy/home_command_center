const STRINGS = {
  zh: {
    open: "打开",
    use: "使用",
    online: "在线",
    offline: "离线",
    unknown: "未知",
    no_description: "没有描述。",
    count_apps: (count) => `${count} 个应用`,
    no_apps: "没有符合条件的应用。",
    search: "搜索",
    filters: "筛选",
    search_placeholder: "名称、地址或描述",
    tags: "标签",
    all_tags: "全部标签",
    status: "状态",
    all_status: "全部状态",
    language: "语言",
    chinese: "中文",
    english: "English",
    back_to_dashboard: "返回命令台",
    generate: "生成",
    practice_chars: "练习汉字",
    chars_too_long: "汉字必须少于等于 40 个字符",
    chars_only_chinese: "只支持中文汉字",
    tool_load_error: "无法加载工具",
    tool_run_error: "工具运行失败",
    no_output: "（没有输出）",
    load_apps_error: "无法加载应用",
    load_daka_error: "无法加载打卡数据",
    generate_report_error: "无法生成报告",
    checkin_failed: "打卡失败",
    checkin_done: "打卡完成",
    date: "日期",
    report_task_summary: "生成任务汇总",
    report_resolution_summary: "生成愿望汇总",
    report_task_summary_done: "任务汇总已生成。",
    report_resolution_summary_done: "愿望汇总已生成。",
    report_task_summary_loading: "正在生成任务汇总。",
    report_resolution_summary_loading: "正在生成愿望汇总。",
    no_daka_items: "还没有打卡项目。",
    no_data: "没有可显示的数据。",
    today_checked: "今天已打卡",
    click_to_checkin: "点击打卡",
    count_items: (count) => `${count} 项`,
    total_checkins: (count) => `累计 ${count} 次`,
    annual_progress: "年度进度",
    weekly_progress: "周度进度",
    day_short: "日",
    week_short: "周",
    daka_task_summary: "任务汇总",
    daka_resolution_summary: "愿望汇总",
    task_level: "任务级别",
    resolution_level: "愿望级别",
  },
  en: {
    open: "Open",
    use: "Use",
    online: "Online",
    offline: "Offline",
    unknown: "Unknown",
    no_description: "No description.",
    count_apps: (count) => `${count} apps`,
    no_apps: "No apps match the current filters.",
    search: "Search",
    filters: "Filters",
    search_placeholder: "Name, address, or description",
    tags: "Tags",
    all_tags: "All tags",
    status: "Status",
    all_status: "All status",
    language: "Language",
    chinese: "中文",
    english: "English",
    back_to_dashboard: "Back to dashboard",
    generate: "Generate",
    practice_chars: "Chinese characters",
    chars_too_long: "Chinese characters must be 40 characters or fewer",
    chars_only_chinese: "Only Chinese characters are supported",
    tool_load_error: "Unable to load the tool",
    tool_run_error: "Tool run failed",
    no_output: "(No output)",
    load_apps_error: "Unable to load apps",
    load_daka_error: "Unable to load check-in data",
    generate_report_error: "Unable to generate report",
    checkin_failed: "Check-in failed",
    checkin_done: "Check-in complete",
    date: "Date",
    report_task_summary: "Generate task summary",
    report_resolution_summary: "Generate resolution summary",
    report_task_summary_done: "Task summary generated.",
    report_resolution_summary_done: "Resolution summary generated.",
    report_task_summary_loading: "Generating task summary.",
    report_resolution_summary_loading: "Generating resolution summary.",
    no_daka_items: "No check-in items yet.",
    no_data: "No data to display.",
    today_checked: "Checked in today",
    click_to_checkin: "Click to check in",
    count_items: (count) => `${count} items`,
    total_checkins: (count) => `${count} total check-ins`,
    annual_progress: "Annual progress",
    weekly_progress: "Weekly progress",
    day_short: "Day",
    week_short: "Week",
    daka_task_summary: "Task summary",
    daka_resolution_summary: "Resolution summary",
    task_level: "Task level",
    resolution_level: "Resolution level",
  },
};

function currentLang() {
  return window.__HCC_LANG__ === "en" ? "en" : "zh";
}

function translate(key, ...args) {
  const lang = currentLang();
  const value = STRINGS[lang][key] ?? STRINGS.zh[key] ?? key;
  if (typeof value === "function") {
    return value(...args);
  }
  if (args.length === 1 && typeof args[0] === "object" && args[0] !== null) {
    return value.replace(/\{(\w+)\}/g, (_, name) => String(args[0][name] ?? ""));
  }
  return value;
}

function applyLangFromStorage() {
  const url = new URL(window.location.href);
  const stored = localStorage.getItem("hcc-lang");
  const current = url.searchParams.get("lang");
  if (!current && stored && stored !== currentLang()) {
    if (stored === "zh") {
      url.searchParams.delete("lang");
    } else {
      url.searchParams.set("lang", stored);
    }
    window.location.replace(url.toString());
    return true;
  }
  return false;
}

function setupLanguageSwitcher() {
  const select = document.querySelector("[data-lang-switcher]");
  if (!select) return;

  select.value = currentLang();
  select.addEventListener("change", () => {
    const lang = select.value === "en" ? "en" : "zh";
    localStorage.setItem("hcc-lang", lang);
    const url = new URL(window.location.href);
    if (lang === "zh") {
      url.searchParams.delete("lang");
    } else {
      url.searchParams.set("lang", lang);
    }
    window.location.href = url.toString();
  });
}

window.__HCC_I18N = { currentLang, t: translate, setupLanguageSwitcher, applyLangFromStorage };
if (!applyLangFromStorage()) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupLanguageSwitcher, { once: true });
  } else {
    setupLanguageSwitcher();
  }
}
