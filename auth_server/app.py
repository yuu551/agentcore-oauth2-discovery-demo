"""OIDCのメタデータを公開しない最小のOAuth 2.0認可サーバー（client_credentialsのみ）"""
import base64
import json
import os
import time
import uuid
from urllib.parse import parse_qs

import jwt
from cryptography.hazmat.primitives import serialization
from jwt.algorithms import RSAAlgorithm

KID = "demo-key-1"
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
PRIVATE_KEY = serialization.load_pem_private_key(os.environ["PRIVATE_KEY_PEM"].encode(), password=None)
PUBLIC_JWK = {**json.loads(RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key())), "kid": KID, "use": "sig", "alg": "RS256"}


def response(status, body):
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def handler(event, context):
    method = event["requestContext"]["http"]["method"]
    path = event["rawPath"]
    issuer = f"https://{event['requestContext']['domainName']}"
    print(json.dumps({"method": method, "path": path, "user_agent": event["headers"].get("user-agent")}))

    # RFC 8414 の認可サーバーメタデータ（openid-configuration は用意しない）
    # client_credentials だけなので認可エンドポイントは持たず、response_type も空にする
    if method == "GET" and path == "/.well-known/oauth-authorization-server":
        return response(200, {
            "issuer": issuer,
            "token_endpoint": f"{issuer}/token",
            "jwks_uri": f"{issuer}/jwks",
            "response_types_supported": [],
            "grant_types_supported": ["client_credentials"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
            "scopes_supported": ["demo.read"],
        })

    if method == "GET" and path == "/jwks":
        return response(200, {"keys": [PUBLIC_JWK]})

    if method == "POST" and path == "/token":
        raw = event.get("body") or ""
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode()
        form = {k: v[0] for k, v in parse_qs(raw).items()}

        # client_secret_basic と client_secret_post の両方を受け付ける
        auth = event["headers"].get("authorization", "")
        if auth.startswith("Basic "):
            client_id, _, client_secret = base64.b64decode(auth[6:]).decode().partition(":")
        else:
            client_id, client_secret = form.get("client_id"), form.get("client_secret")
        print(json.dumps({"grant_type": form.get("grant_type"), "client_id": client_id, "scope": form.get("scope")}))

        if (client_id, client_secret) != (CLIENT_ID, CLIENT_SECRET):
            return response(401, {"error": "invalid_client"})
        if form.get("grant_type") != "client_credentials":
            return response(400, {"error": "unsupported_grant_type"})

        now = int(time.time())
        claims = {
            "iss": issuer,
            "sub": client_id,
            "client_id": client_id,
            "scope": form.get("scope", "demo.read"),
            "iat": now,
            "exp": now + 3600,
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": KID})
        return response(200, {"access_token": token, "token_type": "Bearer", "expires_in": 3600})

    return response(404, {"error": "not_found"})
