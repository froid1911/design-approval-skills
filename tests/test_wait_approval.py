"""wait_approval.py against a fake Discord API. Run: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAITER = os.path.join(ROOT, "skills", "discord-post", "wait_approval.py")
BOSS, OTHER, POST = "100", "200", "1000"


def msg(mid: str, author: str, text: str, reply_to: str | None = None) -> dict:
    m = {"id": mid, "author": {"id": author, "username": f"u{author}"}, "content": text}
    if reply_to:
        m["message_reference"] = {"message_id": reply_to}
    return m


class Fake(BaseHTTPRequestHandler):
    scenario: dict = {}

    def log_message(self, format, *args):  # noqa: A002 — silence the default access log
        pass

    def do_GET(self):
        if self.headers.get("Authorization") != "Bot t":
            return self.reply(401, {"message": "401: Unauthorized"})
        path = urllib.parse.unquote(self.path)
        sc = Fake.scenario
        if f"/messages/{POST}/reactions/" in path:
            emoji = path.rsplit("/", 1)[1].split("?")[0]
            users = sc.get("reactions", {}).get(emoji)
            return self.reply(200, [{"id": u} for u in users]) if users else self.reply(404, {"code": 10014})
        if "/messages?after=" in path:
            after = int(path.split("after=")[1].split("&")[0])
            page = sorted((m for m in sc.get("messages", []) if int(m["id"]) > after),
                          key=lambda m: int(m["id"]))[:100]
            return self.reply(200, list(reversed(page)))  # Discord returns newest first
        if path.endswith(f"/messages/{POST}"):
            post = msg(POST, "webhook", "design")
            post["reactions"] = [{"emoji": {"name": e}, "count": len(u)}
                                 for e, u in sc.get("reactions", {}).items() if u]
            return self.reply(200, post)
        return self.reply(404, {"message": "Unknown Message"})

    def reply(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


class WaitApprovalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.api = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_waiter(self, scenario, message=POST, timeout="20s", token="t", approvers=BOSS, extra=()):
        Fake.scenario = scenario
        env = {**os.environ, "DISCORD_API": self.api, "DISCORD_BOT_TOKEN": token,
               "DISCORD_APPROVERS": approvers, "HOME": "/nonexistent"}
        res = subprocess.run(
            [sys.executable, WAITER, "--channel", "5", "--message", message,
             "--timeout", timeout, "--interval", "1s", *extra],
            capture_output=True, text=True, env=env, timeout=30,
        )
        return res.returncode, json.loads(res.stdout.strip().splitlines()[-1])

    def test_approve_returns_discussion_chain_only(self):
        code, out = self.run_waiter({
            "reactions": {"👍": [BOSS]},
            "messages": [
                msg("1001", OTHER, "what about caching?", reply_to=POST),
                msg("1002", BOSS, "good point, add it", reply_to="1001"),
                msg("1003", OTHER, "unrelated chatter"),
                msg("1004", OTHER, "reply to unrelated", reply_to="1003"),
            ],
        })
        self.assertEqual((code, out["status"], out["by"]), (0, "approved", BOSS))
        self.assertEqual([m["id"] for m in out["discussion"]], ["1001", "1002"])
        self.assertEqual(out["discussion"][1]["reply_to"], "1001")

    def test_reject_beats_revise_beats_approve(self):
        code, out = self.run_waiter({"reactions": {"👍": [BOSS], "🔁": [BOSS], "👎": [BOSS]}})
        self.assertEqual((code, out["status"]), (1, "rejected"))
        code, out = self.run_waiter({"reactions": {"👍": [BOSS], "🔁": [BOSS]}})
        self.assertEqual((code, out["status"]), (5, "revise"))

    def test_revise_carries_the_discussion(self):
        code, out = self.run_waiter({
            "reactions": {"🔁": [BOSS]},
            "messages": [msg("1001", OTHER, "split it into two PRs", reply_to=POST)],
        })
        self.assertEqual((code, out["status"]), (5, "revise"))
        self.assertEqual(out["discussion"][0]["text"], "split it into two PRs")

    def test_non_approvers_and_replies_never_decide(self):
        code, out = self.run_waiter({
            "reactions": {"👍": [OTHER], "👎": [OTHER]},
            "messages": [msg("1001", BOSS, "looks good, go", reply_to=POST)],
        }, timeout="2s")
        self.assertEqual((code, out["status"]), (3, "timeout"))
        self.assertEqual(len(out["discussion"]), 1)

    def test_discussion_pages_past_100_messages(self):
        many = [msg(str(1001 + i), OTHER, f"m{i}", reply_to=POST) for i in range(150)]
        code, out = self.run_waiter({"reactions": {"👍": [BOSS]}, "messages": many})
        self.assertEqual(code, 0)
        self.assertEqual(len(out["discussion"]), 150)

    def test_similar_emoji_decide(self):
        for emoji, expected in [("🔄", (5, "revise")), ("🔃", (5, "revise")),
                                ("✅", (0, "approved")), ("👍🏽", (0, "approved")),
                                ("❌", (1, "rejected")), ("👎🏻", (1, "rejected"))]:
            with self.subTest(emoji=emoji):
                code, out = self.run_waiter({"reactions": {emoji: [BOSS]}})
                self.assertEqual((code, out["status"]), expected)

    def test_similar_emoji_from_non_approvers_never_decide(self):
        code, out = self.run_waiter({"reactions": {"🔄": [OTHER], "✅": [OTHER]}}, timeout="2s")
        self.assertEqual((code, out["status"]), (3, "timeout"))

    def test_return_on_reply_wakes_on_a_new_reply(self):
        code, out = self.run_waiter({
            "messages": [msg("1001", OTHER, "simply remove the output", reply_to=POST)],
        }, extra=["--return-on-reply"])
        self.assertEqual((code, out["status"]), (6, "reply"))
        self.assertEqual(out["discussion"][0]["text"], "simply remove the output")

    def test_seen_skips_replies_already_reported(self):
        first = msg("1001", OTHER, "first", reply_to=POST)
        code, out = self.run_waiter({"messages": [first]}, timeout="2s",
                                    extra=["--return-on-reply", "--seen", "1001"])
        self.assertEqual((code, out["status"]), (3, "timeout"))
        code, out = self.run_waiter({"messages": [first, msg("1002", BOSS, "second", reply_to="1001")]},
                                    extra=["--return-on-reply", "--seen", "1001"])
        self.assertEqual((code, out["status"]), (6, "reply"))
        self.assertEqual([m["id"] for m in out["discussion"]], ["1001", "1002"])

    def test_decision_beats_a_new_reply(self):
        code, out = self.run_waiter({
            "reactions": {"👍": [BOSS]},
            "messages": [msg("1001", OTHER, "nit", reply_to=POST)],
        }, extra=["--return-on-reply"])
        self.assertEqual((code, out["status"]), (0, "approved"))

    def test_errors_fail_fast(self):
        code, out = self.run_waiter({}, message="999")
        self.assertEqual((code, out["status"]), (4, "error"))
        self.assertIn("HTTP 404", out["error"])
        code, out = self.run_waiter({}, token="wrong")
        self.assertEqual((code, out["status"]), (4, "error"))
        code, out = self.run_waiter({}, approvers="")
        self.assertIn("no approvers", out["error"])


if __name__ == "__main__":
    unittest.main()
