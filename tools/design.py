"""しんりラボ 共通デザイン部品（色・フォント・文字組み）"""
import os
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FR = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
FBK = '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'
FMARU = os.path.join(ROOT, 'assets', 'fonts', 'MTLmr3m.ttf')  # 丸ゴシック（吹き出し用・Apache 2.0）

# ブランドの色（ネイビー×コーラル）＋ 物語用のやわらかい色
CREAM = (250, 245, 236)
NAVY = (30, 42, 68)
INK = (38, 44, 64)          # 線画の色
CORAL = (255, 107, 74)
YELLOW = (255, 206, 84)
MINT = (120, 210, 190)
SKY = (152, 200, 240)
PINK = (255, 170, 170)
GRAY = (107, 114, 128)
WHITE = (255, 255, 255)
SOFT = (234, 226, 214)

HANDLE = '@shinri.lab.jp'
BRAND = 'しんりラボ'

@lru_cache(maxsize=256)
def font(size, bold=True, black=False, maru=False):
    if maru:
        return ImageFont.truetype(FMARU, int(size))
    if black and os.path.exists(FBK):
        return ImageFont.truetype(FBK, int(size), index=0)
    return ImageFont.truetype(FB if bold else FR, int(size), index=0)

NO_START = set('、。，．・ー〜」』）！？!?ぁぃぅぇぉっゃゅょァィゥェォッャュョ…')

def wrap(draw, text, fnt, max_w):
    """日本語を文字単位で折り返す（簡易禁則つき）。\\nは強制改行。"""
    lines = []
    for para in text.split('\n'):
        cur = ''
        for ch in para:
            if draw.textlength(cur + ch, font=fnt) <= max_w or not cur:
                cur += ch
            elif ch in NO_START:
                cur += ch
            else:
                lines.append(cur); cur = ch
        lines.append(cur)
    return lines

def text_block(draw, xy, text, size, fill, max_w, bold=True, lh=1.5, anchor_center=False, W=None, **fk):
    fnt = font(size, bold, **fk)
    x, y = xy
    for line in wrap(draw, text, fnt, max_w):
        if anchor_center:
            w = draw.textlength(line, font=fnt)
            draw.text(((W - w) / 2, y), line, font=fnt, fill=fill)
        else:
            draw.text((x, y), line, font=fnt, fill=fill)
        y += int(size * lh)
    return y

def fit_size(draw, text, max_w, start, bold=True, min_size=36, **fk):
    """強制改行された各行が max_w に収まる最大サイズ"""
    s = start
    while s > min_size:
        f = font(s, bold, **fk)
        if all(draw.textlength(l, font=f) <= max_w for l in text.split('\n')):
            return s
        s -= 4
    return s

def outlined(draw, xy, text, size, fill, stroke=WHITE, sw=None, center_w=None, lh=1.22,
             accent=None, accent_fill=CORAL, shadow=True, **fk):
    """太い縁取り＋影つきの見出し（テロップ・サムネ用）。
    accent: 強調したい語（その語だけ accent_fill で塗る）。center_w を渡すと中央ぞろえ。戻り値は最終行の下端y"""
    f = font(size, black=True, **fk)
    sw = sw if sw is not None else max(6, size // 9)
    x0, y = xy
    for line in text.split('\n'):
        w = draw.textlength(line, font=f)
        x = (center_w - w) / 2 if center_w else x0
        if shadow:
            draw.text((x + size * 0.06, y + size * 0.08), line, font=f, fill=(0, 0, 0, 70),
                      stroke_width=sw, stroke_fill=(0, 0, 0, 70))
        draw.text((x, y), line, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)
        if accent and accent in line:
            i = line.index(accent)
            ax = x + draw.textlength(line[:i], font=f)
            draw.text((ax, y), accent, font=f, fill=accent_fill, stroke_width=sw, stroke_fill=stroke)
        y += int(size * lh)
    return y

def highlight(draw, box, color=CORAL, r=14):
    draw.rounded_rectangle(box, radius=r, fill=color)

def pill(draw, xy, text, size, bg=CORAL, fg=WHITE, pad=(28, 12), center_w=None):
    f = font(size)
    w = draw.textlength(text, font=f)
    x, y = xy
    if center_w: x = (center_w - w) / 2 - pad[0]
    draw.rounded_rectangle((x, y, x + w + pad[0] * 2, y + size + pad[1] * 2 + 6), radius=(size + pad[1] * 2) // 2, fill=bg)
    draw.text((x + pad[0], y + pad[1] - size * 0.12), text, font=f, fill=fg)
    return x + w + pad[0] * 2, y + size + pad[1] * 2 + 6

def footer(draw, W, H, page=None, total=None, dark=False):
    c = CREAM if dark else GRAY
    f = font(30, True)
    draw.text((70, H - 80), f'{BRAND}  {HANDLE}', font=f, fill=c)
    if page:
        s = f'{page}/{total}'
        draw.text((W - 70 - draw.textlength(s, font=f), H - 80), s, font=f, fill=c)
