"""「3秒心理クイズ」リール (1080x1920, 30fps)。quiz_reel(content, out_mp4, tmpdir)
content = {
  "no": 1,                                  # シリーズ番号（#01）
  "q": "第一印象は\n何秒で決まる？",          # 問題（大きく1〜2行）
  "choices": ["0.1秒", "3秒", "30秒"],       # 2〜3択
  "answer": 0,                              # 正解の番号
  "reveal": "顔を0.1秒見ただけの印象が\nじっくり見た印象と\nほぼ同じだった",  # 答えの根拠（3行まで）
  "term": "0.1秒の第一印象",                 # 用語バッジ
  "ref": "Willis & Todorov (2006) Psychological Science"
}
ブランド要素：黄色×黒の配色、シリーズ名「3秒心理クイズ」、キャラクター「ハカセ」、
決まった効果音（ポップ・カウントダウン・正解チャイム）。"""
import os, sys, math, random, subprocess, shutil, zlib, wave
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from design import font, HANDLE
from music import make_bgm

W, H, FPS = 1080, 1920, 30
YEL = (255, 214, 64)
YEL2 = (255, 200, 30)
INK = (24, 24, 32)
WHITE = (255, 255, 255)
CORAL = (255, 92, 64)
TEAL = (32, 178, 170)
DIM = (210, 186, 90)
CHOICE_COL = [(255, 92, 64), (64, 132, 255), (32, 178, 170)]
LETTERS = 'ABC'

# タイムライン（秒）
T_Q = 0.25       # 問題
T_CH = 1.6       # 選択肢
T_CD = 3.0       # カウントダウン開始（3秒）
T_DRUM = 6.0     # 「正解は…」
T_REV = 6.8      # 正解発表
T_EXP = 7.6      # 根拠
T_END = 12.4     # エンドカード
DUR = 14.0


def ease(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3


def back(t):  # 少し行き過ぎて戻る（ポップ）
    t = max(0.0, min(1.0, t)); c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def outlined(dr, xy, text, size, fill=INK, stroke=WHITE, sw=10, anchor='mm', alpha=255):
    dr.text(xy, text, font=font(size), fill=fill + (alpha,), stroke_width=sw,
            stroke_fill=stroke + (alpha,), anchor=anchor)


def fit(dr, lines, size, maxw, sw=10):
    while size > 40 and any(dr.textlength(l, font=font(size)) + sw * 2 > maxw for l in lines):
        size -= 4
    return size


def pop_layer(im, draw_fn, box, scale, alpha=255):
    """box 領域に draw_fn で描いた部品を、中心基準で scale 倍して貼る"""
    if scale <= 0.01 or alpha <= 0: return
    x0, y0, x1, y1 = box; w, h = x1 - x0, y1 - y0
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer, 'RGBA'), w, h)
    if abs(scale - 1) > 0.01:
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        layer = layer.resize((nw, nh), Image.BICUBIC)
    else:
        nw, nh = w, h
    if alpha < 255:
        a = layer.split()[3].point(lambda v: v * alpha // 255); layer.putalpha(a)
    im.alpha_composite(layer, (int(x0 + (w - nw) / 2), int(y0 + (h - nh) / 2)))


# ---------- キャラクター「ハカセ」 ----------
def hakase(dr, cx, cy, s, mood, t):
    """丸い頭＋大きな丸メガネ＋頭のフラスコ。mood: think / wow / happy"""
    bob = math.sin(t * 5) * 6 * s
    cy = cy + bob
    # フラスコ（アンテナ）
    dr.line((cx, cy - 150 * s, cx, cy - 200 * s), fill=INK, width=int(10 * s))
    fx, fy = cx, cy - 235 * s
    dr.polygon([(fx - 16 * s, fy - 30 * s), (fx + 16 * s, fy - 30 * s), (fx + 48 * s, fy + 34 * s), (fx - 48 * s, fy + 34 * s)],
               fill=WHITE, outline=INK, width=int(8 * s))
    dr.polygon([(fx - 34 * s, fy + 6 * s), (fx + 34 * s, fy + 6 * s), (fx + 46 * s, fy + 30 * s), (fx - 46 * s, fy + 30 * s)], fill=CORAL)
    for i in range(2):  # 泡
        by = fy - 50 * s - ((t * 60 + i * 30) % 60) * s
        dr.ellipse((fx - 8 * s + i * 14 * s, by - 8 * s, fx + 8 * s + i * 14 * s, by + 8 * s), outline=INK, width=int(4 * s))
    # 頭
    r = 170 * s
    dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=WHITE, outline=INK, width=int(12 * s))
    # ほっぺ
    for sx in (-1, 1):
        dr.ellipse((cx + sx * 110 * s - 26 * s, cy + 40 * s - 14 * s, cx + sx * 110 * s + 26 * s, cy + 40 * s + 14 * s), fill=(255, 170, 160))
    # メガネ
    for sx in (-1, 1):
        gx = cx + sx * 66 * s
        dr.ellipse((gx - 56 * s, cy - 50 * s - 56 * s, gx + 56 * s, cy - 50 * s + 56 * s), fill=(235, 245, 255), outline=INK, width=int(12 * s))
        # 目
        if mood == 'happy':
            dr.arc((gx - 22 * s, cy - 62 * s, gx + 22 * s, cy - 30 * s), 200, 340, fill=INK, width=int(9 * s))
        else:
            er = (17 if mood == 'wow' else 13) * s
            ox, oy = (0, -12 * s) if mood == 'think' else (0, 0)
            dr.ellipse((gx - er + ox, cy - 50 * s - er + oy, gx + er + ox, cy - 50 * s + er + oy), fill=INK)
    dr.line((cx - 12 * s, cy - 50 * s, cx + 12 * s, cy - 50 * s), fill=INK, width=int(10 * s))
    # 口
    if mood == 'wow':
        dr.ellipse((cx - 22 * s, cy + 50 * s, cx + 22 * s, cy + 100 * s), fill=INK)
    elif mood == 'happy':
        dr.chord((cx - 50 * s, cy + 20 * s, cx + 50 * s, cy + 100 * s), 0, 180, fill=INK)
    else:
        dr.arc((cx - 30 * s, cy + 50 * s, cx + 30 * s, cy + 80 * s), 200, 340, fill=INK, width=int(9 * s))


