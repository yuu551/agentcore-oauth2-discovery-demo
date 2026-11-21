"""Gatewayのtools/listとtools/callを、トークンなし・ありで呼び出す"""
import sys
import time

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from common import load_state

state = load_state()


def get_token():
    # 自作の認可サーバーから client_credentials でトークンを取得する
    res = httpx.post(f"{state['issuer']}/token",
                     auth=(state["client_id"], state["client_secret"]),
                     data={"grant_type": "client_credentials", "scope": "demo.read"})
    return res.raise_for_status().json()["access_token"]


def mcp(method, params, token=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.post(state["gateway_url"], headers=headers,
                      json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})


if __name__ == "__main__":
    token = sys.argv[1] if len(sys.argv) > 1 else None
    res = mcp("tools/list", {})
    print("トークンなし:", res.status_code, res.text[:200])

    # 同じクレームで、認可サーバーとは別の鍵で署名したJWT
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    forged = jwt.encode({"iss": state["issuer"], "sub": state["client_id"], "client_id": state["client_id"],
                         "scope": "demo.read", "iat": now, "exp": now + 600},
                        other_key, algorithm="RS256", headers={"kid": "demo-key-1"})
    res = mcp("tools/list", {}, forged)
    print("別の鍵で署名:", res.status_code, res.text[:200])

    token = token or get_token()
    res = mcp("tools/list", {}, token)
    print("トークンあり:", res.status_code, [t["name"] for t in res.json()["result"]["tools"]])

    res = mcp("tools/call", {"name": "greeting___say_hello", "arguments": {"name": "神野"}}, token)
    print("ツール実行:", res.status_code, res.json()["result"]["content"][0]["text"])
