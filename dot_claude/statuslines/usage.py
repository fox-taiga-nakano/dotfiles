#!/usr/bin/env python3
"""Pattern 4: Fine-grained progress bar with true color gradient"""
import json, sys, subprocess, os, re
import urllib.request, urllib.error
from datetime import datetime, timezone

# Claude Code がステータスライン描画時に JSON を stdin に渡す
raw = sys.stdin.read()
data = json.loads(raw)
# デバッグ用: 受信データをファイルに記録（確認後に削除）
try:
    with open(os.path.expanduser('~/.claude/.statusline_debug.json'), 'w') as _f:
        _f.write(raw)
except Exception:
    pass

# セッション開始直後はAPIからrate_limitsが返らないため、前回値をキャッシュして補完する
CACHE_FILE = os.path.expanduser('~/.claude/.statusline_rate_cache.json')

def load_cache():
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass

cache = load_cache()

# 1/8ブロック単位で滑らかに埋めるための文字列
BLOCKS = ' ▏▎▍▌▋▊▉█'
R = '\033[0m'   # リセット
DIM = '\033[2m' # 区切り文字を薄く表示するため

def gradient(pct):
    # 0%→緑、50%→黄、100%→赤 のグラデーションをRGBで生成
    if pct < 50:
        r = int(pct * 5.1)
        return f'\033[38;2;{r};200;80m'
    else:
        g = int(200 - (pct - 50) * 4)
        return f'\033[38;2;255;{max(g,0)};60m'

def bar(pct, width=10):
    # 1/8ブロック単位の滑らかなプログレスバーを生成
    pct = min(max(pct, 0), 100)
    filled = pct * width / 100
    full = int(filled)
    frac = int((filled - full) * 8)
    b = '█' * full
    if full < width:
        # 端数が0のときに空白が入るとバーが途切れて見えるので、未使用部分の░で埋める
        b += BLOCKS[frac] if frac else '░'
        b += '░' * (width - full - 1)
    return b

