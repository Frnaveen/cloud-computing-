"""
Script: run_etl.py
Description: Converts raw food waste telemetry into partitioned columnar Parquet files
             stored in Amazon S3 (s3://<bucket>/processed-data/parquet/) via Amazon Athena CTAS.
"""

import os
import sys
import time
import pandas as pd
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


def run_athena_ctas(bucket_name, region='ap-south-1', db_name='food_waste_db'):
    print("=" * 70)
    print("Executing Athena CTAS ETL Pipeline...")
    print("=" * 70)
    
    session = boto3.Session(region_name=region)
    athena = session.client('athena')
    s3 = session.client('s3')
    
    output_location = f"s3://{bucket_name}/athena-results/"
    
    # Read SQL template
    sql_path = os.path.join(os.path.dirname(__file__), '..', 'sql', 'etl_to_parquet.sql')
    with open(sql_path, 'r') as f:
        sql_content = f.read()

    # Drop old table first if exists
    drop_sql = f"DROP TABLE IF EXISTS {db_name}.canteen_waste_parquet;"
    try:
        print(f"Dropping previous Parquet table if exists...")
        res = athena.start_query_execution(
            QueryString=drop_sql,
            QueryExecutionContext={'Database': db_name},
            ResultConfiguration={'OutputLocation': output_location}
        )
        drop_id = res['QueryExecutionId']
        wait_for_query(athena, drop_id)
    except Exception as e:
        print(f"Notice on drop: {e}")

    # Remove previous S3 files in processed-data/parquet/ to allow clean CTAS
    try:
        print(f"Cleaning previous S3 objects in s3://{bucket_name}/processed-data/parquet/...")
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name, Prefix='processed-data/parquet/'):
            if 'Contents' in page:
                delete_keys = [{'Key': obj['Key']} for obj in page['Contents']]
                s3.delete_objects(Bucket=bucket_name, Delete={'Objects': delete_keys})
    except Exception as e:
        print(f"Notice on S3 clean: {e}")

    # Substitute bucket name
    formatted_sql = sql_content.replace('{BUCKET_NAME}', bucket_name)
    # Extract only the CREATE TABLE statement (after DROP TABLE)
    create_sql = formatted_sql[formatted_sql.find('CREATE TABLE'):].strip()

    print(f"Submitting CTAS Query to Athena...")
    res = athena.start_query_execution(
        QueryString=create_sql,
        QueryExecutionContext={'Database': db_name},
        ResultConfiguration={'OutputLocation': output_location}
    )
    query_id = res['QueryExecutionId']
    print(f"QueryExecutionId: {query_id}")

    success, state = wait_for_query(athena, query_id)
    if not success:
        print(f"CTAS Query failed with state: {state}")
        return False

    print("Athena CTAS completed successfully.")

    # Verify output files in S3
    print("\nVerifying partitioned Parquet output files in S3...")
    resp = s3.list_objects_v2(Bucket=bucket_name, Prefix='processed-data/parquet/')
    contents = resp.get('Contents', [])
    parquet_files = [c['Key'] for c in contents if c['Key'].endswith('.parquet')]
    print(f"Found {len(parquet_files)} Parquet partition files in S3.")
    for p in parquet_files[:5]:
        print(f"  s3://{bucket_name}/{p}")

    # Verify query count
    verify_sql = f"SELECT COUNT(*) AS total_rows FROM {db_name}.canteen_waste_parquet;"
    v_res = athena.start_query_execution(
        QueryString=verify_sql,
        QueryExecutionContext={'Database': db_name},
        ResultConfiguration={'OutputLocation': output_location}
    )
    v_id = v_res['QueryExecutionId']
    v_success, _ = wait_for_query(athena, v_id)
    if v_success:
        results = athena.get_query_results(QueryExecutionId=v_id)
        rows = results['ResultSet']['Rows']
        if len(rows) > 1:
            cnt = rows[1]['Data'][0].get('VarCharValue')
            print(f"Verification Query Result: {cnt} records present in Parquet table.")

    return True


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


def run_local_fallback():
    print("Running local Parquet conversion fallback (pandas/pyarrow)...")
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'food_waste.csv')
    df = pd.read_csv(csv_path)
    df['year'] = df['date'].str.slice(0, 4)
    df['month'] = df['date'].str.slice(5, 7)
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed', 'parquet')
    os.makedirs(out_dir, exist_ok=True)
    df.to_parquet(out_dir, partition_cols=['year', 'month'], index=False)
    print(f"Partitioned Parquet files written to {out_dir}")
    print(f"Total rows converted: {len(df)}")
    return True


if __name__ == '__main__':
    env = load_env()
    bucket = os.getenv('S3_BUCKET_NAME', env.get('S3_BUCKET_NAME'))
    region = os.getenv('AWS_DEFAULT_REGION', env.get('AWS_DEFAULT_REGION', 'ap-south-1'))
    db = os.getenv('ATHENA_DB', env.get('ATHENA_DB', 'food_waste_db'))

    try:
        session = boto3.Session(region_name=region)
        sts = session.client('sts')
        sts.get_caller_identity()
        if not bucket:
            print("Error: S3_BUCKET_NAME not set in environment or .env file.")
            sys.exit(1)
        success = run_athena_ctas(bucket, region, db)
        sys.exit(0 if success else 1)
    except (NoCredentialsError, ClientError) as e:
        print(f"AWS not connected ({e}).")
        run_local_fallback()
