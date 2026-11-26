#!/usr/bin/env python3
"""Claude Code ステータスライン

1行目: モデル名・エフォート・Gitブランチ・差分・PR
2行目以降: Claude / Codex / Antigravity / Copilot の使用量を列をそろえた表で表示する
"""
import json, sys, subprocess, os, re, shutil
import urllib.request, urllib.error
from datetime import datetime, timezone

HOME = os.path.expanduser('~')
CACHE_FILE = f'{HOME}/.claude/.statusline_rate_cache.json'
DEBUG_FILE = f'{HOME}/.claude/.statusline_debug.json'
CODEX_AUTH = f'{HOME}/.codex/auth.json'
CODEX_SESSIONS = f'{HOME}/.codex/sessions'
COPILOT_SESSIONS = f'{HOME}/.copilot/session-state'
ANTIGRAVITY_AUTH = f'{HOME}/.gemini/antigravity-cli/antigravity-oauth-token'
ANTIGRAVITY_USAGE = f'{HOME}/.claude/.statusline_antigravity_usage.json'

NET_TTL = 300             # ネットワーク呼び出しの結果は5分間キャッシュする
CTX_STALE_SEC = 30 * 60   # 最終更新からこれを過ぎたセッションは終了済みとみなし CTX を「—」にする
BAR_WIDTH = 10

now_ts = datetime.now(timezone.utc).timestamp()

# ---------------------------------------------------------------- 色・描画

R = '\033[0m'
DIM = '\033[2m'
GRAY = '\033[38;2;140;140;140m'
BRANCH_COLOR = '\033[38;2;100;180;255m'
PR_COLOR = '\033[38;2;180;140;255m'
INS_COLOR = '\033[38;2;100;220;100m'
DEL_COLOR = '\033[38;2;220;100;100m'
MOD_COLOR = '\033[38;2;220;200;100m'
ERR_COLOR = '\033[38;2;255;90;90m'

# 1/8ブロック単位で滑らかに埋めるための文字列
BLOCKS = ' ▏▎▍▌▋▊▉█'
ANSI_RE = re.compile(r'\033\[[0-9;]*m')


def gradient(pct):
    # 0%→緑、50%→黄、100%→赤 のグラデーション
    if pct < 50:
        return f'\033[38;2;{int(pct * 5.1)};200;80m'
    return f'\033[38;2;255;{max(int(200 - (pct - 50) * 4), 0)};60m'


def bar(pct):
    pct = min(max(pct, 0), 100)
    filled = pct * BAR_WIDTH / 100
    full = int(filled)
    frac = int((filled - full) * 8)
    b = '█' * full
    if full < BAR_WIDTH:
        # 端数が0のときに空白が入るとバーが途切れて見えるので、未使用部分の░で埋める
        b += BLOCKS[frac] if frac else '░'
        b += '░' * (BAR_WIDTH - full - 1)
    return b


def reset_label(resets_at):
    # 「↺ 残り時間 (リセット時刻)」。当日中ならHH:MM、日をまたぐならMM/DD HH:MM
    total = int(resets_at - now_ts)
    if total <= 0:
        return ''
    d, h, m = total // 86400, total % 86400 // 3600, total % 3600 // 60
    remain = f'{d}d{h}h' if d else f'{h}h{m:02d}m' if h else f'{m}m'
    at = datetime.fromtimestamp(resets_at).astimezone()
    at_str = at.strftime('%H:%M' if at.date() == datetime.now().astimezone().date() else '%m/%d %H:%M')
    # 残り時間は最大幅(例: 23h59m)に揃え、行をまたいでも「(」の位置をそろえる
    return f' {GRAY}↺ {remain:<6} ({at_str}){R}'


def fmt(label, pct, resets_at=None):
    # %は最大3桁(100%)で右寄せし、桁数が違っても後続の↺の位置をそろえる
    reset = reset_label(resets_at) if resets_at else ''
    return f'{label} {gradient(pct)}{bar(pct)} {round(pct):>3}%{R}{reset}'


def na(label):
    # そのプロバイダに存在しない枠は薄い「—」で埋めて列を揃える
    return f'{label} {DIM}{"—":^{BAR_WIDTH}}{R}'


