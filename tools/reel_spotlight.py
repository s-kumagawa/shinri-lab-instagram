"""リール: スポットライト効果 (1080x1920, 30fps)"""
import os, sys, math, subprocess, shutil
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from design import *

W, H, FPS = 1080, 1920, 30
OUT = sys.argv[1]
TMP = sys.argv[2]
shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)

# (開始秒, 終了秒, 種類, データ)
SCENES = [
    (0.0, 2.6, 'hook', ('あなたの失敗、', '実は誰も\n覚えていない')),
    (2.6, 6.2, 'text', 'ある実験で\n学生に「恥ずかしい\nTシャツ」を着せて\n教室に入ってもらった'),
    (6.2, 12.0, 'bars', None),
    (12.0, 15.6, 'text2', ('人は自分が思うほど\n他人に見られていない', 'スポットライト効果')),
    (15.6, 19.0, 'end', None),
]
DUR = SCENES[-1][1]

def ease(t):
    t = max(0, min(1, t)); return 1 - (1 - t) ** 3

def bg(t):
    im = Image.new('RGB', (W, H), NAVY); dr = ImageDraw.Draw(im, 'RGBA')
    # ゆっくり動く光（スポットライト）
    cx = W / 2 + 260 * math.sin(t * 0.7); cy = 760 + 180 * math.cos(t * 0.5)
    for r, a in [(620, 18), (460, 22), (300, 26)]:
        dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 240, 220, a))
    # 進行バー
    dr.rectangle((0, 0, W, 10), fill=(255, 255, 255, 40))
    dr.rectangle((0, 0, int(W * t / DUR), 10), fill=CORAL)
    return im, dr

def centered(dr, text, size, y, fill, alpha=255, bold=True, lh=1.35, dy=0):
    f = font(size, bold)
    col = fill + (alpha,)
    for line in text.split('\n'):
        w = dr.textlength(line, font=f)
        dr.text(((W - w) / 2, y + dy), line, font=f, fill=col)
        y += int(size * lh)
    return y

def frame(t):
    im, dr = bg(t)
    for s, e, kind, data in SCENES:
        if not (s <= t < e or (kind == 'end' and t >= s)):
            continue
        lt = t - s; k = ease(lt / 0.35); a = int(255 * k); dy = int(60 * (1 - k))
        if kind == 'hook':
            centered(dr, data[0], 84, 560, CREAM, a, dy=dy)
            k2 = ease((lt - 0.5) / 0.35)
            if k2 > 0:
                sz = int(130 * (0.85 + 0.15 * k2))
                centered(dr, data[1], sz, 720, CORAL, int(255 * k2), lh=1.3)
        elif kind == 'text':
            centered(dr, data, 78, 560, CREAM, a, dy=dy, lh=1.5)
        elif kind == 'text2':
            y = centered(dr, data[0], 80, 600, CREAM, a, dy=dy, lh=1.45)
            k2 = ease((lt - 0.9) / 0.35)
            if k2 > 0:
                f = font(76); w = dr.textlength(data[1], font=f)
                dr.rounded_rectangle(((W - w) / 2 - 40, y + 70, (W + w) / 2 + 40, y + 200), radius=30, fill=CORAL + (int(255 * k2),))
                dr.text(((W - w) / 2, y + 88), data[1], font=f, fill=WHITE + (int(255 * k2),))
        elif kind == 'bars':
            centered(dr, '何人が気づいた？', 80, 300, CREAM, a, dy=dy)
            base, top = 1440, 760
            rows = [('本人の予想', '約半数', 0.50, SOFT, 0.4), ('実際', '約2割', 0.23, CORAL, 2.4)]
            for i, (lab, val, p, col, st) in enumerate(rows):
                x0 = 190 + i * 400; x1 = x0 + 300
                kk = ease((lt - st) / 1.0)
                if lt < st - 0.2: continue
                hh = (base - top) * (p / 0.5) * kk
                dr.rounded_rectangle((x0, base - hh, x1, base), radius=24, fill=col + (255,))
                f = font(56); w = dr.textlength(lab, font=f)
                dr.text((x0 + (300 - w) / 2, base + 30), lab, font=f, fill=CREAM)
                f = font(84); w = dr.textlength(val, font=f)
                dr.text((x0 + (300 - w) / 2, base - hh - 120), val, font=f, fill=(col if i else CREAM) + (int(255 * kk),))
        elif kind == 'end':
            centered(dr, '気にしすぎちゃう人は\n保存して見返してね', 74, 600, CREAM, a, dy=dy, lh=1.45)
            k2 = ease((lt - 0.6) / 0.35)
            centered(dr, 'フォローで毎日1つ\n根拠のある心理学', 56, 960, SOFT, int(255 * k2), bold=False, lh=1.5)
            centered(dr, HANDLE, 72, 1170, CORAL, int(255 * k2))
    f = font(28, False)
    dr.text((80, 1600), '出典: Gilovich, Medvec & Savitsky (2000)', font=f, fill=GRAY)
    return im

n = int(DUR * FPS)
for i in range(n):
    frame(i / FPS).save(f'{TMP}/{i:04d}.png')
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{TMP}/%04d.png',
                '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-shortest',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-c:a', 'aac', OUT], check=True)
frame(0.9).save(OUT.replace('.mp4', '_cover.png'))
print('done', n, 'frames')
