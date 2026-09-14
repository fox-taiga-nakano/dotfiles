#!/bin/bash

# コマンド実行前フック
# Bashコマンドをチェックして危険なコマンドの実行を防ぐ

RULES_FILE="$HOME/.claude/hooks/rules/hook_pre_commands_rules.json"
COMMAND="$1"

# ルールファイルが存在しない場合は正常終了
if [ ! -f "$RULES_FILE" ]; then
  exit 0
fi

# jqが利用できない場合は正常終了
if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

# ブロックされたコマンドをチェック
while read -r rule; do
  pattern=$(echo "$rule" | jq -r '.pattern')
  error_message=$(echo "$rule" | jq -r '.error_message')
  
  if [ -n "$pattern" ] && echo "$COMMAND" | grep -qE "$pattern" 2>/dev/null; then
    echo "🚫 危険なコマンドが検出されました: $error_message" >&2
    echo "実行を停止したコマンド: $COMMAND" >&2
    exit 1
  fi
done < <(jq -c '.blocked_commands[]' "$RULES_FILE")

# 許可されたコマンドをチェック
ALLOWED_COMMANDS=$(jq -r '.allowed_commands[]' "$RULES_FILE" 2>/dev/null)
if [ -n "$ALLOWED_COMMANDS" ]; then
  COMMAND_NAME=$(echo "$COMMAND" | awk '{print $1}')
  if ! echo "$ALLOWED_COMMANDS" | grep -q "^$COMMAND_NAME$"; then
    echo "⚠️  警告: 許可リストにないコマンドです: $COMMAND_NAME" >&2
    echo "コマンド: $COMMAND" >&2
    # 警告のみで実行は継続
  fi
fi

# プロジェクト固有のルールをチェック
jq -r '.project_specific_rules[] | select(.require_confirmation == true) | .pattern' "$RULES_FILE" | while read -r pattern; do
  if [ -n "$pattern" ] && echo "$COMMAND" | grep -qE "$pattern" 2>/dev/null; then
    echo "🔍 重要な操作が検出されました。実行前に確認してください。" >&2
    echo "コマンド: $COMMAND" >&2
    echo "説明: $(jq -r ".project_specific_rules[] | select(.pattern == \"$pattern\") | .description" "$RULES_FILE")" >&2
  fi
done

exit 0