def bubble(dr, x, y, text, size, alpha=255):
    f = font(size); w = dr.textlength(text, font=f)
    dr.rounded_rectangle((x - w / 2 - 34, y - size / 2 - 26, x + w / 2 + 34, y + size / 2 + 26), radius=40,
                         fill=WHITE + (alpha,), outline=INK + (alpha,), width=8)
    dr.text((x, y), text, font=f, fill=INK + (alpha,), anchor='mm')


# ---------- 効果音 ----------
SR = 44100

def sfx_track(events, dur):
    n = int(SR * (dur + 0.5)); mix = np.zeros(n)
    def add(sig, at):
        i = int(at * SR); j = min(n, i + len(sig))
        if i < n: mix[i:j] += sig[:j - i]
    def tone(f0, f1, d, v, decay=12):
        t = np.arange(int(SR * d)) / SR
        f = np.linspace(f0, f1, len(t)); ph = 2 * np.pi * np.cumsum(f) / SR
        return v * np.sin(ph) * np.exp(-t * decay)
    rnd = np.random.RandomState(1)
    for kind, at in events:
        if kind == 'pop':
            add(tone(500, 1100, 0.12, 0.5, 25), at)
        elif kind == 'swish':
            d = 0.22; t = np.arange(int(SR * d)) / SR
            add(0.25 * rnd.randn(len(t)) * np.sin(np.pi * t / d) * np.linspace(0.2, 1, len(t)), at)
        elif kind == 'tick':
            add(tone(1600, 1600, 0.06, 0.45, 60), at)
        elif kind == 'drum':
            d = 0.75; t = np.arange(int(SR * d)) / SR
            roll = (np.sin(2 * np.pi * 22 * t) > 0) * rnd.randn(len(t)) * 0.18 * np.linspace(0.4, 1, len(t))
            add(roll, at)
        elif kind == 'chime':
            for k, f in enumerate([784, 988, 1175, 1568]):
                add(tone(f, f, 0.9, 0.32, 4), at + k * 0.07)
    return mix


def write_wav(path, x):
    x = np.clip(x, -1, 1); d = (x * 32767).astype(np.int16)
    st = np.repeat(d[:, None], 2, axis=1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())


