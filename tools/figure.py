"""ピクトグラム風の人物（顔なし）と、動くための骨組み・ポーズ・小物・背景・図解アイコン。

人物（who）
  me     … 主人公（コーラル）。視聴者の分身
  friend … 友だち・同僚（ネイビー）
  boss   … 上司・店員など（グレー）
  旧仕様の mina→me、sota→friend も使える
ポーズ（pose）。旧仕様の表情名（expr）もそのまま使える
  stand / walk / run / joy / jump / worried(頭を抱える) / sad(うなだれる) / think(あごに手)
  shock(のけぞる) / surprised / point(指さす) / shrug(肩をすくめる) / phone(スマホを見る)
  wave(手を振る) / idea(ひらめき) / write(メモする) / happy / normal / smug / talk(身ぶりで話す)
小物（prop）: phone / bag / note / cup / heart / coin
背景（bg）: room / office / cafe / night / shop / street / park / pop / pop2 / navy / cream
"""
import math, random
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter
from design import *
from art import Pen, _grad, _burst, _mix

COLORS = {'me': CORAL, 'friend': (52, 74, 120), 'boss': (120, 128, 146)}
ALIAS = {'mina': 'me', 'sota': 'friend', 'sensei': 'narr'}
EXPR2POSE = {'normal': 'stand', 'happy': 'joy', 'worried': 'worried', 'surprised': 'surprised',
             'sad': 'sad', 'think': 'think', 'shock': 'shock', 'smug': 'point'}

def who_of(w): return ALIAS.get(w, w)
def pose_of(p): return EXPR2POSE.get(p, p) if p else 'stand'

# ---------------------------------------------------------------- 骨組み
# 寸法（体の高さ ≒ 560 の論理単位）
R_HEAD, GAP = 54, 12
TORSO, UA, FA, TH, SH = 170, 88, 84, 112, 112
W_TORSO, W_LIMB = 76, 38

# 角度は「真下=0、画面右=+90、真上=180」。腕・脚は肩・腰から見た絶対角度
BASE = dict(t=0, hx=0, hy=0, la=-10, lf=-6, ra=10, rf=6, ll=-7, lk=-4, rl=7, rk=4, y=0, prop=None)
POSES = {
    'stand':     {},
    'talk':      dict(ra=40, rf=120),
    'joy':       dict(la=-150, lf=-165, ra=150, rf=165, ll=-12, rl=12),
    'jump':      dict(la=-140, lf=-160, ra=140, rf=160, ll=-25, lk=10, rl=25, rk=-10, y=-60),
    'worried':   dict(la=-128, lf=152, ra=128, rf=-152, hy=8),
    'sad':       dict(t=0, hx=0, hy=26, la=-6, lf=-3, ra=6, rf=3, y=10),
    'think':     dict(ra=30, rf=-165, la=20, lf=95, hx=8),
    'shock':     dict(la=-112, lf=-150, ra=112, rf=150, ll=-16, rl=16, t=-6, hy=-6),
    'surprised': dict(la=-60, lf=-120, ra=60, rf=120, ll=-12, rl=12, y=-14),
    'point':     dict(ra=96, rf=96, la=-12, lf=-6),
    'shrug':     dict(la=-62, lf=-160, ra=62, rf=160),
    'phone':     dict(la=-22, lf=70, ra=22, rf=-70, hy=14, prop='phone'),
    'wave':      dict(ra=150, rf=175),
    'idea':      dict(ra=160, rf=178, la=-12),
    'write':     dict(la=-28, lf=78, ra=26, rf=-50, hy=12, prop='note'),
    'walk':      dict(),
    'run':       dict(),
}
for k in list(POSES): POSES[k] = {**BASE, **POSES[k]}

def _lerp(a, b, k):
    out = {}
    for key, v in a.items():
        if key == 'prop': out[key] = b[key] if k > 0.5 else v
        else: out[key] = v + (b[key] - v) * k
    return out

