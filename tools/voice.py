"""ナレーション（音声合成）。config.json の "tts" で切り替える。
  {"provider": "none"}    … 声なし（字幕＋BGM＋効果音）。既定
  {"provider": "google"}  … Google Cloud Text-to-Speech（自然な日本語）。
     認証は環境のネットワーク設定（種類「GCP access token (with Service Account Key)」、ホスト texttospeech.googleapis.com）。
     プロキシがアクセストークンを作って Authorization ヘッダーに自動で付ける。
     任意で "voices": {"narr": "ja-JP-Neural2-B", "me": "ja-JP-Neural2-B", "friend": "ja-JP-Neural2-C"} など
speak(text, who) -> numpy float 配列（44.1kHz モノラル）。失敗したら例外。"""
import os, re, io, json, wave, base64, hashlib, tempfile, urllib.request
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100
API = 'https://texttospeech.googleapis.com/v1/text:synthesize'
DEFAULT_VOICES = {  # (声の名前, 高さ, 速さ)
    'narr':   ('ja-JP-Neural2-B', 0.0, 1.12),
    'me':     ('ja-JP-Neural2-B', 1.5, 1.12),
    'friend': ('ja-JP-Neural2-C', 0.0, 1.12),
    'boss':   ('ja-JP-Neural2-D', -1.0, 1.08),
}

def config():
    try:
        return json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8')).get('tts', {})
    except Exception:
        return {}

def provider():
    return config().get('provider', 'none')

def credit():
    """キャプションに入れる音声のクレジット（Google は不要）"""
    return ''

def clean(text):
    """画面用の文字を読み上げ用に整える（記号を除き、改行は読点に）"""
    t = text.replace('\n', '、')
    t = re.sub(r'[「」『』（）()【】"“”＂]', '', t)
    t = t.replace('…', '、').replace('→', '、').replace('〜', 'ー')
    t = re.sub(r'、+', '、', t).strip('、 ')
    return t

def _google(t, who):
    v = dict(DEFAULT_VOICES)
    for k, n in config().get('voices', {}).items():
        b = v.get(k, v['narr']); v[k] = (n, b[1], b[2]) if isinstance(n, str) else tuple(n)
    name, pitch, rate = v.get(who, v['narr'])
    body = {'input': {'text': t}, 'voice': {'languageCode': 'ja-JP', 'name': name},
            'audioConfig': {'audioEncoding': 'LINEAR16', 'sampleRateHertz': SR, 'speakingRate': rate, 'pitch': pitch}}
    # 認証は環境のネットワーク設定（GCP access token / サービスアカウントキー）でプロキシが付ける。
    # Authorization はダミー値を送り、プロキシが本物のアクセストークンに差し替える。
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer proxy-injected'}
    if os.environ.get('GOOGLE_TTS_KEY'):  # APIキーを環境変数で渡す場合（予備）
        headers = {'Content-Type': 'application/json', 'X-Goog-Api-Key': os.environ['GOOGLE_TTS_KEY']}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method='POST', headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = base64.b64decode(json.load(r)['audioContent'])
    with wave.open(io.BytesIO(data)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

def speak(text, who='narr', cache_dir=None):
    who = {'mina': 'me', 'sota': 'friend', 'sensei': 'narr'}.get(who, who)
    t = clean(text)
    cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), 'shinri_tts')
    os.makedirs(cache_dir, exist_ok=True)
    f = os.path.join(cache_dir, hashlib.md5(f'{provider()}|{who}|{t}'.encode()).hexdigest()[:16] + '.npy')
    if os.path.exists(f): return np.load(f)
    x = _google(t, who)
    idx = np.where(np.abs(x) > 0.01)[0]
    if len(idx): x = x[max(0, idx[0] - 400): idx[-1] + 2500]
    x = x / (np.abs(x).max() + 1e-9) * 0.9
    np.save(f, x)
    return x

if __name__ == '__main__':  # 動作確認: python3 tools/voice.py "こんにちは"
    import sys
    x = _google(clean(sys.argv[1] if len(sys.argv) > 1 else 'こんにちは。しんりラボです。'), 'narr')
    print('ok', round(len(x) / SR, 2), 'sec')
