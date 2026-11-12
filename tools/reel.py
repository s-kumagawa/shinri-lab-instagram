"""ストーリー×図解アニメのリール生成 (1080x1920, 30fps)。reel(content, out_mp4, tmpdir) -> 秒数

content = {
 "ref": "出典（短く）",
 "thumb": {"title": "サムネの大見出し\\n3行まで", "accent": "強調語", "pose": "shock", "icon": "!", "tag": "分類", "bg": "pop"},
 "scenes": [ 場面, ... ]   # 6〜9場面、合計20〜32秒
}
場面の共通項目
  kind  : story（既定。人物の場面）/ explain（図解）/ versus（AとBの比較）/ chart（グラフ）/ points（箇条書き）/ end
  bg    : room / office / cafe / night / shop / street / park / pop / navy / cream
  telop : 画面上部の大きな見出し。1場面目には必ず入れる（フック）。accent で強調語の色を変える
  caption: 上部の小さなラベル（例「ある日のこと」）
  lines : [{"who": "me|friend|boss|narr", "text": "画面の文字", "say": "読み上げ用（任意）", "pose": "ポーズ（任意）", "style": "say|think|shout"}]
          me/friend/boss は人物の頭上に吹き出し、narr は下の字幕で出す（声ありなら読み上げる）
  dur   : 最低の長さ（任意。セリフの量・音声の長さで自動で延びる）
story   : cast [{"who": "me", "pose": "sad", "x": 0.5, "enter": "left|right", "prop": "phone|bag|note|cup|heart|coin"}]
          icon {"on": "me", "kind": "!|?|idea|sparkle|heart|gloom|..."}, fx "shake|lines"
explain : icon（brain/bulb/warn/check/clock/heart/coin/people/memo/chat/repeat/search/phone/calendar）, term, text, accent
versus  : title, a {"label": "A", "text": "..."}, b {...}, win "a|b"（任意。選ばれた側を強調）
chart   : title, rows [{"label": "予想", "value": "約半数", "p": 0.5, "accent": true}]
points  : title, items ["...", "...", "..."]（3つまで）
end     : text, accent, sub
"""
import os, sys, math, subprocess, shutil, zlib, wave
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from design import *
import art, figure as fg, voice
from music import make_bgm

W, H, FPS = 1080, 1920, 30
SR = voice.SR
LEAD, GAP, TAIL, TR = 0.3, 0.25, 0.6, 0.24
SUB_Y = 1470

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

def legacy(s):
    """旧仕様の場面（hook/text/badge/bars）を新しい場面に読みかえる"""
    k = s.get('kind')
    if k == 'hook':
        return {'kind': 'explain', 'bg': 'navy', 'icon': 'bulb', 'telop': s.get('pre', ''), 'text': s['main'], 'dur': s.get('dur', 2.6)}
    if k == 'text':
        return {'kind': 'explain', 'bg': 'navy', 'text': s['text'], 'dur': s.get('dur', 3.5)}
    if k == 'badge':
        return {'kind': 'explain', 'bg': 'navy', 'icon': 'check', 'term': s['badge'], 'text': s['text'], 'dur': s.get('dur', 3.5)}
    if k == 'bars':
        return {'kind': 'chart', 'title': s['title'], 'rows': s['rows'], 'dur': s.get('dur', 5)}
    return s

# ------------------------------------------------------------ タイムライン（音声）
def plan(content, cache):
    use_voice = voice.provider() != 'none'
    timeline, t = [], 0.0
    for idx, s in enumerate(content['scenes']):
        s = legacy(s); kind = s.get('kind', 'story')
        lines, lt = [], (0.2 if idx == 0 else LEAD + TR * 0.5)
        for ln in s.get('lines', []):
            who = fg.who_of(ln.get('who', 'narr'))
            audio = None
            if use_voice:
                try:
                    audio = voice.speak(ln.get('say', ln['text']), who, cache_dir=cache)
                except Exception as e:
                    print('音声合成に失敗したため、声なしで作ります:', e, file=sys.stderr)
                    use_voice = False
            n = len(ln['text'].replace('\n', ''))
            d = len(audio) / SR if audio is not None else max(1.3, 0.5 + 0.12 * n)
            lines.append({**ln, 'who': who, 't0': lt, 't1': lt + d, 'audio': audio})
            lt += d + GAP
        base = {'explain': 2.6, 'versus': 3.4, 'chart': 3.6, 'points': 3.4, 'end': 3.0}.get(kind, 2.2)
        dur = max(s.get('dur', 0), lt - GAP + TAIL, base)
        timeline.append({'spec': s, 'kind': kind, 'start': t, 'dur': dur, 'lines': lines})
        t += dur
    return timeline, t

