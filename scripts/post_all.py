# -*- coding: utf-8 -*-
"""毎日の自動投稿エントリーポイント
generate_post で文面+カードを作り、X / Bluesky / Threads へ投稿する。
どれか1つが失敗しても他は止めない設計。
"""
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_post import main as generate_main, load_state, save_state  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JST = ZoneInfo("Asia/Tokyo")


def post_to_x(text: str, card_path: str | None) -> str | None:
    """X(v2)に投稿。成功したらtweet idを返す"""
    import tweepy
    auth_kwargs = dict(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )
    client = tweepy.Client(**auth_kwargs)
    media_ids = None
    if card_path:
        api_v1 = tweepy.API(tweepy.OAuth1UserHandler(
            auth_kwargs["consumer_key"], auth_kwargs["consumer_secret"],
            auth_kwargs["access_token"], auth_kwargs["access_token_secret"]))
        media = api_v1.media_upload(card_path)
        media_ids = [media.media_id]
    resp = client.create_tweet(text=text, media_ids=media_ids)
    return str(resp.data["id"])


def post_to_bluesky(text: str, card_path: str | None) -> None:
    from atproto import Client
    client = Client()
    client.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"])
    if card_path:
        img_bytes = Path(card_path).read_bytes()
        client.send_image(text=text, image=img_bytes, image_alt="御朱印豆知識カード")
    else:
        client.send_post(text=text)


def post_to_threads(text: str, card_path: str | None) -> None:
    """Threads Graph API。画像はリポジトリのraw URL経由(公開リポジトリのみ)。
    非公開リポジトリや画像なしの場合はテキストのみ投稿。"""
    import requests
    token = os.environ["THREADS_ACCESS_TOKEN"]
    user_id = os.environ["THREADS_USER_ID"]
    base = f"https://graph.threads.net/v1.0/{user_id}/threads"

    params = {"access_token": token, "text": text}
    image_url = None
    repo = os.environ.get("GITHUB_REPOSITORY")  # 例: username/meguru-auto
    if card_path and repo and os.environ.get("THREADS_IMAGE_VIA_RAW", "true") == "true":
        rel = Path(card_path).resolve().relative_to(ROOT)
        image_url = f"https://raw.githubusercontent.com/{repo}/main/{rel}"
    if image_url:
        params.update({"media_type": "IMAGE", "image_url": image_url})
    else:
        params["media_type"] = "TEXT"

    r = requests.post(base, params=params, timeout=30)
    r.raise_for_status()
    container_id = r.json()["id"]
    pub = requests.post(
        f"https://graph.threads.net/v1.0/{user_id}/threads_publish",
        params={"access_token": token, "creation_id": container_id}, timeout=30)
    pub.raise_for_status()


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    result = generate_main()
    text, card_path = result["text"], result["card_path"]
    print(f"[generated] category={result['category']}\n{text}\n")

    platforms = cfg["posting"]["platforms"]
    errors = []
    tweet_id = None

    if platforms.get("x"):
        try:
            tweet_id = post_to_x(text, card_path)
            print(f"[x] posted: {tweet_id}")
        except Exception:
            errors.append(("x", traceback.format_exc()))

    if platforms.get("bluesky"):
        try:
            post_to_bluesky(text, card_path)
            print("[bluesky] posted")
        except Exception:
            errors.append(("bluesky", traceback.format_exc()))

    if platforms.get("threads"):
        try:
            post_to_threads(text, card_path)
            print("[threads] posted")
        except Exception:
            errors.append(("threads", traceback.format_exc()))

    # セルフリプ・計測用に投稿記録を保存
    if tweet_id:
        state = load_state()
        state.setdefault("last_posts", []).append({
            "tweet_id": tweet_id,
            "posted_at": datetime.now(JST).isoformat(),
            "category": result["category"],
            "topic_id": result["topic_id"],
            "text_head": text[:40],
            "self_replied": False,
            "measured": False,
        })
        state["last_posts"] = state["last_posts"][-60:]  # 直近60件だけ保持
        save_state(state)

    for name, tb in errors:
        print(f"[ERROR] {name}:\n{tb}", file=sys.stderr)
    if errors and len(errors) == sum(1 for v in platforms.values() if v):
        sys.exit(1)  # 全滅した場合のみ失敗扱い(通知が飛ぶ)


if __name__ == "__main__":
    main()
