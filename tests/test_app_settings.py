import tempfile
import unittest
from pathlib import Path

from app_settings import AppSettingsError, chinese_chars_output_dir


class AppSettingsTest(unittest.TestCase):
    def test_loads_chinese_chars_output_dir_from_workbook_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "workbook_go.yaml"
            config.write_text(
                "chinese_chars:\n  output_dir: /tmp/home-command-center-output\n",
                encoding="utf-8",
            )

            self.assertEqual(
                chinese_chars_output_dir(config),
                Path("/tmp/home-command-center-output"),
            )

    def test_rejects_invalid_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "workbook_go.yaml"
            config.write_text("- nope\n", encoding="utf-8")

            with self.assertRaisesRegex(AppSettingsError, "YAML mapping"):
                chinese_chars_output_dir(config)

    def test_rejects_invalid_chinese_chars_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "workbook_go.yaml"
            config.write_text("chinese_chars: nope\n", encoding="utf-8")

            with self.assertRaisesRegex(AppSettingsError, "chinese_chars"):
                chinese_chars_output_dir(config)


if __name__ == "__main__":
    unittest.main()
