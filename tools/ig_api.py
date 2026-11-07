"""Instagram API (Instagram Login) の薄いラッパー。
アクセストークンは環境のネットワークシークレットとしてプロキシが
Authorization ヘッダーに注入する（コードやリポジトリには置かない）。

使い方:
  python3 tools/ig_api.py whoami
  python3 tools/ig_api.py limit
  python3 tools/ig_api.py publish <post_dir> <public_base_url>
  python3 tools/ig_api.py insights            -> state/insights/YYYY-MM-DD.json と要約を出力
  python3 tools/ig_api.py comments [days]     -> 未返信コメント一覧(JSON)
  python3 tools/ig_api.py reply <comment_id> <message>
"""
import json, os, sys, time, datetime as dt
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, 'config.json')
CFG = json.load(open(CFG_PATH)) if os.path.exists(CFG_PATH) else {}
VER = CFG.get('api_version', 'v23.0')
BASE = f'https://graph.instagram.com/{VER}'
HDR = {'Authorization': 'Bearer injected-by-proxy'}
JST = dt.timezone(dt.timedelta(hours=9))

class ApiError(Exception):
    pass

def call(method, path, **params):
    url = path if path.startswith('http') else f'{BASE}/{path.lstrip("/")}'
    for attempt in range(4):
        r = requests.request(method, url, headers=HDR,
                             params=params if method == 'GET' else None,
                             data=params if method != 'GET' else None, timeout=60)
        if r.status_code in (429, 500, 502, 503) and attempt < 3:
            time.sleep(5 * 2 ** attempt); continue
        try:
            j = r.json()
        except Exception:
            raise ApiError(f'{r.status_code} {r.text[:300]}')
        if r.status_code >= 400 or 'error' in j:
            raise ApiError(json.dumps(j.get('error', j), ensure_ascii=False))
        return j

def ig_id():
    if CFG.get('ig_user_id'):
        return CFG['ig_user_id']
    me = call('GET', 'me', fields='user_id,username')
    CFG['ig_user_id'] = str(me['user_id']); CFG['username'] = me.get('username')
    json.dump(CFG, open(CFG_PATH, 'w'), ensure_ascii=False, indent=1)
    return CFG['ig_user_id']

