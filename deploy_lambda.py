"""
Script: deploy_lambda.py
Description: Provisions and deploys the AWS Lambda serverless validation pipeline:
             - Creates IAM role: food-waste-lambda-execution-role
             - Packages and deploys Lambda function: food-waste-validator (Python 3.12)
             - Creates Amazon SNS topic: food-waste-high-waste-alerts
             - Subscribes alert email (naveenk24@karunya.edu.in)
             - Configures Amazon S3 bucket event notification (s3:ObjectCreated:* on raw-data/*.csv)
"""

import os
import sys
import time
import json
import zipfile
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def load_env():
    env_vars = {}
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars


def update_env(updates):
    env_vars = load_env()
    env_vars.update(updates)
    with open('.env', 'w') as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")
    print(f"Updated .env with: {list(updates.keys())}")


def setup_sns_topic(session, region, email="naveenk24@karunya.edu.in"):
    print("\n1. Setting up Amazon SNS Alert Topic...")
    sns = session.client('sns', region_name=region)
    topic_name = "food-waste-high-waste-alerts"

    try:
        resp = sns.create_topic(Name=topic_name)
        topic_arn = resp['TopicArn']
        print(f"SNS Topic created/found: {topic_arn}")

        # Subscribe email address
        print(f"Subscribing email: {email}...")
        sub_resp = sns.subscribe(
            TopicArn=topic_arn,
            Protocol='email',
            Endpoint=email
        )
        print(f"Subscription initiated (Status: {sub_resp.get('SubscriptionArn')}).")
        print(f"AWS will send a confirmation email to {email}. Click the link to confirm.")
        return topic_arn
    except Exception as e:
        print(f"Error setting up SNS topic: {e}")
        return None


def setup_lambda_role(session, bucket_name):
    print("\n2. Setting up IAM Role for Lambda...")
    iam = session.client('iam')
    role_name = "food-waste-lambda-execution-role"

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }

    try:
        try:
            role = iam.get_role(RoleName=role_name)
            role_arn = role['Role']['Arn']
            print(f"IAM role '{role_name}' already exists: {role_arn}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                print(f"Creating IAM role '{role_name}'...")
                role = iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Execution role for Food Waste Lambda validation function"
                )
                role_arn = role['Role']['Arn']
                print(f"Created IAM role: {role_arn}")
            else:
                raise e

        # Attach CloudWatch Logs basic execution
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )

        # Attach S3 and SNS inline policy
        s3_sns_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "sns:Publish"
                    ],
                    "Resource": "*"
                }
            ]
        }
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="FoodWasteLambdaS3SNSPolicy",
            PolicyDocument=json.dumps(s3_sns_policy)
        )
        print("Attached S3 and SNS policies to Lambda role.")

        # Allow IAM propagation
        time.sleep(5)
        return role_arn
    except Exception as e:
        print(f"Error configuring IAM role: {e}")
        return None


def package_lambda_zip():
    print("\n3. Packaging Lambda code...")
    zip_path = "lambda_deployment_package.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write("lambda_function.py", arcname="lambda_function.py")
    with open(zip_path, 'rb') as f:
        zip_bytes = f.read()
    print(f"Packaged {zip_path} ({len(zip_bytes)} bytes)")
    return zip_bytes


