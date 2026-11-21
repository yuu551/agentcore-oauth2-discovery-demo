"""Atlassian MCP v2の認可サーバーを、ディスカバリーURLだけでカスタムOAuthプロバイダーに登録する"""
import httpx

from common import save_state, session

# https://mcp.atlassian.com/.well-known/oauth-protected-resource/v2/mcp の authorization_servers にある認可サーバー
DISCOVERY_URL = "https://auth.atlassian.com/.well-known/oauth-authorization-server/VCeDsk8ZHncYF1g234fKtc4lNipbBhu3"
RETURN_URL = "http://localhost:8799/callback"  # 同意後にブラウザを戻すローカルのURL
WORKLOAD = "atlassian-demo-agent"
PROVIDER = "atlassian-mcp-v2"
ctl = session.client("bedrock-agentcore-control")

ctl.create_workload_identity(name=WORKLOAD, allowedResourceOauth2ReturnUrls=[RETURN_URL])
save_state(atlassian_workload=WORKLOAD, atlassian_return_url=RETURN_URL)


def provider_config(client_id, client_secret):
    return {"customOauth2ProviderConfig": {
        "oauthDiscovery": {"discoveryUrl": DISCOVERY_URL},
        "clientId": client_id,
        "clientSecret": client_secret,
    }}


# コールバックURLを知るため、仮のクライアントIDで先に作る
callback_url = ctl.create_oauth2_credential_provider(
    name=PROVIDER, credentialProviderVendor="CustomOauth2",
    oauth2ProviderConfigInput=provider_config("placeholder", "placeholder"),
)["callbackUrl"]
save_state(atlassian_provider=PROVIDER)

# メタデータの registration_endpoint に、コールバックURLをリダイレクト先として登録する（DCR）
metadata = httpx.get(DISCOVERY_URL).json()
client = httpx.post(metadata["registration_endpoint"], json={
    "client_name": "agentcore-oauth2-discovery-demo",
    "redirect_uris": [callback_url],
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "client_secret_basic",
}).raise_for_status().json()

ctl.update_oauth2_credential_provider(
    name=PROVIDER, credentialProviderVendor="CustomOauth2",
    oauth2ProviderConfigInput=provider_config(client["client_id"], client["client_secret"]),
)
print("callbackUrl:", callback_url)
print("登録したクライアント:", {k: client.get(k) for k in ["client_name", "redirect_uris", "token_endpoint_auth_method"]})
