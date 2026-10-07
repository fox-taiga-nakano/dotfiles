# =========================================
# herdr: report sidebar tokens for the current workspace/pane
#   $pr   PR number of the current branch
#   $main main workspace name (worktree workspaces are labeled by branch)
# =========================================
if [[ "$HERDR_ENV" == 1 && -n "$HERDR_WORKSPACE_ID" ]] && (( $+commands[herdr] && $+commands[gh] && $+commands[python3] )); then
  zmodload zsh/datetime

  typeset -g _herdr_pr_key=""
  typeset -g -i _herdr_pr_checked_at=0
  typeset -g -i _herdr_pr_interval=300

  # Print the label of the main (non-linked) workspace of the given workspace's repo
  typeset -g _herdr_main_py='
import json, sys
wss = json.load(sys.stdin)["result"]["workspaces"]
cur = next((w for w in wss if w["workspace_id"] == sys.argv[1]), None)
if cur:
    wt = cur.get("worktree") or {}
    name = cur["label"]
    if wt.get("is_linked_worktree"):
        main = next((w for w in wss if (w.get("worktree") or {}).get("repo_key") == wt["repo_key"]
                     and not w["worktree"].get("is_linked_worktree")), None)
        name = main["label"] if main else wt.get("repo_name") or name
    print(name)
'

  function _herdr_pr_update() {
    local ws="$HERDR_WORKSPACE_ID" pane="$HERDR_PANE_ID" key
    local -a git_info
    git_info=("${(@f)$(git rev-parse --show-toplevel --abbrev-ref HEAD --absolute-git-dir --path-format=absolute --git-common-dir 2>/dev/null)}")
    key="${git_info[1]}:${git_info[2]}"
    # Linked worktree: git dir differs from common dir
    local is_worktree=0
    [[ -n "${git_info[3]}" && "${git_info[3]}" != "${git_info[4]}" ]] && is_worktree=1

    # Re-check on branch/repo change, or periodically to catch newly created PRs
    if [[ "$key" == "$_herdr_pr_key" ]] && (( EPOCHSECONDS - _herdr_pr_checked_at < _herdr_pr_interval )); then
      return
    fi
    _herdr_pr_key="$key"
    _herdr_pr_checked_at=$EPOCHSECONDS

    {
      # workspace tokens for the spaces sidebar, pane tokens for the agents sidebar
      function _herdr_pr_report() {
        herdr workspace report-metadata "$ws" --source zsh-pr "$@"
        [[ -n "$pane" ]] && herdr pane report-metadata "$pane" --source zsh-pr "$@"
      }

      # Main workspace lookup only in worktrees; otherwise just use this workspace's label
      local main number
      if (( is_worktree )); then
        main="$(herdr workspace list 2>/dev/null | python3 -Ic "$_herdr_main_py" "$ws" 2>/dev/null)"
      elif [[ "$(herdr workspace get "$ws" 2>/dev/null)" =~ '"label":"([^"]*)"' ]]; then
        main="${match[1]}"
      fi
      # Report the name before the slow (network) PR lookup
      [[ -n "$main" ]] && _herdr_pr_report --token "main=$main"

      [[ -n "${git_info[1]}" ]] && number="$(gh pr view --json number -q .number 2>/dev/null)"
      if [[ -n "$number" ]]; then
        _herdr_pr_report --token "pr=#$number"
      else
        _herdr_pr_report --clear-token pr
      fi
    } >/dev/null 2>&1 &!
  }

  autoload -Uz add-zsh-hook
  add-zsh-hook precmd _herdr_pr_update
fi
