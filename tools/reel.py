"""ストーリー型リール生成 (1080x1920, 30fps, ナレーションつき)。reel(content, out_mp4, tmpdir) -> 秒数

content = {
 "ref": "出典（短く）",
 "thumb": {"title": "サムネの大見出し\\n改行で3行まで", "accent": "強調語", "who": "mina", "expr": "shock",
           "bg": "pop", "tag": "用語や分類", "icon": "!"},
 "scenes": [ 場面, ... ]   # 6〜9場面、合計20〜35秒
}
場面の共通項目
  kind   : story（既定）/ explain / chart / end
  bg     : room / office / cafe / night / shop / street / lab / pop / pop2 / board
  telop  : 画面上部の大きな見出し（縁取り文字）。1場面目は必ず入れる＝フック
  accent : telop の中で色を変える語
  caption: 上部の小さなナレーション枠（例「ある日のミナ」）
  lines  : [{"who": "mina|sota|sensei|narr", "text": "画面の文字", "say": "読み上げ用（任意・読み違い対策）",
             "expr": "表情（任意）", "style": "say|think|shout"}]  → 順番に音声で読み上げ、吹き出しを出す
           who が narr、または画面にいない人物のセリフは上部のナレーション枠で出す
  dur    : 最低の長さ（任意。音声の長さに合わせて自動で延びる）
story   : cast [{"who":"mina","expr":"normal","x":0.5,"flip":false}], fx "lines"（集中線）/"shake", icon {"on":"mina","kind":"!|?|idea|sparkle|heart|gloom|..."}
explain : term（用語のバッジ）, text（カードの本文）, expr（先生の表情）
chart   : title, rows [{"label":"予想","value":"約半数","p":0.5,"accent":true}]
end     : text（大きい呼びかけ）, sub（小さい一言）
"""
import os, sys, math, subprocess, shutil, zlib, wave
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from design import *
import art, voice
from music import make_bgm

W, H, FPS = 1080, 1920, 30
SR = voice.SR
LEAD, GAP, TAIL = 0.3, 0.2, 0.55

def ease(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3

def back(t):
    t = max(0.0, min(1.0, t)); c = 1.7
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2

def paste_scaled(base, im, cx, cy, s, alpha=1.0):
    if s <= 0.02 or alpha <= 0.02: return
    if abs(s - 1) > 0.01:
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
    if alpha < 0.99:
        im = im.copy(); im.putalpha(im.split()[3].point(lambda v: int(v * alpha)))
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))

# ------------------------------------------------------------ タイムライン（音声）
def plan(content, cache):
    use_voice = voice.available()
    timeline, t = [], 0.0
    for idx, s in enumerate(content['scenes']):
        kind = s.get('kind', 'story')
        lines, lt = [], (0.15 if idx == 0 else LEAD)
        for ln in s.get('lines', []):
            who = ln.get('who', 'narr')
            expr = ln.get('expr') or next((c.get('expr', 'normal') for c in s.get('cast', []) if c['who'] == who), 'normal')
            if use_voice:
                audio = voice.speak(ln.get('say', ln['text']), who, expr, cache_dir=cache)
                d = len(audio) / SR
            else:
                audio, d = None, 0.5 + 0.12 * len(ln['text'])
            lines.append({**ln, 'who': who, 'expr': expr, 't0': lt, 't1': lt + d, 'audio': audio,
                          'env': voice.envelope(audio, FPS) if audio is not None else None})
            lt += d + GAP
        dur = max(s.get('dur', 0), lt - GAP + TAIL, 2.0)
        timeline.append({'spec': s, 'kind': kind, 'start': t, 'dur': dur, 'lines': lines})
        t += dur
    return timeline, t

