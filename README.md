# dotfiles

WSL 上の開発環境を chezmoi で管理する dotfiles リポジトリです。シェル、Git、開発ツールの設定をまとめて導入・更新できます。

- Zsh: Oh My Zsh、Powerlevel10k、入力補完・構文ハイライト
- Git: delta による差分表示、lazygit の表示設定
- 開発ツール: mise によるランタイム・CLI の管理、Herdr・hunk・druk の設定
- Claude Code: ステータスライン、フック、出力スタイル

## 利用環境

WSL と Linuxbrew（`/home/linuxbrew/.linuxbrew`）を前提にした個人の設定です。ほかの環境に導入する場合は、セットアップ前にパスやエイリアスを調整してください。

あらかじめ Git、Zsh、chezmoi、Linuxbrew、mise、delta をインストールし、コマンドを利用できる状態にします。用途に応じて次のツールも用意してください。

| ツール            | 用途                                    |
| ----------------- | --------------------------------------- |
| bat / eza         | `cat` / `ls` のエイリアス               |
| GitHub CLI (`gh`) | Git の GitHub 認証ヘルパー              |
| Nerd Font         | プロンプトや一覧表示のアイコン          |
| Python 3 / jq     | Claude Code のステータスライン / フック |

Linuxbrew やこれらの依存ツールをインストールするスクリプトは含まれていません。外部依存の取得にはネットワーク接続が必要です。

## セットアップ

### 1. リポジトリを初期化

```sh
chezmoi init https://github.com/fox-taiga-nakano/dotfiles.git
```

Git のユーザー名とメールアドレスを入力すると、chezmoi の設定に保存され、`.gitconfig` に反映されます。自分の設定として継続的に管理する場合は、このリポジトリを fork し、URL を自分のリポジトリに置き換えてください。

### 2. 設定を確認・調整

```sh
chezmoi cd
```

特に次の設定を確認してください。

- [PATH 設定](dot_zsh.d/10-path.zsh): Linuxbrew と .NET のインストール先
- [エイリアス](dot_zsh.d/30-alias.zsh): Windows 連携、個人環境のパス、プロジェクト用コマンド
- [Git 設定](dot_gitconfig.tmpl): エディターと GitHub CLI のパス
- [mise 設定](dot_config/mise/config.toml): インストールするランタイム・CLI

### 3. 差分を確認して適用

既存の設定を置き換えるため、必要なファイルをバックアップしてから差分を確認します。

```sh
chezmoi diff
chezmoi apply
mise install
exec zsh
```

`chezmoi apply` は設定の配置と Oh My Zsh・プラグイン・テーマの取得を行います。`mise install` は mise 設定に記載されたツールをインストールします。

## 設定ファイル

| ソース                        | 配置先                       | 内容                                          |
| ----------------------------- | ---------------------------- | --------------------------------------------- |
| `dot_zshrc`                   | `~/.zshrc`                   | Oh My Zsh、Powerlevel10k、分割設定の読み込み  |
| `dot_zsh.d/`                  | `~/.zsh.d/`                  | PATH、ツール初期化、エイリアス、関数          |
| `dot_p10k.zsh`                | `~/.p10k.zsh`                | プロンプトの表示設定                          |
| `dot_gitconfig.tmpl`          | `~/.gitconfig`               | Git、delta、GitHub CLI の認証ヘルパー         |
| `dot_config/git/ignore`       | `~/.config/git/ignore`       | Git の共通除外設定                            |
| `dot_config/mise/config.toml` | `~/.config/mise/config.toml` | Node.js、Bun、pnpm、各種 CLI のバージョン管理 |
| `dot_config/lazygit/`         | `~/.config/lazygit/`         | Git のログ・差分表示                          |
| `dot_config/herdr/`           | `~/.config/herdr/`           | ターミナルマルチプレクサーの設定              |
| `dot_config/hunk/`            | `~/.config/hunk/`            | 差分ビューアーの設定                          |
| `dot_config/druk/`            | `~/.config/druk/`            | エディターの設定                              |
| `dot_claude/`                 | `~/.claude/`                 | ステータスライン、フック、出力スタイル        |
| `dot_fixpackrc`               | `~/.fixpackrc`               | package.json の整形設定                       |