def fmt(label, pct, resets_at=None):
    # ラベル + バー + % + リセットまでの残り時間（実際のリセット時刻付き）を1セクションに整形
    p = round(pct)
    reset_str = ''
    if resets_at:
        try:
            reset_time_utc = datetime.fromtimestamp(resets_at, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = reset_time_utc - now
            total_sec = int(diff.total_seconds())
            if total_sec > 0:
                d = total_sec // 86400
                h = (total_sec % 86400) // 3600
                m = (total_sec % 3600) // 60
                if d > 0:
                    remain_str = f'{d}d{h}h'
                elif h > 0:
                    remain_str = f'{h}h{m:02d}m'
                else:
                    remain_str = f'{m}m'

                # 実際にリセットされる時刻（ローカルタイム）を併記
                # 当日中にリセットされる場合はHH:MM、日をまたぐ場合はMM/DD HH:MMで表示
                reset_time_local = reset_time_utc.astimezone()
                now_local = now.astimezone()
                if reset_time_local.date() != now_local.date():
                    at_str = reset_time_local.strftime('%m/%d %H:%M')
                else:
                    at_str = reset_time_local.strftime('%H:%M')

                # 残り時間は最大幅(例: 23h59m)に揃え、行をまたいでも「(」の位置をそろえる
                reset_str = f' \033[38;2;140;140;140m↺ {remain_str:<6} ({at_str}){R}'
        except Exception:
            pass
    # %は最大3桁(100%)で右寄せし、桁数が違っても後続の↺の位置をそろえる
    return f'{label} {gradient(pct)}{bar(pct)} {p:>3}%{R}{reset_str}'

# モデル名とGitブランチ
model = data.get('model', {}).get('display_name', 'Claude')
# 推論エフォート（low/medium/high など）をモデル名の横に薄く併記する
effort = (data.get('effort') or {}).get('level')
if effort:
    model = f'{model} {DIM}({effort}){R}'

cwd = data.get('cwd') or data.get('workspace', {}).get('current_dir', '')
branch = ''
if cwd:
    try:
        # カレントディレクトリのブランチを取得（タイムアウト2秒）
        result = subprocess.run(
            ['git', '-C', cwd, 'branch', '--show-current'],
            capture_output=True, text=True, timeout=2
        )
        branch = result.stdout.strip()
    except Exception:
        pass

BRANCH_COLOR = '\033[38;2;100;180;255m'
PR_COLOR = '\033[38;2;180;140;255m'
AHEAD_COLOR = '\033[38;2;140;140;140m'
INS_COLOR = '\033[38;2;100;220;100m'
DEL_COLOR = '\033[38;2;220;100;100m'
MOD_COLOR = '\033[38;2;220;200;100m'

# ブランチのahead/behind、差分行数、変更ファイル数
git_diff_str = ''
if cwd and branch:
    ahead = behind = insertions = deletions = changed = 0
    try:
        # upstream追跡ブランチが存在する場合のみahead/behindを取得
        ab = subprocess.run(
            ['git', '-C', cwd, 'rev-list', '--left-right', '--count', '@{u}...HEAD'],
            capture_output=True, text=True, timeout=2
        )
        if ab.returncode == 0:
            ab_parts = ab.stdout.strip().split()
            if len(ab_parts) == 2:
                behind, ahead = int(ab_parts[0]), int(ab_parts[1])
    except Exception:
        pass

    try:
        # HEADとの差分（staged + unstaged）から追加/削除行数を取得
        shortstat = subprocess.run(
            ['git', '-C', cwd, 'diff', '--shortstat', 'HEAD'],
            capture_output=True, text=True, timeout=2
        )
        ins_match = re.search(r'(\d+) insertion', shortstat.stdout)
        del_match = re.search(r'(\d+) deletion', shortstat.stdout)
        if ins_match:
            insertions = int(ins_match.group(1))
        if del_match:
            deletions = int(del_match.group(1))
    except Exception:
        pass

    try:
        status = subprocess.run(
            ['git', '-C', cwd, 'status', '--porcelain'],
            capture_output=True, text=True, timeout=2
        )
        changed = len([l for l in status.stdout.splitlines() if l.strip()])
    except Exception:
        pass

    segs = []
    if ahead:
        segs.append(f'{AHEAD_COLOR}⇡{ahead}{R}')
    if behind:
        segs.append(f'{AHEAD_COLOR}⇣{behind}{R}')
    if insertions:
        segs.append(f'{INS_COLOR}+{insertions}{R}')
    if deletions:
        segs.append(f'{DEL_COLOR}-{deletions}{R}')
    if changed:
        segs.append(f'{MOD_COLOR}!{changed}{R}')
    if segs:
        git_diff_str = ' '.join(segs)

# 現在のブランチに紐づくPR情報（gh未認証・PR未作成時はエラーにせず省略）
pr_str = ''
if cwd and branch:
    try:
        result = subprocess.run(
            ['gh', 'pr', 'view', '--json', 'number,title,url'],
            capture_output=True, text=True, timeout=3, cwd=cwd
        )
        if result.returncode == 0 and result.stdout.strip():
            pr_data = json.loads(result.stdout)
            pr_number = pr_data.get('number')
            pr_title = pr_data.get('title', '')
            if pr_number:
                pr_str = f'{PR_COLOR}#{pr_number} {pr_title}{R}'
    except Exception:
        pass

parts = [model]
if branch:
    parts[0] = f'{model}  {BRANCH_COLOR}{branch}{R}'
if git_diff_str:
    parts[0] = f'{parts[0]} {git_diff_str}'
if pr_str:
    parts[0] = f'{parts[0]}  {pr_str}'

# コンテキストウィンドウ使用率
ctx_pct = data.get('context_window', {}).get('used_percentage') or 0
parts.append(fmt('CTX', ctx_pct))

now_ts = datetime.now(timezone.utc).timestamp()

# 5時間レートリミット
five_data = data.get('rate_limits', {}).get('five_hour', {})
five_pct = five_data.get('used_percentage') or 0
five_reset = five_data.get('resets_at')
if five_reset:
    # 最新値をキャッシュに保存
    cache['five_reset'] = five_reset
    cache['five_pct'] = five_pct
    save_cache(cache)
else:
    # APIデータがなければキャッシュから補完（resets_atが期限切れなら破棄）
    cached_reset = cache.get('five_reset')
    if cached_reset and cached_reset > now_ts:
        five_reset = cached_reset
        five_pct = cache.get('five_pct', 0)
parts.append(fmt('5H', five_pct, five_reset))

# 7日間レートリミット
week_data = data.get('rate_limits', {}).get('seven_day', {})
week_pct = week_data.get('used_percentage') or 0
week_reset = week_data.get('resets_at')
if week_reset:
    # 最新値をキャッシュに保存
    cache['week_reset'] = week_reset
    cache['week_pct'] = week_pct
    save_cache(cache)
else:
    # APIデータがなければキャッシュから補完（resets_atが期限切れなら破棄）
    cached_reset = cache.get('week_reset')
    if cached_reset and cached_reset > now_ts:
        week_reset = cached_reset
        week_pct = cache.get('week_pct', 0)
parts.append(fmt('7D', week_pct, week_reset))


def live_window(pct, resets_at):
    # リセット時刻を過ぎたウィンドウは使用量0%として扱う
    if resets_at and resets_at > now_ts:
        return pct, resets_at
    return 0, None


def tail_lines(path, size=512 * 1024):
    # ログは大きくなり得るので末尾だけ読み、新しい行から順に返す
    with open(path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(f.tell() - size, 0))
        return reversed(f.read().decode('utf-8', 'ignore').splitlines())


def newest(paths, n=5):
    # 最も新しく更新されたファイルから順に返す
    try:
        return sorted(paths, key=os.path.getmtime, reverse=True)[:n]
    except Exception:
        return []


# 最終更新からこの秒数を過ぎたセッションは終了済みとみなし、CTX を「—」にする
CTX_STALE_SEC = 30 * 60


def is_stale(path):
    return now_ts - os.path.getmtime(path) > CTX_STALE_SEC


def codex_status():
    # Codex CLI はセッションログ(jsonl)の token_count イベントに
    # コンテキスト使用量(info)とアカウント単位の rate_limits を記録する
    base = os.path.expanduser('~/.codex/sessions')
    try:
        day_dirs = [os.path.join(base, y, m, d)
                    for y in sorted(os.listdir(base), reverse=True)[:2]
                    for m in sorted(os.listdir(os.path.join(base, y)), reverse=True)[:2]
                    for d in os.listdir(os.path.join(base, y, m))]
        files = [os.path.join(d, f) for d in sorted(day_dirs, reverse=True)[:3]
                 for f in os.listdir(d) if f.endswith('.jsonl')]
    except Exception:
        return None
    for path in newest(files):
        try:
            for line in tail_lines(path):
                if '"token_count"' not in line:
                    continue
                payload = json.loads(line).get('payload', {})
                if (payload.get('rate_limits') or {}).get('primary'):
                    # rate_limits はアカウント単位なので古くても使うが、CTX は古ければ捨てる
                    if is_stale(path):
                        payload['info'] = None
                    return payload
        except Exception:
            continue
    return None


def copilot_ctx():
    # Copilot CLI はセッションの events.jsonl に usage_record(入力トークン数と上限)を記録する
    files = [os.path.join(d.path, 'events.jsonl')
             for d in os.scandir(os.path.expanduser('~/.copilot/session-state'))
             if d.is_dir()] if os.path.isdir(os.path.expanduser('~/.copilot/session-state')) else []
    for path in newest([p for p in files if os.path.exists(p)]):
        # 新しい順に見ているので、古いファイルに到達したら以降も全て古い
        if is_stale(path):
            return None
        try:
            for line in tail_lines(path):
                if '"session.usage_record"' not in line:
                    continue
                usage = json.loads(line).get('data', {}).get('usage', {})
                if usage.get('maxPromptTokens'):
                    return usage['inputTokens'] * 100 / usage['maxPromptTokens']
        except Exception:
            continue
    return None


NET_TTL = 300  # ネットワーク呼び出しの結果は5分間キャッシュする


def codex_rate_limits():
    # Codex CLI の ChatGPT ログイン情報で、/status と同じ使用量 API を叩く
    auth_path = os.path.expanduser('~/.codex/auth.json')
    cached = cache.get('codex')
    try:
        # 再ログインで auth.json が更新されたら、TTL内でもキャッシュ(認証エラー含む)を捨てる
        fresh = (cached and now_ts - cached.get('fetched', 0) < NET_TTL
                 and os.path.getmtime(auth_path) < cached['fetched'])
    except OSError:
        fresh = False
    if fresh:
        return cached
    try:
        with open(auth_path) as f:
            tokens = json.load(f)['tokens']
        req = urllib.request.Request(
            'https://chatgpt.com/backend-api/wham/usage',
            headers={'Authorization': f'Bearer {tokens["access_token"]}',
                     'ChatGPT-Account-Id': tokens['account_id'],
                     'User-Agent': 'codex-cli'})
        with urllib.request.urlopen(req, timeout=3) as res:
            rl = json.load(res).get('rate_limit') or {}
        info = {'fetched': now_ts}
        for key, name in (('primary_window', 'primary'), ('secondary_window', 'secondary')):
            w = rl.get(key) or {}
            info[name] = {'used_percent': w.get('used_percent'), 'resets_at': w.get('reset_at')}
        cache['codex'] = info
        save_cache(cache)
        return info
    except urllib.error.HTTPError as e:
        if e.code not in (401, 403):
            return cached
        # トークン期限切れ等。古い値を出し続けると誤解を招くので認証エラーとして記録する
        cache['codex'] = {'fetched': now_ts, 'auth_error': True}
        save_cache(cache)
        return cache['codex']
    except Exception:
        # トークン期限切れ等で取得できなければ、前回値(期限切れはlive_windowで0%扱い)を使う
        return cached

def copilot_premium():
    # gh の認証で Copilot の premium requests 月次クォータを取得する
    cached = cache.get('copilot')
    if cached and now_ts - cached.get('fetched', 0) < NET_TTL:
        return cached
    try:
        result = subprocess.run(
            ['gh', 'api', '/copilot_internal/user'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode != 0:
            # 未ログイン(gh auth login を促す)やトークン無効(HTTP 401)は認証エラーとして記録する
            if 'HTTP 401' in result.stderr or 'gh auth login' in result.stderr:
                cache['copilot'] = {'fetched': now_ts, 'auth_error': True}
                save_cache(cache)
                return cache['copilot']
            return cached
        d = json.loads(result.stdout)
        snap = d.get('quota_snapshots', {}).get('premium_interactions') or {}
        if snap.get('unlimited') or 'percent_remaining' not in snap:
            return None
        reset_at = None
        if d.get('quota_reset_date_utc'):
            reset_at = datetime.fromisoformat(
                d['quota_reset_date_utc'].replace('Z', '+00:00')).timestamp()
        info = {'pct': 100 - snap['percent_remaining'], 'reset': reset_at, 'fetched': now_ts}
        cache['copilot'] = info
        save_cache(cache)
        return info
    except Exception:
        return cached


def na(label):
    # そのプロバイダに存在しない枠は薄い「—」で埋めて列を揃える
    return f'{label} {DIM}{"—":^10}{R}'


ERR_COLOR = '\033[38;2;255;90;90m'

def auth_err(label):
    # 認証エラーで使用量が取れない枠は赤字で明示する（バーと同じ10桁幅で列を揃える）
    return f'{label} {ERR_COLOR}{"auth error":^10}{R}'


# プロバイダごとに [CTX, 5H, 7D, (MO)] のセルを組み立てる
rows = [('Claude', parts[1:])]

# レートリミットはネットワークから取得し、失敗時のみセッションログの値で代替する。
# CTX はセッション固有の値なので常にログから読む
codex = codex_status()
codex_rl = codex_rate_limits() or (codex or {}).get('rate_limits')
if codex_rl:
    info = (codex or {}).get('info') or {}
    last = info.get('last_token_usage') or {}
    window = info.get('model_context_window')
    cells = [fmt('CTX', last.get('total_tokens', 0) * 100 / window) if window else na('CTX')]
    for key, name in (('primary', '5H'), ('secondary', '7D')):
        if codex_rl.get('auth_error'):
            cells.append(auth_err(name))
            continue
        w = codex_rl.get(key) or {}
        cells.append(fmt(name, *live_window(w.get('used_percent') or 0, w.get('resets_at'))))
    rows.append(('Codex', cells))

copilot = copilot_premium()
copilot_ctx_pct = copilot_ctx()
if copilot or copilot_ctx_pct is not None:
    # Copilot には 5H/7D 枠がないため、月次クォータ(MO)を2列目に置く
    cells = [fmt('CTX', copilot_ctx_pct) if copilot_ctx_pct is not None else na('CTX')]
    if copilot and copilot.get('auth_error'):
        cells.append(auth_err('MO'))
    elif copilot:
        cells.append(fmt('MO', *live_window(copilot['pct'], copilot.get('reset'))))
    rows.append(('Copilot', cells))

ANSI_RE = re.compile(r'\033\[[0-9;]*m')

def vis_len(s):
    return len(ANSI_RE.sub('', s))

# 列ごとの最大表示幅に合わせて右側をスペースで埋め、全行の区切り位置を揃える
widths = {}
for _, cells in rows:
    for i, c in enumerate(cells):
        widths[i] = max(widths.get(i, 0), vis_len(c))
label_w = max(len(name) for name, _ in rows)
SEP = f'{DIM}│{R}'

def render(name, cells):
    padded = [c + ' ' * (widths[i] - vis_len(c)) for i, c in enumerate(cells)]
    return f' {name:<{label_w}} ' + SEP.join(f' {c} ' for c in padded).rstrip()

# 1行目: モデル名とブランチ、2行目以降: プロバイダごとの使用量を薄い│で区切って出力
print(f' {parts[0]} ')
print('\n'.join(render(name, cells) for name, cells in rows), end='')
