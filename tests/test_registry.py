import tempfile
import unittest
from pathlib import Path

from server import AppRegistry, ConfigError


class AppRegistryTest(unittest.TestCase):
    def test_loads_required_and_optional_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps_dir = Path(tmp)
            (apps_dir / "demo.yaml").write_text(
                """
id: demo
name: Demo
url: "https://example.test:8001"
thumbnail: ./thumb.png
description: Demo app
tags:
  - tools
health_url: "http://127.0.0.1:8001/"
health_verify_tls: false
""".strip(),
                encoding="utf-8",
            )

            apps = AppRegistry(apps_dir).load()

            self.assertEqual(len(apps), 1)
            self.assertEqual(apps[0].id, "demo")
            self.assertEqual(apps[0].tags, ("tools",))
            self.assertEqual(apps[0].health_url, "http://127.0.0.1:8001/")
            self.assertFalse(apps[0].health_verify_tls)

    def test_missing_required_field_is_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps_dir = Path(tmp)
            (apps_dir / "bad.yaml").write_text("id: bad\nname: Bad\n", encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "required string field 'url'"):
                AppRegistry(apps_dir).load()

    def test_duplicate_ids_are_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps_dir = Path(tmp)
            (apps_dir / "one.yaml").write_text(
                'id: demo\nname: Demo\nurl: "https://example.test:8001"\n',
                encoding="utf-8",
            )
            (apps_dir / "two.yaml").write_text(
                'id: demo\nname: Demo 2\nurl: "https://example.test:8002"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "Duplicate app id 'demo'"):
                AppRegistry(apps_dir).load()

    def test_skips_command_tool_settings_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps_dir = Path(tmp)
            (apps_dir / "workbook_go.yaml").write_text(
                "type: command_tool\nchinese_chars:\n  output_dir: /tmp/workbooks\n",
                encoding="utf-8",
            )

            self.assertEqual(AppRegistry(apps_dir).load(), [])

    def test_uses_png_matching_yaml_stem_as_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps_dir = Path(tmp)
            (apps_dir / "demo.yaml").write_text(
                'id: demo\nname: Demo\nurl: "https://example.test"\n',
                encoding="utf-8",
            )
            cover = apps_dir / "demo.png"
            cover.write_bytes(b"png")

            registry = AppRegistry(apps_dir)
            app = registry.load()[0]

            self.assertEqual(app.to_dict()["thumbnail"], "/thumb/demo")
            self.assertEqual(registry.thumbnail_path("demo"), cover.resolve())

    def test_command_tool_cover_uses_registered_app_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            apps_dir = Path(tmp)
            cover = apps_dir / "eat_what.png"
            cover.write_bytes(b"png")

            registry = AppRegistry(apps_dir)

            self.assertEqual(registry.thumbnail_path("tool:eat-what"), cover.resolve())
            payload = next(
                app for app in registry.app_payload()["apps"] if app["id"] == "tool:eat-what"
            )
            self.assertEqual(payload["thumbnail"], "/thumb/tool:eat-what")


if __name__ == "__main__":
    unittest.main()
