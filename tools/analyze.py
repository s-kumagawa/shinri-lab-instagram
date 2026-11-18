"""改善ループの集計・診断ツール。  python3 tools/analyze.py
入力: state/posts.json（投稿の記録とラベル）、state/insights/*.json（毎日の数字）、state/experiments.json（仮説と実験）
出力:
  - state/posts.json の各投稿に d1 / d3 / d7 の数字を自動で書き込む（24h / 72h / 168h 以降の最初の記録）
  - reports/scoreboard.md … 最新の投稿の診断、投稿一覧、企画別・変数別の比較、実験の途中経過、次の打ち手の候補
指標（すべてリーチあたり。リールのフォローは API で取れないため、投稿翌日のフォロワー増減で代用）:
  完走率 = 平均視聴秒 / 動画の長さ、再生/リーチ（くり返し再生）、いいね率、コメント率、保存率、シェア率、
  反応スコア = (いいね + 2×コメント + 3×保存 + 4×シェア) / リーチ × 100"""
import json, os, glob, statistics as st, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = dt.timezone(dt.timedelta(hours=9))
CHECKS = [('d1', 20), ('d3', 68), ('d7', 164)]  # 時間（少し早めでも可）
SERIES_JA = {'quiz': '3秒心理クイズ', 'myth': 'それ、ウソです', 'choice': 'あなたならどっち？', 'ngok': 'NG→OK言いかえ',
             'people': '〇〇な人の心理', 'ranking': '週間ランキング', 'legacy_reel': '旧リール', 'legacy_carousel': '旧カルーセル'}


def ts(s):
    return dt.datetime.fromisoformat(s.replace('+0000', '+00:00'))


def load():
    posts = json.load(open(f'{ROOT}/state/posts.json', encoding='utf-8'))
    snaps = []
    for f in sorted(glob.glob(f'{ROOT}/state/insights/*.json')):
        s = json.load(open(f, encoding='utf-8')); s['_t'] = ts(s['taken_at']); snaps.append(s)
    snaps.sort(key=lambda s: s['_t'])
    exp_path = f'{ROOT}/state/experiments.json'
    exps = json.load(open(exp_path, encoding='utf-8')) if os.path.exists(exp_path) else []
    return posts, snaps, exps


def duration_of(p):
    if p.get('duration'): return p['duration']
    mf = f"{ROOT}/posts/{p['slug']}/manifest.json"
    if os.path.exists(mf):
        return json.load(open(mf, encoding='utf-8')).get('duration')


def series_of(p):
    return p.get('series') or ('legacy_carousel' if p['type'] == 'carousel' else 'legacy_reel')


def derive(raw, dur):
    """生の数字から比較用の指標を作る"""
    if raw is None: return None
    r = raw.get('reach') or 0
    g = lambda k: raw.get(k) or 0
    out = {'reach': r, 'views': g('views'), 'likes': g('likes'), 'comments': g('comments'),
           'saved': g('saved'), 'shares': g('shares')}
    aw = raw.get('ig_reels_avg_watch_time') or raw.get('avg_watch_ms')
    out['avg_watch_s'] = round(aw / 1000, 1) if aw else None
    out['completion_%'] = round(100 * aw / 1000 / dur, 1) if aw and dur else None
    if r:
        out['views_per_reach'] = round(g('views') / r, 2)
        for k in ('likes', 'comments', 'saved', 'shares'):
            out[f'{k}_rate_%'] = round(100 * g(k) / r, 2)
        out['score'] = round(100 * (g('likes') + 2 * g('comments') + 3 * g('saved') + 4 * g('shares')) / r, 2)
    else:
        out['views_per_reach'] = None; out['score'] = None
        for k in ('likes', 'comments', 'saved', 'shares'): out[f'{k}_rate_%'] = None
    return out


