"""
Script: deploy_dashboard.py
Description: Builds the Docker image, pushes to Amazon ECR, and deploys the
             Streamlit dashboard to AWS App Runner with least-privilege permissions.
"""

import os
import sys
import time
import json
import base64
import subprocess
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


def get_or_create_ecr_repo(session, region, repo_name="food-waste-dashboard"):
    ecr = session.client('ecr', region_name=region)
    try:
        desc = ecr.describe_repositories(repositoryNames=[repo_name])
        uri = desc['repositories'][0]['repositoryUri']
        print(f"Existing ECR repository: {uri}")
        return uri
    except ClientError as e:
        if e.response['Error']['Code'] == 'RepositoryNotFoundException':
            print(f"Creating ECR repository '{repo_name}'...")
            resp = ecr.create_repository(repositoryName=repo_name)
            uri = resp['repository']['repositoryUri']
            print(f"Created ECR repository: {uri}")
            return uri
        else:
            raise e


def get_or_create_apprunner_roles(session, account_id, bucket_name):
    iam = session.client('iam')
    access_role_name = "food-waste-apprunner-access-role"
    instance_role_name = "food-waste-apprunner-instance-role"

    # 1. ECR access role (for App Runner to pull image from ECR)
    access_trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "build.apprunner.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    try:
        try:
            r = iam.get_role(RoleName=access_role_name)
            access_role_arn = r['Role']['Arn']
        except ClientError:
            r = iam.create_role(
                RoleName=access_role_name,
                AssumeRolePolicyDocument=json.dumps(access_trust),
                Description="App Runner build/pull access role"
            )
            access_role_arn = r['Role']['Arn']
            iam.attach_role_policy(
                RoleName=access_role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
            )
            print(f"Created App Runner access role: {access_role_arn}")
    except Exception as e:
        print(f"Notice on access role: {e}")
        access_role_arn = f"arn:aws:iam::{account_id}:role/{access_role_name}"

    # 2. Instance role (runtime permissions for app to read S3, Athena, Glue)
    instance_trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "tasks.apprunner.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    try:
        try:
            r = iam.get_role(RoleName=instance_role_name)
            instance_role_arn = r['Role']['Arn']
        except ClientError:
            r = iam.create_role(
                RoleName=instance_role_name,
                AssumeRolePolicyDocument=json.dumps(instance_trust),
                Description="App Runner runtime instance role"
            )
            instance_role_arn = r['Role']['Arn']

        # Custom least-privilege policy for dashboard
        app_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "athena:StartQueryExecution",
                        "athena:GetQueryExecution",
                        "athena:GetQueryResults",
                        "athena:GetWorkGroup"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "glue:GetDatabase",
                        "glue:GetTable",
                        "glue:GetPartitions"
                    ],
                    "Resource": "*"
                }
            ]
        }
        iam.put_role_policy(
            RoleName=instance_role_name,
            PolicyName="FoodWasteDashboardRuntimePolicy",
            PolicyDocument=json.dumps(app_policy)
        )
        print(f"Configured App Runner instance role: {instance_role_arn}")
    except Exception as e:
        print(f"Notice on instance role: {e}")
        instance_role_arn = f"arn:aws:iam::{account_id}:role/{instance_role_name}"

    return access_role_arn, instance_role_arn


def build_and_push_image(session, region, repo_uri):
    print("\n1. Authenticating Docker with Amazon ECR...")
    ecr = session.client('ecr', region_name=region)
    auth_data = ecr.get_authorization_token()
    token = auth_data['authorizationData'][0]['authorizationToken']
    user, password = base64.b64decode(token).decode('utf-8').split(':')
    endpoint = auth_data['authorizationData'][0]['proxyEndpoint']

    login_cmd = ['docker', 'login', '-u', user, '-p', password, endpoint]
    subprocess.run(login_cmd, check=True)

    print("\n2. Building Docker container image...")
    image_tag = f"{repo_uri}:latest"
    build_cmd = ['docker', 'build', '-t', image_tag, '.']
    subprocess.run(build_cmd, check=True)

    print("\n3. Pushing Docker image to Amazon ECR...")
    push_cmd = ['docker', 'push', image_tag]
    subprocess.run(push_cmd, check=True)
    print(f"Image successfully pushed: {image_tag}")
    return image_tag


