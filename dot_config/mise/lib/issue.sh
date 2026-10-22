# shellcheck shell=bash
# issue タスク (~/.config/mise/tasks/issue/*) の共通処理。各タスクが source する
#
# Issue ごとのディレクトリは <ISSUE_DIR>/<並び順>-<状態>_<番号> (例: 2-検証済_4000)。
# ISSUE_DIR はメインのチェックアウトからの相対パスで、リポジトリの mise の [env] に置く。
# worktree から実行してもメイン側を扱う (記録・エビデンスはメインに置く)。
# 状態はディレクトリ名で表し、並び順は ISSUE_STATUSES の位置 (ls で完了に近いものが上に並ぶ)。

# 並び順は位置の番号 (0 から)。対象外 (流れに乗せない Issue。手で進めた例外など) は 0 にして、ls で一番上にまとめる
ISSUE_STATUSES=(対象外 完了 検証済 検証NG 修正中 Issue更新済 再現済 未着手)

issue_die() { echo "$*" >&2; exit 1; }

issue_load() {
  [ -n "${ISSUE_DIR:-}" ] || issue_die "設定がありません: ISSUE_DIR (リポジトリの mise の [env] に、メインのチェックアウトからの相対パスで置く)"
  local main
  main="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || issue_die "git のチェックアウトではありません: $PWD"
  ISSUES_ROOT="$(dirname "$main")/$ISSUE_DIR"
}

# <状態> のディレクトリ名の接頭辞 (<並び順>-<状態>) を表示する。不正な状態なら 1 を返す
issue_prefix() {
  local i
  for i in "${!ISSUE_STATUSES[@]}"; do
    [ "${ISSUE_STATUSES[$i]}" = "$1" ] && { echo "$i-$1"; return 0; }
  done
  echo "状態は次のいずれか: ${ISSUE_STATUSES[*]}" >&2; return 1
}

# <番号> のディレクトリのパスを表示する。無ければ何も表示せず 1、複数あれば 2 を返す
issue_dir() {
  local n="$1" m
  m="$(compgen -G "$ISSUES_ROOT/*_${n}" || true)"
  [ -n "$m" ] || return 1
  [ "$(wc -l <<<"$m")" -eq 1 ] || { echo "Issue #$n のディレクトリが複数あります: $(tr '\n' ' ' <<<"$m")" >&2; return 2; }
  echo "$m"
}

# <番号> のディレクトリのパスを表示する。無ければ「未着手」で作る
issue_dir_ensure() {
  local n="$1" d rc=0
  d="$(issue_dir "$n")" || rc=$?
  [ "$rc" -eq 2 ] && return 2
  if [ -z "$d" ]; then
    d="$ISSUES_ROOT/$(issue_prefix 未着手)_${n}"
    mkdir -p "$d"
    echo "ディレクトリを作成: $d" >&2
  fi
  echo "$d"
}

issue_status_of() { local b; b="$(basename "$1")"; b="${b%_*}"; echo "${b#*-}"; }

issue_number_of() { local b; b="$(basename "$1")"; echo "${b##*_}"; }

# <番号> の状態を <状態> に変える (ディレクトリ名を変える)。新しいパスを表示する
issue_mark() {
  local n="$1" st="$2" d new prefix
  prefix="$(issue_prefix "$st")" || return 1
  d="$(issue_dir "$n")" || { echo "Issue #$n のディレクトリがありません" >&2; return 1; }
  new="$ISSUES_ROOT/${prefix}_${n}"
  if [ "$d" != "$new" ]; then
    mv "$d" "$new"
    echo "状態を変更: $(issue_status_of "$d") → $st" >&2
  fi
  echo "$new"
}