def animate(name, t, seed=0):
    """ポーズ名と時刻から、その瞬間の骨組みを返す（くり返しの小さな動きつき）"""
    p = dict(POSES.get(name, POSES['stand']))
    s = t + seed * 0.37
    if name in ('walk', 'run'):
        sw = 28 if name == 'walk' else 46; f = 1.9 if name == 'walk' else 3.0
        ph = math.sin(2 * math.pi * f * s)
        p.update(ll=-sw * ph, lk=-sw * ph + (20 if ph < 0 else 4), rl=sw * ph, rk=sw * ph + (20 if ph > 0 else 4),
                 la=sw * 0.8 * ph, lf=sw * ph + (30 if name == 'run' else 8), ra=-sw * 0.8 * ph, rf=-sw * ph - (30 if name == 'run' else 8),
                 y=-abs(math.cos(2 * math.pi * f * s)) * (8 if name == 'walk' else 22), t=(4 if name == 'walk' else 10))
    elif name == 'joy':
        j = abs(math.sin(2 * math.pi * 1.3 * s))
        p['y'] = -46 * j; p['la'] -= 10 * j; p['ra'] += 10 * j
    elif name == 'jump':
        j = abs(math.sin(2 * math.pi * 1.1 * s)); p['y'] = -20 - 60 * j
    elif name == 'worried':
        w = math.sin(2 * math.pi * 0.9 * s); p['t'] = 5 * w; p['hx'] = 6 * w
    elif name == 'sad':
        p['y'] += 4 * math.sin(2 * math.pi * 0.4 * s); p['hy'] += 3 * math.sin(2 * math.pi * 0.4 * s)
    elif name == 'think':
        p['hx'] = 8 + 4 * math.sin(2 * math.pi * 0.5 * s); p['rf'] += 4 * math.sin(2 * math.pi * 1.6 * s)
    elif name == 'shock':
        p['hx'] = 4 * math.sin(2 * math.pi * 7 * s)
    elif name == 'wave':
        p['rf'] = 175 + 28 * math.sin(2 * math.pi * 2.2 * s)
    elif name == 'talk':
        p['rf'] = 120 + 22 * math.sin(2 * math.pi * 1.8 * s); p['ra'] = 40 + 8 * math.sin(2 * math.pi * 0.9 * s)
    elif name == 'point':
        p['ra'] = 96 + 3 * math.sin(2 * math.pi * 1.5 * s)
    elif name == 'shrug':
        k = (math.sin(2 * math.pi * 0.8 * s) + 1) / 2; p['y'] = -10 * k
    elif name == 'phone':
        p['hy'] = 14 + 3 * math.sin(2 * math.pi * 0.6 * s)
    elif name == 'idea':
        p['y'] = -8 * abs(math.sin(2 * math.pi * 1.2 * s))
    else:  # stand ほか：呼吸
        p['y'] += 3 * math.sin(2 * math.pi * 0.5 * s)
    return p

def blend_pose(prev, cur, t, t_switch, seed=0, dur=0.28):
    """ポーズの切り替えをなめらかにつなぐ"""
    k = (t - t_switch) / dur
    a = animate(cur, t, seed)
    if prev is None or k >= 1: return a
    k = max(0.0, k); k = 1 - (1 - k) ** 3
    return _lerp(animate(prev, t, seed), a, k)

def _pt(o, ang, L):
    r = math.radians(ang); return (o[0] + L * math.sin(r), o[1] + L * math.cos(r))

def _prop(p, kind, hand, col):
    x, y = hand
    if kind == 'phone':
        p.rrect((x - 28, y - 50, x + 28, y + 42), 10, (40, 44, 60), line=None)
        p.rrect((x - 21, y - 42, x + 21, y + 30), 6, SKY, line=None)
    elif kind == 'note':
        p.rrect((x - 40, y - 46, x + 34, y + 40), 8, WHITE, line=(150, 150, 160), lw=4)
        for i in range(3): p.line([(x - 26, y - 24 + i * 22), (x + 20, y - 24 + i * 22)], fill=(170, 170, 180), lw=4)
    elif kind == 'bag':
        p.arc((x - 26, y - 10, x + 26, y + 40), 180, 360, fill=(90, 90, 110), lw=7)
        p.rrect((x - 44, y + 14, x + 44, y + 100), 10, YELLOW, line=None)
    elif kind == 'cup':
        p.rrect((x - 26, y - 30, x + 26, y + 30), 8, WHITE, line=(150, 150, 160), lw=4)
    elif kind == 'heart':
        p.ellipse((x - 34, y - 40, x + 2, y - 4), CORAL, line=None); p.ellipse((x - 2, y - 40, x + 34, y - 4), CORAL, line=None)
        p.poly([(x - 33, y - 18), (x + 33, y - 18), (x, y + 24)], fill=CORAL, line=None)
    elif kind == 'coin':
        p.ellipse((x - 32, y - 32, x + 32, y + 32), YELLOW, line=(200, 150, 40), lw=5)

