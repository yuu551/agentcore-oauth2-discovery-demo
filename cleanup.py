"""検証で作ったリソースを削除する（state.json に記録したものだけを消す）"""
import time

from common import forget, load_state, session

state = load_state()
ctl = session.client("bedrock-agentcore-control")
lam = session.client("lambda")
iam = session.client("iam")

# Gateway（先にターゲットを消す）
if gateway_id := state.get("gateway_id"):
    for t in ctl.list_gateway_targets(gatewayIdentifier=gateway_id)["items"]:
        ctl.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=t["targetId"])
    while ctl.list_gateway_targets(gatewayIdentifier=gateway_id)["items"]:
        time.sleep(5)
    ctl.delete_gateway(gatewayIdentifier=gateway_id)
    forget("gateway_id", "gateway_url")
    print("Gatewayを削除しました")

# アウトバウンド側
if name := state.get("provider_name"):
    ctl.delete_oauth2_credential_provider(name=name)
    forget("provider_name")
    print("プロバイダーを削除しました")
if name := state.get("workload_name"):
    ctl.delete_workload_identity(name=name)
    forget("workload_name")
    print("ワークロードIDを削除しました")

# Lambda関数とIAMロール
for fn in state.get("functions", []):
    lam.delete_function(FunctionName=fn)
    print("Lambda関数を削除しました:", fn)
forget("functions")
for role in state.get("roles", []):
    for p in iam.list_attached_role_policies(RoleName=role)["AttachedPolicies"]:
        iam.detach_role_policy(RoleName=role, PolicyArn=p["PolicyArn"])
    for policy in iam.list_role_policies(RoleName=role)["PolicyNames"]:
        iam.delete_role_policy(RoleName=role, PolicyName=policy)
    iam.delete_role(RoleName=role)
    print("IAMロールを削除しました:", role)
forget("roles")
