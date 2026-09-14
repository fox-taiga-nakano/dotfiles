#!/usr/bin/env python3
"""Pattern 4: Fine-grained progress bar with true color gradient"""
import json, sys, subprocess, os, re
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
        b += BLOCKS[frac]
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

                reset_str = f' \033[38;2;140;140;140m↺ {remain_str} ({at_str}){R}'
        except Exception:
            pass
    return f'{label} {gradient(pct)}{bar(pct)} {p}%{R}{reset_str}'

# モデル名とGitブランチ
model = data.get('model', {}).get('display_name', 'Claude')

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

# 1行目: モデル名とブランチ、2行目: ctx/5h/7d を薄い│で区切って出力
header = parts[0]
metrics = parts[1:]
print(f' {header} ')
print(f'{DIM}│{R}'.join(f' {p} ' for p in metrics), end='')
