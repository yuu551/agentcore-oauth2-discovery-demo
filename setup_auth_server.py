"""最小のOAuth 2.0認可サーバーをLambda関数URLで公開する"""
import io
import pathlib
import secrets
import subprocess
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from common import create_role, remember, save_state, session

NAME = "oauth2-only-as"
BUILD = pathlib.Path("build/auth_server")

# 依存ライブラリをLambda（arm64）向けに取得してzipにまとめる
subprocess.run(
    ["uv", "pip", "install", "--target", str(BUILD), "--python-platform", "aarch64-manylinux2014",
     "--python-version", "3.14", "--only-binary", ":all:", "pyjwt", "cryptography"],
    check=True,
)
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    for f in BUILD.rglob("*"):
        z.write(f, f.relative_to(BUILD))
    z.write("auth_server/app.py", "app.py")

# 検証用なので署名鍵とクライアントシークレットはその場で作って環境変数に渡す
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
client_id, client_secret = "demo-client", secrets.token_urlsafe(32)

role_arn = create_role(f"{NAME}-role", "lambda.amazonaws.com",
                       ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"])
lam = session.client("lambda")
lam.create_function(
    FunctionName=NAME, Runtime="python3.14", Architectures=["arm64"], Role=role_arn,
    Handler="app.handler", Code={"ZipFile": buf.getvalue()}, Timeout=10,
    Environment={"Variables": {"CLIENT_ID": client_id, "CLIENT_SECRET": client_secret, "PRIVATE_KEY_PEM": pem}},
)
remember("functions", NAME)
lam.get_waiter("function_active_v2").wait(FunctionName=NAME)

url = lam.create_function_url_config(FunctionName=NAME, AuthType="NONE")["FunctionUrl"].rstrip("/")
lam.add_permission(FunctionName=NAME, StatementId="public-url", Action="lambda:InvokeFunctionUrl",
                   Principal="*", FunctionUrlAuthType="NONE")
lam.add_permission(FunctionName=NAME, StatementId="public-invoke", Action="lambda:InvokeFunction",
                   Principal="*", InvokedViaFunctionUrl=True)

state = save_state(
    issuer=url,
    discovery_url=f"{url}/.well-known/oauth-authorization-server",
    client_id=client_id,
    client_secret=client_secret,
)
print("discovery_url:", state["discovery_url"])
