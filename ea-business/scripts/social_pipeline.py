#!/usr/bin/env python3
"""Turn a draft blog post (Markdown + front matter) into platform-ready posts.

Reads a content draft, extracts the title/keywords, and emits short posts for
X/Twitter and note — each with the mandatory compliance disclaimer appended and
length checks for the target platform. It does NOT post anything: account
linking and publishing are done by a human (per project scope).

Usage:
    python social_pipeline.py <draft.md> [--lang ja|en] [-o out.md]

Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DISCLAIMER = {
    "ja": "※投資助言ではありません。取引にはリスクが伴い、過去の成績は将来を保証しません。",
    "en": "Not investment advice. Trading is risky; past performance does not guarantee future results.",
}

TWEET_LIMIT = 280


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Return (meta, body). Supports a leading --- front matter block."""
    meta: dict[str, str] = {}
    body = text
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if m:
        block, body = m.group(1), m.group(2)
        for line in block.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    return meta, body


def first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def with_disclaimer(text: str, lang: str) -> str:
    return f"{text}\n\n{DISCLAIMER.get(lang, DISCLAIMER['en'])}"


def build_posts(meta: dict[str, str], body: str, lang: str) -> str:
    title = meta.get("title") or first_heading(body) or "(untitled)"
    link = "[記事リンク]" if lang == "ja" else "[article link]"

    if lang == "ja":
        tweet = f"{title}\n仕組み化のポイントを記事にまとめました。続きはこちら→{link}"
        note = f"{title}\n\n資金管理を仕組み化する話を書きました。続きはこちら→{link}"
    else:
        tweet = f"{title}\nA short write-up on systematizing this. Read more → {link}"
        note = f"{title}\n\nA longer take on the topic. Read more → {link}"

    tweet = with_disclaimer(tweet, lang)
    note = with_disclaimer(note, lang)

    warn = ""
    if len(tweet) > TWEET_LIMIT:
        warn = f"\n> ⚠️ X/Twitter post is {len(tweet)} chars (> {TWEET_LIMIT}). Trim before publishing.\n"

    out = [
        f"# Social drafts — {title}",
        "",
        "> Review required before publishing. Account linking & posting are manual.",
        warn,
        "## X / Twitter",
        "```",
        tweet,
        "```",
        f"_length: {len(tweet)} / {TWEET_LIMIT}_",
        "",
        "## note",
        "```",
        note,
        "```",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("draft", help="draft markdown file")
    ap.add_argument("--lang", choices=["ja", "en"], default="ja")
    ap.add_argument("-o", "--out", help="output path (default stdout)")
    args = ap.parse_args(argv)

    path = Path(args.draft)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
    lang = meta.get("lang", args.lang)
    out = build_posts(meta, body, lang)

    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
