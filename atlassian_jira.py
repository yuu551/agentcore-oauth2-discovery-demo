"""Atlassian MCP v2のツールでJiraのタスクを作成する"""
import json

from atlassian_connect import MCPClient, get_token

SITE_URL = "https://your-site.atlassian.net"  # タスクを作るサイトのURLに置き換える
PROJECT_KEY = "KAN"  # タスクを作るプロジェクトのキーに置き換える（無料サイトでは最初からあるKAN）

mcp = MCPClient(get_token())
# アクセスできるサイトの一覧から、URLが一致するサイトのcloudIdを使う
resources = json.loads(mcp.call_tool("getAccessibleAtlassianResources", {}))["data"]["resources"]
cloud_id = next(r["cloudId"] for r in resources if r["url"] == SITE_URL)
created = mcp.call_tool("createJiraIssue", {
    "cloudId": cloud_id,
    "projectKey": PROJECT_KEY,
    "issueType": "Task",
    "summary": "AgentCore IdentityからAtlassian MCP経由で作成したタスク",
    "description": "Amazon Bedrock AgentCore IdentityのカスタムOAuthプロバイダーに、RFC 8414のディスカバリーURLだけを設定して取得したトークンで作成しました。",
})
print("作成したタスク:", created)
