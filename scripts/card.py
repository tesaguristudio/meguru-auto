# -*- coding: utf-8 -*-
"""豆知識カード画像生成(デザイン案A: 和紙×朱)
タイトルと本文を渡すと 1200x675 のPNGを生成する。
フォントサイズと改行は文字数に応じて自動調整。AIは使わないため生成コストは0円。
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 675
FONT_DIR = "/usr/share/fonts/opentype/noto"
SERIF_BOLD = f"{FONT_DIR}/NotoSerifCJK-Bold.ttc"
SERIF_REG = f"{FONT_DIR}/NotoSerifCJK-Regular.ttc"
SANS_BOLD = f"{FONT_DIR}/NotoSansCJK-Bold.ttc"

SHU = (178, 45, 48)      # 朱色
SUMI = (45, 40, 38)      # 墨色
BASE = (245, 238, 224)   # 和紙色


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _washi_texture(img: Image.Image, seed: int = 1) -> None:
    """和紙風の粒子テクスチャ"""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    for _ in range(9000):
        x, y = rnd.randint(0, W - 1), rnd.randint(0, H - 1)
        delta = rnd.randint(-8, 8)
        c = tuple(max(0, min(255, v + delta)) for v in BASE)
        d.point((x, y), fill=c)


def _stamp(d: ImageDraw.ImageDraw, cx: int, cy: int, size: int, text: str = "巡") -> None:
    """朱印風の角判子"""
    half = size // 2
    d.rounded_rectangle(
        [cx - half, cy - half, cx + half, cy + half], radius=8, outline=SHU, width=6
    )
    f = _font(SERIF_BOLD, int(size * 0.62))
    bbox = d.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), text, font=f, fill=SHU)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int,
          draw: ImageDraw.ImageDraw) -> list[str]:
    """幅に収まるよう文字単位で折り返し(日本語向け)"""
    lines, current = [], ""
    for ch in text.replace("\n", ""):
        trial = current + ch
        if draw.textbbox((0, 0), trial, font=font)[2] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def generate_card(title: str, body: str, footer: str,
                  out_path: str, seed: int = 1) -> str:
    """カードを生成して out_path に保存し、パスを返す"""
    img = Image.new("RGB", (W, H), BASE)
    _washi_texture(img, seed=seed)
    d = ImageDraw.Draw(img)

    # 左の朱帯
    d.rectangle([0, 0, 26, H], fill=SHU)
    d.rectangle([34, 0, 40, H], fill=SHU)

    # ラベル
    d.text((90, 58), "― 御朱印豆知識 ―", font=_font(SERIF_BOLD, 30), fill=SHU)

    # タイトル(長い場合はフォントを縮小)
    title_size = 64
    f_title = _font(SERIF_BOLD, title_size)
    while d.textbbox((0, 0), title, font=f_title)[2] > 860 and title_size > 40:
        title_size -= 4
        f_title = _font(SERIF_BOLD, title_size)
    d.text((90, 118), title, font=f_title, fill=SUMI)
    d.line([90, 214, 90 + min(860, d.textbbox((0, 0), title, font=f_title)[2] + 20), 214],
           fill=SHU, width=3)

    # 本文(行数に応じてサイズ調整)
    body_size = 44
    f_body = _font(SERIF_REG, body_size)
    lines = _wrap(body, f_body, 800, d)
    while len(lines) > 5 and body_size > 30:
        body_size -= 4
        f_body = _font(SERIF_REG, body_size)
        lines = _wrap(body, f_body, 800, d)
    y = 262
    for line in lines[:6]:
        d.text((90, y), line, font=f_body, fill=SUMI)
        y += int(body_size * 1.65)

    # 朱印とフッター
    _stamp(d, 1050, 480, 150)
    d.text((90, H - 70), footer, font=_font(SANS_BOLD, 26), fill=(120, 110, 100))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


if __name__ == "__main__":
    generate_card(
        "御朱印の「朱」の由来",
        "御朱印はもともと、お寺にお経を納めた証「納経印」が始まり。だから今も納経が正式なお寺が残っています。",
        "参拝記録アプリ meguru ⛩ 御朱印豆知識 vol.1",
        "/tmp/test_card.png",
    )
    print("ok: /tmp/test_card.png")