def draw_figure(base, who, pose, cx, foot_y, scale=1.0, color=None, flip=False, shadow=True):
    """base(RGBA) の (cx, foot_y) に足をそろえて人物を描く"""
    col = color or COLORS.get(who_of(who), CORAL)
    p = dict(pose)
    if flip:
        for a, b in (('la', 'ra'), ('lf', 'rf'), ('ll', 'rl'), ('lk', 'rk')):
            p[a], p[b] = -p[b], -p[a]
        p['t'] = -p['t']; p['hx'] = -p['hx']
    leg = TH + SH
    hip0 = (0.0, 0.0)
    # 腰の位置（足がだいたい地面に着くように、脚の縦の長さで調整）
    lk_ = _pt(_pt(hip0, p['ll'], TH), p['lk'], SH); rk_ = _pt(_pt(hip0, p['rl'], TH), p['rk'], SH)
    drop = max(lk_[1], rk_[1])
    hip = (0.0, -drop + p['y'])
    neck = _pt(hip, 180 + p['t'], TORSO)
    sh = _pt(hip, 180 + p['t'], TORSO - 18)
    head = (neck[0] + p['hx'] + (R_HEAD + GAP) * math.sin(math.radians(p['t'])),
            neck[1] - R_HEAD - GAP + p['hy'])
    ct, st_ = math.cos(math.radians(p['t'])), math.sin(math.radians(p['t']))
    shl = (sh[0] - 24 * ct, sh[1] - 24 * st_); shr = (sh[0] + 24 * ct, sh[1] + 24 * st_)
    hpl = (hip[0] - 13, hip[1]); hpr = (hip[0] + 13, hip[1])
    lel = _pt(shl, p['la'], UA); lha = _pt(lel, p['lf'], FA)
    rel = _pt(shr, p['ra'], UA); rha = _pt(rel, p['rf'], FA)
    lkn = _pt(hpl, p['ll'], TH); lft = _pt(lkn, p['lk'], SH)
    rkn = _pt(hpr, p['rl'], TH); rft = _pt(rkn, p['rk'], SH)
    pts = [hip, neck, head, lel, lha, rel, rha, lkn, lft, rkn, rft]
    pad = 140
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    x0, y0 = min(xs) - pad, min(ys) - R_HEAD - pad; x1, y1 = max(xs) + pad, max(ys) + pad
    Wc, Hc = int(x1 - x0), int(y1 - y0)
    pen = Pen(Wc, Hc)
    T = lambda q: (q[0] - x0, q[1] - y0)
    dark = _mix(col, 0.18)
    # 奥の手足（少し暗く）→ 胴 → 手前
    pen.line([T(hpl), T(lkn), T(lft)], fill=dark, lw=W_LIMB)
    pen.line([T(shl), T(lel), T(lha)], fill=dark, lw=W_LIMB)
    pen.line([T(hip), T(neck)], fill=col, lw=W_TORSO)
    pen.line([T(hpr), T(rkn), T(rft)], fill=col, lw=W_LIMB)
    pen.line([T(shr), T(rel), T(rha)], fill=col, lw=W_LIMB)
    hx, hy = T(head)
    pen.ellipse((hx - R_HEAD, hy - R_HEAD, hx + R_HEAD, hy + R_HEAD), col, line=None)
    if p.get('prop'):
        hm = ((lha[0] + rha[0]) / 2, (lha[1] + rha[1]) / 2) if p['prop'] in ('phone', 'note') else rha
        _prop(pen, p['prop'], T(hm), col)
    im = pen.done(sticker=False)
    if abs(scale - 1) > 0.01:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    ox = cx + x0 * scale; oy = foot_y + y0 * scale
    if shadow:
        sw = 120 * scale * (1 - min(0.5, -p['y'] / 200)); sh_ = 14 * scale
        sd = Image.new('RGBA', (int(sw * 2) + 4, int(sh_ * 2) + 4), (0, 0, 0, 0))
        ImageDraw.Draw(sd).ellipse((2, 2, sw * 2, sh_ * 2), fill=(0, 0, 0, 34))
        base.alpha_composite(sd, (int(cx - sw), int(foot_y - sh_)))
    base.alpha_composite(im, (int(ox), int(oy)))
    # 頭の位置（吹き出し・記号の基準）
    return (cx + head[0] * scale, foot_y + head[1] * scale), (cx + rha[0] * scale, foot_y + rha[1] * scale)

