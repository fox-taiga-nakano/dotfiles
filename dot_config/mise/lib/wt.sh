# shellcheck shell=bash
# worktree タスク (~/.config/mise/tasks/wt/*) の共通処理。各タスクが source する
#
# 設定はメインのチェックアウトの .herdr/worktree.json (worktree からも常にメイン側を読む)。項目はすべて省略可。
#   sync       メインから worktree にコピーするパスの配列 (glob 可。末尾 / はディレクトリごと置き換え)
#   slot_step  ポート = port + slot × slot_step (slot はメイン 0、worktree 1〜9。<worktree>/.ports.env の PORT_SLOT)
#   services   { "<名前>": { "port": <既定ポート>, "cmd": "<wt:serve で起動するコマンド (任意)>" } }
#   env_files  [{ "file", "key", "value" }]。value の {サービス名} をそのサービスのポートに置き換えて書き込む
#   serve      wt:serve で services の cmd と並べて起動する共通コマンド
#   hooks      { "post_create" | "post_sync" | "pre_serve" | "pre_remove": ["<シェルコマンド>", ...] }
#              対象チェックアウトのルートで bash -c で順に実行し、失敗したら止まる
# フック・serve のコマンドでは WT_PATH / WT_MAIN / WT_SLOT / WT_PORT_<サービス名 (大文字・- は _)> が使える

WT_HOOKS="post_create post_sync pre_serve pre_remove"

wt_die() { echo "$*" >&2; exit 1; }

# WT_PATH (対象チェックアウトのルート)・WT_MAIN・WT_CONFIG を設定する
wt_load() {
  WT_PATH="$(cd "${1:-.}" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)" || wt_die "git のチェックアウトではありません: ${1:-.}"
  WT_MAIN="$(dirname "$(git -C "$WT_PATH" rev-parse --path-format=absolute --git-common-dir)")"
  WT_CONFIG="$WT_MAIN/.herdr/worktree.json"
}

wt_has_config() { [ -f "$WT_CONFIG" ]; }

wt_require_config() {
  wt_has_config || wt_die "設定がありません: $WT_CONFIG"
  local err
  err="$(jq -e '
    def fail($m): error($m);
    def strings: type == "array" and all(.[]; type == "string");
    if type != "object" then fail("トップレベルはオブジェクトにしてください") else . end
    | if has("sync") and (.sync | strings | not) then fail("sync は文字列の配列にしてください") else . end
    | if has("services") and (.services | type != "object") then fail("services はオブジェクトにしてください") else . end
    | (.services // {} | to_entries[]
        | if (.key | test("^[A-Za-z0-9_-]+$") | not) then fail("サービス名は英数字・_・- にしてください: \(.key)")
          elif (.value.port | type != "number") then fail("services.\(.key).port は数値にしてください")
          elif (.value | has("cmd")) and (.value.cmd | type != "string") then fail("services.\(.key).cmd は文字列にしてください")
          else . end) as $_
    | if (.services // {} | length > 0) and (.slot_step | type != "number") then fail("services があるときは slot_step (数値) が必要です") else . end
    | if has("env_files") and (.env_files | type == "array" and all(.[]; (.file | type == "string") and (.key | type == "string") and (.value | type == "string")) | not)
      then fail("env_files は { file, key, value } (すべて文字列) の配列にしてください") else . end
    | if has("serve") and (.serve | type != "string") then fail("serve は文字列にしてください") else . end
    | if has("hooks") and (.hooks | type != "object") then fail("hooks はオブジェクトにしてください") else . end
    | (.hooks // {} | to_entries[]
        | if ([.key] | inside($hooks | split(" ")) | not) then fail("未知のフックです: \(.key) (\($hooks))")
          elif (.value | strings | not) then fail("hooks.\(.key) は文字列の配列にしてください")
          else . end) as $_
    | true
  ' --arg hooks "$WT_HOOKS" "$WT_CONFIG" 2>&1 >/dev/null)" || wt_die "$WT_CONFIG: $(sed -E 's/^jq: error \(at [^)]*\): //' <<<"$err")"
}

