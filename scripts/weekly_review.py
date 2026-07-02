# -*- coding: utf-8 -*-
"""週次の自動振り返り: metrics.csv をClaudeが分析し、
翌週の文面生成プロンプトに使う知見メモ(insights.md)を更新する。
データがmin_samples未満の間は何もしない(少数の偶然に引っ張られない安全弁)。
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic
import yaml

ROOT = Path(__file__).resolve().parent.parent
JST = ZoneInfo("Asia/Tokyo")


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    csv_path = ROOT / "data" / "metrics.csv"
    if not csv_path.exists():
        print("no metrics yet")
        return

    cutoff = datetime.now(JST) - timedelta(days=cfg["learning"]["lookback_days"])
    with csv_path.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if datetime.strptime(r["date"], "%Y-%m-%d").replace(tzinfo=JST) >= cutoff]

    if len(rows) < cfg["learning"]["min_samples"]:
        print(f"only {len(rows)} samples (< {cfg['learning']['min_samples']}), skip")
        return

    table = "date,category,weekday,hour,impressions,likes,retweets,replies,text_head\n"
    for r in rows:
        table += (f"{r['date']},{r['category']},{r['weekday']},{r['hour']},"
                  f"{r['impressions']},{r['likes']},{r['retweets']},{r['replies']},"
                  f"{r['text_head']}\n")

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=cfg["claude"]["review_model"],
        max_tokens=800,
        system="SNS運用アナリストとして、御朱印アプリの個人開発者のX投稿実績を分析します。"
               "出力は「来週の投稿文を書くライターへの申し送りメモ」です。"
               "以下の観点で、データに基づく事実のみを箇条書き5点以内・全体300字以内で:"
               "1)伸びたカテゴリ/切り口 2)弱いカテゴリ 3)曜日・時間の傾向 4)文体の示唆。"
               "サンプルが少ない項目は断定せず「傾向あり」に留める。",
        messages=[{"role": "user", "content": f"直近{cfg['learning']['lookback_days']}日の実績:\n{table}"}],
    )
    memo = resp.content[0].text.strip()
    out = ROOT / "data" / "insights.md"
    out.write_text(
        f"# 投稿実績からの知見(自動生成: {datetime.now(JST).strftime('%Y-%m-%d')})\n\n"
        f"分析対象: 直近{len(rows)}件\n\n{memo}\n",
        encoding="utf-8",
    )
    print(f"insights updated ({len(rows)} samples)")


if __name__ == "__main__":
    main()
