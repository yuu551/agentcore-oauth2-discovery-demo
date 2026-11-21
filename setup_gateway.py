"""OAuth 2.0のディスカバリーURLでインバウンド認可するGatewayを作る"""
import io
import time
import zipfile

from common import create_role, load_state, remember, save_state, session

state = load_state()
lam = session.client("lambda")
ctl = session.client("bedrock-agentcore-control")

# ツールにするLambda関数
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.write("tool/app.py", "app.py")
tool_role = create_role("oauth2-demo-tool-role", "lambda.amazonaws.com",
                        ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"])
tool_arn = lam.create_function(
    FunctionName="oauth2-demo-tool", Runtime="python3.14", Architectures=["arm64"], Role=tool_role,
    Handler="app.handler", Code={"ZipFile": buf.getvalue()},
)["FunctionArn"]
remember("functions", "oauth2-demo-tool")

gateway_role = create_role(
    "oauth2-demo-gateway-role", "bedrock-agentcore.amazonaws.com",
    inline_policy={"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": "lambda:InvokeFunction", "Resource": tool_arn}]},
)

# discoveryUrl に oauth-authorization-server を指定する（今回のポイント）
gateway = ctl.create_gateway(
    name="oauth2-discovery-demo",
    roleArn=gateway_role,
    protocolType="MCP",
    authorizerType="CUSTOM_JWT",
    authorizerConfiguration={
        "customJWTAuthorizer": {
            "discoveryUrl": state["discovery_url"],
            "allowedClients": [state["client_id"]],
        }
    },
)
gateway_id = gateway["gatewayId"]
save_state(gateway_id=gateway_id, gateway_url=gateway["gatewayUrl"])
while (status := ctl.get_gateway(gatewayIdentifier=gateway_id)["status"]) == "CREATING":
    time.sleep(5)
print("gateway:", status)

target = ctl.create_gateway_target(
    gatewayIdentifier=gateway_id,
    name="greeting",
    targetConfiguration={"mcp": {"lambda": {
        "lambdaArn": tool_arn,
        "toolSchema": {"inlinePayload": [{
            "name": "say_hello",
            "description": "名前を受け取ってあいさつを返す",
            "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        }]},
    }}},
    credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
)
while (t := ctl.get_gateway_target(gatewayIdentifier=gateway_id, targetId=target["targetId"]))["status"] == "CREATING":
    time.sleep(5)
print("target:", t["status"])

print(ctl.get_gateway(gatewayIdentifier=gateway_id)["authorizerConfiguration"])
