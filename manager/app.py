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
    method = event.get("httpMethod", "")

    # Handle preflight
    if method == "OPTIONS":
        return build_response(200, "OK")

    
    # --------------- GET /status -----------------
    
    if method == "GET":

        response = table.scan()
        tenants = response.get("Items", [])

        dashboard_data = []

        for tenant in tenants:
            function_name = tenant["lambdaName"]

            # Get real Lambda configuration
            config = lambda_client.get_function_configuration(
                FunctionName=function_name
            )

            env_vars = config.get("Environment", {}).get("Variables", {})
            mute_value = env_vars.get("MUTE_ALARM", "false") == "true"

            # Sync DynamoDB alarmMuted automatically
            table.update_item(
                Key={"tenantName": tenant["tenantName"]},
                UpdateExpression="SET alarmMuted = :val",
                ExpressionAttributeValues={":val": mute_value}
            )

            dashboard_data.append({
                "tenantName": tenant["tenantName"],
                "alarmMuted": mute_value,
                "webCpu": random.choice(["OK", "HIGH"]),
                "webMemory": random.choice(["OK", "HIGH"]),
                "tm1Cpu": random.choice(["OK", "HIGH"]),
                "tm1Memory": random.choice(["OK", "HIGH"]),
                "endpointHealth": 200
            })

        return build_response(200, dashboard_data)

    
    # ---------------- POST /toggle ------------------
    
    if method == "POST":

        body = json.loads(event.get("body", "{}"))
        tenant_name = body.get("tenantName")
        action = body.get("action")

        if not tenant_name or not action:
            return build_response(400, "Invalid request")

        response = table.get_item(Key={"tenantName": tenant_name})

        if "Item" not in response:
            return build_response(404, "Tenant not found")

        function_name = response["Item"]["lambdaName"]
        mute_value = action == "turn_off"

        ### Get current environment variables
        config = lambda_client.get_function_configuration(
            FunctionName=function_name
        )

        env_vars = config.get("Environment", {}).get("Variables", {})
        env_vars["MUTE_ALARM"] = str(mute_value).lower()

        ### ------------ Update Lambda configuration -------------------
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={"Variables": env_vars}
        )

        ### ---------------- WAIT until Lambda update completes --------------
        waiter = lambda_client.get_waiter('function_updated')
        waiter.wait(FunctionName=function_name)

        ### ------------ Confirm actual updated state ---------------
        updated_config = lambda_client.get_function_configuration(
            FunctionName=function_name
        )

        updated_env = updated_config.get("Environment", {}).get("Variables", {})
        confirmed_value = updated_env.get("MUTE_ALARM", "false") == "true"

        # ---------------- Sync DynamoDB with confirmed value ----------------
        table.update_item(
            Key={"tenantName": tenant_name},
            UpdateExpression="SET alarmMuted = :val",
            ExpressionAttributeValues={":val": confirmed_value}
        )

        # ---------------- Auto invoke tenant Lambda when alarm turned ON ---------------
        if not confirmed_value:
            lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='Event'
            )

        return build_response(200, "Toggle updated and synced successfully")

    return build_response(405, "Method not allowed")
