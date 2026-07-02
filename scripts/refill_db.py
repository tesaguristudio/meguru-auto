# -*- coding: utf-8 -*-
"""月次のネタDB自動補充: Claude APIで新しいお題を30件生成して追加する。
既存お題と重複しないよう、既存一覧を渡して差分を作らせる。
"""
import json
from pathlib import Path

import anthropic
import yaml

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "neta_db.json"


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    existing = [f"{x['category']}: {x['topic']}" for x in db["items"]]

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=cfg["claude"]["model"],
        max_tokens=3000,
        system="御朱印・神社仏閣に詳しい編集者として、SNS投稿のお題を作成します。"
               "カテゴリ: mame(豆知識)15件, spot(具体的な寺社紹介)10件, question(問いかけ)5件。"
               "確実な知識のみ。不確かな固有情報(具体的な料金・時間)はhintに入れない。"
               '出力は次のJSON配列のみ(コードブロック記号禁止): '
               '[{"category": "mame", "topic": "お題", "hint": "補足(50字以内)"}]',
        messages=[{"role": "user", "content":
                   "以下の既存お題と重複しない新しいお題を30件:\n" + "\n".join(existing)}],
    )
    text = resp.content[0].text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    new_items = json.loads(text)

    # ID採番して追加
    prefix_count = {}
    for x in db["items"]:
        p = x["id"][0]
        prefix_count[p] = max(prefix_count.get(p, 0), int(x["id"][1:]))
    prefix_map = {"mame": "m", "spot": "s", "season": "k", "dev": "d", "question": "q"}
    added = 0
    existing_topics = {x["topic"] for x in db["items"]}
    for item in new_items:
        if item["topic"] in existing_topics:
            continue
        p = prefix_map.get(item["category"], "x")
        prefix_count[p] = prefix_count.get(p, 0) + 1
        item["id"] = f"{p}{prefix_count[p]:03d}"
        db["items"].append(item)
        added += 1

    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"added {added} topics (total {len(db['items'])})")


if __name__ == "__main__":
    main()
