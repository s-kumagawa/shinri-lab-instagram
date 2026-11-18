"""投稿仕様(queue/*.json)から posts/<日付>_<slug>/ を生成する。
  python3 tools/build.py queue/004_peak-end.json [YYYY-MM-DD]
出力: 画像はJPEG（Instagram APIはJPEGのみ受付）、manifest.json、caption.txt、preview.jpg
仕様の形式:
 {"slug":"peak-end","type":"carousel|reel|quiz","series":"企画名(quiz/myth/choice/ngok/people/ranking)",
  "topic":"テーマ","hook":"冒頭の一言","test":"(旧)A/Bテストのラベル",
  "vars":{"変数名":"値", ...},      # 改善ループで比較する変数（hook_type, length_s, cta など）
  "hypothesis":"E003",             # この投稿が参加している実験ID（state/experiments.json）
  "content":{...carousel.py / reel.py / quiz_reel.py の形式...},"caption":"キャプション全文"}"""
import json, os, sys, datetime as dt, tempfile
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import carousel, reel, quiz_reel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = dt.timezone(dt.timedelta(hours=9))

def build(spec_path, date=None):
    sp = json.load(open(spec_path, encoding='utf-8'))
    date = date or dt.datetime.now(JST).strftime('%Y-%m-%d')
    out = os.path.join(ROOT, 'posts', f'{date}_{sp["slug"]}'); os.makedirs(out, exist_ok=True)
    man = {k: sp.get(k) for k in ('type', 'series', 'topic', 'hook', 'test', 'vars', 'hypothesis')}
    man['caption'] = sp['caption']
    if sp['type'] == 'carousel':
        d = sp['content']; total = len(d['items']) + 3
        tmp = tempfile.mkdtemp()
        carousel.cover(d, f'{tmp}/01.png', total)
        for i, it in enumerate(d['items'], 1):
            carousel.item(it, i, f'{tmp}/{i+1:02d}.png', i + 1, total)
        carousel.summary(d, f'{tmp}/{total-1:02d}.png', total - 1, total)
        carousel.cta(d, f'{tmp}/{total:02d}.png', total, total)
        files = []
        for i in range(1, total + 1):
            f = f'{i:02d}.jpg'
            Image.open(f'{tmp}/{i:02d}.png').convert('RGB').save(f'{out}/{f}', quality=92)
            files.append(f)
        man['media'] = files
        ims = [Image.open(f'{out}/{f}').resize((270, 338)) for f in files]
        sheet = Image.new('RGB', (270 * 4, 338 * ((len(ims) + 3) // 4)), (0, 0, 0))
        for j, im in enumerate(ims): sheet.paste(im, ((j % 4) * 270, (j // 4) * 338))
        sheet.save(f'{out}/preview.jpg', quality=85)
    elif sp['type'] == 'reel':
        dur = reel.reel(sp['content'], f'{out}/reel.mp4', tempfile.mkdtemp())
        man['media'] = ['reel.mp4']; man['cover'] = 'reel_cover.jpg'; man['duration'] = dur
        os.replace(f'{out}/reel_preview.jpg', f'{out}/preview.jpg')
    elif sp['type'] == 'quiz':
        dur = quiz_reel.quiz_reel(sp['content'], f'{out}/reel.mp4', tempfile.mkdtemp())
        man['type'] = 'reel'; man['format'] = 'quiz'
        man['media'] = ['reel.mp4']; man['cover'] = 'reel_cover.jpg'; man['duration'] = dur
        os.replace(f'{out}/reel_preview.jpg', f'{out}/preview.jpg')
    json.dump(man, open(f'{out}/manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(f'{out}/caption.txt', 'w', encoding='utf-8').write(sp['caption'])
    print(out)
    return out

if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
