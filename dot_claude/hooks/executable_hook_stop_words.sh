#!/bin/bash

# ストップワードフック
# Claude Codeの回答をチェックして不適切な表現を検出する

RULES_FILE="$HOME/.claude/hooks/rules/hook_stop_words_rules.json"
INPUT_TEXT="$1"

# ルールファイルが存在しない場合は正常終了
if [ ! -f "$RULES_FILE" ]; then
    exit 0
fi

# jqが利用できない場合は正常終了
if ! command -v jq >/dev/null 2>&1; then
    exit 0
fi

# ルールをチェック
while read -r rule; do
    pattern=$(echo "$rule" | jq -r '.pattern')
    error_message=$(echo "$rule" | jq -r '.error_message')
    
    if [ -n "$pattern" ] && echo "$INPUT_TEXT" | grep -qE "$pattern" 2>/dev/null; then
        echo "❌ フック検出: $error_message" >&2
        echo "検出パターン: $pattern" >&2
        exit 1
    fi
done < <(jq -c '.rules[]' "$RULES_FILE")

exit 0
