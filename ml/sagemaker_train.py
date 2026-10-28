"""
Script: ml/sagemaker_train.py
Description: Submits and manages an Amazon SageMaker training job using scikit-learn.
             - Reads training data from S3: s3://<bucket>/raw-data/food_waste.csv
             - Uses lowest-cost instance: ml.m5.large with Spot Training enabled (max 15 mins)
             - Saves model artifacts to: s3://<bucket>/models/
             - If instance quota is zero or restricted, provides an automated fallback that
               trains locally and uploads metrics/artifacts to S3.
"""

import os
import sys
import time
import json
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


def get_or_create_sagemaker_role(session):
    iam = session.client('iam')
    role_name = "food-waste-sagemaker-execution-role"

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sagemaker.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }

    try:
        try:
            role = iam.get_role(RoleName=role_name)
            role_arn = role['Role']['Arn']
            print(f"Existing SageMaker IAM role: {role_arn}")
            return role_arn
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                print(f"Creating SageMaker IAM role '{role_name}'...")
                role = iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Execution role for Food Waste SageMaker training jobs"
                )
                role_arn = role['Role']['Arn']
                iam.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
                )
                print(f"Created SageMaker IAM role: {role_arn}")
                time.sleep(5)
                return role_arn
            else:
                raise e
    except Exception as e:
        print(f"Notice on SageMaker IAM role: {e}")
        return None


def run_local_and_upload_to_s3(session, bucket_name, region):
    """Fallback training execution: runs local scikit-learn models and uploads to S3."""
    print("\nExecuting Training and Uploading Artifacts to S3...")
    import ml.train_models as tm
    results, best_name = tm.train_and_evaluate()

    s3 = session.client('s3', region_name=region)
    metrics_file = os.path.join(os.path.dirname(__file__), 'model_metrics.json')
    model_file = os.path.join(os.path.dirname(__file__), 'best_model.joblib')

    try:
        s3.upload_file(metrics_file, bucket_name, 'models/model_metrics.json')
        s3.upload_file(model_file, bucket_name, 'models/best_model.joblib')
        print(f"Model artifacts successfully synced to s3://{bucket_name}/models/")
        return True
    except Exception as e:
        print(f"Error uploading artifacts to S3: {e}")
        return False


def run_sagemaker_training_job(session, bucket_name, region, role_arn):
    print("=" * 70)
    print("Submitting Amazon SageMaker Training Job...")
    print(f"Bucket:   s3://{bucket_name}/")
    print(f"Role ARN: {role_arn}")
    print("=" * 70)

    sm = session.client('sagemaker', region_name=region)
    job_name = f"food-waste-training-{int(time.time())}"

    # Standard AWS scikit-learn container image for ap-south-1
    # Framework container for scikit-learn 1.2-1
    image_uri = f"646617198159.dkr.ecr.{region}.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3"

    training_params = {
        'TrainingJobName': job_name,
        'AlgorithmSpecification': {
            'TrainingImage': image_uri,
            'TrainingInputMode': 'File'
        },
        'RoleArn': role_arn,
        'InputDataConfig': [
            {
                'ChannelName': 'train',
                'DataSource': {
                    'S3DataSource': {
                        'S3DataType': 'S3Prefix',
                        'S3Uri': f"s3://{bucket_name}/raw-data/food_waste.csv",
                        'S3DataDistributionType': 'FullyReplicated'
                    }
                },
                'ContentType': 'text/csv'
            }
        ],
        'OutputDataConfig': {
            'S3OutputPath': f"s3://{bucket_name}/models/"
        },
        'ResourceConfig': {
            'InstanceType': 'ml.m5.large',
            'InstanceCount': 1,
            'VolumeSizeInGB': 10
        },
        'StoppingCondition': {
            'MaxRuntimeInSeconds': 900,
            'MaxWaitTimeInSeconds': 900
        },
        'EnableManagedSpotTraining': True
    }

    try:
        print(f"Submitting job '{job_name}' on spot instance ml.m5.large...")
        sm.create_training_job(**training_params)
        print(f"Training job created: {job_name}")
        print("Monitoring job progress...")

        for _ in range(15):
            time.sleep(10)
            desc = sm.describe_training_job(TrainingJobName=job_name)
            status = desc['TrainingJobStatus']
            print(f"Current Status: {status}")
            if status in ['Completed', 'Failed', 'Stopped']:
                break

        if status == 'Completed':
            print("SageMaker Training Job completed successfully.")
            return True
        else:
            reason = desc.get('FailureReason', 'Unknown failure')
            print(f"Job finished with status '{status}': {reason}")
            raise Exception(reason)

    except Exception as e:
        err_msg = str(e)
        print(f"\nSageMaker Training Job issue: {err_msg}")
        if 'ResourceLimitExceeded' in err_msg or 'quota' in err_msg.lower():
            print("\n" + "=" * 70)
            print("SERVICE QUOTA NOTICE:")
            print("Your AWS account has a quota limit of 0 for 'ml.m5.large for training job usage'.")
            print("To run managed training jobs on SageMaker clusters:")
            print("  1. Go to AWS Console > Service Quotas > Amazon SageMaker")
            print("  2. Request a quota increase for 'ml.m5.large for training job usage' to 1")
            print("  3. Meanwhile, switching to local training with S3 artifact sync.")
            print("=" * 70)
        
        # Trigger fallback
        return run_local_and_upload_to_s3(session, bucket_name, region)


def main():
    env = load_env()
    region = os.getenv('AWS_DEFAULT_REGION', env.get('AWS_DEFAULT_REGION', 'ap-south-1'))
    bucket_name = os.getenv('S3_BUCKET_NAME', env.get('S3_BUCKET_NAME'))
    role_arn = os.getenv('SAGEMAKER_ROLE_ARN', env.get('SAGEMAKER_ROLE_ARN'))

    try:
        session = boto3.Session(region_name=region)
        sts = session.client('sts')
        sts.get_caller_identity()

        if not bucket_name:
            print("Error: S3_BUCKET_NAME not set.")
            sys.exit(1)

        if not role_arn:
            role_arn = get_or_create_sagemaker_role(session)

        if role_arn:
            run_sagemaker_training_job(session, bucket_name, region, role_arn)
        else:
            run_local_and_upload_to_s3(session, bucket_name, region)

    except (NoCredentialsError, ClientError) as e:
        print(f"AWS not connected ({e}). Running local model training.")
        import ml.train_models as tm
        tm.train_and_evaluate()


if __name__ == '__main__':
    main()
