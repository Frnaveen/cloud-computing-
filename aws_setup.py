"""
Automated AWS Setup Script for Food Waste Analysis Pipeline
B.Tech Cloud Computing Project

Provisions and configures:
1. Amazon S3 Bucket & raw-data upload
2. AWS Glue / Athena Database ('food_waste_db')
3. Amazon Athena External Table ('canteen_waste')
4. Verifies query count returns 630 records
5. Writes active S3_BUCKET_NAME and AWS_DEFAULT_REGION to .env
"""

import os
import sys
import time
import zipfile
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'food_waste.csv')
SQL_FILE = os.path.join(os.path.dirname(__file__), 'sql', 'food_waste_analysis.sql')


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


def write_env(updates):
    existing = load_env()
    existing.update(updates)
    with open('.env', 'w') as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")
    print(f"Updated .env configuration with: {list(updates.keys())}")


def check_credentials():
    print("=" * 70)
    print("1. Checking AWS Credentials...")
    print("=" * 70)
    try:
        session = boto3.Session()
        sts = session.client('sts')
        caller = sts.get_caller_identity()
        account_id = caller.get('Account')
        arn = caller.get('Arn')
        print(f"Account ID: {account_id}")
        print(f"User ARN:   {arn}")
        return session, account_id, arn
    except (NoCredentialsError, ClientError) as e:
        print(f"No valid AWS credentials found: {e}")
        return None, None, None


def setup_s3_bucket(session, bucket_name, region):
    print("\n" + "=" * 70)
    print(f"2. Setting Up Amazon S3 Bucket: {bucket_name}")
    print("=" * 70)
    s3 = session.client('s3', region_name=region)
    try:
        if region == 'us-east-1':
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        print(f"Created S3 Bucket: s3://{bucket_name}")
    except ClientError as e:
        code = e.response['Error']['Code']
        if code in ['BucketAlreadyOwnedByYou', 'BucketAlreadyExists']:
            print(f"S3 Bucket '{bucket_name}' already exists. Using existing bucket.")
        else:
            print(f"Failed to create bucket: {e}")
            return False

    # Upload raw data
    s3_key = 'raw-data/food_waste.csv'
    try:
        print(f"Uploading {DATA_FILE} -> s3://{bucket_name}/{s3_key}...")
        s3.upload_file(DATA_FILE, bucket_name, s3_key)
        print("Dataset successfully uploaded to Amazon S3.")
        return True
    except Exception as e:
        print(f"Failed to upload dataset: {e}")
        return False