def wait_ready(cid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = call('GET', cid, fields='status_code,status')
        if s.get('status_code') == 'FINISHED':
            return
        if s.get('status_code') in ('ERROR', 'EXPIRED'):
            raise ApiError(f'container {cid}: {s}')
        time.sleep(8)
    raise ApiError(f'container {cid} timeout')

def publish(post_dir, base_url):
    """post_dir/manifest.json: {"type":"carousel"|"reel"|"image", "media":[相対パス...], "cover":..., "caption":...}
    base_url: post_dir を指す公開URL（末尾スラッシュなし）"""
    m = json.load(open(os.path.join(post_dir, 'manifest.json'), encoding='utf-8'))
    uid = ig_id(); cap = m['caption']
    if m['type'] == 'carousel':
        kids = []
        for f in m['media']:
            c = call('POST', f'{uid}/media', image_url=f'{base_url}/{f}', is_carousel_item='true')
            kids.append(c['id'])
        for k in kids: wait_ready(k)
        c = call('POST', f'{uid}/media', media_type='CAROUSEL', children=','.join(kids), caption=cap)
    elif m['type'] == 'reel':
        p = dict(media_type='REELS', video_url=f'{base_url}/{m["media"][0]}', caption=cap, share_to_feed='true')
        if m.get('cover'): p['cover_url'] = f'{base_url}/{m["cover"]}'
        c = call('POST', f'{uid}/media', **p)
    else:
        c = call('POST', f'{uid}/media', image_url=f'{base_url}/{m["media"][0]}', caption=cap)
    wait_ready(c['id'], 900)
    pub = call('POST', f'{uid}/media_publish', creation_id=c['id'])
    info = call('GET', pub['id'], fields='id,permalink,timestamp,media_type,media_product_type')
    rec = {'media_id': info['id'], 'permalink': info.get('permalink'), 'timestamp': info.get('timestamp'),
           'type': m['type'], 'slug': os.path.basename(post_dir.rstrip('/')),
           'topic': m.get('topic'), 'hook': m.get('hook'), 'test': m.get('test')}
    log = os.path.join(ROOT, 'state', 'posts.json')
    posts = json.load(open(log, encoding='utf-8')) if os.path.exists(log) else []
    posts.append(rec)
    json.dump(posts, open(log, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(rec, ensure_ascii=False))
    return rec

def metrics(obj_id, names, **extra):
    """指標をまとめて取り、失敗したら1つずつ取り直す（アカウント種別などで使えない指標があるため）"""
    out = {}
    try:
        j = call('GET', f'{obj_id}/insights', metric=','.join(names), **extra)
        rows = j['data']
    except ApiError:
        rows = []
        for n in names:
            try:
                rows += call('GET', f'{obj_id}/insights', metric=n, **extra)['data']
            except ApiError as e:
                out[n] = None
    for row in rows:
        if 'total_value' in row:
            out[row['name']] = row['total_value'].get('value', row['total_value'])
        elif row.get('values'):
            out[row['name']] = row['values'][-1].get('value') if len(row['values']) == 1 else row['values']
    return out

POST_M = ['reach', 'views', 'likes', 'comments', 'shares', 'saved', 'total_interactions', 'follows', 'profile_visits']
REEL_M = ['reach', 'views', 'likes', 'comments', 'shares', 'saved', 'total_interactions',
          'ig_reels_avg_watch_time', 'ig_reels_video_view_total_time']

def insights():
    uid = ig_id()
    acct = call('GET', uid, fields='username,followers_count,follows_count,media_count')
    now = int(time.time())
    acct['day'] = metrics(uid, ['reach', 'views', 'accounts_engaged', 'total_interactions', 'follows_and_unfollows', 'profile_links_taps'],
                          period='day', metric_type='total_value', since=now - 86400, until=now)
    media = call('GET', f'{uid}/media', fields='id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count', limit=50)['data']
    posts = []
    for m in media:
        names = REEL_M if m.get('media_product_type') == 'REELS' else POST_M
        m['insights'] = metrics(m['id'], names)
        m['caption'] = (m.get('caption') or '')[:60]
        r = m['insights'].get('reach') or 0
        if r:
            for k in ('saved', 'shares', 'follows'):
                v = m['insights'].get(k)
                if v is not None: m['insights'][f'{k}_rate_%'] = round(100 * v / r, 2)
        posts.append(m)
    snap = {'taken_at': dt.datetime.now(JST).isoformat(), 'account': acct, 'media': posts}
    d = os.path.join(ROOT, 'state', 'insights'); os.makedirs(d, exist_ok=True)
    path = os.path.join(d, dt.datetime.now(JST).strftime('%Y-%m-%d') + '.json')
    json.dump(snap, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # 要約
    print(f"フォロワー {acct.get('followers_count')} / 投稿 {acct.get('media_count')} / 昨日: {acct['day']}")
    print('日時 | 種類 | リーチ | 保存 | シェア | フォロー | 平均視聴(ms) | 冒頭')
    for m in posts:
        i = m['insights']
        print(f"{m['timestamp'][:10]} | {m.get('media_product_type')} | {i.get('reach')} | {i.get('saved')} | {i.get('shares')} | "
              f"{i.get('follows')} | {i.get('ig_reels_avg_watch_time')} | {m['caption'][:24]}")
    print('saved:', path)

def comments(days=7):
    uid = ig_id(); me = CFG.get('username')
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    media = call('GET', f'{uid}/media', fields='id,timestamp,caption', limit=30)['data']
    todo = []
    for m in media:
        if dt.datetime.fromisoformat(m['timestamp'].replace('+0000', '+00:00')) < cutoff: continue
        cs = call('GET', f'{m["id"]}/comments', fields='id,text,username,timestamp,replies{username,text}', limit=50).get('data', [])
        for c in cs:
            if c.get('username') == me: continue
            reps = c.get('replies', {}).get('data', [])
            if any(r.get('username') == me for r in reps): continue
            todo.append({'comment_id': c['id'], 'post': (m.get('caption') or '')[:30], 'user': c.get('username'), 'text': c.get('text')})
    print(json.dumps(todo, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'whoami': print(call('GET', 'me', fields='user_id,username,account_type,followers_count,media_count'))
    elif cmd == 'limit': print(call('GET', f'{ig_id()}/content_publishing_limit', fields='config,quota_usage'))
    elif cmd == 'publish': publish(sys.argv[2], sys.argv[3])
    elif cmd == 'insights': insights()
    elif cmd == 'comments': comments(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
    elif cmd == 'reply': print(call('POST', f'{sys.argv[2]}/replies', message=sys.argv[3]))
    else: sys.exit(__doc__)
