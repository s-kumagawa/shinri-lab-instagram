"""しんりラボ イラスト部品：登場人物・背景・吹き出し・漫画的効果。すべてPILで描く（外部素材なし）。

登場人物（who）
  mina   … ミナ。20代の会社員。視聴者の分身（主人公）
  sota   … ソウタ。ミナの同僚・友だち
  sensei … ホー先生。研究を紹介するフクロウ（解説役）
表情（expr）
  normal / happy / worried / surprised / sad / think / shock / smug
背景（bg）
  room / office / cafe / night / shop / street / lab / pop / pop2 / board
"""
import math, random
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from design import *

SS = 2  # スーパーサンプリング倍率（なめらかな線のため）
LW = 6  # 線の太さ（論理px）

CAST = {
    'mina':   {'name': 'ミナ', 'skin': (255, 224, 200), 'hair': (120, 78, 58), 'shirt': (255, 150, 120), 'hairstyle': 'bob'},
    'sota':   {'name': 'ソウタ', 'skin': (250, 214, 186), 'hair': (48, 52, 70), 'shirt': (110, 160, 220), 'hairstyle': 'short'},
    'sensei': {'name': 'ホー先生'},
}

# ---------------------------------------------------------------- 低レベル描画
class Pen:
    """論理座標で描き、SS倍のキャンバスに線つきで塗る"""
    def __init__(self, w, h):
        self.im = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
    def _b(self, box): return [v * SS for v in box]
    def ellipse(self, box, fill, line=INK, lw=LW):
        self.d.ellipse(self._b(box), fill=fill, outline=line, width=lw * SS if line else 0)
    def rrect(self, box, r, fill, line=INK, lw=LW):
        self.d.rounded_rectangle(self._b(box), radius=r * SS, fill=fill, outline=line, width=lw * SS if line else 0)
    def poly(self, pts, fill, line=INK, lw=LW):
        p = [(x * SS, y * SS) for x, y in pts]
        self.d.polygon(p, fill=fill)
        if line: self.d.line(p + [p[0]], fill=line, width=lw * SS, joint='curve')
    def line(self, pts, fill=INK, lw=LW):
        p = [(x * SS, y * SS) for x, y in pts]
        self.d.line(p, fill=fill, width=int(lw * SS), joint='curve')
        r = lw * SS / 2
        for x, y in (p[0], p[-1]):
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=fill)
    def arc(self, box, a0, a1, fill=INK, lw=LW):
        self.d.arc(self._b(box), a0, a1, fill=fill, width=int(lw * SS))
    def chord(self, box, a0, a1, fill, line=None, lw=LW):
        self.d.chord(self._b(box), a0, a1, fill=fill, outline=line, width=lw * SS if line else 0)
    def pie(self, box, a0, a1, fill, line=None, lw=LW):
        self.d.pieslice(self._b(box), a0, a1, fill=fill, outline=line, width=lw * SS if line else 0)
    def done(self, sticker=True):
        im = self.im.resize((self.im.width // SS, self.im.height // SS), Image.LANCZOS)
        if not sticker: return im
        # ステッカー風の白フチ（背景から人物を浮かせる）
        a = im.split()[3].point(lambda v: 255 if v > 40 else 0)
        a = a.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(1.2))
        base = Image.new('RGBA', im.size, (255, 255, 255, 0)); base.putalpha(a)
        sh = Image.new('RGBA', im.size, (20, 24, 40, 0)); sh.putalpha(a.point(lambda v: v * 50 // 255))
        out = Image.new('RGBA', im.size, (0, 0, 0, 0))
        out.alpha_composite(sh, (8, 10)); out.alpha_composite(base); out.alpha_composite(im)
        return out

def _mix(c, k, to=(0, 0, 0)):
    return tuple(int(c[i] * (1 - k) + to[i] * k) for i in range(3))

# ---------------------------------------------------------------- 顔パーツ
def _eyes(p, ex, ey, expr, blink, look=(0, 0)):
    lx, rx = ex
    if blink or expr == 'happy':
        for x in (lx, rx):
            if expr == 'happy': p.arc((x - 22, ey - 12, x + 22, ey + 22), 200, 340, lw=7)
            else: p.line([(x - 20, ey + 4), (x + 20, ey + 4)], lw=7)
        return
    if expr == 'sad':
        for x in (lx, rx):
            p.chord((x - 17, ey - 12, x + 17, ey + 26), 0, 180, fill=INK)
        return
    if expr == 'smug':
        for x in (lx, rx):
            p.chord((x - 18, ey - 14, x + 18, ey + 26), 0, 180, fill=INK)
            p.line([(x - 20, ey + 4), (x + 20, ey + 4)], lw=6)
        return
    big = expr in ('surprised', 'shock')
    for x in (lx, rx):
        if expr == 'shock':
            p.ellipse((x - 24, ey - 26, x + 24, ey + 26), fill=WHITE, lw=5)
            p.ellipse((x - 5, ey - 5, x + 5, ey + 5), fill=INK, line=None)
            continue
        rw, rh = (19, 26) if big else (15, 21)
        dx, dy = look
        p.ellipse((x - rw + dx, ey - rh + dy, x + rw + dx, ey + rh + dy), fill=INK, line=None)
        p.ellipse((x - rw * 0.45 + dx, ey - rh * 0.7 + dy, x + rw * 0.25 + dx, ey - rh * 0.05 + dy), fill=WHITE, line=None)

def _brows(p, ex, by, expr):
    lx, rx = ex
    if expr in ('worried', 'sad'):
        p.line([(lx - 22, by + 4), (lx + 18, by - 10)], lw=6); p.line([(rx - 18, by - 10), (rx + 22, by + 4)], lw=6)
    elif expr in ('surprised', 'shock'):
        p.arc((lx - 24, by - 26, lx + 24, by + 6), 200, 340, lw=6); p.arc((rx - 24, by - 26, rx + 24, by + 6), 200, 340, lw=6)
    elif expr == 'think':
        p.line([(lx - 22, by - 6), (lx + 20, by - 2)], lw=6); p.line([(rx - 20, by - 12), (rx + 22, by - 18)], lw=6)
    elif expr == 'smug':
        p.line([(lx - 22, by - 4), (lx + 20, by + 2)], lw=6); p.line([(rx - 20, by + 2), (rx + 22, by - 4)], lw=6)
    else:
        p.arc((lx - 22, by - 14, lx + 22, by + 8), 210, 330, lw=6); p.arc((rx - 22, by - 14, rx + 22, by + 8), 210, 330, lw=6)

def _mouth(p, cx, my, expr, talk=0.0):
    if talk > 0.05 and expr not in ('shock',):
        h = 8 + 22 * talk
        p.ellipse((cx - 18, my - 4, cx + 18, my - 4 + h), fill=(170, 60, 70), lw=5)
        return
    if expr == 'happy':
        p.chord((cx - 30, my - 18, cx + 30, my + 30), 0, 180, fill=(170, 60, 70), line=INK, lw=5)
        p.chord((cx - 16, my + 8, cx + 16, my + 28), 0, 180, fill=(255, 140, 140), line=None)
    elif expr == 'surprised':
        p.ellipse((cx - 14, my - 6, cx + 14, my + 26), fill=(170, 60, 70), lw=5)
    elif expr == 'shock':
        p.line([(cx - 28, my + 10), (cx - 14, my), (cx, my + 10), (cx + 14, my), (cx + 28, my + 10)], lw=5)
    elif expr in ('worried', 'sad'):
        p.arc((cx - 22, my + 2, cx + 22, my + 30), 200, 340, lw=6)
    elif expr == 'think':
        p.line([(cx - 14, my + 8), (cx + 12, my + 4)], lw=6)
    elif expr == 'smug':
        p.arc((cx - 26, my - 22, cx + 22, my + 14), 20, 120, lw=6)
    else:
        p.arc((cx - 20, my - 16, cx + 20, my + 12), 30, 150, lw=6)

def _fx_face(p, expr, cx, top):
    if expr in ('worried', 'shock'):
        # 汗
        x, y = cx + 120, top + 120
        p.poly([(x, y), (x - 14, y + 34), (x + 14, y + 34)], fill=(160, 210, 255), lw=4)
        p.ellipse((x - 15, y + 20, x + 15, y + 50), fill=(160, 210, 255), lw=4)
    if expr == 'shock':
        for i in range(4):
            x = cx - 60 + i * 34
            p.line([(x, top + 40), (x, top + 110)], fill=(90, 110, 190), lw=5)
    if expr == 'sad':
        x, y = cx - 60, top + 245
        p.ellipse((x - 9, y, x + 9, y + 26), fill=(160, 210, 255), lw=3)

# ---------------------------------------------------------------- 人物
def _human(who, expr, blink, talk, look):
    c = CAST[who]; W0, H0 = 560, 760
    p = Pen(W0, H0); cx = W0 / 2
    hair, skin, shirt = c['hair'], c['skin'], c['shirt']
    # 後ろ髪
    if c['hairstyle'] == 'bob':
        p.rrect((cx - 172, 108, cx + 172, 486), 150, hair)
    # 体
    p.rrect((cx - 190, 520, cx + 190, 860), 150, shirt)
    p.rrect((cx - 34, 430, cx + 34, 540), 20, _mix(skin, 0.08))
    if who == 'mina':
        p.poly([(cx - 62, 525), (cx, 590), (cx + 62, 525)], fill=WHITE, lw=5)  # えり
    else:
        p.poly([(cx - 50, 528), (cx, 575), (cx + 50, 528)], fill=_mix(shirt, 0.25), lw=5)
    # 耳と頭
    p.ellipse((cx - 152, 270, cx - 112, 340), skin)
    p.ellipse((cx + 112, 270, cx + 152, 340), skin)
    p.ellipse((cx - 138, 130, cx + 138, 470), skin)
    # 前髪
    if c['hairstyle'] == 'bob':
        p.pie((cx - 150, 108, cx + 150, 380), 180, 360, fill=hair, line=None)
        p.arc((cx - 150, 108, cx + 150, 380), 180, 360, lw=LW)
        for i, x in enumerate(range(int(cx - 132), int(cx + 132), 44)):
            p.ellipse((x - 2, 214 + (i % 2) * 6, x + 50, 268 + (i % 2) * 6), fill=hair, line=None)
        p.poly([(cx - 148, 230), (cx - 104, 250), (cx - 96, 400), (cx - 120, 484), (cx - 168, 470), (cx - 166, 330)], fill=hair)
        p.poly([(cx + 148, 230), (cx + 104, 250), (cx + 96, 400), (cx + 120, 484), (cx + 168, 470), (cx + 166, 330)], fill=hair)
        p.ellipse((cx + 60, 190, cx + 104, 222), fill=YELLOW, lw=4)  # ヘアピン
    else:
        p.pie((cx - 146, 112, cx + 146, 360), 180, 360, fill=hair, line=None)
        p.arc((cx - 146, 112, cx + 146, 360), 180, 360, lw=LW)
        pts = [(cx - 146, 240)]
        for i in range(7):
            x = cx - 140 + i * 42
            pts += [(x + 21, 268 - (i % 2) * 10), (x + 42, 230)]
        pts += [(cx + 146, 240), (cx + 146, 200), (cx - 146, 200)]
        p.poly(pts, fill=hair, line=None)
        p.poly([(cx - 30, 118), (cx + 20, 80), (cx + 40, 124)], fill=hair, lw=5)
        p.rrect((cx - 150, 220, cx - 120, 330), 14, hair)
        p.rrect((cx + 120, 220, cx + 150, 330), 14, hair)
    # 顔
    ex, ey = (cx - 58, cx + 58), 318
    _eyes(p, ex, ey, expr, blink, look)
    _brows(p, ex, 262, expr)
    p.ellipse((cx - 108, 350, cx - 64, 378), fill=PINK + (150,), line=None)
    p.ellipse((cx + 64, 350, cx + 108, 378), fill=PINK + (150,), line=None)
    _mouth(p, cx, 392, expr, talk)
    _fx_face(p, expr, cx, 130)
    return p.done()

# ---------------------------------------------------------------- ホー先生（フクロウ）
def _owl(expr, blink, talk, look):
    W0, H0 = 560, 760; p = Pen(W0, H0); cx = W0 / 2
    body, belly, dark = (150, 112, 86), (250, 232, 205), (110, 80, 60)
    # 羽
    p.ellipse((cx - 230, 380, cx - 120, 640), dark)
    p.ellipse((cx + 120, 380, cx + 230, 640), dark)
    # 耳（羽角）と体
    p.poly([(cx - 170, 220), (cx - 150, 90), (cx - 80, 170)], fill=body)
    p.poly([(cx + 170, 220), (cx + 150, 90), (cx + 80, 170)], fill=body)
    p.ellipse((cx - 200, 140, cx + 200, 760), body)
    p.ellipse((cx - 130, 400, cx + 130, 740), belly, line=None)
    for row in range(3):
        for k in range(-1, 2):
            x, y = cx + k * 60 + (row % 2) * 30 - 15, 470 + row * 70
            p.arc((x - 22, y - 12, x + 22, y + 18), 20, 160, fill=_mix(body, 0.1), lw=5)
    # 顔のハート形
    p.ellipse((cx - 170, 200, cx + 10, 400), (240, 220, 190), line=None)
    p.ellipse((cx - 10, 200, cx + 170, 400), (240, 220, 190), line=None)
    # 目（めがね）
    for x in (cx - 80, cx + 80):
        p.ellipse((x - 62, 240, x + 62, 364), WHITE, line=NAVY, lw=10)
    p.line([(cx - 18, 290), (cx + 18, 290)], fill=NAVY, lw=9)
    ex, ey = (cx - 80, cx + 80), 302
    if blink or expr == 'happy':
        for x in ex:
            if expr == 'happy': p.arc((x - 26, ey - 14, x + 26, ey + 24), 200, 340, lw=8)
            else: p.line([(x - 24, ey + 4), (x + 24, ey + 4)], lw=8)
    else:
        r = 30 if expr == 'surprised' else 24
        for x in ex:
            p.ellipse((x - r + look[0], ey - r + look[1], x + r + look[0], ey + r + look[1]), fill=INK, line=None)
            p.ellipse((x - r * 0.5 + look[0], ey - r * 0.7 + look[1], x + look[0], ey - r * 0.2 + look[1]), fill=WHITE, line=None)
    # くちばし
    o = 10 * talk
    p.poly([(cx - 22, 372), (cx + 22, 372), (cx, 410 + o)], fill=(255, 176, 60), lw=5)
    # 角帽
    p.poly([(cx - 150, 150), (cx, 96), (cx + 150, 150), (cx, 204)], fill=NAVY, lw=5)
    p.rrect((cx - 70, 150, cx + 70, 196), 8, NAVY, lw=5)
    p.line([(cx, 150), (cx + 120, 170), (cx + 120, 236)], fill=CORAL, lw=6)
    p.ellipse((cx + 106, 228, cx + 134, 262), fill=CORAL, lw=4)
    p.ellipse((cx - 100, 360, cx - 70, 380), fill=PINK + (140,), line=None)
    p.ellipse((cx + 70, 360, cx + 100, 380), fill=PINK + (140,), line=None)
    if expr == 'think':
        pass
    return p.done()

@lru_cache(maxsize=512)
def sprite(who, expr='normal', blink=False, talk=0, look=(0, 0), h=760, flip=False):
    """人物の画像（RGBA）。h は出力の高さ。talk は口の開き 0〜3 段階"""
    t = talk / 3
    im = _owl(expr, blink, t, look) if who == 'sensei' else _human(who, expr, blink, t, look)
    if h != im.height:
        im = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
    if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im

# ---------------------------------------------------------------- 背景
def _grad(W, H, top, bot):
    g = Image.new('RGB', (1, 256))
    for y in range(256):
        g.putpixel((0, y), _mix(top, y / 255, bot))
    return g.resize((W, H), Image.BILINEAR)

def _burst(W, H, c1, c2, cx=None, cy=None, n=24):
    im = Image.new('RGB', (W, H), c1); d = ImageDraw.Draw(im)
    cx = W / 2 if cx is None else cx; cy = H * 0.45 if cy is None else cy
    R = max(W, H) * 1.5
    for i in range(n):
        a0 = 2 * math.pi * i / n; a1 = a0 + math.pi / n
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=c2)
    return im

def _window(d, box, sky_top, sky_bot, night=False, frame=WHITE):
    x0, y0, x1, y1 = box
    g = _grad(int(x1 - x0), int(y1 - y0), sky_top, sky_bot)
    return g

@lru_cache(maxsize=32)
def background(kind, W, H):
    rnd = random.Random(kind)
    if kind in ('pop', 'pop2'):
        c1, c2 = ((255, 214, 102), (255, 226, 140)) if kind == 'pop' else ((255, 140, 110), (255, 160, 130))
        im = _burst(W, H, c1, c2)
        d = ImageDraw.Draw(im, 'RGBA')
        for _ in range(18):
            x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(6, 16)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 110))
        return im
    if kind == 'board':
        im = Image.new('RGB', (W, H), (246, 238, 226)); d = ImageDraw.Draw(im, 'RGBA')
        for x in range(0, W, 54): d.line([(x, 0), (x, H)], fill=(0, 0, 0, 10), width=2)
        for y in range(0, H, 54): d.line([(0, y), (W, y)], fill=(0, 0, 0, 10), width=2)
        return im
    im = Image.new('RGB', (W, H)); d = ImageDraw.Draw(im, 'RGBA')
    floor_y = int(H * 0.62)
    if kind == 'night':
        im.paste(_grad(W, H, (40, 50, 90), (70, 70, 120)))
        wx0, wy0, wx1, wy1 = int(W * 0.08), int(H * 0.12), int(W * 0.56), int(H * 0.40)
        im.paste(_grad(wx1 - wx0, wy1 - wy0, (20, 30, 70), (60, 60, 130)), (wx0, wy0))
        for _ in range(26):
            x, y = rnd.uniform(wx0 + 10, wx1 - 10), rnd.uniform(wy0 + 10, wy1 - 10)
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 250, 220, 220))
        mx, my = wx0 + (wx1 - wx0) * 0.7, wy0 + (wy1 - wy0) * 0.35
        d.ellipse((mx - 50, my - 50, mx + 50, my + 50), fill=(255, 240, 180))
        d.ellipse((mx - 30, my - 62, mx + 66, my + 34), fill=(30, 40, 82))
        d.rectangle((wx0, wy0, wx1, wy1), outline=(130, 120, 170), width=18)
        d.line([((wx0 + wx1) / 2, wy0), ((wx0 + wx1) / 2, wy1)], fill=(130, 120, 170), width=12)
        # スタンドライト
        lx = int(W * 0.82)
        d.ellipse((lx - 260, int(H * 0.18) - 120, lx + 260, int(H * 0.18) + 400), fill=(255, 220, 140, 40))
        d.polygon([(lx - 70, int(H * 0.2)), (lx + 70, int(H * 0.2)), (lx + 40, int(H * 0.12)), (lx - 40, int(H * 0.12))], fill=(255, 210, 130))
        d.rectangle((lx - 6, int(H * 0.2), lx + 6, floor_y), fill=(90, 90, 130))
        d.rectangle((0, floor_y, W, H), fill=(60, 60, 105))
        d.rounded_rectangle((-40, floor_y - 40, W + 40, H), radius=60, fill=(110, 120, 180))  # ふとん
        return im
    walls = {'room': ((255, 238, 220), (252, 226, 204)), 'office': ((226, 236, 246), (212, 224, 238)),
             'cafe': ((246, 226, 200), (236, 210, 180)), 'shop': ((255, 240, 236), (250, 224, 220)),
             'street': ((170, 214, 245), (214, 236, 252)), 'lab': ((232, 244, 238), (216, 236, 228))}
    top, bot = walls.get(kind, walls['room'])
    im.paste(_grad(W, H, top, bot))
    if kind == 'street':
        for i in range(7):
            bw = rnd.randint(120, 220); bh = rnd.randint(int(H * 0.2), int(H * 0.45)); bx = i * W // 6 - 40
            col = rnd.choice([(250, 250, 255), (230, 236, 250), (255, 236, 220)])
            d.rectangle((bx, floor_y - bh, bx + bw, floor_y), fill=col, outline=(150, 160, 190), width=4)
            for wy in range(floor_y - bh + 30, floor_y - 40, 70):
                for wx in range(bx + 20, bx + bw - 30, 50):
                    d.rectangle((wx, wy, wx + 26, wy + 36), fill=(170, 200, 240))
        for cx_, cy_ in ((W * 0.2, H * 0.1), (W * 0.75, H * 0.16)):
            for dx, r in ((-50, 40), (0, 56), (50, 40)):
                d.ellipse((cx_ + dx - r, cy_ - r, cx_ + dx + r, cy_ + r), fill=(255, 255, 255, 230))
        d.rectangle((0, floor_y, W, H), fill=(200, 196, 190))
        return im
    # 壁の模様
    if kind in ('room', 'shop'):
        for y in range(0, floor_y, 70):
            for x in range((y // 70 % 2) * 35, W, 70):
                d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 255, 255, 120))
    if kind == 'office':
        for x in range(0, W, 140): d.rectangle((x, 0, x + 4, floor_y), fill=(255, 255, 255, 90))
        wx0, wy0, wx1, wy1 = int(W * 0.55), int(H * 0.08), int(W * 0.95), int(H * 0.36)
        im.paste(_grad(wx1 - wx0, wy1 - wy0, (150, 200, 245), (210, 232, 250)), (wx0, wy0))
        for y in range(wy0 + 20, wy1, 34): d.line([(wx0, y), (wx1, y)], fill=(255, 255, 255, 170), width=8)
        d.rectangle((wx0, wy0, wx1, wy1), outline=WHITE, width=14)
        d.ellipse((int(W * 0.08), int(H * 0.1), int(W * 0.08) + 130, int(H * 0.1) + 130), fill=WHITE, outline=(120, 130, 160), width=6)
        c = (int(W * 0.08) + 65, int(H * 0.1) + 65)
        d.line([c, (c[0], c[1] - 40)], fill=INK, width=6); d.line([c, (c[0] + 30, c[1] + 10)], fill=INK, width=6)
    if kind == 'room':
        wx0, wy0, wx1, wy1 = int(W * 0.1), int(H * 0.1), int(W * 0.5), int(H * 0.34)
        im.paste(_grad(wx1 - wx0, wy1 - wy0, (140, 196, 245), (205, 232, 252)), (wx0, wy0))
        for dx, r in ((-30, 26), (10, 36), (50, 26)):
            d.ellipse((wx0 + 140 + dx - r, wy0 + 90 - r, wx0 + 140 + dx + r, wy0 + 90 + r), fill=(255, 255, 255, 230))
        d.rectangle((wx0, wy0, wx1, wy1), outline=WHITE, width=16)
        d.line([((wx0 + wx1) / 2, wy0), ((wx0 + wx1) / 2, wy1)], fill=WHITE, width=10)
        # 植物
        px, py = int(W * 0.84), floor_y
        for a in (-0.9, -0.4, 0.1, 0.6, 1.0):
            d.ellipse((px + 140 * math.sin(a) - 30, py - 250 - 60 * math.cos(a), px + 140 * math.sin(a) + 30, py - 140 - 60 * math.cos(a)), fill=(110, 190, 150))
        d.rounded_rectangle((px - 60, py - 140, px + 60, py), radius=14, fill=(230, 140, 110))
    if kind == 'cafe':
        for x in (W * 0.22, W * 0.55, W * 0.85):
            d.line([(x, 0), (x, H * 0.12)], fill=(90, 70, 60), width=5)
            d.pieslice((x - 70, H * 0.12 - 50, x + 70, H * 0.12 + 70), 180, 360, fill=(255, 190, 90))
            d.ellipse((x - 120, H * 0.12, x + 120, H * 0.12 + 200), fill=(255, 220, 140, 50))
        for x in range(0, W, 90):
            d.rectangle((x, int(H * 0.5), x + 44, floor_y), fill=(255, 255, 255, 40))
    if kind == 'shop':
        for row in range(3):
            y = int(H * 0.12) + row * int(H * 0.15)
            d.rectangle((0, y + 130, W, y + 146), fill=(200, 160, 130))
            for x in range(20, W, 110):
                col = rnd.choice([CORAL, YELLOW, MINT, SKY, PINK, (200, 170, 240)])
                h = rnd.randint(70, 125)
                d.rounded_rectangle((x, y + 130 - h, x + 84, y + 130), radius=10, fill=col, outline=INK, width=4)
        d.rounded_rectangle((W * 0.58, H * 0.03, W * 0.94, H * 0.1), radius=20, fill=CORAL)
        d.text((W * 0.62, H * 0.035), 'SALE 50%', font=font(int(H * 0.04)), fill=WHITE)
    if kind == 'lab':
        for y in range(0, floor_y, 64):
            for x in range((y // 64 % 2) * 32, W, 64):
                d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 255, 255, 150))
        for i, (bx, by) in enumerate(((W * 0.05, floor_y - 120), (W * 0.82, floor_y - 160))):
            for k in range(4):
                col = (CORAL, YELLOW, SKY, MINT)[(k + i) % 4]
                d.rounded_rectangle((bx + k * 36, by + (k % 2) * 20, bx + k * 36 + 30, floor_y), radius=6, fill=col, outline=INK, width=4)
    # 床・机
    fc = {'office': (190, 200, 220), 'cafe': (170, 120, 90), 'room': (236, 200, 160), 'shop': (230, 210, 200), 'lab': (200, 220, 210)}[kind]
    d.rectangle((0, floor_y, W, H), fill=fc)
    if kind == 'office':
        d.rounded_rectangle((W * 0.62, floor_y - 190, W * 0.98, floor_y - 10), radius=12, fill=(60, 70, 90))
        d.rounded_rectangle((W * 0.64, floor_y - 172, W * 0.96, floor_y - 28), radius=6, fill=(140, 190, 240))
    return im

