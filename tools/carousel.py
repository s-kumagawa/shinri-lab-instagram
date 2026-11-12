"""ストーリー型カルーセル生成 (1080x1350)。build(content, outdir) -> 画像ファイル名のリスト

content = {
 "thumb": {"title": "表紙の大見出し\\n3行まで", "accent": "強調語", "pose": "shock", "icon": "!", "tag": "分類", "bg": "pop"},
 "story": [  # 2枚目の「物語」コマ（1枚が基本）
   {"bg": "shop", "caption": "給料日", "cast": [{"who": "me", "pose": "joy", "prop": "bag"}],
    "lines": [{"who": "me", "text": "今だけ半額！？\\n買わなきゃ！", "style": "shout"}]}],
 "bridge": "物語から解説へのつなぎの一文", "bridge_term": "見出し", "bridge_icon": "brain",
 "items": [{"name": "項目名", "short": "まとめ用の短い説明", "body": "本文", "point": "強調（任意）",
            "use": "使い方", "ref": "出典",
            "scene": {"bg": "shop", "pose": "joy", "prop": "bag", "line": "主人公の心の声", "style": "think"}}],
 "cta_q": "最後の問いかけ", "comment": "コメントの誘い"
}
人物・ポーズ・背景・アイコンの種類は tools/figure.py の冒頭を見る。
"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from design import *
import art, figure as fg
from reel import thumbnail

W, H = 1080, 1350

def _pose(spec, t=0.15):
    p = fg.animate(fg.pose_of(spec.get('pose') or spec.get('expr')), t)
    if spec.get('prop'): p['prop'] = spec['prop']
    return p

def story_slide(sc, page, total):
    im = fg.background(sc.get('bg', 'room'), W, H).copy()
    if sc.get('fx') == 'lines':
        im.alpha_composite(art.speedlines(W, H, W / 2, 800, seed=page))
    cast = sc.get('cast', [{'who': 'me'}]); n = len(cast)
    fy = fg.floor_y(H) + 60; scale = 0.84 if n == 1 else 0.76
    heads = {}
    for j, c in enumerate(cast):
        who = fg.who_of(c['who']); x = c.get('x', 0.5 if n == 1 else (0.3 if j == 0 else 0.7)) * W
        head, _ = fg.draw_figure(im, who, _pose(c), x, fy, scale=scale, flip=c.get('flip', x > W * 0.6 and n > 1))
        heads[who] = head
    ic = sc.get('icon')
    if ic and fg.who_of(ic.get('on', 'me')) in heads:
        hx, hy = heads[fg.who_of(ic.get('on', 'me'))]
        im.alpha_composite(art.icon_fx(ic['kind'], 150), (int(hx + 50), int(hy - 160)))
    top = 70
    if sc.get('caption'):
        box = art.caption_box(sc['caption'], 44, 860)
        im.alpha_composite(box, (50, top)); top += box.height + 10
    d = ImageDraw.Draw(im)
    if sc.get('telop'):
        fs = fit_size(d, sc['telop'], 960, 96, black=True)
        top = outlined(d, (0, top + 10), sc['telop'], fs, INK, WHITE, center_w=W, accent=sc.get('accent')) + 10
    for ln in sc.get('lines', []):
        who = fg.who_of(ln['who'])
        if who in heads:
            hx, hy = heads[who]; mw, fs = (800, 54) if n == 1 else (460, 46)
            b = art.bubble(ln['text'], fs, mw, ln.get('style', 'say'))
            cx = min(max(hx, b.width / 2 + 30), W - b.width / 2 - 30)
            cy = max(hy - 100 - b.height / 2, top + b.height / 2)
            im.alpha_composite(b, (int(cx - b.width / 2), int(cy - b.height / 2)))
        else:
            box = art.caption_box(ln['text'], 46, 900)
            im.alpha_composite(box, (int(W / 2 - box.width / 2), top)); top += box.height + 10
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((W - 230, H - 104, W - 50, H - 40), radius=32, fill=WHITE, outline=INK, width=3)
    d.text((W - 205, H - 98), 'つづく →', font=font(34), fill=INK)
    return im.convert('RGB')

def bridge_slide(c, page, total):
    im = fg.background('navy', W, H).copy(); d = ImageDraw.Draw(im)
    y = 170
    if c.get('bridge_icon'):
        ic = fg.icon(c['bridge_icon'], 300); im.alpha_composite(ic, (int(W / 2 - 150), y)); y += 340
    if c.get('bridge_term'):
        fs = fit_size(d, c['bridge_term'], 940, 96, black=True)
        y = outlined(d, (0, y), c['bridge_term'], fs, INK, WHITE, center_w=W) + 40
    fs = fit_size(d, c['bridge'], 900, 66)
    text_block(d, (0, y), c['bridge'], fs, WHITE, 940, lh=1.5, anchor_center=True, W=W)
    footer(d, W, H, page, total, dark=True)
    return im.convert('RGB')

def item_slide(it, n, page, total):
    im = fg.background('cream', W, H).copy(); d = ImageDraw.Draw(im)
    d.ellipse((60, 56, 160, 156), fill=CORAL)
    f = font(58); s = str(n); d.text((110 - d.textlength(s, font=f) / 2, 66), s, font=f, fill=WHITE)
    ts = fit_size(d, it['name'], W - 260, 70)
    d.text((190, 106 - ts * 0.68), it['name'], font=font(ts), fill=INK)
    # 物語のひとコマ
    sc = it.get('scene') or {}
    px0, py0, px1, py1 = 60, 190, W - 60, 650
    pw, ph = px1 - px0, py1 - py0
    panel = fg.background(sc.get('bg', 'room'), pw, int(ph / 0.62)).crop((0, int(ph / 0.62) - ph - int(ph * 0.08), pw, int(ph / 0.62) - int(ph * 0.08))).copy()
    fg.draw_figure(panel, sc.get('who', 'me'), _pose(sc), pw * 0.76, ph - 26, scale=0.56)
    if sc.get('line'):
        b = art.bubble(sc['line'], 46, 520, sc.get('style', 'say'))
        panel.alpha_composite(b, (30, max(16, int(ph * 0.42 - b.height / 2))))
    mask = Image.new('L', (pw, ph), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=34, fill=255)
    im.paste(panel, (px0, py0), mask)
    d.rounded_rectangle((px0, py0, px1, py1), radius=34, outline=INK, width=5)
    # 本文
    y = py1 + 36; bs = 44
    while True:
        lb = wrap(d, it['body'], font(bs, False), W - 140)
        lp = wrap(d, it.get('point', ''), font(bs + 2), W - 140) if it.get('point') else []
        need = len(lb) * bs * 1.55 + (len(lp) * (bs + 2) * 1.4 + 14 if lp else 0)
        if y + need + 250 < H - 130 or bs <= 34: break
        bs -= 2
    y = text_block(d, (70, y), it['body'], bs, INK, W - 140, bold=False, lh=1.55)
    if lp: y = text_block(d, (70, y + 10), it['point'], bs + 2, CORAL, W - 140, lh=1.4)
    by = max(y + 24, H - 140 - 236)
    d.rounded_rectangle((60, by, W - 60, by + 226), radius=28, fill=WHITE, outline=INK, width=4)
    pill(d, (90, by + 20), '使い方', 30, CORAL, WHITE, pad=(20, 8))
    us = fit_size(d, it['use'], W - 200, 42)
    text_block(d, (96, by + 86), it['use'], us, INK, W - 190, lh=1.4)
    d.text((70, H - 120), '出典: ' + it['ref'], font=font(24, False), fill=GRAY)
    footer(d, W, H, page, total)
    return im.convert('RGB')

def summary_slide(c, page, total):
    im = fg.background('cream', W, H).copy(); d = ImageDraw.Draw(im)
    d.text((70, 70), 'まとめ', font=font(84), fill=INK)
    d.rectangle((70, 186, 190, 194), fill=CORAL)
    y = 240; items = c['items']; rh = min(160, (H - 340 - y) // len(items))
    for i, it in enumerate(items, 1):
        d.rounded_rectangle((60, y, W - 60, y + rh - 18), radius=24, fill=WHITE, outline=INK, width=4)
        cy = y + (rh - 18) / 2
        d.ellipse((84, cy - 30, 144, cy + 30), fill=CORAL)
        f = font(36); s = str(i); d.text((114 - d.textlength(s, font=f) / 2, cy - 24), s, font=f, fill=WHITE)
        d.text((170, y + 18), it['name'], font=font(42), fill=INK)
        d.text((170, y + 76), it['short'], font=font(30, False), fill=GRAY)
        y += rh
    fg.draw_figure(im, 'me', fg.animate('point', 0.1), W - 170, H - 110, scale=0.42, shadow=False)
    footer(d, W, H, page, total)
    return im.convert('RGB')

def cta_slide(c, page, total):
    im = fg.background('pop', W, H).copy(); d = ImageDraw.Draw(im)
    fs = fit_size(d, c['cta_q'], 940, 84, black=True)
    y = outlined(d, (0, 100), c['cta_q'], fs, INK, WHITE, center_w=W, accent=c.get('cta_accent'))
    y += 30
    d.rounded_rectangle((200, y, W - 200, y + 124), radius=62, fill=CORAL, outline=INK, width=6)
    bx = 280
    d.polygon([(bx, y + 30), (bx + 40, y + 30), (bx + 40, y + 94), (bx + 20, y + 78), (bx, y + 94)], fill=WHITE)
    d.text((bx + 72, y + 26), '保存して見返す', font=font(54), fill=WHITE)
    y += 160
    d.rounded_rectangle((150, y, W - 150, y + 250), radius=34, fill=WHITE, outline=INK, width=5)
    text_block(d, (0, y + 28), 'フォローすると毎日ひとつ\n「根拠のある心理学」が届きます', 40, INK, 800, lh=1.5, anchor_center=True, W=W)
    f = font(58, black=True); w = d.textlength(HANDLE, font=f)
    d.text(((W - w) / 2, y + 160), HANDLE, font=f, fill=CORAL)
    fy = H - 50
    fg.draw_figure(im, 'me', fg.animate('joy', 0.0), W * 0.16, fy, scale=0.58)
    fg.draw_figure(im, 'friend', fg.animate('wave', 0.1), W * 0.86, fy, scale=0.58, flip=True)
    b = art.bubble(c.get('comment', 'あなたの体験も\nコメントで教えてね'), 38, 440)
    im.alpha_composite(b, (int(W / 2 - b.width / 2), max(y + 270, H - 60 - b.height - 150)))
    return im.convert('RGB')

def build(c, outdir):
    slides = []
    story = c.get('story', [])
    total = 1 + len(story) + (1 if c.get('bridge') else 0) + len(c['items']) + 2
    slides.append(thumbnail(c['thumb'], W, H, page_label='スワイプ →'))
    for sc in story: slides.append(story_slide(sc, len(slides) + 1, total))
    if c.get('bridge'): slides.append(bridge_slide(c, len(slides) + 1, total))
    for i, it in enumerate(c['items'], 1): slides.append(item_slide(it, i, len(slides) + 1, total))
    slides.append(summary_slide(c, len(slides) + 1, total))
    slides.append(cta_slide(c, len(slides) + 1, total))
    files = []
    for i, s in enumerate(slides, 1):
        f = f'{i:02d}.jpg'; s.save(os.path.join(outdir, f), quality=92); files.append(f)
    return files
