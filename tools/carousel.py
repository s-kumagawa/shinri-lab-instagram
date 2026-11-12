"""ストーリー型カルーセル生成 (1080x1350)。build(content, outdir) -> 画像ファイル名のリスト

content = {
 "thumb": {"title": "表紙の大見出し\\n3行まで", "accent": "強調語", "who": "mina", "expr": "shock", "icon": "!", "tag": "分類", "bg": "pop"},
 "story": [  # 2枚目以降の「物語」コマ（1〜2枚）
   {"bg": "shop", "caption": "ある日のミナ", "cast": [{"who": "mina", "expr": "happy"}],
    "lines": [{"who": "mina", "text": "今だけ半額！？\\n買わなきゃ！", "style": "shout"}]}],
 "bridge": "物語から解説へのつなぎ（先生のひとこと）",
 "items": [{"name": "項目名", "short": "まとめ用の短い説明", "body": "本文", "point": "強調（任意）",
            "use": "使い方", "ref": "出典",
            "scene": {"bg": "shop", "who": "mina", "expr": "happy", "line": "主人公の心の声"}}],
 "cta_q": "最後の問いかけ", "comment": "コメントの誘い"
}
"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from design import *
import art
from reel import thumbnail

W, H = 1080, 1350

def _page(d, page, total, dark=False):
    footer(d, W, H, page, total, dark)

def story_slide(sc, page, total):
    im = art.background(sc.get('bg', 'room'), W, H).convert('RGBA')
    if sc.get('fx') == 'lines':
        im.alpha_composite(art.speedlines(W, H, W / 2, 900, seed=page))
    cast = sc.get('cast', [{'who': 'mina'}]); n = len(cast)
    hh = 700 if n == 1 else 600
    heads = {}
    for j, c in enumerate(cast):
        x = c.get('x', 0.5 if n == 1 else (0.28 if j == 0 else 0.72))
        spr = art.sprite(c['who'], c.get('expr', 'normal'), h=hh, flip=c.get('flip', False))
        y = H - hh + 80
        im.alpha_composite(spr, (int(W * x - spr.width / 2), y))
        heads[c['who']] = (W * x, y + hh * 0.17)
        if sc.get('icon') and sc['icon'].get('on') == c['who']:
            ic = art.icon_fx(sc['icon']['kind'], 140)
            im.alpha_composite(ic, (int(W * x + 150), int(y + 40)))
    top = 70
    if sc.get('caption'):
        box = art.caption_box(sc['caption'], 44, 860, label=sc.get('caption_label'))
        im.alpha_composite(box, (50, top)); top += box.height + 10
    if sc.get('telop'):
        d = ImageDraw.Draw(im, 'RGBA')
        fs = fit_size(d, sc['telop'], 960, 96, black=True)
        top = outlined(d, (0, top + 10), sc['telop'], fs, INK, WHITE, center_w=W, accent=sc.get('accent')) + 10
    lines = sc.get('lines', [])
    for k, ln in enumerate(lines):
        who = ln['who']
        if who in heads:
            hx, hy = heads[who]
            mw = 780 if n == 1 else 460
            b = art.bubble(ln['text'], 54 if n == 1 else 48, mw, ln.get('style', 'say'),
                           tail_x=0.5 if n > 1 else min(0.85, max(0.15, (hx - 150) / 780)))
            cx = min(max(hx, b.width / 2 + 30), W - b.width / 2 - 30)
            cy = hy - 120 - b.height / 2
            if n == 1 and len(lines) > 1: cy -= (len(lines) - 1 - k) * (b.height + 10)
            cy = max(cy, top + b.height / 2)
            im.alpha_composite(b, (int(cx - b.width / 2), int(cy - b.height / 2)))
        else:
            label = None if who == 'narr' else art.CAST.get(who, {}).get('name')
            box = art.caption_box(ln['text'], 46, 900, label=label)
            im.alpha_composite(box, (int(W / 2 - box.width / 2), top)); top += box.height + 10
    d = ImageDraw.Draw(im, 'RGBA')
    d.rounded_rectangle((W - 230, H - 104, W - 50, H - 40), radius=32, fill=(255, 255, 255, 220))
    d.text((W - 205, H - 98), 'つづく →', font=font(34), fill=INK)
    return im.convert('RGB')

def bridge_slide(text, term, page, total):
    im = art.background('lab', W, H).convert('RGBA')
    spr = art.sprite('sensei', 'normal', h=640)
    im.alpha_composite(spr, (int(W / 2 - spr.width / 2), H - 600))
    b = art.bubble(text, 58, 820)
    im.alpha_composite(b, (int(W / 2 - b.width / 2), int(H - 600 - b.height + 10)))
    d = ImageDraw.Draw(im, 'RGBA')
    if term:
        fs = fit_size(d, term, 940, 100, black=True)
        outlined(d, (0, 120), term, fs, INK, WHITE, center_w=W, accent=None)
    return im.convert('RGB')

def item_slide(it, n, page, total):
    im = Image.new('RGBA', (W, H), CREAM); d = ImageDraw.Draw(im, 'RGBA')
    # 見出し
    d.ellipse((60, 56, 160, 156), fill=CORAL, outline=INK, width=5)
    f = font(58); s = str(n); d.text((110 - d.textlength(s, font=f) / 2, 66), s, font=f, fill=WHITE)
    ts = fit_size(d, it['name'], W - 260, 70)
    d.text((190, 106 - ts * 0.68), it['name'], font=font(ts), fill=INK)
    # 物語のコマ
    sc = it.get('scene') or {}
    px0, py0, px1, py1 = 60, 190, W - 60, 640
    panel = art.background(sc.get('bg', 'room'), px1 - px0, py1 - py0 + 200).crop((0, 100, px1 - px0, py1 - py0 + 100)).convert('RGBA')
    who = sc.get('who', 'mina')
    spr = art.sprite(who, sc.get('expr', 'normal'), h=540)
    panel.alpha_composite(spr, (panel.width - spr.width + 20, panel.height - 440))
    if sc.get('line'):
        b = art.bubble(sc['line'], 46, 520, sc.get('style', 'say'), tail_x=0.82)
        panel.alpha_composite(b, (24, max(10, int(panel.height - 330 - b.height * 0.5))))
    mask = Image.new('L', panel.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, panel.width - 1, panel.height - 1), radius=34, fill=255)
    im.paste(panel, (px0, py0), mask)
    d.rounded_rectangle((px0, py0, px1, py1), radius=34, outline=INK, width=6)
    # 本文
    y = py1 + 36
    bs = 44
    while True:
        lines_b = wrap(d, it['body'], font(bs, False), W - 140)
        lines_p = wrap(d, it.get('point', ''), font(bs + 2), W - 140) if it.get('point') else []
        need = len(lines_b) * bs * 1.55 + (len(lines_p) * (bs + 2) * 1.4 + 14 if lines_p else 0)
        if y + need + 230 < H - 140 or bs <= 34: break
        bs -= 2
    y = text_block(d, (70, y), it['body'], bs, INK, W - 140, bold=False, lh=1.55)
    if lines_p:
        y = text_block(d, (70, y + 10), it['point'], bs + 2, CORAL, W - 140, lh=1.4)
    # 使い方
    by = max(y + 24, H - 140 - 236)
    d.rounded_rectangle((60, by, W - 60, by + 226), radius=28, fill=WHITE, outline=INK, width=4)
    pill(d, (90, by + 20), '使い方', 30, CORAL, WHITE, pad=(20, 8))
    us = fit_size(d, it['use'], W - 200, 42)
    text_block(d, (96, by + 86), it['use'], us, INK, W - 190, lh=1.4)
    d.text((70, H - 120), '出典: ' + it['ref'], font=font(24, False), fill=GRAY)
    _page(d, page, total)
    return im.convert('RGB')

def summary_slide(c, page, total):
    im = Image.new('RGBA', (W, H), CREAM); d = ImageDraw.Draw(im, 'RGBA')
    outlined(d, (70, 70), 'まとめ', 84, INK, WHITE, shadow=False, sw=0)
    d.rectangle((70, 186, 190, 194), fill=CORAL)
    y = 240; items = c['items']
    rh = min(160, (H - 360 - y) // len(items))
    for i, it in enumerate(items, 1):
        d.rounded_rectangle((60, y, W - 60, y + rh - 18), radius=24, fill=WHITE, outline=INK, width=4)
        d.ellipse((84, y + (rh - 18) / 2 - 30, 144, y + (rh - 18) / 2 + 30), fill=CORAL)
        f = font(36); s = str(i); d.text((114 - d.textlength(s, font=f) / 2, y + (rh - 18) / 2 - 24), s, font=f, fill=WHITE)
        d.text((170, y + 18), it['name'], font=font(42), fill=INK)
        d.text((170, y + 76), it['short'], font=font(30, False), fill=GRAY)
        y += rh
    spr = art.sprite('sensei', 'happy', h=300)
    im.alpha_composite(spr, (W - spr.width - 10, H - spr.height - 100))
    _page(d, page, total)
    return im.convert('RGB')

def cta_slide(c, page, total):
    im = art.background('pop', W, H).convert('RGBA'); d = ImageDraw.Draw(im, 'RGBA')
    fs = fit_size(d, c['cta_q'], 940, 84, black=True)
    y = outlined(d, (0, 110), c['cta_q'], fs, INK, WHITE, center_w=W, accent=c.get('cta_accent'))
    y += 30
    d.rounded_rectangle((200, y, W - 200, y + 124), radius=62, fill=CORAL, outline=INK, width=6)
    bx = 280
    d.polygon([(bx, y + 30), (bx + 40, y + 30), (bx + 40, y + 94), (bx + 20, y + 78), (bx, y + 94)], fill=WHITE)
    d.text((bx + 72, y + 26), '保存して見返す', font=font(54), fill=WHITE)
    y += 160
    d.rounded_rectangle((150, y, W - 150, y + 250), radius=34, fill=(255, 255, 255, 235), outline=INK, width=5)
    text_block(d, (0, y + 28), 'フォローすると毎日ひとつ\n「根拠のある心理学」が届きます', 40, INK, 800, lh=1.5, anchor_center=True, W=W)
    f = font(58, black=True); w = d.textlength(HANDLE, font=f)
    d.text(((W - w) / 2, y + 160), HANDLE, font=f, fill=CORAL)
    s1 = art.sprite('mina', 'happy', h=430); s2 = art.sprite('sensei', 'happy', h=400)
    im.alpha_composite(s1, (int(W * 0.3 - s1.width / 2), H - 400))
    im.alpha_composite(s2, (int(W * 0.72 - s2.width / 2), H - 360))
    b = art.bubble(c.get('comment', 'あなたの体験も\nコメントで教えてね'), 36, 400, tail_x=0.25)
    im.alpha_composite(b, (int(W * 0.5 - 60), max(y + 262, H - 400 - b.height + 90)))
    return im.convert('RGB')

def build(c, outdir):
    slides = []
    story = c.get('story', [])
    total = 1 + len(story) + (1 if c.get('bridge') else 0) + len(c['items']) + 2
    slides.append(thumbnail(c['thumb'], W, H, page_label='スワイプ →'))
    for sc in story: slides.append(story_slide(sc, len(slides) + 1, total))
    if c.get('bridge'): slides.append(bridge_slide(c['bridge'], c.get('bridge_term'), len(slides) + 1, total))
    for i, it in enumerate(c['items'], 1): slides.append(item_slide(it, i, len(slides) + 1, total))
    slides.append(summary_slide(c, len(slides) + 1, total))
    slides.append(cta_slide(c, len(slides) + 1, total))
    files = []
    for i, s in enumerate(slides, 1):
        f = f'{i:02d}.jpg'; s.save(os.path.join(outdir, f), quality=92); files.append(f)
    return files
