# sunaba-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> English version: [README.md](README.md)

**AI エージェント開発用の devcontainer sandbox をコマンド一発で作る CLI。**

「砂場」(sunaba) のように、壊してもすぐ作り直せる隔離環境で
[Claude Code](https://claude.com/claude-code) /
[OpenAI Codex CLI](https://github.com/openai/codex) /
[Gemini CLI](https://github.com/google-gemini/gemini-cli) を同時に動かせます。
MCP サーバー、クラウド SDK、エージェント指示ファイルまで揃った状態で起動します。

---

## なぜ sunaba か

AI コーディングエージェントは強力ですが、グローバルパッケージをインストールし、
任意のスクリプトを取得し、ホストを予期せず書き換えがちです。`sunaba-cli` は
プロジェクトごとに **新品の Linux コンテナ** を用意し、3 つの主要エージェントが
MCP 経由で互いに通信できる状態で起動します。

- 🧪 **使い捨て** — エージェントが壊しても作り直せる
- 🔌 **合成可能** — スタックを組み合わせ (`python`, `nextjs`, `aws`, `gcp` …)
- 🤖 **エージェント相互連携** — Claude Code が MCP 経由で Codex / Gemini を呼べる
- 🔐 **秘密情報は opt-in** — API キーは `--stack agents` を指定したときだけ注入
- 📦 **自己完結** — `uv tool install` でグローバル `sunaba` コマンド化

## インストール

[uv](https://docs.astral.sh/uv/) が必要です:

```bash
uv tool install git+https://github.com/morimorijap/sunaba-cli
```

`sunaba` コマンドが PATH に追加されます。

### アップグレード

```bash
sunaba upgrade
```

## クイックスタート

```bash
# 対話 picker でスタック選択
sunaba new myapp

# 明示的にスタック指定
sunaba new myapp --stack python --stack agents

cd myapp
code .
# VS Code: Cmd+Shift+P → "Dev Containers: Reopen in Container"
```

初回のコンテナ起動はベースイメージとエージェント CLI のインストールに数分かかります。
2 回目以降はキャッシュで高速です。

### ホスト直接実行モード (`--no-devcontainer`)

コンテナを使わずホスト上で直接エージェントを動かしたい場合は `--no-devcontainer`
を指定します:

```bash
sunaba new local --stack python --no-devcontainer
```

`.devcontainer/devcontainer.json` と `bootstrap.sh` の生成をスキップし、ホストでも
そのまま使えるファイル群 (`.mcp.json`、`.vscode/settings.json`、エージェント指示
ファイル `CLAUDE.md` / `GEMINI.md` / `AGENTS.md` / `skills.md`、`devcontainers` /
`docker` を除いた `dependabot.yml`、`.gitignore`) のみを出力します。

devcontainer feature 経由でしか自動インストールされないツール (`aws-cli`、
`gcloud`、`python` ツールチェーン等) は警告として一覧表示されます。必要なら
ホスト側で手動インストールしてください。

## コマンド一覧

| コマンド | 用途 |
|---|---|
| `sunaba new <name>` | 新規 sandbox プロジェクト作成 |
| `sunaba rebuild <name\|path>` | 既存プロジェクトの stack を変更 |
| `sunaba register <path> --stack ...` | 既存プロジェクトを registry に追加 |
| `sunaba list` | 登録済みプロジェクト一覧 |
| `sunaba stacks` | 利用可能な stack 一覧 |
| `sunaba sync [<name>\|--all]` | エージェント指示ファイルを同期 |
| `sunaba upgrade` | sunaba-cli 自体を更新 |

## Stack 一覧

| Stack | 内容 |
|---|---|
| `python` | Python 3.14 + `uv` (pip 経由でインストール、`curl \| sh` 不使用) |
| `nextjs` | Vercel CLI + ESLint / Tailwind 拡張 (Node.js は base に含まれる) |
| `aws` | `aws-cli` (devcontainer feature) + AWS 認証環境変数 |
| `azure` | `az` CLI + Azure 認証環境変数 |
| `gcp` | `gcloud` CLI + GCP 認証環境変数 |
| `neon` | `neonctl` (Neon Postgres CLI) + `NEON_API_KEY` |
| `agents` | `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` をホストから注入 |
| `docker` | `docker-outside-of-docker` (ホストの Docker daemon にアクセス) |

## セキュリティについて (必読)

マーケティング抜きで正直に書きます。機微なコードで使う前に目を通してください。

### `sunaba-cli` が守るもの

- **パストラバーサル対策**: プロジェクト名に `/` `\` `..` を含むものは拒否。
  生成ファイルのパスは project root に対して解決してから書き込み。
- **Symlink に対する fail-closed**: `sunaba rebuild` は symlink を経由した書き込みや
  プロジェクト外への書き込みを拒否します。
- **秘密情報は opt-in**: `--stack agents` 等を指定しない限り API キーは注入されません。
  base の `remoteEnv` は空です。
- **Docker-in-docker も opt-in**: `--stack docker` でのみホスト Docker socket をマウント。
- **Fail-closed な依存解決**: `package-lock.json` がある場合のみ `npm ci --ignore-scripts`、
  `pyproject.toml` がある場合のみ `uv sync --frozen` を実行。無言のフォールバックなし。
- **`uv` は pip 経由でインストール**: リモートシェルスクリプトの実行を回避。

### `sunaba-cli` が守れないもの

- **`@latest` のエージェント CLI**: Claude Code / Codex / Gemini CLI は初回起動時に
  `@latest` でインストールされます。常に最新にする代わりに、上流が侵害されれば
  sandbox も影響を受けます。再現性が必要なら fork して固定してください。
- **MCP サーバーの supply chain**: `playwright` / `chrome-devtools-mcp` /
  `notebooklm-mcp-cli` は初回利用時に `npx` / `uvx` で取得されます。
- **コンテナ内の秘密情報の可視性**: `--stack agents` を指定した時点で、コンテナ内の
  *すべてのプロセス* (AI エージェント含む) が環境変数から API キーを読めます。
- **Docker socket**: `--stack docker` は実質ホストの Docker を完全制御できるので、
  信頼できるコードにのみ使ってください。
- **エージェントそのものの制約**: このツールは AI エージェント自体をサンドボックス化
  するものではありません。コンテナ内で `rm -rf` したりシークレットを push したりは
  可能です。**sandbox が守るのはホストであり、あなたの repo ではありません。**

脆弱性の報告は [SECURITY.md](SECURITY.md) を参照してください。

## コンテナ内から GitHub に SSH 接続する

`sunaba-cli` はホストの SSH 鍵をコンテナにコピーしません。代わりに
VS Code Dev Containers 標準の **SSH agent forwarding** を使います。
ホストの `ssh-agent` のソケットがコンテナ内に `$SSH_AUTH_SOCK` として
bind mount され、秘密鍵自体はホストから出ないまま `git push` が通ります。

### ホスト側の初回設定 (macOS)

```bash
# キーチェーンに鍵を登録 (再起動後も自動ロード)
ssh-add --apple-use-keychain ~/.ssh/id_ed25519

# ~/.ssh/config にキーチェーン利用を追記
cat >> ~/.ssh/config <<'EOF'
Host *
  UseKeychain yes
  AddKeysToAgent yes
  IdentityFile ~/.ssh/id_ed25519
EOF

# 確認
ssh-add -l   # 鍵が表示されればOK
```

Linux の場合は `.bashrc` 等に `eval "$(ssh-agent -s)" && ssh-add ~/.ssh/id_ed25519`
を書いておけば十分です。

### コンテナ内での動作確認

プロジェクトをコンテナで開き直した後:

```bash
echo "$SSH_AUTH_SOCK"     # パスが表示されるはず
ssh -T git@github.com      # ユーザー名で挨拶されればOK
git push                   # SSH 経由で push できる
```

### トラブルシューティング

| 症状 | 対処 |
|---|---|
| `$SSH_AUTH_SOCK` が空 | ホストで `ssh-add -l` → no identities なら `ssh-add --apple-use-keychain ~/.ssh/id_ed25519` を実行してコンテナ再起動 |
| `Permission denied (publickey)` | ホストの agent に鍵が無い (`ssh-add -l` で確認) |
| `fatal: detected dubious ownership` | bootstrap で対処済み。古いプロジェクトで出る場合は再 rebuild |

> ⚠️ forwarding された agent はコンテナ内の **すべてのプロセス** (AI エージェント
> を含む) からアクセス可能です。秘密鍵そのものは取り出せませんが、コンテナが
> 起動している間は認証署名が可能です。機微な鍵を扱う sandbox で信頼できない
> コードを同時に動かすのは避けてください。

## 必要な環境

- macOS / Linux (devcontainer は Linux コンテナで動作)
- [uv](https://docs.astral.sh/uv/)
- Docker 互換ランタイム (Docker Desktop / Colima / Rancher Desktop 等)
- VS Code + Dev Containers 拡張

## ライセンス

MIT — [LICENSE](LICENSE) 参照。
