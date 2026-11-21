# agentcore-oauth2-discovery-demo

Amazon Bedrock AgentCore IdentityのディスカバリーURLに、OAuth 2.0の認可サーバーメタデータ（RFC 8414）のURLを指定して試すサンプルです。

解説記事: https://dev.classmethod.jp/articles/agentcore-identity-oauth2-discovery/

## 試せること

- 前半: OIDCのメタデータを公開しない最小のOAuth 2.0認可サーバーをLambda関数URLで公開し、Gatewayのインバウンド認可とIdentityのカスタムOAuthプロバイダーの両方に指定します。
- 後半: Atlassian MCP v2の認可サーバーをディスカバリーURLでプロバイダーに登録し、ユーザーの同意を経て取得したトークンでJiraにタスクを作成します。

## 前提

- Python 3.14と[uv](https://docs.astral.sh/uv/)
- AWSの認証を済ませておくこと（リージョンは `common.py` の `REGION` で指定、デフォルトはus-east-1）
- 後半はAtlassianのサイト（Jiraの無料プランで作成可能）と、管理画面でAgentCoreのドメインを許可しておくこと

前半の認可サーバーは検証用に認証なしの関数URLで公開します。試し終わったら後片付けのスクリプトで削除してください。

## 使い方

```bash
uv sync
```

### 前半: 自作の認可サーバー

```bash
uv run setup_auth_server.py   # 認可サーバーをLambda関数URLで公開
uv run setup_gateway.py       # discoveryUrlにRFC 8414のURLを指定してGatewayを作成
uv run call_gateway.py        # トークンなし・別の鍵で署名したJWT・本物のJWTでGatewayを呼び出す
uv run outbound.py            # カスタムOAuthプロバイダーを作成してM2Mでトークンを取得
```

### 後半: Atlassian MCP

Atlassianの管理画面（admin.atlassian.com）の「コネクタ」→「Atlassian MCP サーバー」で、次のドメインを追加しておきます。

```text
https://bedrock-agentcore.us-east-1.amazonaws.com/**
```

```bash
uv run atlassian_setup.py     # プロバイダーを作成し、DCRでクライアントを登録
uv run atlassian_connect.py   # 表示された認可URLをブラウザで開いて同意し、ツール一覧を取得
```

`atlassian_jira.py` の `SITE_URL` と `PROJECT_KEY` を自分のサイトとプロジェクトに書き換えてから実行します。

```bash
uv run atlassian_jira.py      # Jiraにタスクを作成
```

## 後片付け

```bash
uv run cleanup.py
uv run atlassian_cleanup.py
```

各スクリプトは作成したリソースの名前やIDを `state.json` に記録し、後片付けは記録されたものだけを削除します。Lambdaのロググループ、Atlassian側で追加したドメイン、作成したJiraのタスクは必要に応じて手動で削除してください。

## ファイル

| ファイル | 内容 |
| --- | --- |
| `common.py` | リージョン、`state.json` の読み書き、IAMロールの作成 |
| `auth_server/app.py` | client_credentialsだけに対応した最小の認可サーバー（Lambda） |
| `tool/app.py` | Gatewayに登録するツール（Lambda） |
| `setup_auth_server.py` | 認可サーバーのデプロイ |
| `setup_gateway.py` | ツールとGatewayの作成 |
| `call_gateway.py` | Gatewayの呼び出し |
| `outbound.py` | カスタムOAuthプロバイダーの作成とM2Mのトークン取得 |
| `atlassian_setup.py` | Atlassian用のワークロードIDとプロバイダーの作成、DCR |
| `atlassian_connect.py` | ユーザーの同意を経たトークン取得とMCPクライアント |
| `atlassian_jira.py` | Jiraのタスク作成 |
| `cleanup.py` / `atlassian_cleanup.py` | 後片付け |
