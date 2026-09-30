---
name: commit
description: このchezmoi dotfilesリポジトリでgit commitやgit pushを行う前に必ず使用する。「コミットして」「pushして」などユーザーから明示の指示があったとき、または自分の作業をコミットしようとする直前に読み込む。変更を適切な単位に分割し、明示の指示がない限りコミット・pushをせず、指示や自分の作業と無関係な未説明の差分やchezmoiのsource/target間のずれを検知したら黙って含めず必ず質問する、というこのリポジトリ固有の安全なコミット運用を定義する。
---

# commit

このリポジトリ（chezmoiのsource directory `~/.local/share/chezmoi`、remoteは`origin` = `github.com:fox-taiga-nakano/dotfiles`）でgit commit / git pushを行うときの手順。4つのルールを必ず守る:

1. 適切に分割する。
2. 明示の指示がない限りコミットしない。
3. 明示の指示がない限りpushしない。
4. 検知していない変更は無視せず質問する。

## 0. 前提確認（毎回必須）

何か操作する前に必ず次を実行し、sourceのワークツリーとtarget（ホームディレクトリ）の両方の状態を把握する。

```bash
git status
git diff
git diff --staged
chezmoi status
```

- 印象や記憶で判断せず、この出力を根拠にする。
- `chezmoi status`に出力がある場合、ホーム側のファイルがsourceと食い違っている（ホーム側を直接編集した、または未applyの変更がある）。その差分を`chezmoi diff`で確認し、`chezmoi re-add` / `chezmoi add`で取り込むか、`chezmoi apply`で上書きするかは自己判断せずユーザーに確認する。

## 1. コミットは明示の指示があるときだけ

- 「このターンでユーザーが明示的にコミットを依頼したか」を確認する。
- 設定変更などの作業が完了しても、それだけを理由に「ついでにコミットしておく」ことはしない。
- 過去に承認された「コミットして」等の指示は、その時点の作業範囲にのみ適用される。以降に加わった変更をコミットするには、改めて明示の指示が必要。

## 2. pushも明示の指示があるときだけ

- 「コミットして」という指示だけでpushしない。コミットとpushは別の指示として扱う。
- pushする場合は対象ブランチ・remoteをユーザーの指示から確認する（通常は`origin main`）。
- force push（`git push --force` / `--force-with-lease`）はユーザーが明示的に要求しない限り行わない。

## 3. 検知していない変更は無視せず質問する

- `git status` / `chezmoi status`の出力と、ユーザーが説明・依頼した変更内容、および自分がこのセッションで実際に手を加えた内容を突き合わせる。
- ユーザーの指示にも自分の直近の作業にも紐づかない差分（既存の未コミット作業、ツールが自動で書き換えた設定ファイル、心当たりのないuntrackedファイルなど）が見つかったら、`git add -A` / `git add .`で一括に巻き込んだり、逆に黙って除外したりせず、AskUserQuestionで「今回のコミットに含めるか」「別コミットにするか」「触らないか」を確認する。
- 例: `dot_config/druk/config.json`や`dot_config/herdr/config.toml`のように、アプリ自身が設定を書き換える／`chezmoi re-add`で一括取り込みされるファイルは、意図しない差分が混ざりやすい。「関連しそうだから」で自己判断せず、依頼された範囲だけを扱う。

## 4. 秘匿情報・マシン固有値の確認

このリポジトリはGitHubにpushされるdotfilesなので、ステージ前に差分を必ず確認する。

- トークン・APIキー・パスワード・秘密鍵・社内ホスト名などが含まれていないか。見つけたらコミットせずユーザーに報告する。
- メールアドレスやユーザー名などのマシン／個人固有値は直書きせず、`dot_gitconfig.tmpl`のように`.tmpl`化して`.chezmoi.toml.tmpl`の`promptStringOnce`で埋め込む既存パターンに従う。テンプレート化が必要そうなら、コミット前にユーザーへ提案する。
- 絶対パス（例: `/home/linuxbrew/...`）は既存ファイルにも存在するため直ちに問題ではないが、新規に追加する場合は他マシンで壊れないか意識する。

## 5. 適切に分割する

- 関心事ごと、基本的には**対象ツール／設定ファイルごと**にコミットを分ける（例: zsh、herdr、mise、Claude Codeのhooksなど）。同じ目的で複数ツールを横断して変えた場合のみまとめる。
- `git add -A` / `git add .`ではなくファイルを指定して`git add`する。
- 1コミットずつ作成し、都度`git status`で確認してから次の分割コミットに進む。

### コミットメッセージ形式

既存ログ（`add: dot_p10k.zsh`、`add: chezmoi diff pager to delta`、`update: herdr hook, druk, hunk, mise configs`）に合わせる。

- 形式: `<type>: <英語の簡潔な説明>`（小文字始まり、末尾ピリオドなし、scopeなし）。
- type:
  - `add`: 新しいdotfile・設定項目・スクリプトの追加
  - `update`: 既存設定の変更・調整
  - `fix`: 壊れていた設定・スクリプトの修正
  - `remove`: dotfile・設定項目の削除
- 説明には対象のツール名や設定名を入れる（sourceのファイル名`dot_*`をそのまま使ってもよい）。
- 末尾にはセッションで指定されたattribution行（`Co-Authored-By:`等）を付ける。

## 6. 禁止事項

明示の指示がない限り行わない:

- `--no-verify`によるフックスキップ
- `git commit --amend`
- `git push --force` / `git reset --hard`などの破壊的操作
- コミットのついでに`chezmoi apply` / `chezmoi re-add`を実行してホーム側やsource側を書き換えること