def deploy_lambda_function(session, region, role_arn, zip_bytes, sns_arn):
    print("\n4. Deploying AWS Lambda Function...")
    client = session.client('lambda', region_name=region)
    func_name = "food-waste-validator"

    env_variables = {
        'HIGH_WASTE_THRESHOLD': '25.0'
    }
    if sns_arn:
        env_variables['SNS_TOPIC_ARN'] = sns_arn

    try:
        try:
            client.get_function(FunctionName=func_name)
            print(f"Lambda function '{func_name}' exists. Updating code and configuration...")
            client.update_function_code(
                FunctionName=func_name,
                ZipFile=zip_bytes
            )
            # Wait for code update
            time.sleep(3)
            client.update_function_configuration(
                FunctionName=func_name,
                Role=role_arn,
                Handler="lambda_function.lambda_handler",
                Runtime="python3.12",
                Timeout=60,
                MemorySize=256,
                Environment={'Variables': env_variables}
            )
            resp = client.get_function(FunctionName=func_name)
            func_arn = resp['Configuration']['FunctionArn']
            print(f"Lambda function updated successfully: {func_arn}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"Creating Lambda function '{func_name}' (Python 3.12, 60s timeout)...")
                resp = client.create_function(
                    FunctionName=func_name,
                    Runtime="python3.12",
                    Role=role_arn,
                    Handler="lambda_function.lambda_handler",
                    Code={'ZipFile': zip_bytes},
                    Timeout=60,
                    MemorySize=256,
                    Environment={'Variables': env_variables},
                    Description="Event-driven validation pipeline for canteen food waste telemetry"
                )
                func_arn = resp['FunctionArn']
                print(f"Lambda function created: {func_arn}")
            else:
                raise e

        return func_arn
    except Exception as e:
        print(f"Error deploying Lambda function: {e}")
        return None


def configure_s3_trigger(session, region, bucket_name, lambda_arn):
    print("\n5. Configuring S3 Bucket Event Trigger...")
    lambda_client = session.client('lambda', region_name=region)
    s3_client = session.client('s3', region_name=region)
    func_name = "food-waste-validator"

    # Add invoke permission for S3
    statement_id = "s3-invoke-food-waste-validator"
    try:
        lambda_client.add_permission(
            FunctionName=func_name,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{bucket_name}"
        )
        print("Added S3 invoke permission to Lambda policy.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceConflictException':
            print("S3 invoke permission already exists.")
        else:
            print(f"Notice on add_permission: {e}")

    # Configure S3 bucket notification
    notification_config = {
        'LambdaFunctionConfigurations': [
            {
                'Id': 'raw-data-csv-upload-trigger',
                'LambdaFunctionArn': lambda_arn,
                'Events': ['s3:ObjectCreated:*'],
                'Filter': {
                    'Key': {
                        'FilterRules': [
                            {'Name': 'prefix', 'Value': 'raw-data/'},
                            {'Name': 'suffix', 'Value': '.csv'}
                        ]
                    }
                }
            }
        ]
    }

    try:
        s3_client.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=notification_config
        )
        print(f"Configured S3 event notification on s3://{bucket_name}/raw-data/*.csv -> {lambda_arn}")
        return True
    except Exception as e:
        print(f"Error setting bucket notification: {e}")
        return False


def main():
    env = load_env()
    region = os.getenv('AWS_DEFAULT_REGION', env.get('AWS_DEFAULT_REGION', 'ap-south-1'))
    bucket_name = os.getenv('S3_BUCKET_NAME', env.get('S3_BUCKET_NAME'))
    email = "naveenk24@karunya.edu.in"

    print("=" * 70)
    print("Deploying Serverless Validation Pipeline (AWS Lambda + S3 + SNS)")
    print(f"Target Region: {region}")
    print(f"Target Bucket: {bucket_name}")
    print(f"Alert Email:   {email}")
    print("=" * 70)

    try:
        session = boto3.Session(region_name=region)
        sts = session.client('sts')
        caller = sts.get_caller_identity()
        account_id = caller['Account']

        if not bucket_name:
            bucket_name = f"food-waste-canteen-{account_id}-{region}"

        # 1. SNS
        sns_arn = setup_sns_topic(session, region, email)
        if sns_arn:
            update_env({'SNS_TOPIC_ARN': sns_arn})

        # 2. IAM Role
        role_arn = setup_lambda_role(session, bucket_name)
        if not role_arn:
            print("Failed to configure IAM role.")
            sys.exit(1)

        # 3. Zip package
        zip_bytes = package_lambda_zip()

        # 4. Deploy Lambda
        lambda_arn = deploy_lambda_function(session, region, role_arn, zip_bytes, sns_arn)
        if not lambda_arn:
            print("Failed to deploy Lambda function.")
            sys.exit(1)

        # 5. S3 trigger
        configure_s3_trigger(session, region, bucket_name, lambda_arn)

        print("\n" + "=" * 70)
        print("Serverless Validation Pipeline Deployment Completed.")
        print(f"Lambda Function: food-waste-validator")
        print(f"SNS Topic:       {sns_arn}")
        print("=" * 70)

    except (NoCredentialsError, ClientError) as e:
        print(f"\nAWS connection notice: {e}")
        print("Lambda deployment script ready for execution once AWS credentials are authenticated.")


if __name__ == '__main__':
    main()