def fill_checkpoints(posts, snaps):
    """各投稿の d1/d3/d7 と最新値、投稿翌日のフォロワー増減を計算"""
    for p in posts:
        t0 = ts(p['timestamp']); dur = duration_of(p)
        if dur and not p.get('duration'): p['duration'] = dur
        p['_latest'] = None
        for s in snaps:
            m = next((x for x in s['media'] if x['id'] == p['media_id']), None)
            if not m: continue
            age_h = (s['_t'] - t0).total_seconds() / 3600
            raw = dict(m['insights']); raw['taken_at'] = s['taken_at'][:16]
            p['_latest'] = raw
            for key, h in CHECKS:
                old = p.get(key) or {}
                if age_h >= h and not old.get('auto'):
                    p[key] = {'auto': True, 'age_h': round(age_h), 'measured_at': s['taken_at'][:16],
                              **{k: raw.get(k) for k in ('reach', 'views', 'likes', 'comments', 'saved', 'shares', 'follows',
                                                          'profile_visits', 'ig_reels_avg_watch_time')}}
        # フォロワー増減：投稿直前の記録 → 投稿から24h以降の最初の記録
        before = [s for s in snaps if s['_t'] <= t0]; after = [s for s in snaps if (s['_t'] - t0).total_seconds() >= 20 * 3600]
        if before and after:
            p['follower_delta_d1'] = after[0]['account']['followers_count'] - before[-1]['account']['followers_count']


def metrics_for(p, key='d1'):
    raw = p.get(key) or (p.get('_latest') if key == 'latest' else None)
    return derive(raw, p.get('duration'))


def med(vals):
    v = [x for x in vals if x is not None]
    return round(st.median(v), 2) if v else None


KEYS = ['reach', 'completion_%', 'views_per_reach', 'likes_rate_%', 'comments_rate_%', 'saved_rate_%', 'shares_rate_%', 'score']
LABEL = {'reach': 'リーチ', 'completion_%': '完走率%', 'views_per_reach': '再生/リーチ', 'likes_rate_%': 'いいね率%',
         'comments_rate_%': 'コメント率%', 'saved_rate_%': '保存率%', 'shares_rate_%': 'シェア率%', 'score': '反応スコア'}


def diagnose(m, base):
    """ファネルのどこで落ちたかを判定（基準＝直近のリールの中央値）"""
    if not m: return '数字がまだない（投稿後24時間未満）'
    out = []
    def ratio(k):
        b = base.get(k)
        return (m.get(k) or 0) / b if b else None
    rr, cr, sc = ratio('reach'), ratio('completion_%'), ratio('score')
    if m['reach'] == 0:
        return '【配信ゼロ】誰にも表示されていない。形式（カルーセル等）か投稿の不具合を疑う'
    if rr is not None and rr < 0.6: out.append(f'【配信が弱い】リーチが基準の{rr:.0%}。表紙・冒頭0.5秒・テーマの引きを疑う')
    elif rr is not None and rr > 1.5: out.append(f'【配信が強い】リーチが基準の{rr:.0%}。何が効いたかを仮説にする')
    if m.get('completion_%') is not None:
        if m['completion_%'] < 35: out.append(f'【離脱が早い】完走率{m["completion_%"]}%。冒頭〜2場面目で離れている')
        elif m['completion_%'] >= 60: out.append(f'【よく見られた】完走率{m["completion_%"]}%')
    if (m.get('score') or 0) == 0: out.append('【反応ゼロ】いいね・コメント・保存・シェアなし。呼びかけか中身の価値を疑う')
    elif sc is not None and sc > 1.5: out.append(f'【反応が強い】反応スコアが基準の{sc:.0%}')
    if (m.get('shares') or 0) > 0: out.append(f'【シェアあり】{m["shares"]}件。共感・送りたくなる要素が効いた可能性')
    if (m.get('saved') or 0) > 0: out.append(f'【保存あり】{m["saved"]}件。役立つ情報として評価された可能性')
    return ' / '.join(out) or '基準並み'


