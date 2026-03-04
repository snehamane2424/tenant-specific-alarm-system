import os
import boto3

sns = boto3.client('sns')

def lambda_handler(event, context):

    mute = os.environ.get("MUTE_ALARM", "false")
    topic_arn = os.environ.get("SNS_TOPIC_ARN")

    if mute == "true":
        print("Tenant A alarm muted.")
        return

    sns.publish(
        TopicArn=topic_arn,
        Message="Alarm triggered for Tenant A",
        Subject="Tenant A Alert"
    )

    print("Notification sent for Tenant A")