# ---------------------------------------------------------------- 背景（平面＋線画。人物が主役になるよう控えめに）
BG = {
    'room':   ((252, 241, 228), (244, 226, 206)), 'office': ((232, 240, 248), (214, 226, 240)),
    'cafe':   ((247, 233, 214), (236, 214, 188)), 'night':  ((44, 54, 96), (30, 38, 72)),
    'shop':   ((255, 236, 232), (250, 218, 212)), 'street': ((214, 236, 250), (190, 222, 244)),
    'park':   ((226, 244, 228), (204, 232, 208)), 'navy':   (NAVY, (22, 32, 54)),
    'cream':  ((250, 245, 236), (242, 234, 220)),
}
FLOOR = 0.76  # 床の高さ（画面の割合）

@lru_cache(maxsize=48)
def background(kind, W, H):
    if kind in ('pop', 'pop2'):
        c1, c2 = ((255, 214, 102), (255, 226, 140)) if kind == 'pop' else ((255, 140, 110), (255, 160, 130))
        return _burst(W, H, c1, c2).convert('RGBA')
    top, bot = BG.get(kind, BG['room'])
    im = _grad(W, H, top, bot).convert('RGBA'); d = ImageDraw.Draw(im, 'RGBA')
    fy = int(H * FLOOR)
    ln = _mix(bot, 0.12) if kind not in ('night', 'navy') else (88, 100, 150)
    lw = max(5, W // 180)
    s = W / 1080
    def box(x0, y0, x1, y1, r=14, fill=None): d.rounded_rectangle((x0 * s, y0 * s, x1 * s, y1 * s), radius=r * s, outline=ln, width=lw, fill=fill)
    if kind in ('navy', 'cream'):
        return im
    if kind == 'room':
        box(110, fy / s - 760, 470, fy / s - 400, 18); d.line([(290 * s, fy - 760 * s), (290 * s, fy - 400 * s)], fill=ln, width=lw)
        box(800, fy / s - 170, 900, fy / s, 12)
        for a in (-0.7, 0, 0.7):
            d.ellipse(((850 + 90 * math.sin(a)) * s - 34 * s, fy - 300 * s - 40 * s * math.cos(a), (850 + 90 * math.sin(a)) * s + 34 * s, fy - 170 * s - 40 * s * math.cos(a)), outline=ln, width=lw)
    elif kind == 'office':
        box(640, fy / s - 300, 960, fy / s - 120, 12); d.line([(800 * s, fy - 120 * s), (800 * s, fy - 60 * s)], fill=ln, width=lw)
        d.line([(560 * s, fy - 60 * s), (1040 * s, fy - 60 * s)], fill=ln, width=lw)
        d.ellipse((120 * s, fy - 820 * s, 260 * s, fy - 680 * s), outline=ln, width=lw)
        d.line([(190 * s, fy - 750 * s), (190 * s, fy - 795 * s)], fill=ln, width=lw); d.line([(190 * s, fy - 750 * s), (225 * s, fy - 740 * s)], fill=ln, width=lw)
    elif kind == 'cafe':
        for x in (220, 540, 860):
            d.line([(x * s, 0), (x * s, fy - 900 * s)], fill=ln, width=lw)
            d.chord(((x - 70) * s, fy - 940 * s, (x + 70) * s, fy - 820 * s), 180, 360, outline=ln, width=lw)
        box(640, fy / s - 140, 1000, fy / s - 110, 8); d.line([(820 * s, fy - 110 * s), (820 * s, fy)], fill=ln, width=lw)
        box(760, fy / s - 210, 820, fy / s - 145, 8)
    elif kind == 'night':
        d.ellipse((760 * s, fy - 980 * s, 900 * s, fy - 840 * s), fill=(255, 238, 180))
        d.ellipse((720 * s, fy - 1000 * s, 850 * s, fy - 870 * s), fill=top)
        rnd = random.Random(3)
        for _ in range(26):
            x, y = rnd.uniform(0, W), rnd.uniform(0, fy - 300 * s)
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 250, 220, 200))
        box(60, fy / s - 120, 520, fy / s - 10, 30, fill=(70, 80, 130))
    elif kind == 'shop':
        for row in range(3):
            y = fy / s - 900 + row * 220
            d.line([(0, (y + 160) * s), (W, (y + 160) * s)], fill=ln, width=lw)
            for x in range(40, 1080, 130):
                h = 60 + (x * 7 + row * 13) % 70
                box(x, y + 160 - h, x + 90, y + 160, 10)
        d.rounded_rectangle((700 * s, 60 * s, 1000 * s, 150 * s), radius=24 * s, fill=CORAL)
        d.text((740 * s, 72 * s), 'SALE', font=font(int(60 * s)), fill=WHITE)
    elif kind == 'street':
        for i, (x, h) in enumerate(((0, 520), (200, 700), (420, 460), (600, 760), (820, 560))):
            box(x + 10, fy / s - h, x + 190, fy / s, 6)
            for wy in range(int(fy / s - h + 50), int(fy / s - 60), 90):
                for wx in (x + 40, x + 110): box(wx, wy, wx + 40, wy + 50, 4)
    elif kind == 'park':
        for x, r in ((150, 130), (900, 160)):
            d.ellipse(((x - r) * s, fy - (330 + r) * s, (x + r) * s, fy - (330 - r) * s), outline=ln, width=lw)
            d.line([(x * s, fy - (330 - r) * s), (x * s, fy)], fill=ln, width=lw)
        box(400, fy / s - 90, 680, fy / s - 60, 8)
    d.rectangle((0, fy, W, H), fill=_mix(bot, 0.06) + (255,))
    d.line([(0, fy), (W, fy)], fill=ln, width=lw)
    return im

