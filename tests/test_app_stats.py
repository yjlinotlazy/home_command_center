import unittest
from datetime import date

import tempfile
from pathlib import Path

from app_stats import aggregate_events, repo_for_app, stats_for_app


class AppStatsTest(unittest.TestCase):
    def test_smart_house_hunting_uses_checkout_repo_root(self):
        repo = repo_for_app("smart_house_hunting")
        self.assertIsNotNone(repo)
        self.assertEqual(repo.name, "smart_house_hunting")

    def test_embedded_app_reads_tool_log_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            raw = repo / "server_logs" / "tool:tomato_watch" / "raw"
            raw.mkdir(parents=True)
            (raw / "2026-09-09.jsonl").write_text(
                '{"timestamp":"2026-09-09T10:00:00-04:00","method":"GET","route":"/tools/tomato_watch","status":200}\n',
                encoding="utf-8",
            )
            import app_stats
            original = app_stats.repo_for_app
            try:
                app_stats.repo_for_app = lambda _app_id: repo
                self.assertEqual(stats_for_app("tomato_watch", 30)["usage"]["requests"], 1)
            finally:
                app_stats.repo_for_app = original

    def test_aggregates_decision_metrics(self):
        result = aggregate_events(
            [
                {"timestamp": "2026-09-09T10:00:00-04:00", "method": "GET", "route": "/", "status": 200, "request_bytes": 0, "response_bytes": 10, "latency_ms": 4},
                {"timestamp": "2026-09-09T10:01:00-04:00", "method": "POST", "route": "/api/games", "status": 400, "request_bytes": 20, "response_bytes": 30, "latency_ms": 8},
            ],
            date(2026, 9, 1),
        )
        self.assertEqual(result["requests"], 2)
        self.assertEqual(result["active_days"], 1)
        self.assertEqual(result["error_requests"], 1)
        self.assertEqual(result["methods"], {"GET": 1, "POST": 1})
        self.assertEqual(result["response_bytes"], 40)


if __name__ == "__main__":
    unittest.main()
