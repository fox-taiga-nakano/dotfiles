# Windows Terminal: keep current directory when duplicating tabs/panes
if [[ -n "$WT_SESSION" ]] && command -v wslpath >/dev/null 2>&1; then
  function _wt_set_cwd() {
    local win_pwd
    win_pwd="$(wslpath -w "$PWD")" || return
    printf '\e]9;9;%s\e\\' "$win_pwd"
  }

  autoload -Uz add-zsh-hook
  add-zsh-hook -Uz precmd _wt_set_cwd
fi

clip() {
  perl -pe '
    s/\e\][^\a]*(?:\a|\e\\)//g;
    s/\e\[[0-?]*[ -\/]*[@-~]//g;
    s/\e[@-_]//g;
  ' \
    | iconv -f UTF-8 -t UTF-16LE \
    | command clip.exe
}

tee() {
  perl -pe '
    BEGIN { $| = 1 }

    # OSC制御シーケンス
    s/\e\][^\a]*(?:\a|\e\\)//g;

    # 色・カーソル移動などのCSI制御シーケンス
    s/\e\[[0-?]*[ -\/]*[@-~]//g;

    # その他の短いESCシーケンス
    s/\e[@-_]//g;
  ' | command tee "$@"
}
