# -*- coding: utf-8 -*-
"""セルフリプ: 投稿から数時間後に反応を確認し、
しきい値(いいね数)を超えた投稿にだけ文脈に沿ったアプリ誘導リプを付ける。
指標取得は自アカウントのowned readsのため低単価($0.001/件)。
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
import tweepy
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_post import load_state, save_state  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JST = ZoneInfo("Asia/Tokyo")


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    sr = cfg["self_reply"]
    if not sr["enabled"]:
        print("self_reply disabled")
        return

    state = load_state()
    now = datetime.now(JST)
    targets = [
        p for p in state.get("last_posts", [])
        if not p["self_replied"]
        and p["category"] != "promo"  # 宣伝投稿にはリプしない
        and datetime.fromisoformat(p["posted_at"]) <= now - timedelta(hours=sr["check_hours_after"] - 1)
        and datetime.fromisoformat(p["posted_at"]) >= now - timedelta(hours=48)
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
    ids = [p["tweet_id"] for p in targets]
    resp = client.get_tweets(ids=ids, tweet_fields=["public_metrics"],
                             user_auth=True)
    metrics = {str(t.id): t.public_metrics for t in (resp.data or [])}

    ai = anthropic.Anthropic()
    for p in targets:
        m = metrics.get(p["tweet_id"])
        if not m:
            continue
        likes = m.get("like_count", 0)
        print(f"{p['tweet_id']} likes={likes} (threshold={sr['like_threshold']})")
        if likes < sr["like_threshold"]:
            continue

        link_line = ""
        if sr["include_store_link"]:
            link_line = f"\niOS: {cfg['app']['ios_url']}\nAndroid: {cfg['app']['android_url']}"

        gen = ai.messages.create(
            model=cfg["claude"]["model"],
            max_tokens=300,
            system="伸びた投稿へのセルフリプライを書きます。元投稿の話題に自然につなげて、"
                   "個人開発アプリを一言だけ紹介。80字以内。押し売り禁止。絵文字1個まで。"
                   "URLは書かない(こちらで追加します)。出力はリプ本文のみ。",
            messages=[{"role": "user", "content":
                       f"元投稿(冒頭): {p['text_head']}\nアプリ: {cfg['app']['name']} - {cfg['app']['description']}"}],
        )
        reply_text = gen.content[0].text.strip() + link_line
        client.create_tweet(text=reply_text, in_reply_to_tweet_id=p["tweet_id"])
        p["self_replied"] = True
        print(f"[replied] {p['tweet_id']}")

    save_state(state)


if __name__ == "__main__":
    main()
