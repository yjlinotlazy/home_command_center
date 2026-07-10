import unittest

from cli_tools import chinese_practice, daka_checkin, eat_what


class ToolPageTest(unittest.TestCase):
    def test_each_tool_renders_its_own_page_shell(self):
        cases = [
            (daka_checkin.render_tool_page(), "daka", "新年愿望打卡"),
            (eat_what.render_tool_page(), "eat-what", "吃啥"),
        ]

        for html, tool_id, tool_name in cases:
            self.assertIn(f'window.__COMMAND_TOOL_ID__ = "{tool_id}";', html)
            self.assertIn(f"<h1 data-tool-title>{tool_name}</h1>", html)
            self.assertIn("<script src=\"/static/tool.js?v=", html)
            self.assertIn("<a class=\"back\" href=\"/\">返回命令台</a>", html)

    def test_eat_what_uses_single_row_submit_layout(self):
        html = eat_what.render_tool_page()

        self.assertIn('tool-panel--eat-what', html)
        self.assertIn('tool-fields--eat-what', html)
        self.assertIn('tool-submit-row', html)
        self.assertIn('tool-submit--eat-what', html)

    def test_chinese_practice_uses_custom_field_layout(self):
        html = chinese_practice.render_tool_page()

        self.assertIn('<link rel="stylesheet" href="/static/chinese_practice.css?v=', html)
        self.assertIn('<script src="/static/chinese_practice.js?v=', html)
        self.assertIn('type="module" defer></script>', html)
        self.assertIn('data-tool-slot="chars"', html)
        self.assertIn('data-tool-slot="output_dir"', html)
        self.assertIn('data-tool-slot="density"', html)
        self.assertIn('data-tool-slot="paper"', html)
        self.assertIn('data-tool-slot="mode"', html)
        self.assertIn('data-tool-slot="copies"', html)
        self.assertIn('tool-submit--large', html)


if __name__ == "__main__":
    unittest.main()
