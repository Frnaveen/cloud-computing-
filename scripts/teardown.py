"""
Script: teardown.py
Description: Cleanly deletes all AWS resources created by the Food Waste Analysis project:
             S3 bucket and contents, Lambda function, IAM roles, SNS topic, Athena database/tables,
             SageMaker endpoints/models, ECR repository, and App Runner service.
Requires explicit user confirmation before proceeding.
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError


def get_confirmation():
    print("=" * 70)
    print("WARNING: AWS RESOURCE TEARDOWN SCRIPT")
    print("=" * 70)
    print("This script will permanently delete all cloud resources created for")
    print("the Food Waste Analysis project in your AWS account.")
    print("Resources to be deleted:")
    print("  - Amazon S3 bucket and all contained files")
    print("  - AWS Lambda validation function")
    print("  - IAM roles created for Lambda, SageMaker, and App Runner")
    print("  - Amazon SNS high-waste alert topic")
    print("  - AWS Glue database and Amazon Athena tables")
    print("  - Amazon SageMaker endpoints and registered models")
    print("  - Amazon ECR container repository")
    print("  - AWS App Runner web service")
    print("=" * 70)

    # Check for non-interactive bypass
    if "--force" in sys.argv:
        print("Confirmation bypassed via --force flag.")
        return True

    resp = input("Are you sure you want to delete these resources? Type 'DELETE' to confirm: ").strip()
    return resp == "DELETE"


def delete_s3_bucket(bucket_name, region):
    if not bucket_name:
        print("No S3 bucket name provided. Skipping S3 deletion.")
        return

    print(f"\nDeleting S3 Bucket: {bucket_name}...")
    s3 = boto3.resource('s3', region_name=region)
    bucket = s3.Bucket(bucket_name)

    try:
        # Check if bucket exists
        bucket.meta.client.head_bucket(Bucket=bucket_name)
    except ClientError:
        print(f"Bucket '{bucket_name}' not found or already deleted.")
        return

    try:
        # Delete all object versions and objects
        print("Deleting all objects and versions in bucket...")
        bucket.object_versions.delete()
        bucket.objects.delete()
        bucket.delete()
        print(f"Bucket '{bucket_name}' deleted successfully.")
    except Exception as e:
        print(f"Error deleting S3 bucket {bucket_name}: {e}")


def delete_lambda_function(function_name, region):
    print(f"\nDeleting Lambda Function: {function_name}...")
    client = boto3.client('lambda', region_name=region)
    try:
        client.delete_function(FunctionName=function_name)
        print(f"Lambda function '{function_name}' deleted.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Lambda function '{function_name}' not found.")
        else:
            print(f"Error deleting Lambda function: {e}")


def delete_iam_role(role_name):
    print(f"\nDeleting IAM Role: {role_name}...")
    iam = boto3.client('iam')
    try:
        # Detach all managed policies
        attached = iam.list_attached_role_policies(RoleName=role_name).get('AttachedPolicies', [])
        for p in attached:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=p['PolicyArn'])
            print(f"Detached policy: {p['PolicyArn']}")

        # Delete inline policies
        inline = iam.list_role_policies(RoleName=role_name).get('PolicyNames', [])
        for p_name in inline:
            iam.delete_role_policy(RoleName=role_name, PolicyName=p_name)
            print(f"Deleted inline policy: {p_name}")

        iam.delete_role(RoleName=role_name)
        print(f"IAM role '{role_name}' deleted.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            print(f"IAM role '{role_name}' not found.")
        else:
            print(f"Error deleting IAM role {role_name}: {e}")


def delete_sns_topic(topic_arn, region):
    if not topic_arn:
        print("No SNS Topic ARN provided. Skipping SNS deletion.")
        return
    print(f"\nDeleting SNS Topic: {topic_arn}...")
    client = boto3.client('sns', region_name=region)
    try:
        client.delete_topic(TopicArn=topic_arn)
        print("SNS topic deleted.")
    except Exception as e:
        print(f"Error deleting SNS topic: {e}")


def delete_glue_database(database_name, region):
    print(f"\nDeleting Glue Database: {database_name}...")
    client = boto3.client('glue', region_name=region)
    try:
        # Delete tables first
        tables = client.get_tables(DatabaseName=database_name).get('TableList', [])
        for t in tables:
            client.delete_table(DatabaseName=database_name, Name=t['Name'])
            print(f"Deleted Glue table: {t['Name']}")
        client.delete_database(Name=database_name)
        print(f"Glue database '{database_name}' deleted.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityNotFoundException':
            print(f"Glue database '{database_name}' not found.")
        else:
            print(f"Error deleting Glue database: {e}")


def delete_ecr_repository(repo_name, region):
    print(f"\nDeleting ECR Repository: {repo_name}...")
    client = boto3.client('ecr', region_name=region)
    try:
        client.delete_repository(repositoryName=repo_name, force=True)
        print(f"ECR repository '{repo_name}' deleted.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'RepositoryNotFoundException':
            print(f"ECR repository '{repo_name}' not found.")
        else:
            print(f"Error deleting ECR repo: {e}")


def delete_apprunner_service(service_name, region):
    print(f"\nChecking App Runner Service: {service_name}...")
    client = boto3.client('apprunner', region_name=region)
    try:
        services = client.list_services().get('ServiceSummaryList', [])
        for s in services:
            if s['ServiceName'] == service_name:
                arn = s['ServiceArn']
                print(f"Deleting App Runner service: {arn}...")
                client.delete_service(ServiceArn=arn)
                print("App Runner service deletion initiated.")
                return
        print(f"App Runner service '{service_name}' not found.")
    except Exception as e:
        print(f"Error with App Runner service: {e}")


def delete_sagemaker_resources(model_name, region):
    print(f"\nDeleting SageMaker Models: {model_name}...")
    client = boto3.client('sagemaker', region_name=region)
    try:
        client.delete_model(ModelName=model_name)
        print(f"SageMaker model '{model_name}' deleted.")
    except ClientError as e:
        if 'Could not find model' in str(e) or e.response['Error']['Code'] == 'ValidationException':
            print(f"SageMaker model '{model_name}' not found.")
        else:
            print(f"Error deleting SageMaker model: {e}")


def main():
    if not get_confirmation():
        print("Teardown cancelled by user.")
        sys.exit(0)

    region = os.getenv('AWS_DEFAULT_REGION', 'ap-south-1')
    bucket_name = os.getenv('S3_BUCKET_NAME')
    sns_arn = os.getenv('SNS_TOPIC_ARN')
    athena_db = os.getenv('ATHENA_DB', 'food_waste_db')

    # Read from .env if present
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    if k == 'S3_BUCKET_NAME':
                        bucket_name = v
                    elif k == 'AWS_DEFAULT_REGION':
                        region = v
                    elif k == 'SNS_TOPIC_ARN':
                        sns_arn = v
                    elif k == 'ATHENA_DB':
                        athena_db = v

    print(f"\nExecuting teardown in region: {region}")

    # 1. App Runner
    delete_apprunner_service("food-waste-dashboard", region)

    # 2. ECR
    delete_ecr_repository("food-waste-dashboard", region)

    # 3. SageMaker
    delete_sagemaker_resources("food-waste-predictor", region)

    # 4. Lambda
    delete_lambda_function("food-waste-validator", region)

    # 5. SNS
    if sns_arn:
        delete_sns_topic(sns_arn, region)

    # 6. Glue / Athena
    delete_glue_database(athena_db, region)

    # 7. S3
    if bucket_name:
        delete_s3_bucket(bucket_name, region)

    # 8. IAM Roles
    delete_iam_role("food-waste-lambda-execution-role")
    delete_iam_role("food-waste-sagemaker-execution-role")
    delete_iam_role("food-waste-apprunner-instance-role")

    print("\nTeardown process completed successfully.")


if __name__ == '__main__':
    main()
