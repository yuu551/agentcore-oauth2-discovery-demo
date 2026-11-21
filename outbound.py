"""OAuth 2.0のディスカバリーURLでカスタムOAuthプロバイダーを作り、M2Mでトークンを取得する"""
import json

import jwt

from call_gateway import mcp
from common import load_state, save_state, session

state = load_state()
ctl = session.client("bedrock-agentcore-control")
dp = session.client("bedrock-agentcore")

ctl.create_workload_identity(name="oauth2-demo-agent")
save_state(workload_name="oauth2-demo-agent")

# oauthDiscovery に oauth-authorization-server を指定する（今回のポイント）
provider = ctl.create_oauth2_credential_provider(
    name="oauth2-only-as",
    credentialProviderVendor="CustomOauth2",
    oauth2ProviderConfigInput={
        "customOauth2ProviderConfig": {
            "oauthDiscovery": {"discoveryUrl": state["discovery_url"]},
            "clientId": state["client_id"],
            "clientSecret": state["client_secret"],
        }
    },
)
save_state(provider_name="oauth2-only-as")
discovered = provider["oauth2ProviderConfigOutput"]["customOauth2ProviderConfig"]["oauthDiscovery"]
print("ディスカバリー結果:", json.dumps(discovered, indent=2, ensure_ascii=False))

# エージェントの立場でAgentCore Identityにトークンを頼む（ユーザーなしのM2M）
workload_token = dp.get_workload_access_token(workloadName="oauth2-demo-agent")["workloadAccessToken"]
access_token = dp.get_resource_oauth2_token(
    workloadIdentityToken=workload_token,
    resourceCredentialProviderName="oauth2-only-as",
    scopes=["demo.read"],
    oauth2Flow="M2M",
)["accessToken"]
print("取得したトークンの中身:", json.dumps(jwt.decode(access_token, options={"verify_signature": False}), indent=2))

# 取得したトークンで、さきほどのGatewayを呼び出す
res = mcp("tools/call", {"name": "greeting___say_hello", "arguments": {"name": "AgentCore Identity"}}, access_token)
print("Gateway呼び出し:", res.status_code, res.json()["result"]["content"][0]["text"])
