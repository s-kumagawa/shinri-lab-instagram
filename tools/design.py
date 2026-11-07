"""しんりラボ 共通デザイン部品"""
from PIL import Image, ImageDraw, ImageFont

FB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FR = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

CREAM = (246, 241, 233)
NAVY = (30, 42, 68)
CORAL = (255, 107, 74)
GRAY = (107, 114, 128)
WHITE = (255, 255, 255)
SOFT = (234, 226, 214)

HANDLE = '@shinri.lab.jp'
BRAND = 'しんりラボ'

def font(size, bold=True):
    return ImageFont.truetype(FB if bold else FR, size, index=0)

NO_START = set('、。，．・ー〜」』）！？!?ぁぃぅぇぉっゃゅょァィゥェォッャュョ…')

def wrap(draw, text, fnt, max_w):
    """日本語を文字単位で折り返す（簡易禁則つき）。\nは強制改行。"""
    lines = []
    for para in text.split('\n'):
        cur = ''
        for ch in para:
            if draw.textlength(cur + ch, font=fnt) <= max_w or not cur:
                cur += ch
            elif ch in NO_START:
                cur += ch  # 行頭禁則：ぶら下げ
            else:
                lines.append(cur); cur = ch
        lines.append(cur)
    return lines

def text_block(draw, xy, text, size, fill, max_w, bold=True, lh=1.5, anchor_center=False, W=None):
    fnt = font(size, bold)
    x, y = xy
    for line in wrap(draw, text, fnt, max_w):
        if anchor_center:
            w = draw.textlength(line, font=fnt)
            draw.text(((W - w) / 2, y), line, font=fnt, fill=fill)
        else:
            draw.text((x, y), line, font=fnt, fill=fill)
        y += int(size * lh)
    return y

def fit_size(draw, text, max_w, start, bold=True, min_size=40):
    """強制改行された各行が max_w に収まる最大サイズ"""
    s = start
    while s > min_size:
        f = font(s, bold)
        if all(draw.textlength(l, font=f) <= max_w for l in text.split('\n')):
            return s
        s -= 4
    return s

def highlight(draw, box, color=CORAL, r=14):
    draw.rounded_rectangle(box, radius=r, fill=color)

def footer(draw, W, H, page=None, total=None, dark=False):
    c = CREAM if dark else GRAY
    f = font(30, True)
    draw.text((80, H - 90), f'{BRAND}  {HANDLE}', font=f, fill=c)
    if page:
        s = f'{page}/{total}'
        draw.text((W - 80 - draw.textlength(s, font=f), H - 90), s, font=f, fill=c)
