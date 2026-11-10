#!/usr/bin/env python3
"""Post text and files to a Discord channel through a webhook.

  post.py "message"                       # text
  post.py --file shot.png "caption"       # text + attachment(s), up to 10
  echo "long text" | post.py -            # text from stdin
  post.py --dry-run --file a.png "hi"     # show what would be sent, send nothing

Webhook URL: $DISCORD_WEBHOOK_URL, else ~/.config/discord-post/webhook.
Mentions are disabled (allowed_mentions.parse = []): a post never pings anyone.
Text over 2000 characters is split on line boundaries; files ride on the last message.
Standard library only.
"""
import argparse
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

LIMIT = 2000
MAX_FILES = 10
MAX_FILE_BYTES = 10 * 1024 * 1024
CONFIG = os.path.expanduser("~/.config/discord-post/webhook")
WEBHOOK_RE = re.compile(r"^https://(?:canary\.|ptb\.)?(?:discord|discordapp)\.com/api/webhooks/\d+/[\w-]+$")


def webhook_url() -> str:
    url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not url and os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8") as fh:
            url = fh.read().strip()
    if not url:
        sys.exit(f"no webhook: set DISCORD_WEBHOOK_URL or write the URL to {CONFIG}")
    if not WEBHOOK_RE.match(url):
        sys.exit("webhook URL does not look like https://discord.com/api/webhooks/<id>/<token>")
    return url


def chunks(text: str) -> list[str]:
    """Split on line boundaries; hard-split any single line longer than the limit."""
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > LIMIT:
            if cur:
                out.append(cur)
                cur = ""
            out.append(line[:LIMIT])
            line = line[LIMIT:]
        if len(cur) + len(line) > LIMIT:
            out.append(cur)
            cur = ""
        cur += line
    if cur.strip():
        out.append(cur)
    return out


def multipart(payload: dict, files: list[str]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n"
        f"Content-Type: application/json\r\n\r\n".encode() + json.dumps(payload).encode() + b"\r\n"
    ]
    for i, path in enumerate(files):
        name = os.path.basename(path)
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        with open(path, "rb") as fh:
            data = fh.read()
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"files[{i}]\"; filename=\"{name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n".encode() + data + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def send(url: str, payload: dict, files: list[str]) -> dict:
    body, ctype = multipart(payload, files)
    for attempt in range(2):
        req = urllib.request.Request(
            url + "?wait=true", data=body, method="POST",
            headers={"Content-Type": ctype, "User-Agent": "discord-post-skill/1"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return json.load(res)
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")
            if err.code == 429 and attempt == 0:
                retry = json.loads(detail or "{}").get("retry_after", 2)
                time.sleep(float(retry) + 0.5)
                continue
            sys.exit(f"discord answered {err.code}: {detail[:300]}")
    sys.exit("rate limited twice; try again later")


_webhook_info: dict = {}


def jump_url(url: str, message_id: str) -> str:
    """https://discord.com/channels/<guild>/<channel>/<message>, from the webhook's own info."""
    if not _webhook_info:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "discord-post-skill/2"}), timeout=30
        ) as res:
            _webhook_info.update(json.load(res))
    return f"https://discord.com/channels/{_webhook_info['guild_id']}/{_webhook_info['channel_id']}/{message_id}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Post to a Discord channel via webhook")
    ap.add_argument("message", nargs="?", default="", help='text to post, or "-" to read stdin')
    ap.add_argument("--file", action="append", default=[], help="attachment (repeatable, max 10)")
    ap.add_argument("--username", help="override the webhook's display name for this post")
    ap.add_argument("--dry-run", action="store_true", help="print what would be sent and exit")
    ap.add_argument("--json", action="store_true",
                    help='print {"id", "channel_id", "url"} of the last message as JSON (for wait_approval.py)')
    ap.add_argument("--link-to", metavar="MESSAGE_ID",
                    help="end the post with a link to an earlier message (webhooks cannot reply)")
    args = ap.parse_args()

    text = sys.stdin.read() if args.message == "-" else args.message
    if args.link_to:
        text = f"{text.rstrip()}\n↪ follows {jump_url(webhook_url(), args.link_to)}"
    files = args.file
    if not text.strip() and not files:
        sys.exit("nothing to post: give a message and/or --file")
    if len(files) > MAX_FILES:
        sys.exit(f"at most {MAX_FILES} files per post")
    for path in files:
        if not os.path.isfile(path):
            sys.exit(f"no such file: {path}")
        if os.path.getsize(path) > MAX_FILE_BYTES:
            sys.exit(f"{path} is over 10 MB, Discord's upload limit for webhooks")

    pieces = chunks(text) or [""]
    base = {"allowed_mentions": {"parse": []}}
    if args.username:
        base["username"] = args.username

    if args.dry_run:
        for i, piece in enumerate(pieces):
            last = i == len(pieces) - 1
            print(f"--- message {i + 1}/{len(pieces)} ({len(piece)} chars)"
                  + (f", files: {', '.join(files)}" if last and files else ""))
            print(piece)
        return

    url = webhook_url()
    msg: dict = {}
    for i, piece in enumerate(pieces):
        last = i == len(pieces) - 1
        msg = send(url, {**base, "content": piece}, files if last else [])
        if not args.json:
            print(f"posted message {msg.get('id')} in channel {msg.get('channel_id')}")
    if args.json:
        print(json.dumps({"id": msg.get("id"), "channel_id": msg.get("channel_id"),
                          "url": jump_url(url, msg.get("id", ""))}))


if __name__ == "__main__":
    main()