def floor_y(H): return int(H * FLOOR)

# ---------------------------------------------------------------- 図解アイコン（線画・白）
def icon(kind, size=260, col=WHITE, accent=CORAL):
    p = Pen(size, size); c = size / 2; L = max(8, size // 22)
    if kind == 'brain':
        pk, dk = (255, 168, 178), (214, 104, 124)
        for (x, y, r) in ((c - 52, c - 40, 50), (c - 8, c - 62, 52), (c + 46, c - 44, 50), (c - 64, c + 12, 46), (c + 60, c + 10, 48), (c - 20, c + 30, 52), (c + 26, c + 26, 50)):
            p.ellipse((x - r, y - r, x + r, y + r), pk, line=None)
        p.rrect((c - 14, c + 50, c + 22, c + 104), 14, pk, line=None)
        p.line([(c + 2, c - 100), (c + 2, c + 60)], fill=dk, lw=L - 2)
        for (x, y, a0, a1) in ((c - 60, c - 40, 200, 340), (c - 50, c + 20, 0, 160), (c + 50, c - 40, 200, 340), (c + 54, c + 18, 20, 170)):
            p.arc((x - 30, y - 22, x + 30, y + 22), a0, a1, fill=dk, lw=L - 2)
    elif kind == 'bulb':
        p.ellipse((c - 70, c - 100, c + 70, c + 40), fill=None, line=col, lw=L)
        p.rrect((c - 36, c + 46, c + 36, c + 100), 10, None, line=col, lw=L)
        for a in (-150, -120, -90, -60, -30):
            r = math.radians(a); p.line([(c + 92 * math.cos(r), c - 30 + 92 * math.sin(r)), (c + 120 * math.cos(r), c - 30 + 120 * math.sin(r))], fill=accent, lw=L)
    elif kind == 'warn':
        p.poly([(c, c - 100), (c + 110, c + 90), (c - 110, c + 90)], fill=None, line=col, lw=L)
        p.line([(c, c - 30), (c, c + 30)], fill=accent, lw=L + 4); p.ellipse((c - 9, c + 52, c + 9, c + 70), accent, line=None)
    elif kind == 'check':
        p.ellipse((c - 100, c - 100, c + 100, c + 100), fill=None, line=col, lw=L)
        p.line([(c - 50, c), (c - 12, c + 40), (c + 56, c - 40)], fill=accent, lw=L + 4)
    elif kind == 'clock':
        p.ellipse((c - 100, c - 100, c + 100, c + 100), fill=None, line=col, lw=L)
        p.line([(c, c), (c, c - 64)], fill=col, lw=L); p.line([(c, c), (c + 48, c + 20)], fill=accent, lw=L)
    elif kind == 'heart':
        p.arc((c - 96, c - 80, c + 4, c + 20), 140, 360, fill=col, lw=L); p.arc((c - 4, c - 80, c + 96, c + 20), 180, 40, fill=col, lw=L)
        p.line([(c - 88, c - 6), (c, c + 90), (c + 88, c - 6)], fill=col, lw=L)
    elif kind == 'coin':
        p.ellipse((c - 100, c - 100, c + 100, c + 100), fill=None, line=col, lw=L)
        p.ellipse((c - 70, c - 70, c + 70, c + 70), fill=None, line=accent, lw=L // 2 + 2)
        f = font(int(size * 0.34)); p.d.text(((c - size * 0.1) * 2, (c - size * 0.22) * 2), '¥', font=font(int(size * 0.68)), fill=col)
    elif kind == 'people':
        for dx, r in ((-60, 34), (60, 34), (0, 42)):
            p.ellipse((c + dx - r, c - 70 - r, c + dx + r, c - 70 + r), fill=None, line=col if dx else accent, lw=L)
            p.arc((c + dx - r * 1.8, c - 20, c + dx + r * 1.8, c + 120), 180, 360, fill=col if dx else accent, lw=L)
    elif kind == 'memo':
        p.rrect((c - 80, c - 100, c + 80, c + 100), 14, None, line=col, lw=L)
        for i in range(4): p.line([(c - 50, c - 54 + i * 40), (c + 50 if i < 3 else c + 10, c - 54 + i * 40)], fill=col if i < 3 else accent, lw=L)
    elif kind == 'chat':
        p.rrect((c - 110, c - 80, c + 110, c + 50), 40, None, line=col, lw=L)
        p.line([(c - 50, c + 50), (c - 70, c + 100), (c - 10, c + 50)], fill=col, lw=L)
        for i in (-1, 0, 1): p.ellipse((c + i * 50 - 12, c - 27, c + i * 50 + 12, c - 3), accent, line=None)
    elif kind == 'repeat':
        p.arc((c - 90, c - 90, c + 90, c + 90), 200, 470, fill=col, lw=L)
        p.poly([(c - 100, c - 10), (c - 60, c - 10), (c - 84, c - 46)], fill=accent, line=None)
    elif kind == 'search':
        p.ellipse((c - 90, c - 90, c + 40, c + 40), fill=None, line=col, lw=L)
        p.line([(c + 30, c + 30), (c + 100, c + 100)], fill=accent, lw=L + 6)
    elif kind == 'phone':
        p.rrect((c - 60, c - 110, c + 60, c + 110), 20, None, line=col, lw=L)
        p.ellipse((c - 9, c + 76, c + 9, c + 94), accent, line=None)
    elif kind == 'calendar':
        p.rrect((c - 100, c - 80, c + 100, c + 100), 16, None, line=col, lw=L)
        p.line([(c - 100, c - 30), (c + 100, c - 30)], fill=col, lw=L)
        for x in (-50, 50): p.line([(c + x, c - 110), (c + x, c - 60)], fill=col, lw=L)
        p.ellipse((c + 10, c + 10, c + 60, c + 60), accent, line=None)
    return p.done(sticker=False)
