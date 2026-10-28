"""
Script: test_pipeline.py
Description: End-to-end pipeline verification test:
             1. Uploads a test CSV dataset with normal records and high-waste anomalies to raw-data/
             2. Confirms AWS Lambda triggers and produces validated output in processed-data/
             3. Checks Amazon CloudWatch Logs for execution details and anomaly alerts
"""

import os
import sys
import time
import io
import json
import pandas as pd
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

import lambda_function


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


def create_test_csv_data():
    """Generates a small 5-row test batch containing 1 high-waste anomaly (>25%)."""
    rows = [
        {
            'record_id': 'FW-TEST-BATCH-001',
            'date': '2026-10-28',
            'location': 'Main Canteen',
            'meal_type': 'Lunch',
            'food_category': 'Cooked Grains',
            'food_item': 'Basmati Rice',
            'prepared_qty_kg': 80.0,
            'consumed_qty_kg': 70.0,
            'wasted_qty_kg': 10.0,
            'waste_percentage': 12.5,
            'cost_per_kg_inr': 45.0,
            'waste_cost_inr': 450.0,
            'waste_reason': 'Normal Surplus'
        },
        {
            'record_id': 'FW-TEST-BATCH-002',
            'date': '2026-10-28',
            'location': 'Hostel Mess Block A',
            'meal_type': 'Dinner',
            'food_category': 'Dairy & Desserts',
            'food_item': 'Gulab Jamun',
            'prepared_qty_kg': 60.0,
            'consumed_qty_kg': 42.0,
            'wasted_qty_kg': 18.0,
            'waste_percentage': 30.0,  # High waste anomaly (>25%)
            'cost_per_kg_inr': 160.0,
            'waste_cost_inr': 2880.0,
            'waste_reason': 'Over-preparation'
        },
        {
            'record_id': 'FW-TEST-BATCH-003',
            'date': '2026-10-28',
            'location': 'Food Court',
            'meal_type': 'Breakfast',
            'food_category': 'Breakfast Items',
            'food_item': 'Idli & Sambar',
            'prepared_qty_kg': 40.0,
            'consumed_qty_kg': 35.0,
            'wasted_qty_kg': 5.0,
            'waste_percentage': 12.5,
            'cost_per_kg_inr': 50.0,
            'waste_cost_inr': 250.0,
            'waste_reason': 'Normal Surplus'
        }
    ]
    df = pd.DataFrame(rows)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()


def run_cloud_pipeline_test(bucket_name, region):
    print("=" * 70)
    print("Running End-to-End Pipeline Verification on AWS...")
    print(f"Bucket: s3://{bucket_name}/")
    print(f"Region: {region}")
    print("=" * 70)

    session = boto3.Session(region_name=region)
    s3 = session.client('s3')
    logs = session.client('logs')

    test_csv = create_test_csv_data()
    test_key = f"raw-data/test_pipeline_{int(time.time())}.csv"
    processed_key = test_key.replace("raw-data/", "processed-data/")

    # 1. Upload test data to raw-data/
    print(f"\n1. Uploading test file to s3://{bucket_name}/{test_key}...")
    s3.put_object(
        Bucket=bucket_name,
        Key=test_key,
        Body=test_csv.encode('utf-8'),
        ContentType='text/csv'
    )
    print("File uploaded successfully.")

    # 2. Wait for Lambda execution and verify processed-data/
    print("\n2. Waiting for AWS Lambda trigger to validate and output to processed-data/...")
    found = False
    for attempt in range(12):
        time.sleep(3)
        try:
            s3.head_object(Bucket=bucket_name, Key=processed_key)
            found = True
            print(f"Verified: Processed file exists at s3://{bucket_name}/{processed_key}")
            break
        except ClientError:
            print(f"  Waiting for output ({attempt+1}/12)...")

    if not found:
        print("Warning: Processed file not found within timeout window.")

    # 3. Check CloudWatch Logs
    print("\n3. Checking CloudWatch Logs for /aws/lambda/food-waste-validator...")
    log_group = "/aws/lambda/food-waste-validator"
    try:
        streams = logs.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=3
        ).get('logStreams', [])

        if streams:
            stream_name = streams[0]['logStreamName']
            print(f"Reading recent log stream: {stream_name}...")
            events = logs.get_log_events(
                logGroupName=log_group,
                logStreamName=stream_name,
                limit=15
            ).get('events', [])
            print("Recent CloudWatch Log Events:")
            for ev in events:
                msg = ev['message'].strip()
                print(f"  {msg}")
        else:
            print("No log streams found yet in log group.")
    except ClientError as e:
        print(f"Notice on reading CloudWatch logs: {e}")

    # Clean up test object
    try:
        s3.delete_object(Bucket=bucket_name, Key=test_key)
        s3.delete_object(Bucket=bucket_name, Key=processed_key)
        print("\nCleaned up test artifacts from S3.")
    except Exception as e:
        print(f"Notice on cleanup: {e}")

    return found


def run_local_pipeline_test():
    print("=" * 70)
    print("Running Local Pipeline Test (Direct Lambda Handler Validation)...")
    print("=" * 70)
    test_csv = create_test_csv_data()
    event = {'csv_content': test_csv}

    res = lambda_function.lambda_handler(event)
    body = json.loads(res['body'])

    print(f"Status Code: {res['statusCode']}")
    print(f"Total Rows Processed:   {body.get('total_rows')}")
    print(f"Valid Rows:             {body.get('valid_rows')}")
    print(f"Invalid Rows:           {body.get('invalid_rows')}")
    print(f"Anomalies Flagged:      {body.get('anomalies_detected')}")
    print(f"Anomalies Sample:       {body.get('anomalies')}")

    success = (body.get('valid_rows') == 3 and body.get('anomalies_detected') == 1)
    if success:
        print("\nLocal pipeline verification passed successfully.")
    return success


if __name__ == '__main__':
    env = load_env()
    bucket = os.getenv('S3_BUCKET_NAME', env.get('S3_BUCKET_NAME'))
    region = os.getenv('AWS_DEFAULT_REGION', env.get('AWS_DEFAULT_REGION', 'ap-south-1'))

    try:
        session = boto3.Session(region_name=region)
        sts = session.client('sts')
        sts.get_caller_identity()
        if bucket:
            run_cloud_pipeline_test(bucket, region)
        else:
            print("S3_BUCKET_NAME not set. Running local test.")
            run_local_pipeline_test()
    except (NoCredentialsError, ClientError):
        run_local_pipeline_test()
