import json
import boto3
import os
import random

dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')

TABLE_NAME = os.environ['TABLE_NAME']


def build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body)
    }


def lambda_handler(event, context):

    table = dynamodb.Table(TABLE_NAME)
    http_method = event.get("httpMethod", "")

    # Handle preflight OPTIONS request
    if http_method == "OPTIONS":
        return build_response(200, "OK")

    # ---------------- GET /status ----------------
    if http_method == "GET":

        response = table.scan()
        tenants = response.get("Items", [])

        dashboard_data = []

        for tenant in tenants:
            dashboard_data.append({
                "tenantName": tenant["tenantName"],
                "alarmMuted": tenant.get("alarmMuted", False),
                "webCpu": random.choice(["OK", "HIGH"]),
                "webMemory": random.choice(["OK", "HIGH"]),
                "tm1Cpu": random.choice(["OK", "HIGH"]),
                "tm1Memory": random.choice(["OK", "HIGH"]),
                "endpointHealth": 200
            })

        return build_response(200, dashboard_data)

    # ---------------- POST /toggle ----------------
    if http_method == "POST":

        body = json.loads(event.get("body", "{}"))
        tenant_name = body.get("tenantName")
        action = body.get("action")

        if not tenant_name or not action:
            return build_response(400, "Invalid request payload")

        response = table.get_item(Key={"tenantName": tenant_name})

        if "Item" not in response:
            return build_response(404, "Tenant not found")

        function_name = response["Item"]["lambdaName"]
        mute_value = action == "turn_off"

        current_config = lambda_client.get_function_configuration(
            FunctionName=function_name
        )

        existing_env = current_config.get("Environment", {}).get("Variables", {})
        existing_env["MUTE_ALARM"] = str(mute_value).lower()

        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={"Variables": existing_env}
        )

        table.update_item(
            Key={"tenantName": tenant_name},
            UpdateExpression="SET alarmMuted = :val",
            ExpressionAttributeValues={":val": mute_value}
        )

        return build_response(200, "Updated successfully")

    return build_response(405, "Method not allowed")