def deploy_to_apprunner(session, region, image_tag, access_role_arn, instance_role_arn, bucket_name, athena_db):
    print("\n4. Deploying to AWS App Runner...")
    ar = session.client('apprunner', region_name=region)
    service_name = "food-waste-dashboard"

    service_config = {
        'ServiceName': service_name,
        'SourceConfiguration': {
            'ImageRepository': {
                'ImageIdentifier': image_tag,
                'ImageConfiguration': {
                    'Port': '8501',
                    'RuntimeEnvironmentVariables': {
                        'AWS_DEFAULT_REGION': region,
                        'S3_BUCKET_NAME': bucket_name,
                        'ATHENA_DB': athena_db
                    }
                },
                'ImageRepositoryType': 'ECR'
            },
            'AuthenticationConfiguration': {
                'AccessRoleArn': access_role_arn
            },
            'AutoDeploymentsEnabled': False
        },
        'InstanceConfiguration': {
            'Cpu': '1024',
            'Memory': '2048',
            'InstanceRoleArn': instance_role_arn
        }
    }

    try:
        # Check if service exists
        existing = ar.list_services().get('ServiceSummaryList', [])
        found_service = None
        for s in existing:
            if s['ServiceName'] == service_name:
                found_service = s
                break

        if found_service:
            print(f"Updating existing App Runner service: {found_service['ServiceArn']}...")
            ar.update_service(
                ServiceArn=found_service['ServiceArn'],
                SourceConfiguration=service_config['SourceConfiguration'],
                InstanceConfiguration=service_config['InstanceConfiguration']
            )
            arn = found_service['ServiceArn']
            url = f"https://{found_service['ServiceUrl']}"
        else:
            print(f"Creating new App Runner service '{service_name}'...")
            resp = ar.create_service(**service_config)
            arn = resp['Service']['ServiceArn']
            url = f"https://{resp['Service']['ServiceUrl']}"

        print("\n" + "=" * 70)
        print("AWS App Runner Service Deployment Initiated.")
        print(f"Service ARN: {arn}")
        print(f"Public URL:  {url}")
        print("=" * 70)
        return url
    except Exception as e:
        print(f"Notice on App Runner service: {e}")
        return None


def main():
    env = load_env()
    region = os.getenv('AWS_DEFAULT_REGION', env.get('AWS_DEFAULT_REGION', 'ap-south-1'))
    bucket_name = os.getenv('S3_BUCKET_NAME', env.get('S3_BUCKET_NAME'))
    athena_db = os.getenv('ATHENA_DB', env.get('ATHENA_DB', 'food_waste_db'))

    try:
        session = boto3.Session(region_name=region)
        sts = session.client('sts')
        caller = sts.get_caller_identity()
        account_id = caller['Account']

        if not bucket_name:
            bucket_name = f"food-waste-canteen-{account_id}-{region}"

        print("=" * 70)
        print("Deploying Food Waste Dashboard to AWS App Runner")
        print(f"Account: {account_id} | Region: {region}")
        print("=" * 70)

        repo_uri = get_or_create_ecr_repo(session, region)
        access_role_arn, instance_role_arn = get_or_create_apprunner_roles(session, account_id, bucket_name)
        image_tag = build_and_push_image(session, region, repo_uri)
        deploy_to_apprunner(session, region, image_tag, access_role_arn, instance_role_arn, bucket_name, athena_db)

    except (NoCredentialsError, ClientError) as e:
        print(f"AWS not connected: {e}")
        print("Dashboard deployment script ready to execute once AWS credentials are authenticated.")


if __name__ == '__main__':
    main()