chezmoi の命名規則に従い、`dot_` はドットファイル、`.tmpl` はテンプレート、`executable_` は実行可能ファイルを表します。

### Zsh の分割設定

`~/.zsh.d/*.zsh` はファイル名順に読み込まれます。

- `10-path.zsh`: Linuxbrew、.NET、ローカルコマンドの PATH
- `20-tool.zsh`: mise の有効化、Herdr の補完
- `30-alias.zsh`: bat、eza、pnpm、Docker、mise などのエイリアス
- `40-command.zsh`: Windows Terminal の作業ディレクトリ連携、クリップボード転送、制御文字を除去する `tee` 関数

### Claude Code

フックやステータスラインは、配置後に Claude Code の `~/.claude/settings.json` で登録してください。このファイルはリポジトリの管理対象に含まれていません。フックのルールは `dot_claude/hooks/rules/` で調整できます。

## 設定の編集

```sh
chezmoi cd
# ソースファイルを編集
chezmoi diff
chezmoi apply
```

ホームディレクトリ側で編集した設定を取り込む場合は、対象を指定します。

```sh
chezmoi add ~/.zshrc
```

テンプレートを使っている設定は、ソースの `.tmpl` ファイルと chezmoi のテンプレートデータを編集してください。

## 更新

### dotfiles

```sh
chezmoi update
```

リモートリポジトリの変更を取得して反映します。シェル設定を更新した場合は `exec zsh` で読み込み直してください。

### Oh My Zsh・プラグイン・Powerlevel10k を更新する

Oh My Zsh、zsh-autosuggestions、zsh-syntax-highlighting、Powerlevel10k は [.chezmoiexternal.toml](.chezmoiexternal.toml) でアーカイブとして管理しています。

これらをまとめて更新する場合は、対象を `~/.oh-my-zsh` に指定します。

```sh
chezmoi diff -r -R ~/.oh-my-zsh
chezmoi apply -R ~/.oh-my-zsh
exec zsh
```

`diff` で更新内容を確認し、`apply` で反映します。`-R`（`--refresh-externals`）はキャッシュの経過時間に関係なく外部依存を取得し直します。4つとも上流の `master` ブランチを参照しているため、通常の更新にリポジトリ内の設定変更は必要ありません。

すべての設定もあわせて反映する場合は、対象を指定せず `chezmoi apply -R` を実行します。

### 更新コマンドの使い分け

| コマンド            | dotfiles の反映元        | 外部依存の再取得            |
| ------------------- | ------------------------ | --------------------------- |
| `chezmoi apply`     | ローカルの設定を反映     | キャッシュが7日より古い場合 |
| `chezmoi apply -R`  | ローカルの設定を反映     | 毎回                        |
| `chezmoi update`    | リモートから取得して反映 | キャッシュが7日より古い場合 |
| `chezmoi update -R` | リモートから取得して反映 | 毎回                        |

`refreshPeriod = "168h"` はキャッシュの更新間隔です。7日ごとにバックグラウンドで更新される仕組みではなく、chezmoi を実行したときに再取得が必要か判断されます。

### 外部依存の管理

Oh My Zsh 自身の自動更新は `zstyle ':omz:update' mode disabled` で無効にしています。アーカイブで配置しているため、更新には上記の chezmoi コマンドを使います。

`exact = true` により、上流で削除されたファイルは手元からも削除されます。独自のファイルは chezmoi のソースで管理してください。実行時に生成されるキャッシュ、ログ、コンパイル済み Zsh ファイル（`*.zwc`）は [.chezmoiignore](.chezmoiignore) で除外しています。

バージョンを固定したい場合は、`.chezmoiexternal.toml` のアーカイブ URL をタグやコミットに変更してください。
