# sunaba-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/github/v/release/morimorijap/sunaba-cli)](https://github.com/morimorijap/sunaba-cli/releases)
[![CI](https://github.com/morimorijap/sunaba-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/morimorijap/sunaba-cli/actions/workflows/ci.yml)

> English version: [README.md](README.md)

> **0.3.0 (2026-09-24)** が最初のタグ付きリリースです。`--stack secrets` の
> バグを修正しました。生成される gitleaks の設定が何も検出していませんでした。
> 以前にこの stack を使ったことがある方は [CHANGELOG](CHANGELOG.md#security) を
> 確認してください。あわせて、opt-in の Semgrep / Trivy マージゲート
> (`--stack security-ci`) を追加しました。

**AI エージェント開発用の devcontainer sandbox をコマンド一発で作る CLI。**

「砂場」(sunaba) のように、壊してもすぐ作り直せる隔離環境で
[Claude Code](https://claude.com/claude-code) /
[OpenAI Codex CLI](https://github.com/openai/codex) /
[Antigravity CLI](https://antigravity.google)(`agy`、Gemini CLI の後継) を同時に動かせます。
MCP サーバー、クラウド SDK、エージェント指示ファイルまで揃った状態で起動します。

---

## なぜ sunaba か

AI コーディングエージェントは強力ですが、グローバルパッケージをインストールし、
任意のスクリプトを取得し、ホストを予期せず書き換えがちです。`sunaba-cli` は
プロジェクトごとに **新品の Linux コンテナ** を用意し、3 つの主要エージェントが
MCP 経由で互いに通信できる状態で起動します。

- 🧪 **使い捨て** — エージェントが壊しても作り直せる
- 🔌 **合成可能** — スタックを組み合わせ (`python`, `nextjs`, `aws`, `gcp` …)
- 🤖 **エージェント相互連携** — Claude Code が MCP 経由で Codex を、`agy -p` で Antigravity CLI を呼べる
- 🔐 **秘密情報は opt-in** — API キーは `--stack agents` を指定したときだけ注入
- 🛡️ **セキュリティゲートも opt-in** — secret スキャン (`--stack secrets`) と、マージをブロックできる Semgrep SAST・Trivy 依存関係スキャン (`--stack security-ci`)
- 📦 **自己完結** — `uv tool install` でグローバル `sunaba` コマンド化

## インストール

[uv](https://docs.astral.sh/uv/) が必要です:

```bash
uv tool install git+https://github.com/morimorijap/sunaba-cli
```

`sunaba` コマンドが PATH に追加されます (`sunaba --version` で確認できます)。

`main` を追いかけずに、リリースを固定して入れる場合:

```bash
uv tool install git+https://github.com/morimorijap/sunaba-cli@v0.3.0
```

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
ファイル `CLAUDE.md` / `AGENTS.md` / `skills.md`、`devcontainers` /
`docker` を除いた `dependabot.yml`、`.gitignore`) のみを出力します。

作成後、`sunaba` は `PATH` を確認し、不足しているコマンド (エージェント CLI
`claude` / `codex` / `agy`、MCP ランタイム `npx` / `uvx`、stack 依存ツール
`uv` / `aws` / `gcloud` / `az` / `neonctl` / `vercel` 等) を警告として
表示します。表示されたものをホスト側で手動インストールしてください。

### セキュリティゲート付きで作る

```bash
sunaba new secured --stack python --stack secrets --stack security-ci
# push して、デフォルトブランチでチェックが一度成功したら:
scripts/protect-branch.sh --dry-run && scripts/protect-branch.sh
```

`scripts/protect-branch.sh` は、GitHub のルールセットで各チェックを必須にします。
依存関係の警告を整理し終えたら、`gh variable set SUNABA_TRIVY_BLOCKING --body true`
で Trivy もブロックに切り替えます。詳しくは生成される `docs/security/README.md` を
参照してください。

## コマンド一覧

| コマンド | 用途 |
|---|---|
| `sunaba new <name>` | 新規 sandbox プロジェクト作成 |
| `sunaba rebuild <name\|path>` | 既存プロジェクトの stack を変更 |
| `sunaba register <path> --stack ...` | 既存プロジェクトを registry に追加 |
| `sunaba list` | 登録済みプロジェクト一覧 |
| `sunaba stacks` | 利用可能な stack 一覧 |
| `sunaba sync [<name>\|--all]` | エージェント指示ファイルを同期 (既知の問題がある生成設定も警告) |
| `sunaba sync-gitignore <name\|path>` | プロジェクトの `.gitignore` を最新の secret ファイル baseline に更新 (独自の行は保持) |
| `sunaba upgrade` | sunaba-cli 自体を更新 |

## Stack 一覧

| Stack | 内容 |
|---|---|
| `python` | Python 3.14 + `uv` (pip 経由でインストール、`curl \| sh` 不使用) |
| `nextjs` | Vercel CLI + ESLint / Tailwind 拡張 (Node.js は base に含まれる) |
| `aws` | `aws-cli` (devcontainer feature) + AWS 認証環境変数 |
| `azure` | `az` CLI + Azure 認証環境変数 |
| `gcp` | `gcloud` CLI + GCP 認証環境変数 |
| `neon` | `neonctl` (Neon Postgres CLI) + PostgreSQL サーバー本体 (`postgresql` apt パッケージ、`psql` 含む) + `NEON_API_KEY` |
| `agents` | `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` をホストから注入 |
| `docker` | `docker-outside-of-docker` (ホストの Docker daemon にアクセス) |
| `playwright` | Chromium + Linux 依存ライブラリ (Playwright / Chrome DevTools MCP の E2E 用) |
| `harness` | Claude Code 向け harness テンプレート: `.claude/settings.json` (permissions + Stop hook)、silent-on-success な `verify.sh`、オンデマンド skill、planner / reviewer / verifier 役割定義、60行以内の ratchet `AGENTS.md`、`claudedocs/` トレースディレクトリ。**セッション境界での agent 挙動が変わるため opt-in。** |
| `secrets` | Secret 漏洩防止スキャフォールド: `gitleaks` をリリースのコミット SHA で固定した `.pre-commit-config.yaml`、gitleaks のデフォルトルールを継承する `.gitleaks.toml`、CI scan workflow (action は SHA 固定、gitleaks は SHA-256 検証、全履歴スキャン)、`docs/secrets/` 配下のクラウド別ドキュメント (Vercel · Firebase · AWS · GCP · Azure Foundry → APIM → Gemini → Cosmos)。**コミット時挙動が変わる(検知時は `git commit` がブロック)ため opt-in。** |
| `rules` | パススコープ付きルールを複数ターゲットに展開。`templates/rules/` のキャノニカル source 1 ファイルから `.cursor/rules/<name>.mdc`(Cursor の `globs:` / `alwaysApply:`)、`.claude/rules/<name>.md`(Claude の `paths:`)、`docs/agents/rules/<name>.md`(Codex / Gemini フォールバック)を生成。低リスクなコンテキスト改善で、ランタイム挙動は変わりません。 |
| `autopilot` | Claude Code / Codex CLI 向けの opt-in な自走環境: budget cap (`SUNABA_AUTOPILOT_MAX_ITERS` / `_MINUTES` / `_CHANGED_FILES`)付き構造化 Stop hook 再起動、`.githooks/pre-push` によるブランチ保護、operational な planner / reviewer / verifier 役割定義(Claude `.claude/agents/*.md` + Codex `.codex/agents/*.toml`)、subagent dispatch protocol ドキュメント、`claudedocs/{plans,checkpoints}/`。**agent ランタイム挙動が変わる**(verifier 失敗時 Stop hook が再起動)。推奨呼び出し: `--stack harness --stack rules --stack autopilot` の順(autopilot の operational 役割定義が harness の seed を上書きするため)。Antigravity CLI(`agy`)の対応状況と注意点は `docs/agents/antigravity-autopilot.md` で扱う。 |
| `multi-agent` | 並列エージェント協調オーケストレーション: `.agents/multi-agent/tasks.yaml` で `schema.json` 検証された共有タスクリスト、`owns:` ベースの hybrid 衝突回避(重複 → orchestrator が直列化)、デフォルト cohort cap 4(`SUNABA_MULTI_AGENT_MAX`)、`docs/multi-agent/sharding.md` の sharding フローチャート、`flock` 保護ヘルパースクリプト(`scripts/agent-task.py` の `claim` / `start` / `complete` / `fail` / `block` / `check-owns` / `overlap` サブコマンド)、scoped subagent プロンプトテンプレート。テンプレートのみ — 協調は **cooperative, not enforced**(ヘルパーが正しい操作を最も簡単にする;defense-in-depth は per-shard `git worktree` + autopilot のブランチ保護 + reviewer subagent)。`--stack autopilot` との併用推奨。 |
| `security-ci` | セキュリティのマージゲート: `.github/workflows/security-scan.yml` で **Semgrep** の SAST(`p/security-audit` + `p/owasp-top-ten`、`--error` 付きで検出時にブロック、イメージはダイジェスト固定)と、あらゆるロックファイルを対象にした **Trivy** の依存関係スキャン(バイナリは SHA-256 検証、リポジトリ変数 `SUNABA_TRIVY_BLOCKING` を `true` にするまでは警告のみ)を実行します。`paths:` フィルタを使わないので、どちらも必須チェックにできます。`scripts/protect-branch.sh` は GitHub のルールセットで、デフォルトブランチと `--branch` で指定したブランチ(例: `staging`)にこれらを必須チェックとして設定します(そのブランチで一度成功してから)。成熟度の段階と、検出されたときの対処は `docs/security/` にあります。**マージゲートが増えるため opt-in。** `--stack secrets` と組み合わせて使う想定です。 |

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
- **スキャナは固定・検証済み**: CI テンプレートは GitHub Actions をすべてコミット SHA で、
  Semgrep イメージを digest で、gitleaks と Trivy のバイナリをバージョンと SHA-256 で
  固定しています。スキャナが失敗したときはジョブも失敗します (fail-closed)。
  2026 年 3 月の Trivy 侵害
  ([GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23))
  を踏まえ、スキャナの action や書き換え可能なタグは使っていません。sunaba 自身にも
  同じゲートを適用しています。

### `sunaba-cli` が守れないもの

- **`@latest` のエージェント CLI**: Claude Code / Codex は `@latest`、Antigravity CLI(`agy`)は公式インストーラで初回起動時に
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
- **セキュリティゲートは保証ではない**: `--stack security-ci` が検出するのは、
  既知のパターン (Semgrep) と、ロックファイルに記載された公開済みの脆弱性 (Trivy)
  です。認可やビジネスロジックの欠陥は見つけられません。また、
  `scripts/protect-branch.sh` でチェックを必須にするまではマージを止めません。
  これには public リポジトリか GitHub の有料プランが必要です。
  [SECURITY.md](SECURITY.md#merge-gates) を参照してください。
- **`--stack harness`**: 各エージェントセッション終了時に `bash .claude/hooks/verify.sh`
  を走らせる Claude Code Stop hook を仕込みます。hook はテンプレートなので、コードと
  同じ目で review してください。任意のローカルコマンドを実行できます。permissions リストは
  ルーチン操作の承認プロンプトを減らしますが、**セキュリティ境界ではありません。**

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

## 設計メモ / ロードマップ

大きめの設計変更は、コード化する前に [`thinking/`](thinking/) で
公開設計ドキュメントとして練ります。各エントリは「現状把握 → リサーチ
→ 独立した LLM レビュー → 統合提案」という自己完結セットです。

実装済みの設計(取り込んだ順):

- [`thinking/2026-05-09-harness-engineering/`](thinking/2026-05-09-harness-engineering/):
  `--stack harness` と `_files` によるテンプレート出力の仕組み。
- [`thinking/2026-05-09-stack-aware-agent-files/`](thinking/2026-05-09-stack-aware-agent-files/):
  stack ごとの `AGENTS.md` / `CLAUDE.md` / `skills.md` と、registry フラグで切り替える sync モード。
- [`thinking/2026-05-09-secrets-management/`](thinking/2026-05-09-secrets-management/):
  `.gitignore` の baseline、`--stack secrets`、Azure Foundry → APIM → Gemini →
  Cosmos の「key behind a proxy」パターン。
- [`thinking/2026-05-09-rules-and-autonomy/`](thinking/2026-05-09-rules-and-autonomy/):
  `--stack rules` と `--stack autopilot`。
- [`thinking/2026-05-09-multi-agent-orchestration/`](thinking/2026-05-09-multi-agent-orchestration/):
  `--stack multi-agent`。
- [`thinking/2026-06-07-antigravity-cli-migration/`](thinking/2026-06-07-antigravity-cli-migration/):
  Gemini CLI から Antigravity CLI (`agy`) への移行。
- [`thinking/2026-09-24-maruda-adoption/`](thinking/2026-09-24-maruda-adoption/):
  `--stack secrets` の検出不能バグの修正と gitleaks の堅牢化 (0.3.0)。
- [`thinking/2026-09-24-security-ci-gates/`](thinking/2026-09-24-security-ci-gates/):
  `--stack security-ci` と `scripts/protect-branch.sh` (0.3.0)。

設計メモのみで未実装のもの:
[`2026-05-22-e2e-evidence-artifacts/`](thinking/2026-05-22-e2e-evidence-artifacts/)、
[エンタープライズ開発エッセイ](thinking/2026-05-26-enterprise-development-improvements/)。
次は maruda 取り込みの Phase 3 (LLM によるセキュリティレビュー skill) の予定です。
全体の索引は [`thinking/README.md`](thinking/README.md)、リリース履歴は
[CHANGELOG.md](CHANGELOG.md) にあります。

## 謝辞

- 堅牢化した secret スキャンの workflow、`.gitleaks.toml` の運用方針、
  SHA 固定を監査するテスト、`security-ci` のゲート構成、成熟度の段階、
  ブランチ保護スクリプトは
  [northraystudio/maruda](https://github.com/northraystudio/maruda)
  (MIT, © 2026 NorthRay Studio株式会社) を元にしています。詳細は
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) と
  [`thinking/2026-09-24-maruda-adoption/`](thinking/2026-09-24-maruda-adoption/)、
  [`thinking/2026-09-24-security-ci-gates/`](thinking/2026-09-24-security-ci-gates/) を参照してください。

## ライセンス

MIT — [LICENSE](LICENSE) 参照。
