"""ナレーション・セリフの音声合成（Open JTalk + HTS Voice "Mei" / "Takumi"）。
  必要: apt-get install -y open-jtalk open-jtalk-mecab-naist-jdic
  音声: assets/voices/*.htsvoice  © Nagoya Institute of Technology (CC BY 3.0) → キャプションにクレジットを入れる
speak(text, who, expr) -> numpy float 配列（44.1kHz モノラル）"""
import os, re, subprocess, tempfile, wave, hashlib, shutil
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VDIR = os.path.join(ROOT, 'assets', 'voices')
DIC = '/var/lib/mecab/dic/open-jtalk/naist-jdic'
SR = 44100
CREDIT = '音声：HTS Voice "Mei"・"Takumi" © Nagoya Institute of Technology（CC BY 3.0）'

# 話者ごとの声: (声ファイル, 音の高さの調整[半音], 話す速さ)
VOICE = {
    'mina':   ('mei_normal', 0.0, 1.15),
    'sota':   ('takumi_normal', 1.5, 1.15),
    'sensei': ('takumi_normal', -1.0, 1.1),
    'narr':   ('takumi_normal', -1.0, 1.1),
}
EXPR_VOICE = {('mina', 'happy'): 'mei_happy', ('mina', 'smug'): 'mei_happy',
              ('mina', 'sad'): 'mei_sad', ('mina', 'worried'): 'mei_sad'}

def available():
    return shutil.which('open_jtalk') is not None and os.path.isdir(DIC)

def clean(text):
    """画面用の文字を読み上げ用に整える（記号を除き、改行は読点に）"""
    t = text.replace('\n', '、')
    t = re.sub(r'[「」『』（）()【】"“”＂]', '', t)
    t = t.replace('…', '、').replace('→', '、').replace('〜', 'ー')
    t = re.sub(r'、+', '、', t).strip('、 ')
    return t

def speak(text, who='narr', expr='normal', speed=None, cache_dir=None):
    vname, fm, r = VOICE.get(who, VOICE['narr'])
    vname = EXPR_VOICE.get((who, expr), vname)
    r = speed or r
    t = clean(text)
    key = hashlib.md5(f'{t}|{vname}|{fm}|{r}'.encode()).hexdigest()[:16]
    cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), 'shinri_tts')
    os.makedirs(cache_dir, exist_ok=True)
    out = os.path.join(cache_dir, key + '.wav')
    if not os.path.exists(out):
        subprocess.run(['open_jtalk', '-x', DIC, '-m', os.path.join(VDIR, vname + '.htsvoice'),
                        '-r', str(r), '-fm', str(fm), '-ow', out], input=t.encode('utf-8'), check=True)
    with wave.open(out) as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if sr != SR:
        n = int(len(x) * SR / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    # 前後の無音を詰める
    idx = np.where(np.abs(x) > 0.01)[0]
    if len(idx): x = x[max(0, idx[0] - 400): idx[-1] + 2000]
    return x / (np.abs(x).max() + 1e-9) * 0.9

def envelope(x, fps=30):
    """口パク用：フレームごとの音量（0〜3の4段階）"""
    hop = SR // fps
    n = len(x) // hop + 1
    v = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(x) else 0 for i in range(n)])
    v = v / (v.max() + 1e-9)
    return np.digitize(v, [0.15, 0.4, 0.7])