# ---------------------------------------------------------------- 吹き出し・テロップ・効果
def bubble(text, size=56, max_w=760, kind='say', tail='down', tail_x=0.5, fg=INK, bg=WHITE, name=None):
    """吹き出しのRGBA画像を返す。kind: say（ふつう）/ think（もくもく）/ shout（ギザギザ）"""
    tmp = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    f = font(size, maru=True)
    lines = wrap(tmp, text, f, max_w)
    tw = max(tmp.textlength(l, font=f) for l in lines); lh = int(size * 1.42)
    th = lh * len(lines)
    padx, pady = int(size * 0.8), int(size * 0.62)
    if kind == 'shout': padx, pady = int(size * 1.5), int(size * 1.15)
    bw, bh = int(tw + padx * 2), int(th + pady * 2)
    tail_h = int(size * 0.9)
    m = 24
    Wc, Hc = bw + m * 2, bh + m * 2 + tail_h
    im = Image.new('RGBA', (Wc * SS, Hc * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    s = lambda v: int(v * SS)
    box = (m, m, m + bw, m + bh)
    tx = m + bw * tail_x
    lw = 6
    if kind == 'shout':
        cx, cy = m + bw / 2, m + bh / 2; pts = []
        n = 28
        for i in range(n):
            a = 2 * math.pi * i / n
            r = 1.0 if i % 2 == 0 else 0.86
            pts.append((cx + (bw / 2 + 14) * r * math.cos(a), cy + (bh / 2 + 14) * r * math.sin(a)))
        d.polygon([(s(x), s(y)) for x, y in pts], fill=bg, outline=INK)
        d.line([(s(x), s(y)) for x, y in pts + [pts[0]]], fill=INK, width=s(lw), joint='curve')
    elif kind == 'think':
        r = min(bh / 2, 60)
        d.rounded_rectangle([s(v) for v in box], radius=s(r), fill=bg, outline=INK, width=s(lw))
        for i in range(int(bw // 70)):
            x = m + 40 + i * 70
            d.chord((s(x - 40), s(m - 16), s(x + 40), s(m + 40)), 180, 360, fill=bg, outline=INK, width=s(lw))
            d.chord((s(x - 40), s(m + bh - 40), s(x + 40), s(m + bh + 16)), 0, 180, fill=bg, outline=INK, width=s(lw))
        d.rounded_rectangle([s(v) for v in (m + 8, m + 8, m + bw - 8, m + bh - 8)], radius=s(r), fill=bg)
        for k, (dy, rr) in enumerate(((22, 16), (52, 10))):
            y = m + bh + dy
            d.ellipse((s(tx - rr), s(y - rr), s(tx + rr), s(y + rr)), fill=bg, outline=INK, width=s(lw - 1))
    else:
        r = min(bh / 2, 64)
        if tail == 'down':
            tri = [(tx - 30, m + bh - 10), (tx + 30, m + bh - 10), (tx + (-18 if tail_x > 0.5 else 18), m + bh + tail_h)]
            d.polygon([(s(x), s(y)) for x, y in tri], fill=bg)
            d.line([(s(x), s(y)) for x, y in [tri[0], tri[2], tri[1]]], fill=INK, width=s(lw), joint='curve')
        d.rounded_rectangle([s(v) for v in box], radius=s(r), fill=bg, outline=INK, width=s(lw))
        if tail == 'down':
            d.polygon([(s(tx - 26), s(m + bh - 14)), (s(tx + 26), s(m + bh - 14)), (s(tx), s(m + bh + 2))], fill=bg)
            d.rectangle((s(tx - 26), s(m + bh - 20), s(tx + 26), s(m + bh - 2)), fill=bg)
    im = im.resize((Wc, Hc), Image.LANCZOS); d = ImageDraw.Draw(im)
    y = m + pady - int(size * 0.08)
    for l in lines:
        w = d.textlength(l, font=f)
        d.text((m + (bw - w) / 2, y), l, font=f, fill=fg, stroke_width=max(1, size // 30), stroke_fill=fg)
        y += lh
    if name:
        nf = font(30); nw = d.textlength(name, font=nf)
    return im

def caption_box(text, size=50, max_w=880, bg=NAVY, fg=WHITE, label=None):
    """ナレーション用の四角い帯（漫画のナレーション枠）"""
    tmp = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    f = font(size)
    lines = wrap(tmp, text, f, max_w)
    tw = max(tmp.textlength(l, font=f) for l in lines); lh = int(size * 1.45)
    padx, pady = 44, 30
    lab_h = 0
    bw, bh = int(tw + padx * 2), int(lh * len(lines) + pady * 2)
    im = Image.new('RGBA', (bw + 20, bh + 20 + (46 if label else 0)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    oy = 46 if label else 0
    d.rounded_rectangle((10, 10 + oy, 10 + bw, 10 + oy + bh), radius=22, fill=bg + (240,))
    if label:
        lf = font(32); lw_ = d.textlength(label, font=lf)
        d.rounded_rectangle((26, 0, 26 + lw_ + 40, 62), radius=31, fill=CORAL)
        d.text((46, 8), label, font=lf, fill=WHITE)
    y = 10 + oy + pady - int(size * 0.1)
    for l in lines:
        d.text((10 + padx, y), l, font=f, fill=fg); y += lh
    return im

def speedlines(W, H, cx, cy, color=(255, 255, 255), n=70, seed=0, inner=0.32):
    """集中線（RGBA）"""
    rnd = random.Random(seed)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    R = math.hypot(W, H)
    for i in range(n):
        a = rnd.uniform(0, 2 * math.pi); r0 = rnd.uniform(inner, inner + 0.15) * min(W, H)
        w = rnd.uniform(0.004, 0.012)
        d.polygon([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
                   (cx + R * math.cos(a - w), cy + R * math.sin(a - w)),
                   (cx + R * math.cos(a + w), cy + R * math.sin(a + w))], fill=color + (150,))
    return im

def icon_fx(kind, size=120):
    """人物の頭の横に出す記号：! / ? / ♪ / ✨ / 💡(電球) / …"""
    p = Pen(size, size)
    c = size / 2
    if kind == '!':
        p.rrect((c - 14, 10, c + 14, size * 0.66), 14, CORAL, lw=5); p.ellipse((c - 15, size * 0.74, c + 15, size * 0.74 + 30), CORAL, lw=5)
    elif kind == '?':
        p.arc((c - 34, 12, c + 34, 80), 180, 90, fill=SKY, lw=16); p.line([(c, 80), (c, 92)], fill=SKY, lw=16)
        p.ellipse((c - 10, size - 28, c + 10, size - 8), SKY, line=None)
    elif kind == 'idea':
        p.ellipse((c - 38, 10, c + 38, 86), YELLOW, lw=5); p.rrect((c - 20, 82, c + 20, 108), 6, (200, 200, 210), lw=5)
        for a in range(-150, -20, 32):
            r = math.radians(a); p.line([(c + 50 * math.cos(r), 48 + 50 * math.sin(r)), (c + 64 * math.cos(r), 48 + 64 * math.sin(r))], fill=YELLOW, lw=6)
    elif kind == 'sparkle':
        for (x, y, r) in ((c, c, 40), (c + 36, 26, 16), (c - 38, size - 24, 14)):
            p.poly([(x, y - r), (x + r * 0.25, y - r * 0.25), (x + r, y), (x + r * 0.25, y + r * 0.25), (x, y + r), (x - r * 0.25, y + r * 0.25), (x - r, y), (x - r * 0.25, y - r * 0.25)], fill=YELLOW, lw=4)
    elif kind == 'heart':
        p.ellipse((c - 44, 24, c + 4, 72), CORAL, line=None); p.ellipse((c - 4, 24, c + 44, 72), CORAL, line=None)
        p.poly([(c - 42, 56), (c + 42, 56), (c, 104)], fill=CORAL, line=None)
    elif kind == 'gloom':
        for i in range(3):
            p.arc((10 + i * 30, 10 + i * 26, size - 10 - i * 30, size - 10 - i * 26), 0, 300, fill=(120, 120, 160), lw=6)
    elif kind == '...':
        for i in range(3): p.ellipse((14 + i * 34, c - 10, 34 + i * 34, c + 10), INK, line=None)
    return p.done(sticker=False)
