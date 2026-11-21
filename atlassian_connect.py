"""ユーザーの同意を経てAtlassian MCP v2のトークンを取得し、ツール一覧を取得する"""
import http.server
import json
import time
import urllib.parse

import httpx

from common import load_state, session

state = load_state()
dp = session.client("bedrock-agentcore")
USER_ID = "demo-user"  # ローカルで1人だけで試すので固定のユーザーIDにする
MCP_URL = "https://mcp.atlassian.com/v2/mcp"
# MCPサーバーの保護リソースメタデータに載っているスコープをすべて要求する
SCOPES = httpx.get("https://mcp.atlassian.com/.well-known/oauth-protected-resource/v2/mcp").json()["scopes_supported"]


def request_token(workload_token, session_uri=None):
    params = dict(workloadIdentityToken=workload_token, resourceCredentialProviderName=state["atlassian_provider"],
                  scopes=SCOPES, resources=[MCP_URL], oauth2Flow="USER_FEDERATION",
                  resourceOauth2ReturnUrl=state["atlassian_return_url"])
    if session_uri:
        params["sessionUri"] = session_uri
    return dp.get_resource_oauth2_token(**params)


def wait_for_callback(session_uri):
    # 戻り先（/callback）に、認可を始めたときと同じ session_id が届くまで待つ
    received = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            session_id = urllib.parse.parse_qs(url.query).get("session_id", [""])[0]
            ok = url.path == "/callback" and session_id == session_uri
            if ok:
                received["session_id"] = session_id
            else:
                print("認可を始めたリクエストと一致しないので無視しました:", self.path, flush=True)
            self.send_response(200 if ok else 400)
            self.send_header("content-type", "text/plain; charset=utf-8")
            self.end_headers()
            message = "同意が完了しました。ターミナルに戻ってください。" if ok else "認可を始めたリクエストと一致しません。"
            self.wfile.write(message.encode())

        def log_message(self, *args):
            pass

    deadline = time.time() + 600  # 認可URLの有効期限は10分
    with http.server.HTTPServer(("localhost", 8799), Handler) as server:
        while "session_id" not in received:
            server.timeout = deadline - time.time()
            if server.timeout <= 0:
                raise TimeoutError("10分以内に同意が完了しませんでした")
            server.handle_request()
    return received["session_id"]


def get_token():
    workload_token = dp.get_workload_access_token_for_user_id(
        workloadName=state["atlassian_workload"], userId=USER_ID)["workloadAccessToken"]
    result = request_token(workload_token)
    if "accessToken" not in result:
        print("認可URL:", result["authorizationUrl"])
        print("ブラウザで開いて同意してください。戻り先を待っています...", flush=True)
        session_id = wait_for_callback(result["sessionUri"])
        print("戻り先で認可を始めたときと同じsession_idを受け取りました")
        # 認可を始めたユーザーと同じユーザーIDで、受け取ったセッションの完了を通知する
        dp.complete_resource_token_auth(userIdentifier={"userId": USER_ID}, sessionUri=session_id)
        result = request_token(workload_token, session_id)
    print("アクセストークンを取得しました（先頭）:", result["accessToken"][:12], "...")
    return result["accessToken"]


class MCPClient:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"}
        self.next_id = 1
        res, init = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                "clientInfo": {"name": "agentcore-demo", "version": "0.1"}})
        self.headers["Mcp-Session-Id"] = res.headers["mcp-session-id"]
        # 初期化で合意したプロトコルバージョンを以降のリクエストに付ける
        self.headers["MCP-Protocol-Version"] = init["result"]["protocolVersion"]
        self.request("notifications/initialized", {}, notify=True)
        print("initialize:", res.status_code, init["result"]["serverInfo"])

    def request(self, method, params, notify=False):
        body = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            body["id"] = self.next_id
            self.next_id += 1
        res = httpx.post(MCP_URL, headers=self.headers, json=body, timeout=60)
        text = res.text
        if "text/event-stream" in res.headers.get("content-type", ""):
            text = next((l[5:] for l in text.splitlines() if l.startswith("data:")), "{}")
        return res, (json.loads(text) if text.strip() else {})

    def call_tool(self, name, arguments):
        _, body = self.request("tools/call", {"name": name, "arguments": arguments})
        return body["result"]["content"][0]["text"]


if __name__ == "__main__":
    mcp = MCPClient(get_token())
    res, tools = mcp.request("tools/list", {})
    names = [t["name"] for t in tools["result"]["tools"]]
    print("tools/list:", res.status_code, f"{len(names)}件", names)