# ------------------------------------------------------------ 描画
class Renderer:
    def __init__(self, content, timeline, total):
        self.c, self.tl, self.total = content, timeline, total
        self.bub_cache, self.box_cache = {}, {}
        self.bgs = {}
        self.card_bottom = 0

    def bg(self, kind):
        if kind not in self.bgs:
            self.bgs[kind] = art.background(kind, int(W * 1.08), int(H * 1.08)).convert('RGBA')
        return self.bgs[kind]

    def bubble(self, ln, tail_x, max_w=780, size=58):
        key = (ln['text'], ln.get('style', 'say'), round(tail_x, 2), max_w, size)
        if key not in self.bub_cache:
            self.bub_cache[key] = art.bubble(ln['text'], size, max_w, ln.get('style', 'say'), tail_x=tail_x)
        return self.bub_cache[key]

    def capbox(self, text, label=None, size=50, bg=NAVY):
        key = (text, label, size, bg)
        if key not in self.box_cache:
            self.box_cache[key] = art.caption_box(text, size, 860, bg=bg, label=label)
        return self.box_cache[key]

    def talk_level(self, sc, who, lt):
        for ln in sc['lines']:
            if ln['who'] == who and ln['t0'] <= lt < ln['t1']:
                if ln['env'] is None: return int(2 * (0.5 + 0.5 * math.sin(lt * 18)) + 0.5)
                i = int((lt - ln['t0']) * FPS)
                return int(ln['env'][min(i, len(ln['env']) - 1)])
        return 0

    def expr_of(self, sc, who, base, lt):
        e = base
        for ln in sc['lines']:
            if ln['who'] == who and ln.get('expr') and lt >= ln['t0']: e = ln['expr']
        return e

    def active_lines(self, sc, lt):
        """表示中のセリフ（最新2つまで）"""
        shown = [ln for ln in sc['lines'] if lt >= ln['t0']]
        return shown[-2:]

    def frame(self, t):
        sc = next((s for s in self.tl if s['start'] <= t < s['start'] + s['dur']), self.tl[-1])
        i_sc = self.tl.index(sc)
        lt = t - sc['start']; sp = sc['spec']; kind = sc['kind']
        # 背景（ゆっくりパン）
        bgk = sp.get('bg', {'explain': 'lab', 'chart': 'board', 'end': 'pop'}.get(kind, 'room'))
        b = self.bg(bgk); pr = lt / sc['dur']
        ox = int((b.width - W) * (0.5 + 0.4 * (pr - 0.5))); oy = int((b.height - H) * (0.3 + 0.4 * pr))
        sh = (0, 0)
        if sp.get('fx') == 'shake' and lt < 0.45:
            sh = (int(14 * math.sin(lt * 70)), int(8 * math.cos(lt * 55)))
        im = b.crop((ox + sh[0] + 20, oy + sh[1] + 20, ox + sh[0] + 20 + W, oy + sh[1] + 20 + H)).copy()
        if sp.get('fx') == 'lines':
            im.alpha_composite(art.speedlines(W, H, W / 2, 1100, seed=i_sc))
        blink = (t % 3.2) < 0.12
        heads = {}
        if kind == 'story':
            cast = sp.get('cast', [])
            n = len(cast)
            hh = 940 if n == 1 else 800
            prev = self.tl[i_sc - 1]['spec'].get('cast', []) if i_sc > 0 else []
            for j, c in enumerate(cast):
                who = c['who']; x = c.get('x', 0.5 if n == 1 else (0.28 if j == 0 else 0.72))
                e = self.expr_of(sc, who, c.get('expr', 'normal'), lt)
                talk = self.talk_level(sc, who, lt)
                spr = art.sprite(who, e, blink and e not in ('happy',), talk, h=hh, flip=c.get('flip', False))
                same = any(p['who'] == who for p in prev)
                k = 1.0 if (same or i_sc == 0) else ease(lt / 0.35)
                bob = 7 * math.sin(2 * math.pi * 0.7 * t + j * 1.7)
                y_top = (920 if n == 1 else 1010) + int((1 - k) * 400) + bob
                xx = int(W * x - spr.width / 2)
                im.alpha_composite(spr, (xx, int(y_top)))
                heads[who] = (W * x, y_top + hh * 0.17)
            icon = sp.get('icon')
            if icon and icon.get('on') in heads:
                hx, hy = heads[icon['on']]
                kk = back((lt - 0.25) / 0.3)
                paste_scaled(im, art.icon_fx(icon['kind'], 150), hx + 210, hy - 10, kk)
        elif kind == 'explain':
            e = self.expr_of(sc, 'sensei', sp.get('expr', 'normal'), lt)
            spr = art.sprite('sensei', e, blink, self.talk_level(sc, 'sensei', lt), h=720)
            k = 1.0 if (i_sc > 0 and self.tl[i_sc - 1]['kind'] == 'explain') else ease(lt / 0.35)
            y_top = 1180 + int((1 - k) * 300) + 6 * math.sin(t * 4.4)
            im.alpha_composite(spr, (int(W * 0.5 - spr.width / 2), int(y_top)))
            heads['sensei'] = (W * 0.5, y_top + 140)
        elif kind == 'chart':
            spr = art.sprite('sensei', self.expr_of(sc, 'sensei', 'normal', lt), blink, self.talk_level(sc, 'sensei', lt), h=470)
            im.alpha_composite(spr, (W - spr.width + 30, H - spr.height - 60 + int(5 * math.sin(t * 4))))
        elif kind == 'end':
            s1 = art.sprite('mina', 'happy', False, self.talk_level(sc, 'mina', lt), h=640)
            s2 = art.sprite('sensei', 'happy', False, self.talk_level(sc, 'sensei', lt), h=600)
            k = ease(lt / 0.4)
            im.alpha_composite(s1, (int(W * 0.3 - s1.width / 2), int(1280 + (1 - k) * 300 + 6 * math.sin(t * 4))))
            im.alpha_composite(s2, (int(W * 0.72 - s2.width / 2), int(1320 + (1 - k) * 300 + 6 * math.sin(t * 4 + 1))))
            heads['mina'] = (W * 0.3, 1380); heads['sensei'] = (W * 0.72, 1420)

        d = ImageDraw.Draw(im, 'RGBA')
        # 中身（カード・グラフ）
        if kind == 'explain':
            k = ease((lt - 0.1) / 0.35)
            y = 300 + int((1 - k) * 40)
            if k > 0:
                card = Image.new('RGBA', (W, H), (0, 0, 0, 0)); cd = ImageDraw.Draw(card)
                body = sp.get('text', '')
                fs = 64; f = font(fs)
                ls = wrap(cd, body, f, 820)
                ch = 140 + len(ls) * int(fs * 1.45) + (150 if sp.get('term') else 0) + (50 if self.c.get('ref') else 0)
                cd.rounded_rectangle((70, y, W - 70, y + ch), radius=40, fill=(255, 255, 255, 245), outline=INK, width=6)
                yy = y + 60
                if sp.get('term'):
                    pill(cd, (0, yy), sp['term'], 60, CORAL, WHITE, pad=(36, 16), center_w=W); yy += 150
                for l in ls:
                    w = cd.textlength(l, font=f); cd.text(((W - w) / 2, yy), l, font=f, fill=INK); yy += int(fs * 1.45)
                self.card_bottom = y + ch
                if self.c.get('ref'):
                    rf = font(24, False); rs = '出典: ' + self.c['ref']
                    while cd.textlength(rs, font=rf) > 840: rs = rs[:-2] + '…' if not rs.endswith('…') else rs[:-3] + '…'
                    cd.text(((W - cd.textlength(rs, font=rf)) / 2, y + ch - 62), rs, font=rf, fill=GRAY)
                card.putalpha(card.split()[3].point(lambda v: int(v * k)))
                im.alpha_composite(card)
        if kind == 'chart':
            card_y0, card_y1 = 320, 1420
            d.rounded_rectangle((60, card_y0, W - 60, card_y1), radius=40, fill=(255, 255, 255, 250), outline=INK, width=6)
            tf = fit_size(d, sp['title'], 860, 70)
            yy = card_y0 + 60
            for l in sp['title'].split('\n'):
                w = d.textlength(l, font=font(tf)); d.text(((W - w) / 2, yy), l, font=font(tf), fill=INK); yy += int(tf * 1.35)
            rows = sp['rows']; n = len(rows); base, top = card_y1 - 150, yy + 160
            pmax = max(r['p'] for r in rows); bw = 280 if n == 2 else 210; gap = (W - 120 - n * bw) / (n + 1)
            for i, r in enumerate(rows):
                st = 0.5 + i * 0.9
                kk = ease((lt - st) / 0.9)
                if kk <= 0: continue
                col = CORAL if r.get('accent') else (200, 205, 220)
                x0 = 60 + gap + i * (bw + gap); hh = (base - top) * r['p'] / pmax * kk
                d.rounded_rectangle((x0, base - hh, x0 + bw, base), radius=26, fill=col, outline=INK, width=5)
                f = font(48); w = d.textlength(r['label'], font=f)
                d.text((x0 + (bw - w) / 2, base + 30), r['label'], font=f, fill=INK)
                f = font(88 if n == 2 else 70, black=True); w = d.textlength(r['value'], font=f)
                d.text((x0 + (bw - w) / 2, base - hh - 120), r['value'], font=f, fill=(CORAL if r.get('accent') else INK) + (int(255 * kk),))
            d.line([(110, base), (W - 110, base)], fill=INK, width=6)
        if kind == 'end':
            k = back(lt / 0.4)
            ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
            txt = sp.get('text', '')
            fs = fit_size(od, txt, 900, 104, black=True)
            y = outlined(od, (0, 330), txt, fs, INK, WHITE, center_w=W, accent=sp.get('accent'))
            # 保存ボタン
            y += 40
            od.rounded_rectangle((210, y, W - 210, y + 136), radius=68, fill=CORAL, outline=INK, width=6)
            bx = 290
            od.polygon([(bx, y + 34), (bx + 44, y + 34), (bx + 44, y + 104), (bx + 22, y + 86), (bx, y + 104)], fill=WHITE)
            t2 = '保存して見返す'; f = font(58); od.text((bx + 80, y + 28), t2, font=f, fill=WHITE)
            y += 190
            od.rounded_rectangle((180, y, W - 180, y + 200), radius=36, fill=(255, 255, 255, 235), outline=INK, width=5)
            text_block(od, (0, y + 26), sp.get('sub', 'フォローで毎日ひとつ\n根拠のある心理学'), 44, INK, 700, lh=1.45, anchor_center=True, W=W)
            f = font(62, black=True); w = od.textlength(HANDLE, font=f)
            od.text(((W - w) / 2, y + 220), HANDLE, font=f, fill=CORAL, stroke_width=6, stroke_fill=WHITE)
            paste_scaled(im, ov, W / 2, H / 2, min(1.0, 0.85 + 0.15 * k), alpha=min(1.0, lt / 0.25))

        # 上部：ナレーション枠 / テロップ
        top_y = 230
        if sp.get('caption'):
            box = self.capbox(sp['caption'], label=sp.get('caption_label'), size=44)
            a = min(1.0, (lt + (1 if i_sc == 0 else 0)) / 0.2)
            paste_scaled(im, box, 60 + box.width / 2, top_y + box.height / 2, 1.0, a)
            top_y += box.height + 14
        if sp.get('telop'):
            k = 1.0 if i_sc == 0 and lt < 0.01 else back(lt / 0.28)
            if i_sc == 0: k = back((lt + 0.12) / 0.28)
            tov = Image.new('RGBA', (W, 700), (0, 0, 0, 0)); td = ImageDraw.Draw(tov)
            fs = fit_size(td, sp['telop'], 940, 112, black=True)
            yb = outlined(td, (0, 20), sp['telop'], fs, INK, WHITE, center_w=W, accent=sp.get('accent'), sw=max(10, fs // 7))
            tov = tov.crop((0, 0, W, yb + 30))
            paste_scaled(im, tov, W / 2, top_y + tov.height / 2, k)
            top_y += tov.height

        # セリフ（吹き出し or ナレーション枠）
        act = self.active_lines(sc, lt)
        by = max(top_y + 10, 560 if kind == 'story' else 0)
        for j, ln in enumerate(act):
            old = (j == 0 and len(act) == 2)
            age = lt - ln['t0']
            k = back(age / 0.22)
            who = ln['who']
            if kind == 'end':
                continue  # 終わりの場面は画面の文字で十分（声のみ）
            if who in heads and kind in ('story', 'explain'):
                hx, hy = heads[who]
                ncast = len(sp.get('cast', [])) if kind == 'story' else 1
                if ncast >= 2:
                    bub = self.bubble(ln, 0.5, max_w=462, size=50)
                    cx = min(max(hx, bub.width / 2 + 20), W - bub.width / 2 - 20)
                    # 二人の場面：それぞれの頭の上。古いほうは少し上にずらして薄く
                    cy = hy - 150 - bub.height / 2 - (90 if old else 0)
                else:
                    tail_x = min(0.85, max(0.15, (hx - 150) / 780))
                    bub = self.bubble(ln, tail_x)
                    cx = min(max(hx, bub.width / 2 + 40), W - bub.width / 2 - 40)
                    if kind == 'explain':
                        cy = max(hy - 130 - bub.height / 2, self.card_bottom + 24 + bub.height / 2)
                    else:
                        cy = hy - 200 - bub.height / 2
                        if old: cy -= bub.height + 20
                cy = max(cy, by + bub.height / 2)
                if old and ncast < 2 and kind == 'story' and cy + bub.height / 2 > hy - 200 - 10:
                    continue
                paste_scaled(im, bub, cx, cy, k, alpha=0.5 if old else 1.0)
            else:
                label = None if who == 'narr' else art.CAST.get(who, {}).get('name')
                box = self.capbox(ln['text'], label=label, size=50, bg=(INK if who in ('narr', 'sensei') else (90, 70, 60)))
                y0 = 1450 if kind == 'chart' else max(by, 600)
                if kind == 'chart':
                    box = art.caption_box(ln['text'], 46, 560, bg=INK, label=label)
                    paste_scaled(im, box, 60 + box.width / 2, y0 + box.height / 2, 1.0, min(1, age / 0.2))
                elif not old:
                    paste_scaled(im, box, W / 2, y0 + box.height / 2, k)

        # 出典・進行バー
        if self.c.get('ref') and kind == 'chart':
            f = font(26, False); s = '出典: ' + self.c['ref']
            while d.textlength(s, font=f) > 900: s = s[:-2]
            if s != '出典: ' + self.c['ref']: s += '…'
            w = d.textlength(s, font=f)
            ry = 1372
            d.text(((W - w) / 2, ry), s, font=f, fill=GRAY)
        d.rectangle((0, 0, W, 12), fill=(255, 255, 255, 120))
        d.rectangle((0, 0, int(W * t / self.total), 12), fill=CORAL)
        return im.convert('RGB')

# ------------------------------------------------------------ サムネイル（カバー）
def thumbnail(th, Wt=1080, Ht=1920, page_label=None):
    """見たくなる表紙：派手な背景＋大きな縁取り文字＋表情の大きい人物。
    リールは中央 3:4（y=240〜1680）がプロフィールの一覧で見える範囲なので、要素はその中に収める。"""
    im = art.background(th.get('bg', 'pop'), Wt, Ht).convert('RGBA')
    cy = Ht / 2
    im.alpha_composite(art.speedlines(Wt, Ht, Wt / 2, Ht * 0.72, seed=7, n=60, inner=0.25))
    d = ImageDraw.Draw(im, 'RGBA')
    safe_top = 240 if Ht > 1500 else 70
    safe_bot = 1680 if Ht > 1500 else Ht - 40
    # タグ
    y = safe_top + 40
    if th.get('tag'):
        pill(d, (0, y), th['tag'], 46, NAVY, WHITE, pad=(34, 14), center_w=Wt)
        y += 120
    title = th['title']
    fs = fit_size(d, title, Wt - 110, 150 if Ht > 1500 else 132, black=True)
    y = outlined(d, (0, y), title, fs, INK, WHITE, sw=max(12, fs // 6), center_w=Wt, accent=th.get('accent'), lh=1.18)
    # 人物
    hh = (safe_bot - y + 120) if Ht > 1500 else (Ht - y + 160)
    hh = int(max(520, min(hh, 900)))
    spr = art.sprite(th.get('who', 'mina'), th.get('expr', 'surprised'), h=hh)
    sx = int(Wt / 2 - spr.width / 2); sy = int(max(y + 10, safe_bot - hh * 0.92))
    im.alpha_composite(spr, (sx, sy))
    if th.get('icon'):
        ic = art.icon_fx(th['icon'], 190); im.alpha_composite(ic, (sx + spr.width - 120, sy + 10))
    if th.get('who2'):
        s2 = art.sprite(th['who2'], th.get('expr2', 'happy'), h=int(hh * 0.62))
        im.alpha_composite(s2, (Wt - s2.width + 40, safe_bot - s2.height + 80))
    d = ImageDraw.Draw(im, 'RGBA')
    f = font(30)
    lab = f'{BRAND}｜根拠のある心理学'
    w = d.textlength(lab, font=f)
    d.rounded_rectangle(((Wt - w) / 2 - 24, safe_bot - 10, (Wt + w) / 2 + 24, safe_bot + 46), radius=28, fill=(30, 42, 68, 220))
    d.text(((Wt - w) / 2, safe_bot - 4), lab, font=f, fill=WHITE)
    if page_label:
        f = font(36); s = page_label; w = d.textlength(s, font=f)
        d.rounded_rectangle((Wt - w - 110, Ht - 120, Wt - 50, Ht - 50), radius=35, fill=WHITE, outline=INK, width=4)
        d.text((Wt - w - 80, Ht - 114), s, font=f, fill=INK)
    return im.convert('RGB')

# ------------------------------------------------------------ 音
def mix_audio(timeline, total, out_wav, seed):
    n = int(total * SR) + SR
    vox = np.zeros(n, np.float32)
    for sc in timeline:
        for ln in sc['lines']:
            if ln['audio'] is None: continue
            i = int((sc['start'] + ln['t0']) * SR)
            a = ln['audio'][: n - i]
            vox[i:i + len(a)] += a.astype(np.float32)
    bgm_path = out_wav + '.bgm.wav'
    make_bgm(total, bgm_path, seed=seed, hits=[sc['start'] for sc in timeline[1:]])
    with wave.open(bgm_path) as w:
        b = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32).reshape(-1, 2).mean(1) / 32768
    bg = np.zeros(n, np.float32); bg[:len(b)] = b[:n]
    # ダッキング：声があるところはBGMを下げる
    env = np.convolve(np.abs(vox), np.ones(4410) / 4410, mode='same')
    duck = np.clip(env * 25, 0, 1)
    duck = np.convolve(duck, np.ones(8820) / 8820, mode='same')
    g = 0.55 - 0.38 * duck
    mix = vox * 0.95 + bg * g
    mix = mix[:int(total * SR)]
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.92
    st = (np.stack([mix, mix], 1) * 32767).astype(np.int16)
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
    os.remove(bgm_path)

def reel(content, out, tmp):
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    timeline, total = plan(content, os.path.join(tmp, 'tts'))
    r = Renderer(content, timeline, total)
    wav = f'{tmp}/audio.wav'
    mix_audio(timeline, total, wav, zlib.crc32(out.encode()))
    nf = int(total * FPS)
    proc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                             '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', wav, '-shortest',
                             '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'medium',
                             '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '160k', out], stdin=subprocess.PIPE)
    picks = {int((sc['start'] + min(sc['dur'] - 0.2, max((ln['t1'] for ln in sc['lines']), default=1.2))) * FPS): k
             for k, sc in enumerate(timeline)}
    shots = {}
    for i in range(nf):
        fr = r.frame(i / FPS)
        proc.stdin.write(fr.tobytes())
        if i in picks: shots[picks[i]] = fr.resize((270, 480))
    proc.stdin.close(); proc.wait()
    if proc.returncode: raise RuntimeError('ffmpeg failed')
    cover = out.replace('.mp4', '_cover.jpg')
    th = thumbnail(content['thumb']) if content.get('thumb') else r.frame(1.0)
    th.save(cover, quality=93)
    # 確認用：サムネ＋各場面
    ims = [th.resize((270, 480))] + [shots[k] for k in sorted(shots)]
    cols = 5; rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * 270, rows * 480), (0, 0, 0))
    for j, s in enumerate(ims): sheet.paste(s, ((j % cols) * 270, (j // cols) * 480))
    sheet.save(out.replace('.mp4', '_preview.jpg'), quality=85)
    shutil.rmtree(tmp, ignore_errors=True)
    return round(total, 1)
