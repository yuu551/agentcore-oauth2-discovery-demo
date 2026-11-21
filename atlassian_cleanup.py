"""Atlassian MCPの接続で作ったリソースを削除する（state.json に記録したものだけを消す）"""
from common import forget, load_state, session

state = load_state()
ctl = session.client("bedrock-agentcore-control")
if name := state.get("atlassian_provider"):
    ctl.delete_oauth2_credential_provider(name=name)
    print("プロバイダーを削除しました")
if name := state.get("atlassian_workload"):
    ctl.delete_workload_identity(name=name)
    print("ワークロードIDを削除しました")
forget("atlassian_provider", "atlassian_workload", "atlassian_return_url")
