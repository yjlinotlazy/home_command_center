import unittest
import tempfile
from pathlib import Path
from datetime import date

import app_settings
from app_settings import eat_what_recipes_csv
from command_tools import ToolError, get_command_tool, list_command_tools, run_command_tool


class CommandToolsTest(unittest.TestCase):
    def test_tools_are_registered(self):
        self.assertEqual([tool.id for tool in list_command_tools()], ["eat-what", "daka", "chinese-practice"])

    def test_rejects_unknown_tool(self):
        with self.assertRaisesRegex(ToolError, "Unknown command tool"):
            get_command_tool("not-real")

    def test_rejects_non_chinese_chars(self):
        with self.assertRaisesRegex(ToolError, "练习汉字格式无效"):
            run_command_tool(
                "chinese-practice",
                {
                    "chars": "abc",
                    "density": "5",
                    "paper": "us_letter",
                    "mode": "1",
                    "copies": "2",
                    "output_dir": "/tmp",
                },
            )

    def test_rejects_invalid_choice(self):
        with self.assertRaisesRegex(ToolError, "纸张只能是"):
            run_command_tool(
                "chinese-practice",
                {
                    "chars": "永",
                    "density": "5",
                    "paper": "legal",
                    "mode": "1",
                    "copies": "2",
                    "output_dir": "/tmp",
                },
            )

    def test_rejects_overlong_output_dir(self):
        with self.assertRaisesRegex(ToolError, "输出目录不能超过 500 个字符"):
            run_command_tool(
                "chinese-practice",
                {
                    "chars": "永",
                    "density": "5",
                    "paper": "us_letter",
                    "mode": "1",
                    "copies": "2",
                    "output_dir": "/" + "x" * 501,
                },
            )

    def test_workbook_tool_runs_and_returns_file_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_command_tool(
                "chinese-practice",
                {
                    "chars": "永",
                    "density": "5",
                    "paper": "us_letter",
                    "mode": "1",
                    "copies": "1",
                    "output_dir": tmp,
                },
            )

            self.assertTrue(result["ok"], result["stderr"])
            self.assertEqual(len(result["files"]), 1)
            self.assertTrue(Path(tmp, result["files"][0]["name"]).exists())

    def test_eat_what_lists_recipes(self):
        result = run_command_tool(
            "eat-what",
            {
                "action": "list",
                "recipes": str(eat_what_recipes_csv()),
                "max_time": "",
                "max_weekly_time": "400",
                "max_overlap": "6",
                "veg_dishes": "3",
                "spicy_dishes": "0",
                "seed": "",
            },
        )

        self.assertTrue(result["ok"], result["stderr"])
        self.assertIn("All Recipes", result["stdout"])

    def test_eat_what_rejects_missing_recipes(self):
        result = run_command_tool(
            "eat-what",
            {
                "action": "list",
                "recipes": "/tmp/not-a-real-recipes.csv",
                "max_time": "",
                "max_weekly_time": "400",
                "max_overlap": "6",
                "veg_dishes": "3",
                "spicy_dishes": "0",
                "seed": "",
            },
        )

        self.assertFalse(result["ok"])
        self.assertIn("菜谱文件不存在", result["stderr"])

    def test_output_dir_default_refreshes_from_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "workbook_go.yaml"
            original_app_path = app_settings.WORKBOOK_GO_CONFIG
            try:
                app_settings.WORKBOOK_GO_CONFIG = config

                config.write_text("chinese_chars:\n  output_dir: /tmp/one\n", encoding="utf-8")
                first = _schema_arg("chinese-practice", "output_dir")["default"]

                config.write_text("chinese_chars:\n  output_dir: /tmp/two\n", encoding="utf-8")
                second = _schema_arg("chinese-practice", "output_dir")["default"]

                self.assertEqual(first, "/tmp/one")
                self.assertEqual(second, "/tmp/two")
            finally:
                app_settings.WORKBOOK_GO_CONFIG = original_app_path

    def test_daka_date_default_is_today(self):
        self.assertEqual(_schema_arg("daka", "date")["default"], date.today().isoformat())


def _schema_arg(tool_id, name):
    schema = get_command_tool(tool_id).to_schema()
    return next(arg for arg in schema["args"] if arg["name"] == name)


if __name__ == "__main__":
    unittest.main()