def read_wav(path):
    with wave.open(path) as w:
        ch = w.getnchannels(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32767
    return x.reshape(-1, ch).mean(axis=1)


# ---------- 本体 ----------
def quiz_reel(c, out, tmp):
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    choices = c['choices']; ans = c['answer']; nC = len(choices)
    rnd = random.Random(zlib.crc32(c['q'].encode()))
    confetti = [(rnd.uniform(-1, 1), rnd.uniform(-1.4, -0.4), rnd.choice(CHOICE_COL + [WHITE, INK]), rnd.uniform(0, 6.28)) for _ in range(70)]
    qlines = c['q'].split('\n')
    ch_top = 650; Z = 1200; ch_h = 150 if nC == 3 else 180; ch_gap = 34

    def frame(t):
        im = Image.new('RGBA', (W, H), YEL + (255,)); dr = ImageDraw.Draw(im, 'RGBA')
        # 背景：流れる斜めストライプ
        off = (t * 60) % 160
        for x in range(-H, W + 160, 160):
            x0 = x + off
            dr.polygon([(x0, 0), (x0 + 60, 0), (x0 + 60 + H * 0.5, H), (x0 + H * 0.5, H)], fill=YEL2 + (255,))
        # 上部の帯：シリーズ名
        k = back((t - 0.0) / 0.35)
        def band(d, w, h):
            d.rounded_rectangle((0, 0, w, h), radius=h // 2, fill=INK)
            d.text((w / 2, h / 2), f"3秒心理クイズ  #{c.get('no', 1):02d}", font=font(54), fill=YEL, anchor='mm')
        pop_layer(im, band, (190, 120, 890, 220), k)
        # 進行バー
        dr.rectangle((0, 0, W, 14), fill=INK + (60,)); dr.rectangle((0, 0, int(W * min(1, t / DUR)), 14), fill=INK)

        if t < T_END:
            # 問題文
            qs = fit(dr, qlines, 112, 960, 12)
            k = back((t - T_Q) / 0.35)
            def qdraw(d, w, h):
                y = h / 2 - (len(qlines) - 1) * qs * 0.62
                for ln in qlines:
                    d.text((w / 2, y), ln, font=font(qs), fill=INK, stroke_width=12, stroke_fill=WHITE, anchor='mm'); y += qs * 1.24
            q_box = (0, 300, W, 600)
            pop_layer(im, qdraw, q_box, k)

            # 選択肢
            for i, ch in enumerate(choices):
                st = T_CH + i * 0.22
                if t < st: continue
                kk = ease((t - st) / 0.3); x_off = int((1 - kk) * (W if i % 2 == 0 else -W))
                y0 = ch_top + i * (ch_h + ch_gap)
                revealed = t >= T_REV; correct = i == ans
                col = CHOICE_COL[i]
                if revealed and not correct:
                    col = DIM
                scale = 1.0
                if revealed and correct:
                    scale = 1 + 0.06 * math.sin(min(1, (t - T_REV) / 0.3) * math.pi) + 0.04
                x0, x1 = 90 + x_off, 990 + x_off
                if scale != 1:
                    cxm, cym = (x0 + x1) / 2, y0 + ch_h / 2
                    x0, x1 = cxm - (x1 - x0) / 2 * scale, cxm + (x1 - x0) / 2 * scale
                    ya, yb = cym - ch_h / 2 * scale, cym + ch_h / 2 * scale
                else:
                    ya, yb = y0, y0 + ch_h
                dr.rounded_rectangle((x0 + 10, ya + 14, x1 + 10, yb + 14), radius=40, fill=INK)
                dr.rounded_rectangle((x0, ya, x1, yb), radius=40, fill=col + (255,), outline=INK, width=8)
                dr.ellipse((x0 + 26, (ya + yb) / 2 - 50, x0 + 126, (ya + yb) / 2 + 50), fill=WHITE, outline=INK, width=6)
                dr.text((x0 + 76, (ya + yb) / 2), LETTERS[i], font=font(64), fill=INK, anchor='mm')
                fs = fit(dr, [ch], 78 if nC == 3 else 88, x1 - x0 - 200, 0)
                dr.text((x0 + 160, (ya + yb) / 2), ch, font=font(fs), fill=WHITE if not (revealed and not correct) else (120, 105, 60),
                        anchor='lm')
                if revealed and correct:
                    kk2 = back((t - T_REV) / 0.3)
                    def tag(d, w, h):
                        d.rounded_rectangle((6, 6, w - 6, h - 6), radius=(h - 12) // 2, fill=WHITE, outline=INK, width=6)
                        d.text((w / 2, h / 2), '正解！', font=font(50), fill=CORAL, anchor='mm')
                    pop_layer(im, tag, (int(x1 - 250), int((ya + yb) / 2 - 50), int(x1 - 30), int((ya + yb) / 2 + 50)), kk2)

            ch_bottom = ch_top + nC * (ch_h + ch_gap)
            # カウントダウン
            if T_CD <= t < T_DRUM:
                left = 3 - int(t - T_CD); frac = (t - T_CD) % 1
                cx, cy, r = 780, Z + 150, 130
                dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=WHITE, outline=INK, width=10)
                dr.arc((cx - r + 18, cy - r + 18, cx + r - 18, cy + r - 18), -90, -90 + 360 * (1 - frac), fill=CORAL, width=26)
                s = 1 + 0.25 * (1 - ease(frac / 0.25))
                dr.text((cx, cy), str(left), font=font(int(130 * s)), fill=INK, anchor='mm')
                outlined(dr, (360, Z + 110), 'コメントで', 64, sw=8)
                outlined(dr, (360, Z + 195), '答えてね！', 64, sw=8)
            # 正解は…
            if T_DRUM <= t < T_REV:
                outlined(dr, (W / 2, Z + 150), '正解は…', 120, sw=12)
            # 根拠
            if t >= T_EXP:
                kk = ease((t - T_EXP) / 0.35)
                ty = Z
                term = c.get('term', '')
                if term:
                    f = font(60); tw = dr.textlength(term, font=f)
                    dr.rounded_rectangle((W / 2 - tw / 2 - 36, ty + (1 - kk) * 40, W / 2 + tw / 2 + 36, ty + 100 + (1 - kk) * 40), radius=50,
                                         fill=INK + (int(255 * kk),))
                    dr.text((W / 2, ty + 50 + (1 - kk) * 40), term, font=f, fill=YEL + (int(255 * kk),), anchor='mm')
                lines = c['reveal'].split('\n'); fs = fit(dr, lines, 54, 940, 0)
                y = ty + 150
                for ln in lines:
                    dr.text((W / 2, y + (1 - kk) * 40), ln, font=font(fs), fill=INK + (int(255 * kk),), anchor='mm'); y += fs * 1.35
            # 紙吹雪
            if T_REV <= t < T_REV + 2.0:
                lt = t - T_REV
                for vx, vy, col, ph in confetti[:40]:
                    x = W / 2 + vx * 600 * (1 + lt); y = -60 + (ph * 60) + 1100 * lt * (0.8 + abs(vy) * 0.4)
                    a = abs(math.sin(ph + lt * 9))
                    dr.rounded_rectangle((x - 22, y - 12 * a - 4, x + 22, y + 12 * a + 4), radius=4, fill=col)
            # ハカセ（左下）
            mood = 'think' if t < T_REV else ('wow' if t < T_REV + 1.2 else 'happy')
            if t < T_DRUM or t >= T_REV:
                hx, hy = 175, 1660
                hakase(dr, hx, hy, 0.62, mood, t)
                if t < T_REV and t >= T_CH:
                    bubble(dr, 470, 1540, 'どれだと思う？', 48)
                elif t >= T_REV and t < T_EXP:
                    bubble(dr, 420, 1540, 'へぇ〜！', 52)
        else:
            # エンドカード
            lt = t - T_END
            k = back(lt / 0.35)
            hakase(dr, W / 2, 860, 1.25 * max(0.01, k), 'happy', t)
            outlined(dr, (W / 2, 1210), '毎日1問、心理クイズ', 76, sw=10)
            outlined(dr, (W / 2, 1320), 'フォローして挑戦しよう', 76, sw=10)
            dr.rounded_rectangle((W / 2 - 330, 1420, W / 2 + 330, 1530), radius=55, fill=INK)
            dr.text((W / 2, 1475), HANDLE, font=font(60), fill=YEL, anchor='mm')
        if c.get('ref'):
            dr.text((W / 2, 268), '出典: ' + c['ref'], font=font(28, False), fill=INK + (170,), anchor='mm')
        return im.convert('RGB')

    n = int(DUR * FPS)
    for i in range(n):
        frame(i / FPS).save(f'{tmp}/{i:04d}.png')
    # 音：BGM（小さめ）＋効果音
    bgm = f'{tmp}/bgm.wav'; make_bgm(DUR, bgm, seed=zlib.crc32(out.encode()))
    b = read_wav(bgm) * 0.45
    ev = [('pop', 0.0), ('pop', T_Q)] + [('swish', T_CH + i * 0.22) for i in range(nC)] + \
         [('tick', T_CD + i) for i in range(3)] + [('drum', T_DRUM), ('chime', T_REV), ('pop', T_END)]
    s = sfx_track(ev, DUR); m = min(len(b), len(s)); mix = b[:m] + s[:m]
    wav = f'{tmp}/mix.wav'; write_wav(wav, mix / max(1.0, np.abs(mix).max() / 0.95))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', f'{tmp}/%04d.png', '-i', wav, '-shortest',
                    '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', '20',
                    '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '160k', out], check=True)
    frame(T_CH + 1.0).save(out.replace('.mp4', '_cover.jpg'), quality=92)
    picks = [0.5, T_CH + 0.9, T_CD + 0.5, T_DRUM + 0.3, T_REV + 0.6, T_EXP + 1.5, T_END + 0.8]
    sheet = Image.new('RGB', (len(picks) * 270, 480))
    for j, p in enumerate(picks):
        sheet.paste(Image.open(f'{tmp}/{min(int(p * FPS), n - 1):04d}.png').resize((270, 480)), (j * 270, 0))
    sheet.save(out.replace('.mp4', '_preview.jpg'), quality=85)
    shutil.rmtree(tmp, ignore_errors=True)
    return DUR


if __name__ == '__main__':
    import json
    c = json.load(open(sys.argv[1]))
    quiz_reel(c, sys.argv[2], sys.argv[2] + '_tmp')
