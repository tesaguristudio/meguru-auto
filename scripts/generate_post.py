# -*- coding: utf-8 -*-
"""投稿文の自動生成
- 祭事カレンダー該当日はそのネタを優先
- 宣伝はN回に1回(config.posting.promo_interval)
- 週次分析メモ(insights.md)があればプロンプトに反映=学習ループ
"""
import json
import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
import yaml

ROOT = Path(__file__).resolve().parent.parent
JST = ZoneInfo("Asia/Tokyo")


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def load_state() -> dict:
    p = ROOT / "data" / "state.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"post_count": 0, "used_ids": [], "mame_vol": 0, "last_posts": []}


def save_state(state: dict) -> None:
    (ROOT / "data" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def seasonal_event(now: datetime) -> dict | None:
    """今日が lead_days 圏内の祭事があれば返す"""
    cal = json.loads((ROOT / "data" / "seasonal_calendar.json").read_text(encoding="utf-8"))
    for ev in cal["events"]:
        month, day = map(int, ev["date"].split("-"))
        target = now.replace(month=month, day=day, hour=12)
        delta = (target - now).days
        if 0 <= delta <= ev["lead_days"]:
            return ev
    return None


def pick_topic(state: dict, now: datetime, cfg: dict) -> dict:
    """お題を選ぶ。優先度: 宣伝回 > 祭事 > 未使用のお題(カテゴリはランダム加重)"""
    count = state["post_count"] + 1

    if count % cfg["posting"]["promo_interval"] == 0:
        return {"id": "promo", "category": "promo", "topic": "アプリの控えめな紹介",
                "hint": cfg["app"]["description"] + "。押し売り感を出さず、個人開発の親しみやすさで"}

    ev = seasonal_event(now)
    if ev and random.random() < 0.8:  # 祭事期間は8割の確率で季節ネタ
        return {"id": f"cal-{ev['date']}", "category": "season",
                "topic": ev["name"], "hint": ev["hint"]}

    db = json.loads((ROOT / "data" / "neta_db.json").read_text(encoding="utf-8"))["items"]
    unused = [x for x in db if x["id"] not in state["used_ids"]]
    if not unused:  # 全消化したらリセット(文面は毎回生成なので再利用OK)
        state["used_ids"] = []
        unused = db
    # カテゴリ加重(学習ループで将来調整可能)
    weights = {"mame": 4, "spot": 3, "season": 2, "dev": 2, "question": 2}
    pool = [x for x in unused for _ in range(weights.get(x["category"], 1))]
    return random.choice(pool)


def load_insights() -> str:
    p = ROOT / "data" / "insights.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def generate(topic: dict, now: datetime, cfg: dict) -> dict:
    """Claude APIで投稿文(+カード用テキスト)を生成"""
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 環境変数を使用
    insights = load_insights()
    date_str = now.strftime("%Y年%m月%d日(%a)")
    hashtags = " ".join(random.sample(
        cfg["posting"]["hashtags_x"], k=min(2, len(cfg["posting"]["hashtags_x"]))))

    system = f"""あなたは御朱印・神社仏閣好きの個人開発者のSNS投稿を書くライターです。
アプリ「{cfg['app']['name']}」({cfg['app']['description']})の開発者として投稿します。

絶対に守るルール:
- 全体で{cfg['posting']['max_length']}字以内(ハッシュタグ含む)
- URLは絶対に入れない
- 広告らしさ・宣伝臭を出さない。一人の御朱印好きとしての語り口
- 絵文字は0〜2個まで。⛩は使ってよい
- 事実に自信がない固有の日時・料金は書かない(「〜が多いようです」等でぼかす)
- 誇張・断定を避ける。丁寧だが硬すぎない口調

出力は必ず次のJSONのみ(前置きやコードブロック記号は禁止):
{{"post": "投稿本文(ハッシュタグ込み)", "card_title": "カード用タイトル15字以内", "card_body": "カード用本文60字以内"}}"""

    user = f"""今日は{date_str}です。以下のお題で投稿を1本書いてください。

カテゴリ: {topic['category']}
お題: {topic['topic']}
補足: {topic['hint']}

ハッシュタグはこれを末尾に: {hashtags}
{"カテゴリがpromoの場合: 個人開発の紹介として控えめに。「リンクはプロフィールから」と一言添える。" if topic['category'] == 'promo' else ''}
{"カテゴリがquestionの場合: フォロワーへの問いかけで締める。" if topic['category'] == 'question' else ''}

これまでの投稿実績から得られた知見(あれば文体・切り口の参考に):
{insights if insights else "(まだ十分なデータなし)"}"""

    resp = client.messages.create(
        model=cfg["claude"]["model"],
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = resp.content[0].text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    result = json.loads(text)
    result["topic"] = topic
    return result


def main() -> dict:
    cfg = load_config()
    state = load_state()
    now = datetime.now(JST)
    topic = pick_topic(state, now, cfg)
    generated = generate(topic, now, cfg)

    # カード画像(対象カテゴリのみ)
    card_path = None
    if cfg["card"]["enabled"] and topic["category"] in cfg["card"]["categories"]:
        from card import generate_card
        state["mame_vol"] += 1
        card_path = str(ROOT / "output" / "cards" /
                        f"card_{now.strftime('%Y%m%d')}.png")
        generate_card(
            generated["card_title"], generated["card_body"],
            f"参拝記録アプリ meguru ⛩ 御朱印豆知識 vol.{state['mame_vol']}",
            card_path, seed=state["mame_vol"],
        )

    state["post_count"] += 1
    if not topic["id"].startswith(("promo", "cal-")):
        state["used_ids"].append(topic["id"])
    save_state(state)

    return {"text": generated["post"], "card_path": card_path,
            "category": topic["category"], "topic_id": topic["id"]}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=1))