def auth_err(label):
    # 認証エラーで使用量が取れない枠は赤字で明示する
    return f'{label} {ERR_COLOR}{"auth error":^{BAR_WIDTH}}{R}'


def live_window(pct, resets_at):
    # リセット時刻を過ぎたウィンドウは使用量0%として扱う
    if resets_at and resets_at > now_ts:
        return pct, resets_at
    return 0, None


def vis_len(s):
    return len(ANSI_RE.sub('', s))

# ---------------------------------------------------------------- 共通ユーティリティ


def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass


def run(cmd, timeout=2, **kw):
    # 失敗・タイムアウト時は None を返す
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    except Exception:
        return None


def is_fresh(entry, invalidated_by=None):
    # ネットワーク取得結果のキャッシュが有効か。依存ファイルが後から更新されていたら無効
    if not entry or now_ts - entry.get('fetched', 0) >= NET_TTL:
        return False
    try:
        return not invalidated_by or os.path.getmtime(invalidated_by) < entry['fetched']
    except OSError:
        return False


def tail_lines(path, size=512 * 1024):
    # ログは大きくなり得るので末尾だけ読み、新しい行から順に返す
    with open(path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(f.tell() - size, 0))
        return reversed(f.read().decode('utf-8', 'ignore').splitlines())


def newest(paths, n=5):
    try:
        return sorted(paths, key=os.path.getmtime, reverse=True)[:n]
    except Exception:
        return []


def is_stale(path):
    return now_ts - os.path.getmtime(path) > CTX_STALE_SEC

# ---------------------------------------------------------------- 1行目: モデル・Git・PR


def header(data):
    model = data.get('model', {}).get('display_name', 'Claude')
    effort = (data.get('effort') or {}).get('level')
    if effort:
        model = f'{model} {DIM}({effort}){R}'

    cwd = data.get('cwd') or data.get('workspace', {}).get('current_dir', '')
    res = run(['git', '-C', cwd, 'branch', '--show-current']) if cwd else None
    branch = res.stdout.strip() if res else ''
    if not branch:
        return model

    line = f'{model}  {BRANCH_COLOR}{branch}{R}'
    diff = git_diff_summary(cwd)
    if diff:
        line += f' {diff}'
    pr = pr_summary(cwd)
    if pr:
        line += f'  {pr}'
    return line


def git_diff_summary(cwd):
    # ahead/behind、追加/削除行数(staged + unstaged)、変更ファイル数
    ahead = behind = insertions = deletions = 0
    res = run(['git', '-C', cwd, 'rev-list', '--left-right', '--count', '@{u}...HEAD'])
    if res and res.returncode == 0:  # upstream追跡ブランチがある場合のみ
        nums = res.stdout.split()
        if len(nums) == 2:
            behind, ahead = map(int, nums)

    res = run(['git', '-C', cwd, 'diff', '--shortstat', 'HEAD'])
    if res:
        if m := re.search(r'(\d+) insertion', res.stdout):
            insertions = int(m.group(1))
        if m := re.search(r'(\d+) deletion', res.stdout):
            deletions = int(m.group(1))

    res = run(['git', '-C', cwd, 'status', '--porcelain'])
    changed = len([l for l in res.stdout.splitlines() if l.strip()]) if res else 0

    segs = [(ahead, GRAY, '⇡'), (behind, GRAY, '⇣'), (insertions, INS_COLOR, '+'),
            (deletions, DEL_COLOR, '-'), (changed, MOD_COLOR, '!')]
    return ' '.join(f'{color}{mark}{n}{R}' for n, color, mark in segs if n)


def pr_summary(cwd):
    # gh未認証・PR未作成時は省略する
    res = run(['gh', 'pr', 'view', '--json', 'number,title'], timeout=3, cwd=cwd)
    if not res or res.returncode != 0 or not res.stdout.strip():
        return ''
    try:
        pr = json.loads(res.stdout)
    except Exception:
        return ''
    return f'{PR_COLOR}#{pr["number"]} {pr.get("title", "")}{R}' if pr.get('number') else ''

# ---------------------------------------------------------------- Claude