wt_cfg() { jq -r "$@" "$WT_CONFIG"; }

wt_has_services() { [ "$(wt_cfg '.services // {} | length')" -gt 0 ]; }

wt_require_worktree() {
  [ "$WT_PATH" != "$WT_MAIN" ] || wt_die "worktree で実行してください (メインのチェックアウトです): $WT_PATH"
}

wt_slot_of() { sed -n 's/^PORT_SLOT=//p' "$1/.ports.env" 2>/dev/null || true; }

# 対象チェックアウトの slot (メインは 0、未割り当ての worktree は空)
wt_slot() { if [ "$WT_PATH" = "$WT_MAIN" ]; then echo 0; else wt_slot_of "$WT_PATH"; fi; }

# slot $1 のサービスごとのポートを「名前<TAB>ポート」で出力する
wt_ports() { wt_cfg --argjson slot "$1" '(.slot_step // 0) as $s | .services // {} | to_entries[] | "\(.key)\t\(.value.port + $slot * $s)"'; }

wt_port_var() { local v="${1^^}"; echo "WT_PORT_${v//-/_}"; }

# フック・serve 用の環境変数を export する
wt_export_env() {
  WT_SLOT="$(wt_slot)"
  export WT_PATH WT_MAIN WT_SLOT
  [ -n "$WT_SLOT" ] || { wt_has_services && wt_die "slot が未割り当てです (mise wt:ports $WT_PATH を実行してください)"; return 0; }
  local name port
  while IFS=$'\t' read -r name port; do export "$(wt_port_var "$name")=$port"; done < <(wt_ports "$WT_SLOT")
}

wt_has_hook() { [ "$(wt_cfg --arg h "$1" '.hooks[$h] // [] | length')" -gt 0 ]; }

# フック $1 を WT_PATH で順に実行する (wt_export_env の後に呼ぶ)
wt_run_hook() {
  local cmd
  while IFS= read -r -d '' cmd; do
    echo "==> $1: $cmd" >&2
    (cd "$WT_PATH" && bash -c "$cmd") || wt_die "フック $1 が失敗しました (exit $?): $cmd"
  done < <(jq -j --arg h "$1" '.hooks[$h] // [] | .[] | . + "\u0000"' "$WT_CONFIG")
}

# 「ポート<TAB>pid」で listen 中の TCP ポートを出力する
wt_listening() { ss -ltnpH | awk '{ n = split($4, a, ":"); pid = "-"; if (match($0, /pid=[0-9]+/)) pid = substr($0, RSTART + 4, RLENGTH - 4); print a[n] "\t" pid }' | sort -u; }

# チェックアウト $1 が開かれている herdr workspace の ID
wt_workspace() {
  local ws
  ws="$(herdr worktree list --cwd "$1" | jq -r --arg p "$1" '.result.worktrees[] | select(.path == $p) | .open_workspace_id // empty')"
  [ -n "$ws" ] || wt_die "worktree が herdr で開かれていません: $1"
  echo "$ws"
}

# workspace $1 のラベル $2 のタブの先頭ペイン。$3 (cwd) を渡すとタブが無いとき作る。無ければ空
wt_tab_pane() {
  local tab
  tab="$(herdr tab list --workspace "$1" | jq -r --arg l "$2" '[.result.tabs[] | select(.label == $l)][0].tab_id // empty')"
  if [ -n "$tab" ]; then
    herdr pane list --workspace "$1" | jq -r --arg t "$tab" '[.result.panes[] | select(.tab_id == $t)][0].pane_id'
  elif [ -n "${3:-}" ]; then
    herdr tab create --workspace "$1" --cwd "$3" --label "$2" | jq -r '.result.root_pane.pane_id'
  fi
}
