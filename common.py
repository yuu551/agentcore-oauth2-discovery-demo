import json
import pathlib
import time

import boto3

REGION = "us-east-1"
STATE = pathlib.Path("state.json")
session = boto3.Session(region_name=REGION)


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(**values):
    state = {**load_state(), **values}
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    return state


def remember(key, name):
    # 作成したリソースの名前を state.json のリストに追記する（後片付けはここに記録したものだけを消す）
    names = load_state().get(key, [])
    if name not in names:
        save_state(**{key: [*names, name]})


def forget(*keys):
    # 削除し終えたリソースの記録を state.json から外す
    state = {k: v for k, v in load_state().items() if k not in keys}
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def create_role(name, service, policy_arns=(), inline_policy=None):
    iam = session.client("iam")
    trust = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": service}, "Action": "sts:AssumeRole"}],
    }
    arn = iam.create_role(RoleName=name, AssumeRolePolicyDocument=json.dumps(trust))["Role"]["Arn"]
    remember("roles", name)
    for policy_arn in policy_arns:
        iam.attach_role_policy(RoleName=name, PolicyArn=policy_arn)
    if inline_policy:
        iam.put_role_policy(RoleName=name, PolicyName="inline", PolicyDocument=json.dumps(inline_policy))
    time.sleep(10)  # IAMロールの反映待ち
    return arn
