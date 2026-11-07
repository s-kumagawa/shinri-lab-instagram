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
