def handler(event, context):
    # Gatewayから呼ばれるツール。引数のnameにあいさつを返す
    return {"message": f"こんにちは、{event.get('name', 'ゲスト')}さん！"}
