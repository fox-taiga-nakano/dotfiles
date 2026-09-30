# =========================================
# tool initialization
# =========================================
eval "$(mise activate zsh)"

if type 'herdr' > /dev/null 2>&1; then
    eval "$(herdr completion zsh)"
fi