def claude_cells(data, cache):
    cells = [fmt('CTX', data.get('context_window', {}).get('used_percentage') or 0)]
    # セッション開始直後は rate_limits が返らないため、前回値をキャッシュして補完する
    for key, name, ck in (('five_hour', '5H', 'five'), ('seven_day', '7D', 'week')):
        w = data.get('rate_limits', {}).get(key, {})
        pct, reset = w.get('used_percentage') or 0, w.get('resets_at')
        if reset:
            cache[f'{ck}_reset'], cache[f'{ck}_pct'] = reset, pct
        elif (cache.get(f'{ck}_reset') or 0) > now_ts:  # 期限切れのキャッシュは使わない
            reset, pct = cache[f'{ck}_reset'], cache.get(f'{ck}_pct', 0)
        cells.append(fmt(name, pct, reset))
    return cells

# ---------------------------------------------------------------- Codex


def codex_log():
    # Codex CLI はセッションログ(jsonl)の token_count イベントに
    # コンテキスト使用量(info)とアカウント単位の rate_limits を記録する
    try:
        base = CODEX_SESSIONS
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


def codex_rate_limits(cache):
    # Codex CLI の ChatGPT ログイン情報で、/status と同じ使用量 API を叩く。
    # 再ログインで auth.json が更新されたら TTL 内でも取り直す
    cached = cache.get('codex')
    if is_fresh(cached, invalidated_by=CODEX_AUTH):
        return cached
    try:
        tokens = load_json(CODEX_AUTH)['tokens']
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
    except urllib.error.HTTPError as e:
        if e.code not in (401, 403):
            return cached
        # トークン期限切れ等。古い値を出し続けると誤解を招くので認証エラーとして記録する
        info = {'fetched': now_ts, 'auth_error': True}
    except Exception:
        # 一時的な失敗は前回値(期限切れは live_window で0%扱い)を使う
        return cached
    cache['codex'] = info
    return info


def codex_cells(cache):
    # レートリミットはネットワークから取得し、失敗時のみセッションログの値で代替する。
    # CTX はセッション固有の値なので常にログから読む
    log = codex_log() or {}
    rl = codex_rate_limits(cache) or log.get('rate_limits')
    if not rl:
        return None
    info = log.get('info') or {}
    window = info.get('model_context_window')
    used = (info.get('last_token_usage') or {}).get('total_tokens', 0)
    cells = [fmt('CTX', used * 100 / window) if window else na('CTX')]
    for key, name in (('primary', '5H'), ('secondary', '7D')):
        if rl.get('auth_error'):
            cells.append(auth_err(name))
        else:
            w = rl.get(key) or {}
            cells.append(fmt(name, *live_window(w.get('used_percent') or 0, w.get('resets_at'))))
    return cells

# ---------------------------------------------------------------- Copilot


def copilot_ctx():
    # Copilot CLI はセッションの events.jsonl に usage_record(入力トークン数と上限)を記録する
    if not os.path.isdir(COPILOT_SESSIONS):
        return None
    files = [os.path.join(d.path, 'events.jsonl') for d in os.scandir(COPILOT_SESSIONS) if d.is_dir()]
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


def copilot_premium(cache):
    # gh の認証で Copilot の premium requests 月次クォータを取得する
    cached = cache.get('copilot')
    if is_fresh(cached):
        return cached
    res = run(['gh', 'api', '/copilot_internal/user'], timeout=3)
    if not res:
        return cached
    if res.returncode != 0:
        # 未ログイン(gh auth login を促す)やトークン無効(HTTP 401)は認証エラーとして記録する
        if 'HTTP 401' in res.stderr or 'gh auth login' in res.stderr:
            cache['copilot'] = {'fetched': now_ts, 'auth_error': True}
            return cache['copilot']
        return cached
    try:
        d = json.loads(res.stdout)
        snap = d.get('quota_snapshots', {}).get('premium_interactions') or {}
        if snap.get('unlimited') or 'percent_remaining' not in snap:
            return None
        reset_at = None
        if d.get('quota_reset_date_utc'):
            reset_at = datetime.fromisoformat(d['quota_reset_date_utc'].replace('Z', '+00:00')).timestamp()
    except Exception:
        return cached
    cache['copilot'] = {'pct': 100 - snap['percent_remaining'], 'reset': reset_at, 'fetched': now_ts}
    return cache['copilot']


