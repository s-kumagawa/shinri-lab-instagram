"""投稿仕様(queue/*.json)から posts/<日付>_<slug>/ を生成する。
  python3 tools/build.py queue/004_peak-end.json [YYYY-MM-DD]
出力: 画像はJPEG（Instagram APIはJPEGのみ受付）、manifest.json、caption.txt、preview.jpg
仕様の形式:
 {"slug":"peak-end","type":"carousel|reel","topic":"テーマ","hook":"冒頭の一言","test":"A/Bテストのラベル(任意)",
  "content":{...carousel.py または reel.py 冒頭の説明の形式...},"caption":"キャプション全文"}
リールの声は config.json の tts で切り替える（tools/voice.py）。"""
import json, os, sys, datetime as dt, tempfile
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import carousel, reel, voice

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = dt.timezone(dt.timedelta(hours=9))

def build(spec_path, date=None):
    sp = json.load(open(spec_path, encoding='utf-8'))
    date = date or dt.datetime.now(JST).strftime('%Y-%m-%d')
    out = os.path.join(ROOT, 'posts', f'{date}_{sp["slug"]}'); os.makedirs(out, exist_ok=True)
    man = {k: sp.get(k) for k in ('type', 'topic', 'hook', 'test')}
    if sp['type'] == 'reel' and voice.credit() and voice.credit() not in sp['caption']:
        sp['caption'] = sp['caption'].rstrip() + '\n\n' + voice.credit()
    man['caption'] = sp['caption']
    if sp['type'] == 'carousel':
        files = carousel.build(sp['content'], out)
        if len(files) > 10:
            raise SystemExit(f'カルーセルは10枚まで（今は{len(files)}枚）。story か items を減らしてください')
        man['media'] = files
        ims = [Image.open(f'{out}/{f}').resize((270, 338)) for f in files]
        sheet = Image.new('RGB', (270 * 4, 338 * ((len(ims) + 3) // 4)), (0, 0, 0))
        for j, im in enumerate(ims): sheet.paste(im, ((j % 4) * 270, (j // 4) * 338))
        sheet.save(f'{out}/preview.jpg', quality=85)
    elif sp['type'] == 'reel':
        dur = reel.reel(sp['content'], f'{out}/reel.mp4', tempfile.mkdtemp())
        man['media'] = ['reel.mp4']; man['cover'] = 'reel_cover.jpg'; man['duration'] = dur
        os.replace(f'{out}/reel_preview.jpg', f'{out}/preview.jpg')
    json.dump(man, open(f'{out}/manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(f'{out}/caption.txt', 'w', encoding='utf-8').write(sp['caption'])
    print(out)
    return out

if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
