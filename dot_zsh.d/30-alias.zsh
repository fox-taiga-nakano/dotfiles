# =========================================
# general
# =========================================
alias cat="bat"
alias open="explorer.exe"
alias claude-mem='bun "/home/taiga/.claude/plugins/marketplaces/thedotmack/plugin/scripts/worker-service.cjs"'

# =========================================
# pnpm
# =========================================
alias generate="pnpm generate"
alias ser="pnpm serve"
alias te="pnpm test"
alias mock="pnpm dev:mock"
alias start="pnpm run --filter=client start"
alias story="pnpm storybook"

# =========================================
# mise tasks
# =========================================
alias format='mise format'
alias dev='mise dev'
alias check='mise check'
alias build='mise build'

# =========================================
# docker
# =========================================
alias dc='docker compose'
alias dp='docker ps'

EZA_BASE='--color=always --group-directories-first --icons --show-symlinks --git -F'
# =========================================
# ls replacement
# =========================================
alias ls="eza $EZA_BASE"
alias ll='ls -al'
alias la='ls -a'
# =========================================
# tree
# =========================================
alias lt='ls --tree --level=3'
# =========================================
# filtered listing
# =========================================
# ディレクトリのみ
alias ld='ls -Da'
# ファイルのみ
alias lf='ls -fa'