def copilot_cells(cache):
    premium = copilot_premium(cache)
    ctx = copilot_ctx()
    if not premium and ctx is None:
        return None
    # Copilot には 5H/7D 枠がないため、月次クォータ(MO)を2列目に置く
    cells = [fmt('CTX', ctx) if ctx is not None else na('CTX')]
    if premium and premium.get('auth_error'):
        cells.append(auth_err('MO'))
    elif premium:
        cells.append(fmt('MO', *live_window(premium['pct'], premium.get('reset'))))
    return cells

# ---------------------------------------------------------------- Antigravity


def antigravity_refresh(cache):
    # Antigravity CLI の `agy -p /usage` は /usage と同じ公式の残量を返す(クォータは消費しない)。
    # 起動に数秒かかり描画を止めてしまうので、バックグラウンドで実行して結果をファイルに書かせる
    try:
        last = os.path.getmtime(ANTIGRAVITY_USAGE)
    except OSError:
        last = 0
    if now_ts - max(last, cache.get('antigravity_started', 0)) < NET_TTL:
        return
    agy = shutil.which('agy')
    if not agy:
        return
    # 失敗時も TTL 内は再実行しないよう、起動時刻を記録する
    cache['antigravity_started'] = now_ts
    try:
        subprocess.Popen(
            ['sh', '-c', '"$0" -p /usage --output-format json > "$1.tmp" && mv "$1.tmp" "$1"',
             agy, ANTIGRAVITY_USAGE],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
    except Exception:
        pass


def antigravity_cells(cache):
    if not os.path.exists(ANTIGRAVITY_AUTH):
        return None
    antigravity_refresh(cache)
    try:
        groups = load_json(ANTIGRAVITY_USAGE)['command']['data']['groups']
    except Exception:
        return None
    # CTX は取得元が未調査のため「—」で表示する
    cells = [na('CTX')]
    # クォータはモデルグループ単位(Gemini / Claude・GPT)。列名は bucket id の先頭(gemini-weekly→GEM, 3p-weekly→3P)
    for g in groups:
        for b in g.get('buckets') or []:
            label = b.get('id', '?').split('-')[0].upper()[:3]
            pct = (1 - (b.get('remaining_fraction') or 0)) * 100
            reset = b.get('reset_time')
            reset = datetime.fromisoformat(reset.replace('Z', '+00:00')).timestamp() if reset else None
            cells.append(fmt(label, *live_window(pct, reset)))
    return cells

# ---------------------------------------------------------------- 出力


def render_table(rows):
    # 列ごとの最大表示幅に合わせて右側をスペースで埋め、全行の区切り位置を揃える
    widths = {}
    for _, cells in rows:
        for i, c in enumerate(cells):
            widths[i] = max(widths.get(i, 0), vis_len(c))
    label_w = max(len(name) for name, _ in rows)
    sep = f'{DIM}│{R}'
    lines = []
    for name, cells in rows:
        padded = [c + ' ' * (widths[i] - vis_len(c)) for i, c in enumerate(cells)]
        lines.append(f' {name:<{label_w}} ' + sep.join(f' {c} ' for c in padded).rstrip())
    return '\n'.join(lines)


def main():
    # Claude Code がステータスライン描画時に JSON を stdin に渡す
    raw = sys.stdin.read()
    data = json.loads(raw)
    # デバッグ用: 受信データをファイルに記録（確認後に削除）
    try:
        with open(DEBUG_FILE, 'w') as f:
            f.write(raw)
    except Exception:
        pass

    cache = load_json(CACHE_FILE, {})
    rows = [('Claude', claude_cells(data, cache))]
    for name, build in (('Codex', codex_cells), ('Antigravity', antigravity_cells),
                        ('Copilot', copilot_cells)):
        cells = build(cache)
        if cells:
            rows.append((name, cells))
    save_cache(cache)

    print(f' {header(data)} ')
    print(render_table(rows), end='')


if __name__ == '__main__':
    main()