# ------------------------------------------------------------ 描画
class Renderer:
    def __init__(self, content, timeline, total):
        self.c, self.tl, self.total = content, timeline, total
        self.cache = {}
        self.last = {}

    def _c(self, key, fn):
        if key not in self.cache: self.cache[key] = fn()
        return self.cache[key]

    def scene_at(self, t):
        for i, s in enumerate(self.tl):
            if s['start'] <= t < s['start'] + s['dur']: return i
        return len(self.tl) - 1

    def frame(self, t):
        i = self.scene_at(t); sc = self.tl[i]; lt = t - sc['start']
        im = self.render(i, lt, t)
        if i > 0 and lt < TR:
            # 場面転換：新しい場面が斜めにスライドして入る
            prev = self.last.get(i - 1)
            if prev is None:
                ps = self.tl[i - 1]; prev = self.render(i - 1, ps['dur'] - 1 / FPS, sc['start'] - 1 / FPS); self.last[i - 1] = prev
            k = ease(lt / TR)
            out = prev.copy()
            mask = Image.new('L', (W, H), 0); md = ImageDraw.Draw(mask)
            x = (W + 600) * k - 300
            md.polygon([(-10, 0), (x + 300, 0), (x - 300, H), (-10, H)], fill=255)
            out.paste(im, (0, 0), mask)
            d = ImageDraw.Draw(out)
            d.polygon([(x + 300, 0), (x + 360, 0), (x - 240, H), (x - 300, H)], fill=CORAL)
            im = out
        if i < len(self.tl) - 1 and lt > sc['dur'] - 1.5 / FPS:
            self.last[i] = im
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, W, 12), fill=(230, 230, 230))
        d.rectangle((0, 0, int(W * t / self.total), 12), fill=CORAL)
        return im

    # ---- 部品
    def telop(self, im, sp, lt, i, top):
        if not sp.get('telop'): return top
        def mk():
            ov = Image.new('RGBA', (W, 760), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
            fs = fit_size(d, sp['telop'], 960, 112, black=True)
            yb = outlined(d, (0, 20), sp['telop'], fs, INK, WHITE, center_w=W, accent=sp.get('accent'), sw=max(10, fs // 7))
            return ov.crop((0, 0, W, yb + 30))
        ov = self._c(('telop', i), mk)
        k = back((lt + (0.15 if i == 0 else -0.1)) / 0.3)
        paste_scaled(im, ov, W / 2, top + ov.height / 2, k)
        return top + ov.height

    def subtitle(self, im, ln, lt):
        box = self._c(('sub', ln['text']), lambda: self._subbox(ln['text']))
        age = lt - ln['t0']
        paste_scaled(im, box, W / 2, SUB_Y + box.height / 2 - 40 * (1 - ease(age / 0.25)), 1.0, min(1.0, age / 0.18))

    def _subbox(self, text):
        tmp = ImageDraw.Draw(Image.new('RGB', (4, 4)))
        f = font(54); ls = wrap(tmp, text, f, 880)
        w = max(tmp.textlength(l, font=f) for l in ls); lh = 78
        bw, bh = int(w + 80), int(lh * len(ls) + 44)
        im = Image.new('RGBA', (bw + 12, bh + 12), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((6, 10, bw + 6, bh + 10), radius=26, fill=(0, 0, 0, 60))
        d.rounded_rectangle((0, 0, bw, bh), radius=26, fill=WHITE, outline=INK, width=5)
        y = 18
        for l in ls:
            d.text(((bw - tmp.textlength(l, font=f)) / 2, y), l, font=f, fill=INK); y += lh
        return im

    def drift(self, im, i, t, col=(255, 255, 255, 18)):
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        for k in range(5):
            r = 140 + 60 * k
            cx = (W * (0.15 + 0.2 * k) + 80 * math.sin(t * 0.6 + k * 1.3)) % (W + 200) - 100
            cy = H * (0.2 + 0.15 * k) + 60 * math.cos(t * 0.5 + k)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
        im.alpha_composite(ov)

    # ---- 場面
    def render(self, i, lt, t):
        sc = self.tl[i]; sp = sc['spec']; kind = sc['kind']
        default_bg = {'explain': 'navy', 'versus': 'cream', 'chart': 'cream', 'points': 'navy', 'end': 'pop'}.get(kind, 'room')
        bgk = sp.get('bg', default_bg)
        im = fg.background(bgk, W, H).copy()
        dark = bgk in ('navy', 'night')
        if kind != 'story' and bgk not in ('pop', 'pop2'):
            self.drift(im, i, t, (255, 255, 255, 14) if dark else (30, 42, 68, 10))
        top = 230
        if sp.get('caption'):
            box = self._c(('cap', sp['caption']), lambda: art.caption_box(sp['caption'], 44, 860))
            im.alpha_composite(box, (50, top)); top += box.height + 10
        top = self.telop(im, sp, lt, i, top)
        heads = {}
        if kind == 'story': heads = self.story(im, sc, lt, t, i)
        elif kind == 'explain': self.explain(im, sc, lt, t, top, dark)
        elif kind == 'versus': self.versus(im, sc, lt, t, top)
        elif kind == 'chart': self.chart(im, sc, lt, t, top)
        elif kind == 'points': self.points(im, sc, lt, t, top, dark)
        elif kind == 'end': self.end(im, sc, lt, t)
        # セリフ
        act = [ln for ln in sc['lines'] if lt >= ln['t0']]
        bubbles = {}
        for ln in act:
            if ln['who'] in heads: bubbles[ln['who']] = ln
        subs = [ln for ln in act if ln['who'] not in heads]
        n_cast = len(heads)
        for who, ln in bubbles.items():
            hx, hy = heads[who]
            mw, fs = (460, 50) if n_cast >= 2 else (800, 58)
            bub = self._c(('bub', ln['text'], ln.get('style', 'say'), mw), lambda: art.bubble(ln['text'], fs, mw, ln.get('style', 'say')))
            cx = min(max(hx, bub.width / 2 + 24), W - bub.width / 2 - 24)
            cy = max(hy - 110 - bub.height / 2, top + 10 + bub.height / 2)
            paste_scaled(im, bub, cx, cy, back((lt - ln['t0']) / 0.22))
        if subs and kind != 'end':
            self.subtitle(im, subs[-1], lt)
        if self.c.get('ref') and kind in ('explain', 'versus', 'chart'):
            d = ImageDraw.Draw(im, 'RGBA')
            f = font(26, False); s = '出典: ' + self.c['ref']
            while d.textlength(s, font=f) > 960: s = s[:-2]
            d.text(((W - d.textlength(s, font=f)) / 2, 1700), s, font=f, fill=(200, 205, 220) if dark else GRAY)
        return im

    def story(self, im, sc, lt, t, i):
        sp = sc['spec']; cast = sp.get('cast', []); n = len(cast)
        fy = fg.floor_y(H); scale = 1.22 if n == 1 else 1.05
        heads = {}
        if sp.get('fx') == 'lines':
            im.alpha_composite(self._c(('lines', i), lambda: art.speedlines(W, H, W / 2, 1050, seed=i, color=(255, 255, 255))))
        for j, c in enumerate(cast):
            who = fg.who_of(c['who'])
            x = c.get('x', 0.5 if n == 1 else (0.3 if j == 0 else 0.7)) * W
            # ポーズの切り替え（セリフごとに pose を変えられる）
            cur, prev, t_sw = fg.pose_of(c.get('pose') or c.get('expr')), None, 0.0
            for ln in sc['lines']:
                if ln['who'] == who and (ln.get('pose') or ln.get('expr')) and lt >= ln['t0']:
                    prev, cur, t_sw = cur, fg.pose_of(ln.get('pose') or ln.get('expr')), ln['t0']
            if c.get('enter') and lt < 0.9:
                k = ease(lt / 0.9); sx = -0.25 * W if c['enter'] == 'left' else 1.25 * W
                x = sx + (x - sx) * k
                pose = fg.animate('walk', lt, j)
            else:
                pose = fg.blend_pose(prev if t_sw else ('walk' if c.get('enter') else None), cur, lt, t_sw if t_sw else (0.9 if c.get('enter') else 0), seed=j)
            if c.get('prop') and not pose.get('prop'): pose['prop'] = c['prop']
            shake = (int(16 * math.sin(lt * 60)) if sp.get('fx') == 'shake' and lt < 0.5 else 0)
            head, hand = fg.draw_figure(im, who, pose, x + shake, fy, scale=scale, flip=c.get('flip', x > W * 0.6 and n > 1))
            heads[who] = head
        ic = sp.get('icon')
        if ic and fg.who_of(ic.get('on', 'me')) in heads:
            hx, hy = heads[fg.who_of(ic.get('on', 'me'))]
            k = back((lt - 0.3) / 0.3)
            paste_scaled(im, self._c(('icon', ic['kind']), lambda: art.icon_fx(ic['kind'], 170)), hx + 120, hy - 90 + 8 * math.sin(t * 5), k)
        return heads

    def explain(self, im, sc, lt, t, top, dark):
        sp = sc['spec']; fgc = WHITE if dark else INK
        tmpd = ImageDraw.Draw(Image.new('RGB', (4, 4)))
        fs0 = fit_size(tmpd, sp.get('text', ''), 920, sp.get('size', 88))
        block = (320 if sp.get('icon') else 0) + (160 if sp.get('term') else 0) + len(sp.get('text', '').split('\n')) * int(fs0 * 1.42)
        y = max(top + 30, int((330 + SUB_Y - 60) / 2 - block / 2))
        if sp.get('icon'):
            ic = self._c(('xicon', sp['icon'], dark), lambda: fg.icon(sp['icon'], 280, WHITE if dark else INK))
            k = back(lt / 0.35)
            paste_scaled(im, ic, W / 2, y + 150 + 10 * math.sin(t * 2.4), k)
            y += 320
        d = ImageDraw.Draw(im, 'RGBA')
        if sp.get('term'):
            k = back((lt - 0.25) / 0.3)
            if k > 0:
                pl = self._c(('term', sp['term']), lambda: self._pill(sp['term']))
                paste_scaled(im, pl, W / 2, y + pl.height / 2, 1.8 - 0.8 * k if k < 1 else 1.0, min(1, (lt - 0.25) / 0.12))
            y += 160
        text = sp.get('text', '')
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        fs = fs0
        f = font(fs); acc = sp.get('accent')
        for j, line in enumerate(text.split('\n')):
            st = 0.35 + 0.14 * j + (0.25 if sp.get('term') else 0)
            k = ease((lt - st) / 0.3)
            if k <= 0: y += int(fs * 1.42); continue
            w = d.textlength(line, font=f); x = (W - w) / 2; yy = y + 30 * (1 - k)
            if acc and acc in line:
                a0 = x + d.textlength(line[:line.index(acc)], font=f); aw = d.textlength(acc, font=f)
                km = ease((lt - st - 0.3) / 0.35)
                d.rectangle((a0 - 6, yy + fs * 0.62, a0 - 6 + (aw + 12) * km, yy + fs * 1.08), fill=CORAL + (200,))
            d.text((x, yy), line, font=f, fill=fgc + (int(255 * k),))
            y += int(fs * 1.42)
        im.alpha_composite(ov)

    def _pill(self, text):
        tmp = ImageDraw.Draw(Image.new('RGB', (4, 4))); f = font(62)
        w = tmp.textlength(text, font=f)
        im = Image.new('RGBA', (int(w + 100), 120), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w + 96, 116), radius=58, fill=CORAL, outline=WHITE, width=5)
        d.text((48, 16), text, font=f, fill=WHITE)
        return im

    def versus(self, im, sc, lt, t, top):
        sp = sc['spec']; d = ImageDraw.Draw(im, 'RGBA')
        y = max(top + 20, 320)
        if sp.get('title'):
            fs = fit_size(d, sp['title'], 940, 76)
            y = text_block(d, (0, y), sp['title'], fs, INK, 960, lh=1.35, anchor_center=True, W=W) + 40
        cw, ch = 450, 640
        for j, key in enumerate(('a', 'b')):
            card = sp[key]; st = 0.2 + 0.45 * j
            k = ease((lt - st) / 0.4)
            if k <= 0: continue
            tx = 60 if j == 0 else W - 60 - cw
            ox = (-1 if j == 0 else 1) * (1 - k) * 600
            win = sp.get('win') == key
            hl = win and lt > st + 1.2
            ov = Image.new('RGBA', (cw + 20, ch + 20), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
            od.rounded_rectangle((6, 10, cw + 6, ch + 10), radius=36, fill=(0, 0, 0, 40))
            od.rounded_rectangle((0, 0, cw, ch), radius=36, fill=CORAL if hl else WHITE, outline=INK, width=6)
            lab = card.get('label', key.upper())
            lf = font(110, black=True); lw_ = od.textlength(lab, font=lf)
            od.text(((cw - lw_) / 2, 40), lab, font=lf, fill=WHITE if hl else CORAL)
            ts = fit_size(od, card['text'], cw - 60, 52)
            text_block(od, (0, 230), card['text'], ts, WHITE if hl else INK, cw - 50, lh=1.45, anchor_center=True, W=cw)
            sc_ = 1.0 + (0.05 * ease((lt - st - 1.2) / 0.3) if hl else 0)
            paste_scaled(im, ov, tx + cw / 2 + ox, y + ch / 2, sc_)
        k = back((lt - 0.8) / 0.3)
        if k > 0:
            vs = self._c('vs', lambda: self._vs())
            paste_scaled(im, vs, W / 2, y + ch / 2, k)

    def _vs(self):
        im = Image.new('RGBA', (170, 170), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.ellipse((4, 4, 166, 166), fill=NAVY, outline=WHITE, width=6)
        f = font(64, black=True); d.text(((170 - d.textlength('VS', font=f)) / 2, 40), 'VS', font=f, fill=WHITE)
        return im

    def chart(self, im, sc, lt, t, top):
        sp = sc['spec']; d = ImageDraw.Draw(im, 'RGBA')
        y0 = max(top + 10, 310); y1 = 1400
        d.rounded_rectangle((60, y0, W - 60, y1), radius=40, fill=(255, 255, 255, 250), outline=INK, width=6)
        tf = fit_size(d, sp['title'], 860, 70)
        yy = text_block(d, (0, y0 + 50), sp['title'], tf, INK, 900, lh=1.35, anchor_center=True, W=W)
        rows = sp['rows']; n = len(rows); base, topb = y1 - 130, yy + 170
        pmax = max(r['p'] for r in rows); bw = 280 if n == 2 else 210; gap = (W - 120 - n * bw) / (n + 1)
        for j, r in enumerate(rows):
            st = 0.4 + j * 0.8; kk = ease((lt - st) / 0.9)
            if kk <= 0: continue
            col = CORAL if r.get('accent') else (200, 205, 220)
            x0 = 60 + gap + j * (bw + gap); hh = (base - topb) * r['p'] / pmax * kk
            d.rounded_rectangle((x0, base - hh, x0 + bw, base), radius=26, fill=col, outline=INK, width=5)
            f = font(46); w = d.textlength(r['label'], font=f)
            d.text((x0 + (bw - w) / 2, base + 26), r['label'], font=f, fill=INK)
            kv = back((lt - st - 0.7) / 0.3)
            if kv > 0:
                vim = self._c(('val', r['value'], bool(r.get('accent'))), lambda: self._val(r['value'], CORAL if r.get('accent') else INK))
                paste_scaled(im, vim, x0 + bw / 2, base - hh - 70, kv)
        d.line([(110, base), (W - 110, base)], fill=INK, width=6)

    def _val(self, s, col):
        f = font(88, black=True); tmp = ImageDraw.Draw(Image.new('RGB', (4, 4))); w = tmp.textlength(s, font=f)
        im = Image.new('RGBA', (int(w + 40), 130), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.text((20, 6), s, font=f, fill=col, stroke_width=6, stroke_fill=WHITE)
        return im

    def points(self, im, sc, lt, t, top, dark):
        sp = sc['spec']; d = ImageDraw.Draw(im, 'RGBA'); fgc = WHITE if dark else INK
        y = max(top + 20, 340)
        if sp.get('title'):
            fs = fit_size(d, sp['title'], 940, 80)
            y = text_block(d, (0, y), sp['title'], fs, YELLOW if dark else CORAL, 960, lh=1.3, anchor_center=True, W=W) + 50
        for j, item in enumerate(sp.get('items', [])):
            st = 0.3 + 0.55 * j; k = ease((lt - st) / 0.35)
            if k <= 0: continue
            ov = Image.new('RGBA', (W - 120, 190), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
            od.rounded_rectangle((0, 0, W - 120, 180), radius=30, fill=(255, 255, 255, 235), outline=INK, width=5)
            od.ellipse((30, 50, 110, 130), fill=CORAL)
            od.line([(50, 92), (66, 110), (94, 72)], fill=WHITE, width=10)
            ts = fit_size(od, item, W - 300, 52)
            text_block(od, (140, 90 - ts * 0.75 * (item.count('\n') + 1)), item, ts, INK, W - 300, lh=1.4)
            paste_scaled(im, ov, W / 2 + (1 - k) * 300, y + 90, 1.0, k)
            y += 215

    def end(self, im, sc, lt, t):
        sp = sc['spec']
        fy = H - 130
        fg.draw_figure(im, 'me', fg.animate('joy', t), W * 0.36, fy, scale=0.8)
        fg.draw_figure(im, 'friend', fg.animate('wave', t, 1), W * 0.66, fy, scale=0.8, flip=True)
        def mk():
            ov = Image.new('RGBA', (W, 1300), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
            txt = sp.get('text', '')
            fs = fit_size(od, txt, 920, 104, black=True)
            y = outlined(od, (0, 20), txt, fs, INK, WHITE, center_w=W, accent=sp.get('accent'), sw=max(10, fs // 7))
            by = y + 30; y = by + 190
            od.rounded_rectangle((180, y, W - 180, y + 200), radius=36, fill=(255, 255, 255, 240), outline=INK, width=5)
            text_block(od, (0, y + 28), sp.get('sub', 'フォローで毎日ひとつ\n根拠のある心理学'), 44, INK, 700, lh=1.45, anchor_center=True, W=W)
            f = font(62, black=True); w = od.textlength(HANDLE, font=f)
            od.text(((W - w) / 2, y + 226), HANDLE, font=f, fill=CORAL, stroke_width=6, stroke_fill=WHITE)
            return ov.crop((0, 0, W, y + 320)), by
        ov, by = self._c('endov', mk)
        k = back(lt / 0.35)
        paste_scaled(im, ov, W / 2, 280 + ov.height / 2, 0.85 + 0.15 * k, min(1.0, lt / 0.2))
        # 保存ボタン（脈打つ）
        kb = back((lt - 0.5) / 0.3)
        if kb > 0:
            btn = self._c('btn', self._btn)
            paste_scaled(im, btn, W / 2, 280 + by + 75, kb * (1 + 0.04 * math.sin(t * 6)))

    def _btn(self):
        im = Image.new('RGBA', (680, 150), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, 676, 136), radius=68, fill=CORAL, outline=INK, width=6)
        bx = 90
        d.polygon([(bx, 34), (bx + 44, 34), (bx + 44, 104), (bx + 22, 86), (bx, 104)], fill=WHITE)
        d.text((bx + 80, 28), '保存して見返す', font=font(58), fill=WHITE)
        return im

# ------------------------------------------------------------ サムネイル（カバー）
def thumbnail(th, Wt=1080, Ht=1920, page_label=None):
    """見たくなる表紙：派手な背景＋大きな縁取り文字＋大きく動きのあるポーズの人物。
    リールは中央 3:4（y=240〜1680）がプロフィールの一覧で見える範囲なので、要素はその中に収める。"""
    im = fg.background(th.get('bg', 'pop'), Wt, Ht).copy()
    im.alpha_composite(art.speedlines(Wt, Ht, Wt / 2, Ht * 0.72, seed=7, n=60, inner=0.25))
    d = ImageDraw.Draw(im, 'RGBA')
    tall = Ht > 1500
    safe_top, safe_bot = (240, 1680) if tall else (60, Ht - 50)
    y = safe_top + 40
    if th.get('tag'):
        pill(d, (0, y), th['tag'], 46, NAVY, WHITE, pad=(34, 14), center_w=Wt); y += 120
    fs = fit_size(d, th['title'], Wt - 110, 150 if tall else 128, black=True)
    y = outlined(d, (0, y), th['title'], fs, INK, WHITE, sw=max(12, fs // 6), center_w=Wt, accent=th.get('accent'), lh=1.18)
    foot = safe_bot - 70
    avail = foot - y - 40
    scale = max(0.7, min(1.35, avail / 560))
    pose = fg.animate(fg.pose_of(th.get('pose') or th.get('expr') or 'shock'), 0.15)
    if th.get('prop'): pose['prop'] = th['prop']
    head, _ = fg.draw_figure(im, th.get('who', 'me'), pose, Wt / 2, foot, scale=scale)
    if th.get('icon'):
        ic = art.icon_fx(th['icon'], 200); im.alpha_composite(ic, (int(head[0] + 70), int(head[1] - 170)))
    d = ImageDraw.Draw(im, 'RGBA')
    f = font(30); lab = f'{BRAND}｜根拠のある心理学'; w = d.textlength(lab, font=f)
    d.rounded_rectangle(((Wt - w) / 2 - 24, safe_bot - 6, (Wt + w) / 2 + 24, safe_bot + 48), radius=28, fill=(30, 42, 68, 230))
    d.text(((Wt - w) / 2, safe_bot - 1), lab, font=f, fill=WHITE)
    if page_label:
        f = font(36); w = d.textlength(page_label, font=f)
        d.rounded_rectangle((Wt - w - 110, Ht - 190, Wt - 50, Ht - 120), radius=35, fill=WHITE, outline=INK, width=4)
        d.text((Wt - w - 80, Ht - 184), page_label, font=f, fill=INK)
    return im.convert('RGB')

# ------------------------------------------------------------ 音（BGM＋声＋効果音）
def _sfx_whoosh():
    n = int(SR * 0.35); t = np.arange(n) / SR
    x = np.random.default_rng(1).standard_normal(n)
    x = np.convolve(x, np.ones(18) / 18, mode='same')
    return (x * np.sin(np.pi * t / t[-1]) ** 2 * 0.5).astype(np.float32)

def _sfx_pop():
    n = int(SR * 0.12); t = np.arange(n) / SR
    return (0.35 * np.sin(2 * np.pi * (900 - 2500 * t) * t) * np.exp(-t * 40)).astype(np.float32)

def mix_audio(timeline, total, out_wav, seed):
    n = int(total * SR) + SR
    vox = np.zeros(n, np.float32); sfx = np.zeros(n, np.float32)
    def add(buf, sig, at, g=1.0):
        i = int(at * SR); j = min(n, i + len(sig))
        if 0 <= i < n: buf[i:j] += sig[:j - i] * g
    wh, pp = _sfx_whoosh(), _sfx_pop()
    for k, sc in enumerate(timeline):
        if k: add(sfx, wh, sc['start'] - 0.05, 0.6)
        for ln in sc['lines']:
            if ln['audio'] is not None: add(vox, ln['audio'].astype(np.float32), sc['start'] + ln['t0'])
            add(sfx, pp, sc['start'] + ln['t0'], 0.5)
    bgm_path = out_wav + '.bgm.wav'
    make_bgm(total, bgm_path, seed=seed, hits=[])
    with wave.open(bgm_path) as w:
        b = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32).reshape(-1, 2).mean(1) / 32768
    bg = np.zeros(n, np.float32); bg[:len(b)] = b[:n]
    has_voice = np.abs(vox).max() > 0
    if has_voice:
        env = np.convolve(np.abs(vox), np.ones(4410) / 4410, mode='same')
        duck = np.convolve(np.clip(env * 25, 0, 1), np.ones(8820) / 8820, mode='same')
        g = 0.5 - 0.33 * duck
    else:
        g = 0.8
    mix = vox * 0.95 + bg * g + sfx * 0.6
    mix = mix[:int(total * SR)]
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.9
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
    picks = {int((sc['start'] + sc['dur'] * 0.8) * FPS): k for k, sc in enumerate(timeline)}
    shots = {}
    for i in range(nf):
        fr = r.frame(i / FPS).convert('RGB')
        proc.stdin.write(fr.tobytes())
        if i in picks: shots[picks[i]] = fr.resize((270, 480))
    proc.stdin.close(); proc.wait()
    if proc.returncode: raise RuntimeError('ffmpeg failed')
    cover = out.replace('.mp4', '_cover.jpg')
    th = thumbnail(content['thumb']) if content.get('thumb') else r.frame(1.0).convert('RGB')
    th.save(cover, quality=93)
    ims = [th.resize((270, 480))] + [shots[k] for k in sorted(shots)]
    cols = 5; rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * 270, rows * 480), (0, 0, 0))
    for j, s in enumerate(ims): sheet.paste(s, ((j % cols) * 270, (j // cols) * 480))
    sheet.save(out.replace('.mp4', '_preview.jpg'), quality=85)
    shutil.rmtree(tmp, ignore_errors=True)
    return round(total, 1)
