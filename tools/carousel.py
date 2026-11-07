"""カルーセル生成: python3 carousel.py <content.json> <outdir>"""
import json, sys, os
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from design import *

W, H = 1080, 1350  # 4:5

def cover(d, out, total):
    im = Image.new('RGB', (W, H), NAVY); dr = ImageDraw.Draw(im)
    # 上部ラベル
    lab = d.get('label', '保存推奨')
    f = font(34); lw = dr.textlength(lab, font=f)
    highlight(dr, (80, 120, 80 + lw + 48, 190), CORAL, 35)
    dr.text((104, 128), lab, font=f, fill=WHITE)
    y = 300
    y = text_block(dr, (80, y), d['pre'], 60, SOFT, W - 160, lh=1.45)
    y += 40
    s = fit_size(dr, d['title'], W - 160, 160)
    for i, line in enumerate(d['title'].split('\n')):
        fnt = font(s)
        col = CORAL if i == len(d['title'].split('\n')) - 1 else CREAM
        dr.text((80, y), line, font=fnt, fill=col)
        y += int(s * 1.25)
    y += 50
    dr.rectangle((80, y, 200, y + 8), fill=CORAL)
    text_block(dr, (80, y + 50), d.get('sub', ''), 46, SOFT, W - 160, bold=False)
    swipe = 'スワイプしてね →'
    f = font(38); dr.text((W - 80 - dr.textlength(swipe, font=f), H - 200), swipe, font=f, fill=CREAM)
    footer(dr, W, H, dark=True)
    im.save(out)

def item(d, n, out, page, total):
    im = Image.new('RGB', (W, H), CREAM); dr = ImageDraw.Draw(im)
    # 番号
    dr.ellipse((80, 100, 200, 220), fill=CORAL)
    f = font(64); s = str(n)
    dr.text((140 - dr.textlength(s, font=f) / 2, 112), s, font=f, fill=WHITE)
    ts = fit_size(dr, d['name'], W - 320, 68)
    dr.text((230, 160 - ts * 0.7), d['name'], font=font(ts), fill=NAVY)
    y = 290
    y = text_block(dr, (80, y), d['body'], 52, NAVY, W - 160, bold=False, lh=1.6)
    if d.get('point'):
        y += 20
        y = text_block(dr, (80, y), d['point'], 54, CORAL, W - 160, lh=1.45)
    # 使い方ボックス
    box_h = 290
    y = max(y + 60, H - 200 - box_h - 40) if y + 60 > H - 200 - box_h - 200 else y + 80
    dr.rounded_rectangle((80, y, W - 80, y + box_h), radius=28, fill=WHITE)
    dr.text((120, y + 34), '使い方', font=font(38), fill=CORAL)
    text_block(dr, (120, y + 95), d['use'], 46, NAVY, W - 240, lh=1.5)
    # 出典
    dr.text((80, H - 160), '出典: ' + d['ref'], font=font(28, False), fill=GRAY)
    footer(dr, W, H, page, total)
    im.save(out)

def summary(d, out, page, total):
    im = Image.new('RGB', (W, H), CREAM); dr = ImageDraw.Draw(im)
    dr.text((80, 110), 'まとめ', font=font(80), fill=NAVY)
    dr.rectangle((80, 230, 200, 238), fill=CORAL)
    y = 300
    for i, it in enumerate(d['items'], 1):
        dr.rounded_rectangle((80, y, W - 80, y + 150), radius=24, fill=WHITE)
        dr.text((120, y + 22), f'{i}. {it["name"]}', font=font(44), fill=NAVY)
        dr.text((120, y + 84), it['short'], font=font(32, False), fill=GRAY)
        y += 175
    footer(dr, W, H, page, total)
    im.save(out)

def cta(d, out, page, total):
    im = Image.new('RGB', (W, H), NAVY); dr = ImageDraw.Draw(im)
    y = 260
    y = text_block(dr, (0, y), d['cta_q'], 60, CREAM, W - 160, lh=1.45, anchor_center=True, W=W)
    y += 60
    # 保存ボタン風
    highlight(dr, (190, y, W - 190, y + 130), CORAL, 65)
    t = '🔖 保存して見返す'.replace('🔖 ', '')
    f = font(52); dr.text(((W - dr.textlength(t, font=f)) / 2, y + 30), t, font=f, fill=WHITE)
    y += 220
    y = text_block(dr, (0, y), 'フォローすると毎日ひとつ\n「根拠のある心理学」が届きます', 44, SOFT, W - 160, bold=False, lh=1.6, anchor_center=True, W=W)
    y += 50
    f = font(64); dr.text(((W - dr.textlength(HANDLE, font=f)) / 2, y), HANDLE, font=f, fill=CORAL)
    y += 140
    text_block(dr, (0, y), d.get('comment', 'あなたの体験もコメントで教えてね'), 38, SOFT, W - 160, bold=False, anchor_center=True, W=W)
    footer(dr, W, H, page, total, dark=True)
    im.save(out)

if __name__ == '__main__':
    d = json.load(open(sys.argv[1], encoding='utf-8')); outdir = sys.argv[2]
    total = len(d['items']) + 3
    cover(d, f'{outdir}/01.png', total)
    for i, it in enumerate(d['items'], 1):
        item(it, i, f'{outdir}/{i+1:02d}.png', i + 1, total)
    summary(d, f'{outdir}/{total-1:02d}.png', total - 1, total)
    cta(d, f'{outdir}/{total:02d}.png', total, total)
    print('done', total, 'slides')