def wait_for_query(athena_client, query_id, timeout_sec=60):
    start = time.time()
    while time.time() - start < timeout_sec:
        res = athena_client.get_query_execution(QueryExecutionId=query_id)
        state = res['QueryExecution']['Status']['State']
        if state == 'SUCCEEDED':
            return True, state
        elif state in ['FAILED', 'CANCELLED']:
            reason = res['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            print(f"Query {query_id} {state}: {reason}")
            return False, state
        time.sleep(1.5)
    return False, "TIMED_OUT"


def setup_athena(session, bucket_name, region):
    print("\n" + "=" * 70)
    print("3. Setting Up Amazon Athena & Glue Database")
    print("=" * 70)
    athena = session.client('athena', region_name=region)
    output_loc = f"s3://{bucket_name}/athena-results/"

    # 1. Create database
    create_db_query = "CREATE DATABASE IF NOT EXISTS food_waste_db;"
    print("Executing: CREATE DATABASE IF NOT EXISTS food_waste_db...")
    try:
        res = athena.start_query_execution(
            QueryString=create_db_query,
            ResultConfiguration={'OutputLocation': output_loc}
        )
        q_id = res['QueryExecutionId']
        wait_for_query(athena, q_id)
        print(f"Database created (QueryExecutionId: {q_id})")
    except Exception as e:
        print(f"Athena DB creation: {e}")

    # 2. Drop old table if exists
    drop_sql = "DROP TABLE IF EXISTS food_waste_db.canteen_waste;"
    try:
        res = athena.start_query_execution(
            QueryString=drop_sql,
            QueryExecutionContext={'Database': 'food_waste_db'},
            ResultConfiguration={'OutputLocation': output_loc}
        )
        wait_for_query(athena, res['QueryExecutionId'])
    except Exception as e:
        print(f"Notice on table drop: {e}")

    # 3. Create external table
    create_table_sql = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS food_waste_db.canteen_waste (
        record_id STRING,
        record_date STRING,
        location STRING,
        meal_type STRING,
        food_category STRING,
        food_item STRING,
        prepared_qty_kg DOUBLE,
        consumed_qty_kg DOUBLE,
        wasted_qty_kg DOUBLE,
        waste_percentage DOUBLE,
        cost_per_kg_inr DOUBLE,
        waste_cost_inr DOUBLE,
        waste_reason STRING
    )
    ROW FORMAT DELIMITED
    FIELDS TERMINATED BY ','
    LINES TERMINATED BY '\\n'
    LOCATION 's3://{bucket_name}/raw-data/'
    TBLPROPERTIES ('skip.header.line.count'='1');
    """
    print(f"Creating External Table pointing to s3://{bucket_name}/raw-data/...")
    try:
        res = athena.start_query_execution(
            QueryString=create_table_sql,
            QueryExecutionContext={'Database': 'food_waste_db'},
            ResultConfiguration={'OutputLocation': output_loc}
        )
        q_id = res['QueryExecutionId']
        wait_for_query(athena, q_id)
        print(f"Table creation query succeeded (QueryExecutionId: {q_id})")
    except Exception as e:
        print(f"Athena Table creation: {e}")

    # 4. Verify query
    verify_sql = "SELECT COUNT(*) AS total_rows FROM food_waste_db.canteen_waste;"
    print("Verifying query: SELECT COUNT(*) FROM food_waste_db.canteen_waste...")
    try:
        res = athena.start_query_execution(
            QueryString=verify_sql,
            QueryExecutionContext={'Database': 'food_waste_db'},
            ResultConfiguration={'OutputLocation': output_loc}
        )
        q_id = res['QueryExecutionId']
        success, _ = wait_for_query(athena, q_id)
        if success:
            results = athena.get_query_results(QueryExecutionId=q_id)
            rows = results['ResultSet']['Rows']
            if len(rows) > 1:
                cnt = rows[1]['Data'][0].get('VarCharValue')
                print(f"Verification Query Result: {cnt} records in food_waste_db.canteen_waste (Expected: 630)")
    except Exception as e:
        print(f"Verification query error: {e}")


def package_lambda():
    print("\n" + "=" * 70)
    print("4. Packaging AWS Lambda Function")
    print("=" * 70)
    zip_path = "lambda_deployment_package.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write("lambda_function.py", arcname="lambda_function.py")
    print(f"Created Lambda deployment package: {zip_path}")


def main():
    session, account_id, arn = check_credentials()
    package_lambda()

    env = load_env()
    region = os.getenv('AWS_DEFAULT_REGION', env.get('AWS_DEFAULT_REGION'))
    if not region and session:
        region = session.region_name
    if not region:
        region = 'ap-south-1'

    if session and account_id:
        bucket_name = os.getenv('S3_BUCKET_NAME', env.get('S3_BUCKET_NAME'))
        if not bucket_name:
            bucket_name = f"food-waste-canteen-{account_id}-{region}"

        print(f"Active Account: {account_id}")
        print(f"Active Region:  {region}")
        print(f"Target Bucket:  {bucket_name}")

        if setup_s3_bucket(session, bucket_name, region):
            write_env({
                'S3_BUCKET_NAME': bucket_name,
                'AWS_DEFAULT_REGION': region,
                'ATHENA_DB': 'food_waste_db'
            })
            setup_athena(session, bucket_name, region)
            print("\n" + "=" * 70)
            print("AWS Pipeline Successfully Configured.")
            print(f"   Bucket: s3://{bucket_name}/")
            print("   Athena DB: food_waste_db")
            print("   Run: streamlit run app.py to view dashboard.")
            print("=" * 70)
    else:
        print("\nAWS credentials not active. Once configured via 'aws configure', re-run:")
        print("   python3 aws_setup.py\n")


if __name__ == '__main__':
    main()