def compare(rows, keyfn):
    groups = {}
    for p, m in rows:
        k = keyfn(p)
        if k is None: continue
        groups.setdefault(k, []).append(m)
    out = []
    for k, ms in sorted(groups.items(), key=lambda kv: str(kv[0])):
        out.append((k, len(ms), {key: med([m.get(key) for m in ms]) for key in KEYS}))
    return out


def eval_experiment(e, rows):
    """実験の途中経過：control と treatment の中央値を比べる"""
    var, metric = e['variable'], e.get('metric', 'completion_%')
    arms = {'control': [], 'treatment': []}
    for p, m in rows:
        if p.get('hypothesis') != e['id'] and e['id'] not in (p.get('hypotheses') or []): continue
        v = (p.get('vars') or {}).get(var)
        if v == e['control']: arms['control'].append(m.get(metric))
        elif v == e['treatment']: arms['treatment'].append(m.get(metric))
    c, t = med(arms['control']), med(arms['treatment'])
    nc, nt = len([x for x in arms['control'] if x is not None]), len([x for x in arms['treatment'] if x is not None])
    need = e.get('min_n', 3); thr = e.get('threshold', 0.2)
    if nc < need or nt < need:
        verdict = f'データ不足（control {nc}/{need}・treatment {nt}/{need}）'
    elif not c:
        verdict = '基準が0のため比較不可'
    else:
        lift = t / c - 1
        verdict = (f'採用候補（{lift:+.0%}）' if lift >= thr else f'不採用候補（{lift:+.0%}）' if lift <= -thr
                   else f'差なし（{lift:+.0%}）→ 判定保留か打ち切り')
    return c, t, nc, nt, verdict


def fmt(v):
    return '–' if v is None else (f'{v:g}' if isinstance(v, (int, float)) else str(v))


