import json
import os

import boto3
import boto3.session
from botocore.exceptions import ClientError


def get_aws_secrets() -> dict:
    secret_name = os.environ.get("AWS_SECRETS_NAME", "")
    region_name = os.environ.get("AWS_REGION", "us-east-1")

    if not secret_name:
        return {}

    session = boto3.session.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name=region_name,
    )

    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e

    return json.loads(response["SecretString"])
