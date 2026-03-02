import os
import boto3

sns = boto3.client('sns')

def lambda_handler(event, context):

    mute = os.environ.get("MUTE_ALARM", "false")
    topic_arn = os.environ.get("SNS_TOPIC_ARN")

    if mute == "true":
        print("Tenant A alarm muted.")
        return {
            "statusCode": 200,
            "body": "Alarm muted"
        }

    if not topic_arn:
        print("SNS_TOPIC_ARN missing.")
        return {
            "statusCode": 500,
            "body": "SNS topic not configured"
        }

    sns.publish(
        TopicArn=topic_arn,
        Message="Alarm triggered for Tenant A",
        Subject="Tenant A Alert"
    )

    print("Notification sent for Tenant A")

    return {
        "statusCode": 200,
        "body": "Notification sent"
    }