def main():
    posts, snaps, exps = load()
    fill_checkpoints(posts, snaps)
    rows_d1 = [(p, metrics_for(p, 'd1')) for p in posts if p.get('d1')]
    reels = [(p, m) for p, m in rows_d1 if p['type'] == 'reel']
    base_pool = reels[-10:]
    base = {k: med([m.get(k) for _, m in base_pool]) for k in KEYS}
    L = []
    now = dt.datetime.now(JST).strftime('%Y-%m-%d %H:%M')
    L.append(f'# スコアボード（{now} JST 更新）\n')
    L.append('毎日 `python3 tools/analyze.py` で自動更新。数字は**初日（d1＝投稿から約24時間）**で比べる。基準＝直近リール最大10本の中央値。\n')
    # KPI
    fol = [(s['taken_at'][:10], s['account']['followers_count']) for s in snaps]
    if fol:
        last7 = fol[-8:]
        L.append('## KPI')
        L.append(f'- フォロワー：{fol[-1][1]}（7日前比 {fol[-1][1] - last7[0][1]:+d}）　推移：' + ' → '.join(str(v) for _, v in last7))
        L.append('- 基準（直近リールの初日中央値）：' + '、'.join(f'{LABEL[k]} {fmt(base[k])}' for k in KEYS) + '\n')
    # 最新投稿の診断
    L.append('## 直近の投稿の診断')
    for p in posts[-3:]:
        m = metrics_for(p, 'd1')
        L.append(f"- **{p['slug']}**（{SERIES_JA.get(series_of(p), series_of(p))}）：{diagnose(m, base)}")
    L.append('')
    # 投稿一覧
    L.append('## 投稿一覧（初日）')
    L.append('| 投稿 | 企画 | 変数 | 実験 | リーチ | 完走率% | 再生/リーチ | いいね | コメント | 保存 | シェア | 反応スコア | フォロワー増減 |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for p in posts:
        m = metrics_for(p, 'd1') or {}
        vs = ', '.join(f'{k}={v}' for k, v in (p.get('vars') or {}).items()) or '–'
        L.append(f"| {p['slug']} | {SERIES_JA.get(series_of(p), series_of(p))} | {vs} | {p.get('hypothesis') or '–'} | {fmt(m.get('reach'))} | "
                 f"{fmt(m.get('completion_%'))} | {fmt(m.get('views_per_reach'))} | {fmt(m.get('likes'))} | {fmt(m.get('comments'))} | "
                 f"{fmt(m.get('saved'))} | {fmt(m.get('shares'))} | {fmt(m.get('score'))} | {fmt(p.get('follower_delta_d1'))} |")
    L.append('')
    # 企画別
    def table(title, groups):
        L.append(f'## {title}')
        L.append('| 区分 | 本数 | ' + ' | '.join(LABEL[k] for k in KEYS) + ' |')
        L.append('|---|---|' + '---|' * len(KEYS))
        for k, n, md in groups:
            L.append(f'| {SERIES_JA.get(k, k)} | {n} | ' + ' | '.join(fmt(md[x]) for x in KEYS) + ' |')
        L.append('')
    table('企画別（初日の中央値）', compare(rows_d1, series_of))
    allvars = sorted({k for p, _ in rows_d1 for k in (p.get('vars') or {})})
    for v in allvars:
        table(f'変数別：{v}', compare(rows_d1, lambda p, v=v: (p.get('vars') or {}).get(v)))
    table('テーマ別', compare(rows_d1, lambda p: p.get('topic')))
    # 実験
    L.append('## 実験（state/experiments.json）')
    L.append('| ID | 状態 | 仮説 | 変数 | control → treatment | 指標 | control | treatment | 途中経過 |')
    L.append('|---|---|---|---|---|---|---|---|---|')
    for e in exps:
        if e.get('status') in ('running', 'backlog'):
            c, t, nc, nt, v = eval_experiment(e, rows_d1) if e['status'] == 'running' else (None, None, 0, 0, '未開始')
        else:
            c, t, v = None, None, e.get('result', '')
        L.append(f"| {e['id']} | {e['status']} | {e['hypothesis']} | {e['variable']} | {e['control']} → {e['treatment']} | "
                 f"{LABEL.get(e.get('metric'), e.get('metric'))} | {fmt(c)} | {fmt(t)} | {v} |")
    L.append('')
    # 打ち手の候補（ルールベースの気づき。判断は運用担当が行う）
    L.append('## 自動で出た気づき（仮説づくりの材料）')
    hints = []
    if base.get('completion_%') is not None and base['completion_%'] < 35:
        hints.append(f"完走率の基準が{base['completion_%']}%と低い → 冒頭2秒・テンポ・長さの実験を優先")
    if all((m.get('saved') or 0) == 0 and (m.get('shares') or 0) == 0 for _, m in rows_d1[-7:]):
        hints.append('直近7本で保存・シェアが0 → 「あとで使える」「友達に送りたい」要素の実験を優先')
    sg = compare(rows_d1, series_of)
    sg2 = [g for g in sg if g[1] >= 2]
    if len(sg2) >= 2:
        best = max(sg2, key=lambda g: (g[2]['score'] or 0, g[2]['reach'] or 0))
        if (best[2]['score'] or 0) > 0: hints.append(f"反応スコアが最も高い企画：{SERIES_JA.get(best[0], best[0])}（{best[1]}本）→ 頻度を増やす候補")
    for p, m in rows_d1[-7:]:
        if m and base.get('reach') and m['reach'] > 1.5 * base['reach']:
            hints.append(f"{p['slug']} のリーチが基準の1.5倍超 → 何が違ったか（テーマ・冒頭・表紙）を仮説にする")
    L += [f'- {h}' for h in hints] or ['- 特になし']
    L.append('')
    os.makedirs(f'{ROOT}/reports', exist_ok=True)
    open(f'{ROOT}/reports/scoreboard.md', 'w', encoding='utf-8').write('\n'.join(L))
    for p in posts: p.pop('_latest', None)
    json.dump(posts, open(f'{ROOT}/state/posts.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n'.join(L[:L.index('## 投稿一覧（初日）')]))
    print('→ reports/scoreboard.md を更新')


if __name__ == '__main__':
    main()
