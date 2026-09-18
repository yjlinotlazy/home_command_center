import unittest

from request_logging import route_for_target, tool_id_for_target


class RequestLoggingTest(unittest.TestCase):
    def test_identifies_only_embedded_tool_routes(self):
        self.assertEqual(tool_id_for_target("/api/tools/tomato_watch/action"), "tool:tomato_watch")
        self.assertEqual(tool_id_for_target("/tools/chinese-practice"), "tool:chinese-practice")
        self.assertIsNone(tool_id_for_target("/monitor"))
        self.assertIsNone(tool_id_for_target("/static/monitor.js"))

    def test_normalizes_tool_route(self):
        self.assertEqual(route_for_target("/api/tools/tomato_watch/action"), "/api/tools/tomato_watch/:path")
        self.assertEqual(route_for_target("/tools/daka"), "/tools/daka")


if __name__ == "__main__":
    unittest.main()
