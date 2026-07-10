import unittest
from types import SimpleNamespace
from unittest.mock import patch

import daka_bridge


class DakaBridgeTest(unittest.TestCase):
    def test_load_state_marks_completed_items(self):
        data = {
            "resolutions": [
                {
                    "name": "Fitness",
                    "items": [
                        {"name": "Run", "checkins": ["2026-07-10"]},
                        {"name": "Swim", "checkins": []},
                    ],
                }
            ]
        }
        fake_loader = SimpleNamespace(load_data=lambda: data)
        fake_handler = SimpleNamespace(parse_date=lambda value: "2026-07-10")

        with patch.object(daka_bridge, "_load_modules", return_value=(fake_loader, fake_handler, [])):
            state = daka_bridge.load_state("2026-07-10")

        self.assertEqual(state["kind"], "daka")
        self.assertEqual(state["date"], "2026-07-10")
        self.assertTrue(state["resolutions"][0]["items"][0]["checked"])
        self.assertFalse(state["resolutions"][0]["items"][1]["checked"])

    def test_record_checkin_saves_and_returns_message(self):
        data = {
            "resolutions": [
                {
                    "name": "Fitness",
                    "items": [{"name": "Run", "checkins": []}],
                }
            ]
        }
        saves = []

        def load_data():
            return data

        def save_resolutions(payload):
            saves.append(("resolutions", payload["resolutions"][0]["items"][0]["checkins"][:]))

        def save_checkins(payload):
            saves.append(("checkins", payload["resolutions"][0]["items"][0]["checkins"][:]))

        def parse_date(value):
            return value or "2026-07-10"

        def check_in(item, date_value):
            item["checkins"].append(date_value)
            return True

        fake_loader = SimpleNamespace(
            load_data=load_data,
            save_resolutions=save_resolutions,
            save_checkins=save_checkins,
        )
        fake_handler = SimpleNamespace(parse_date=parse_date, check_in=check_in)

        with patch.object(daka_bridge, "_load_modules", return_value=(fake_loader, fake_handler, [])), patch.object(
            daka_bridge, "load_state", return_value={"kind": "daka", "date": "2026-07-10", "resolutions": []}
        ):
            result = daka_bridge.record_checkin("2026-07-10", "Fitness", "Run")

        self.assertEqual(result["message"], "已打卡：Fitness / Run（2026-07-10）")
        self.assertEqual(saves[0][0], "resolutions")
        self.assertEqual(saves[1][0], "checkins")
        self.assertEqual(data["resolutions"][0]["items"][0]["checkins"], ["2026-07-10"])

    def test_generate_summary_report_returns_colors_and_bars(self):
        data = {
            "resolutions": [
                {
                    "name": "Fitness",
                    "items": [{"name": "Run", "checkins": ["2026-01-01", "2026-01-02"]}],
                }
            ]
        }
        fake_loader = SimpleNamespace(load_data=lambda: data)
        fake_handler = SimpleNamespace(parse_date=lambda value: "2026-07-10")
        palette = ["red"]

        with patch.object(daka_bridge, "_load_modules", return_value=(fake_loader, fake_handler, palette)):
            report = daka_bridge.generate_report("summary", "2026-07-10")

        self.assertEqual(report["kind"], "daka-report")
        self.assertEqual(report["report_kind"], "summary")
        self.assertEqual(report["groups"][0]["resolution"], "Fitness")
        self.assertEqual(report["groups"][0]["item"], "Run")
        self.assertEqual(report["groups"][0]["color"], "red")
        self.assertIn("[", report["groups"][0]["day_bar"])
        self.assertIn("[", report["groups"][0]["week_bar"])

    def test_generate_resolution_report_aggregates_items(self):
        data = {
            "resolutions": [
                {
                    "name": "Fitness",
                    "items": [
                        {"name": "Run", "checkins": ["2026-01-01"]},
                        {"name": "Walk", "checkins": ["2026-01-01", "2026-01-03"]},
                    ],
                }
            ]
        }
        fake_loader = SimpleNamespace(load_data=lambda: data)
        fake_handler = SimpleNamespace(parse_date=lambda value: "2026-07-10")
        palette = ["red"]

        with patch.object(daka_bridge, "_load_modules", return_value=(fake_loader, fake_handler, palette)):
            report = daka_bridge.generate_report("resolution-summary", "2026-07-10")

        self.assertEqual(report["groups"][0]["resolution"], "Fitness")
        self.assertEqual(report["groups"][0]["color"], "red")
        self.assertEqual(report["groups"][0]["checked_days"], 2)


if __name__ == "__main__":
    unittest.main()
