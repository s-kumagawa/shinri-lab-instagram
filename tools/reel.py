"""汎用リール生成 (1080x1920, 30fps)。reel(spec_content, out_mp4, tmpdir)
content = {"ref": "出典", "scenes": [
  {"kind":"hook","dur":2.6,"pre":"小見出し","main":"大きい一言"},
  {"kind":"text","dur":3.6,"text":"本文\\n改行可"},
  {"kind":"bars","dur":5.8,"title":"問い","rows":[{"label":"予想","value":"約半数","p":0.5},{"label":"実際","value":"約2割","p":0.23,"accent":true}]},
  {"kind":"badge","dur":3.6,"text":"本文","badge":"用語名"},
  {"kind":"end","dur":3.4,"text":"保存を促す一言"} ]}
テキストは安全領域（上300px〜下1500px、横900px）に収まるよう自動縮小。"""
import os, sys, math, subprocess, shutil
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from design import *
from music import make_bgm
import zlib

W, H, FPS = 1080, 1920, 30
MAXW = 900

def ease(t):
    t = max(0, min(1, t)); return 1 - (1 - t) ** 3

def fit(dr, text, size, bold=True):
    while size > 36 and any(dr.textlength(l, font=font(size, bold)) > MAXW for l in text.split('\n')):
        size -= 4
    return size

def centered(dr, text, size, y, fill, alpha=255, bold=True, lh=1.4, dy=0):
    size = fit(dr, text, size, bold); f = font(size, bold)
    for line in text.split('\n'):
        w = dr.textlength(line, font=f)
        dr.text(((W - w) / 2, y + dy), line, font=f, fill=fill + (alpha,))
        y += int(size * lh)
    return y

def reel(content, out, tmp):
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    scenes, t = [], 0.0
    for s in content['scenes']:
        scenes.append((t, t + s['dur'], s)); t += s['dur']
    DUR = t

    def frame(t):
        im = Image.new('RGB', (W, H), NAVY); dr = ImageDraw.Draw(im, 'RGBA')
        cx = W / 2 + 260 * math.sin(t * 0.7); cy = 760 + 180 * math.cos(t * 0.5)
        for r, a in [(620, 16), (460, 20), (300, 24)]:
            dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 240, 220, a))
        dr.rectangle((0, 0, W, 10), fill=(255, 255, 255, 40))
        dr.rectangle((0, 0, int(W * t / DUR), 10), fill=CORAL)
        for s0, s1, s in scenes:
            if not (s0 <= t < s1 or (s is scenes[-1][2] and t >= s0)): continue
            lt = t - s0; k = ease(lt / 0.35); a = int(255 * k); dy = int(60 * (1 - k))
            k2 = ease((lt - 0.6) / 0.35); a2 = int(255 * k2)
            kind = s['kind']
            if kind == 'hook':
                y = centered(dr, s.get('pre', ''), 84, 520, CREAM, a, dy=dy)
                if k2 > 0: centered(dr, s['main'], 130, y + 40, CORAL, a2, lh=1.3)
            elif kind == 'text':
                n = s['text'].count('\n') + 1
                centered(dr, s['text'], 78, 900 - n * 55, CREAM, a, dy=dy, lh=1.5)
            elif kind == 'badge':
                y = centered(dr, s['text'], 80, 600, CREAM, a, dy=dy, lh=1.45)
                if k2 > 0:
                    sz = fit(dr, s['badge'], 76); f = font(sz); w = dr.textlength(s['badge'], font=f)
                    dr.rounded_rectangle(((W - w) / 2 - 40, y + 70, (W + w) / 2 + 40, y + 70 + sz + 54), radius=30, fill=CORAL + (a2,))
                    dr.text(((W - w) / 2, y + 88), s['badge'], font=f, fill=WHITE + (a2,))
            elif kind == 'bars':
                centered(dr, s['title'], 80, 300, CREAM, a, dy=dy)
                rows = s['rows']; base, top = 1440, 760
                pmax = max(r['p'] for r in rows); n = len(rows)
                bw = 300 if n == 2 else 230; gap = (W - n * bw) / (n + 1)
                for i, r in enumerate(rows):
                    st = 0.4 + i * 2.0 * (2 / n)
                    if lt < st - 0.2: continue
                    kk = ease((lt - st) / 1.0)
                    col = CORAL if r.get('accent') else SOFT
                    x0 = gap + i * (bw + gap); hh = (base - top) * (r['p'] / pmax) * kk
                    dr.rounded_rectangle((x0, base - hh, x0 + bw, base), radius=24, fill=col + (255,))
                    f = font(52 if n == 2 else 44); w = dr.textlength(r['label'], font=f)
                    dr.text((x0 + (bw - w) / 2, base + 30), r['label'], font=f, fill=CREAM)
                    f = font(84 if n == 2 else 68); w = dr.textlength(r['value'], font=f)
                    dr.text((x0 + (bw - w) / 2, base - hh - 120), r['value'], font=f, fill=(CORAL if r.get('accent') else CREAM) + (int(255 * kk),))
            elif kind == 'end':
                centered(dr, s['text'], 74, 600, CREAM, a, dy=dy, lh=1.45)
                centered(dr, s.get('sub', 'フォローで毎日1つ\n根拠のある心理学'), 56, 960, SOFT, a2, bold=False, lh=1.5)
                centered(dr, HANDLE, 72, 1170, CORAL, a2)
        if content.get('ref'):
            dr.text((80, 1600), '出典: ' + content['ref'], font=font(28, False), fill=GRAY)
        return im

    n = int(DUR * FPS)
    for i in range(n):
        frame(i / FPS).save(f'{tmp}/{i:04d}.png')
    wav = f'{tmp}/bgm.wav'
    make_bgm(DUR, wav, seed=zlib.crc32(out.encode()), hits=[s0 for s0, _, _ in scenes[1:]])
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/%04d.png',
                    '-i', wav, '-shortest',
                    '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', '20',
                    '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '128k', out], check=True)
    cover = out.replace('.mp4', '_cover.jpg')
    frame(1.2).convert('RGB').save(cover, quality=92)
    # 確認用の縮小コンタクトシート
    picks = [int(FPS * ((s1 - 0.3) if s['kind'] == 'bars' else (s0 + min(1.6, (s1 - s0) * 0.8)))) for s0, s1, s in scenes]
    sheet = Image.new('RGB', (len(picks) * 270, 480), (0, 0, 0))
    for j, p in enumerate(picks):
        sheet.paste(Image.open(f'{tmp}/{min(p, n-1):04d}.png').resize((270, 480)), (j * 270, 0))
    sheet.save(out.replace('.mp4', '_preview.jpg'), quality=85)
    shutil.rmtree(tmp, ignore_errors=True)
    return DUR
