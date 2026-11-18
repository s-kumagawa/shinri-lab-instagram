"""著作権フリーのBGMをその場で合成する（ローファイ風: エレピ風の和音＋柔らかいキック＋ハイハット）。
make_bgm(duration, out_wav, seed, hits=[場面切替の秒...])"""
import numpy as np, wave, random

SR = 44100
PROGS = [  # 半音（ルートからの度数）のコード進行
    [[0, 4, 7, 11], [9, 12, 16, 19], [5, 9, 12, 16], [7, 11, 14, 17]],   # IM7-vi7-IVM7-V
    [[5, 9, 12, 16], [7, 11, 14, 17], [4, 7, 11, 14], [9, 12, 16, 19]],  # IVM7-V-iii7-vi7
    [[9, 12, 16, 19], [5, 9, 12, 16], [0, 4, 7, 11], [7, 11, 14, 17]],   # vi7-IVM7-IM7-V
]

def tone(freq, dur, vel=0.2):
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-t * 1.8) * (1 - np.exp(-t * 60))
    w = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t) + 0.1 * np.sin(6 * np.pi * freq * t)
    return vel * env * w

def make_bgm(duration, out, seed=0, hits=()):
    rnd = random.Random(seed)
    bpm = rnd.choice([78, 82, 86, 90]); beat = 60 / bpm
    root = 48 + rnd.choice([0, 2, 3, 5, 7])  # C3付近
    prog = rnd.choice(PROGS)
    n = int(SR * (duration + 1)); mix = np.zeros(n)
    def add(sig, at):
        i = int(at * SR); j = min(n, i + len(sig))
        if i < n: mix[i:j] += sig[:j - i]
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    bar = beat * 4; t = 0.0; k = 0
    while t < duration:
        ch = prog[k % len(prog)]
        for iv in ch:
            add(tone(midi(root + 12 + iv), bar * 1.1, 0.06), t + rnd.uniform(0, 0.03))
        add(tone(midi(root + ch[0] - 12), bar, 0.10), t)
        for b in range(4):
            bt = t + b * beat
            if b in (0, 2):  # キック
                tt = np.arange(int(SR * 0.25)) / SR
                add(0.35 * np.sin(2 * np.pi * (110 * np.exp(-tt * 18) + 40) * tt) * np.exp(-tt * 14), bt)
            for off in (0, beat / 2):  # ハイハット
                tt = np.arange(int(SR * 0.05)) / SR
                add(0.03 * np.random.default_rng(int(bt * 1000) + seed).standard_normal(len(tt)) * np.exp(-tt * 90), bt + off)
        t += bar; k += 1
    for h in hits:  # 場面切替の「ポン」
        add(tone(midi(root + 24 + prog[0][2]), 0.4, 0.12), h)
    # 簡易ローパス＋フェード
    mix = np.convolve(mix, np.ones(6) / 6, mode='same')
    fade = int(SR * 1.2); mix[int(SR * duration) - fade:int(SR * duration)] *= np.linspace(1, 0, fade)
    mix[int(SR * duration):] = 0
    mix = mix[:int(SR * duration)]
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.5
    st = (np.stack([mix, mix], 1) * 32767).astype(np.int16)
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())


def make_pop_bgm(duration, out, seed=0, drop=None):
    """明るいポップ調BGM（クイズ用）。長調・テンポ速め、マリンバ風メロディ＋跳ねるベース＋手拍子。
    drop=(開始秒, 終了秒) の間は音楽を止める（「正解は…」の溜め用）。"""
    rnd = random.Random(seed)
    bpm = rnd.choice([124, 128, 132]); beat = 60 / bpm; e = beat / 2
    root = 60 + rnd.choice([0, 2, 5, 7])  # C/D/F/G メジャー
    prog = [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]]  # I-V-vi-IV
    penta = [0, 2, 4, 7, 9, 12, 14, 16]
    n = int(SR * (duration + 1)); mix = np.zeros(n)
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    def add(sig, at):
        i = int(at * SR); j = min(n, i + len(sig))
        if i < n: mix[i:j] += sig[:j - i]
    def marimba(f, d, v):
        t = np.arange(int(SR * d)) / SR
        return v * (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 30)) * np.exp(-t * 9)
    def pluck(f, d, v):
        t = np.arange(int(SR * d)) / SR
        w = 2 * (t * f % 1) - 1  # のこぎり波
        return v * w * np.exp(-t * 14) * (1 - np.exp(-t * 300))
    rng = np.random.default_rng(seed)
    t = 0.0; k = 0; bar = beat * 4
    motif = [rnd.choice(penta) for _ in range(8)]
    while t < duration:
        ch = prog[k % 4]
        for b in range(4):  # 和音：裏拍で軽く刻む
            for iv in ch:
                add(pluck(midi(root + iv), 0.18, 0.035), t + b * beat + e)
        for b in range(4):  # ベース：跳ねる
            add(marimba(midi(root - 12 + ch[0]), 0.22, 0.22), t + b * beat)
            add(marimba(midi(root - 12 + ch[0] + 12), 0.12, 0.10), t + b * beat + e * 1.5)
        for i in range(8):  # メロディ：8分音符のマリンバ（コードに寄せる）
            if (k % 2 == 1 and i in (6, 7)): continue
            m = motif[i] if i % 2 == 0 else ch[i // 2 % 3] + 12
            add(marimba(midi(root + 12 + m), 0.3, 0.13), t + i * e)
        for b in range(4):
            bt = t + b * beat
            tt = np.arange(int(SR * 0.2)) / SR  # キック
            add(0.30 * np.sin(2 * np.pi * (120 * np.exp(-tt * 20) + 50) * tt) * np.exp(-tt * 16), bt)
            if b in (1, 3):  # 手拍子
                tt = np.arange(int(SR * 0.12)) / SR
                cl = rng.standard_normal(len(tt)) * (np.exp(-tt * 45) + 0.6 * np.exp(-np.maximum(tt - 0.012, 0) * 45) * (tt > 0.012))
                add(0.11 * cl, bt)
            for s in range(4):  # シェイカー
                tt = np.arange(int(SR * 0.04)) / SR
                add((0.025 if s % 2 else 0.012) * rng.standard_normal(len(tt)) * np.exp(-tt * 80), bt + s * beat / 4)
        t += bar; k += 1
    # 軽いハイパス（こもり防止）
    mix = mix - np.convolve(mix, np.ones(40) / 40, mode='same') * 0.5
    if drop:
        a, b = int(drop[0] * SR), int(drop[1] * SR); f = int(0.08 * SR)
        mix[a:a + f] *= np.linspace(1, 0, f); mix[a + f:b] = 0
    fade = int(SR * 0.8); end = int(SR * duration)
    mix[end - fade:end] *= np.linspace(1, 0, fade); mix = mix[:end]
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.6
    st = (np.stack([mix, mix], 1) * 32767).astype(np.int16)
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
