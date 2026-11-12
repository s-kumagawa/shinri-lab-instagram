"""しんりラボ UI部品：吹き出し・ナレーション枠・集中線・記号。人物と背景は figure.py。"""
import math, random
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter
from design import *

SS = 2  # スーパーサンプリング倍率（なめらかな線のため）
LW = 6  # 線の太さ（論理px）

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
