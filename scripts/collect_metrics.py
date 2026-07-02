# -*- coding: utf-8 -*-
"""投稿から24時間後の反応データをCSVに蓄積する(学習ループの素材)"""
import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import tweepy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_post import load_state, save_state  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JST = ZoneInfo("Asia/Tokyo")
CSV_PATH = ROOT / "data" / "metrics.csv"
FIELDS = ["date", "tweet_id", "category", "topic_id", "text_head",
          "impressions", "likes", "retweets", "replies", "weekday", "hour"]


def main() -> None:
    state = load_state()
    now = datetime.now(JST)
    targets = [
        p for p in state.get("last_posts", [])
        if not p.get("measured")
        and datetime.fromisoformat(p["posted_at"]) <= now - timedelta(hours=23)
    ]
    if not targets:
        print("no targets")
        return

    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )
    resp = client.get_tweets(
        ids=[p["tweet_id"] for p in targets],
        tweet_fields=["public_metrics", "non_public_metrics"],
        user_auth=True,
    )
    metrics = {str(t.id): t for t in (resp.data or [])}

    new_file = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for p in targets:
            t = metrics.get(p["tweet_id"])
            if not t:
                p["measured"] = True  # 削除済みなどはスキップ扱い
                continue
            pm = t.public_metrics or {}
            npm = getattr(t, "non_public_metrics", None) or {}
            posted = datetime.fromisoformat(p["posted_at"])
            w.writerow({
                "date": posted.strftime("%Y-%m-%d"),
                "tweet_id": p["tweet_id"],
                "category": p["category"],
                "topic_id": p["topic_id"],
                "text_head": p["text_head"],
                "impressions": npm.get("impression_count", pm.get("impression_count", 0)),
                "likes": pm.get("like_count", 0),
                "retweets": pm.get("retweet_count", 0),
                "replies": pm.get("reply_count", 0),
                "weekday": posted.strftime("%a"),
                "hour": posted.hour,
            })
            p["measured"] = True
            print(f"[measured] {p['tweet_id']}")

    save_state(state)


if __name__ == "__main__":
    main()
