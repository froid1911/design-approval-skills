"""post.py against a fake Discord webhook. Run: python3 -m unittest discover tests"""
import json
import os
import re
import subprocess
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTER = os.path.join(ROOT, "skills", "discord-post", "post.py")
WEBHOOK = "https://discord.com/api/webhooks/1/tok"
CHANNEL, NEW_THREAD = "5", "77"


class FakeWebhook(BaseHTTPRequestHandler):
    forum = True
    requests: list = []

    def log_message(self, format, *args):  # noqa: A002 — silence the default access log
        pass

    def do_GET(self):  # webhook info, for jump URLs
        self.reply(200, {"guild_id": "9", "channel_id": CHANNEL})

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"])).decode(errors="replace")
        found = re.search(r'name="payload_json"\r\n.*?\r\n\r\n(.*?)\r\n--', body, re.S)
        assert found, "no payload_json part"
        payload = json.loads(found.group(1))
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        FakeWebhook.requests.append({"payload": payload, "query": query})
        if "thread_name" in payload and not FakeWebhook.forum:
            return self.reply(400, {"message": "Webhooks can only create threads in forum channels",
                                    "code": 220003})
        channel = (NEW_THREAD if "thread_name" in payload
                   else query.get("thread_id", [CHANNEL])[0])
        self.reply(200, {"id": "500", "channel_id": channel})

    def reply(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


class PostTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeWebhook)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.api = f"http://127.0.0.1:{cls.server.server_address[1]}/api"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def post(self, *args, forum=True):
        FakeWebhook.forum, FakeWebhook.requests = forum, []
        env = {**os.environ, "DISCORD_API": self.api, "DISCORD_WEBHOOK_URL": WEBHOOK,
               "HOME": "/nonexistent"}
        res = subprocess.run([sys.executable, POSTER, "--json", *args, "design"],
                             capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout.strip().splitlines()[-1])

    def test_thread_name_creates_a_forum_post(self):
        out = self.post("--thread-name", "Design: X")
        self.assertEqual(FakeWebhook.requests[0]["payload"]["thread_name"], "Design: X")
        self.assertEqual(out["thread_id"], NEW_THREAD)
        self.assertEqual(out["url"], f"https://discord.com/channels/9/{NEW_THREAD}/500")

    def test_thread_posts_into_an_existing_thread(self):
        out = self.post("--thread", NEW_THREAD)
        req = FakeWebhook.requests[0]
        self.assertEqual(req["query"]["thread_id"], [NEW_THREAD])
        self.assertNotIn("thread_name", req["payload"])
        self.assertEqual(out["thread_id"], NEW_THREAD)

    def test_text_channel_falls_back_to_a_plain_post(self):
        out = self.post("--thread-name", "Design: X", forum=False)
        self.assertEqual(len(FakeWebhook.requests), 2)
        self.assertNotIn("thread_name", FakeWebhook.requests[1]["payload"])
        self.assertIsNone(out["thread_id"])
        self.assertEqual(out["channel_id"], CHANNEL)

    def test_plain_post_has_no_thread(self):
        out = self.post()
        self.assertIsNone(out["thread_id"])


if __name__ == "__main__":
    unittest.main()
