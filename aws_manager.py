"""
AWS Helper Module for Food Waste Analytics Pipeline
Handles AWS S3, Athena, Glue, and SageMaker integration with graceful offline fallback.
"""

import os
import time
import io
import pandas as pd
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError


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


class AWSManager:
    def __init__(self, access_key=None, secret_key=None, region=None, bucket_name=None, athena_db=None):
        env = load_env()
        self.region = region or os.getenv('AWS_DEFAULT_REGION', env.get('AWS_DEFAULT_REGION', 'ap-south-1'))
        self.bucket_name = bucket_name or os.getenv('S3_BUCKET_NAME', env.get('S3_BUCKET_NAME', ''))
        self.athena_db = athena_db or os.getenv('ATHENA_DB', env.get('ATHENA_DB', 'food_waste_db'))
        self.access_key = access_key or os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_key = secret_key or os.getenv('AWS_SECRET_ACCESS_KEY')
        
        self.session = None
        self.s3_client = None
        self.athena_client = None
        self.glue_client = None
        self.sagemaker_client = None
        self.is_connected = False
        self.connection_message = "AWS not initialized."
        self.data_source_active = "Local CSV (data/food_waste.csv)"
        
        self._init_session()

    def _init_session(self):
        try:
            if self.access_key and self.secret_key:
                self.session = boto3.Session(
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region
                )
            else:
                self.session = boto3.Session(region_name=self.region)

            # Test credentials using STS caller identity
            sts = self.session.client('sts')
            caller = sts.get_caller_identity()
            self.s3_client = self.session.client('s3')
            self.athena_client = self.session.client('athena')
            self.glue_client = self.session.client('glue')
            self.sagemaker_client = self.session.client('sagemaker')
            self.is_connected = True
            self.connection_message = f"Connected as {caller.get('Arn', 'AWS User')} (Account: {caller.get('Account')})"
        except (NoCredentialsError, PartialCredentialsError):
            self.is_connected = False
            self.connection_message = "AWS credentials not detected. Running in Local Demo Mode."
        except ClientError as e:
            self.is_connected = False
            self.connection_message = f"AWS Authentication failed: {e.response['Error']['Message']}"
        except Exception as e:
            self.is_connected = False
            self.connection_message = f"AWS connection error: {str(e)}"

    def load_dataset(self, local_path='data/food_waste.csv', s3_key='raw-data/food_waste.csv'):
        """
        Loads the dataset from S3 if connected and available; falls back to local CSV.
        Returns: (df, source_label)
        """
        if self.is_connected and self.bucket_name:
            try:
                obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
                df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                df['date'] = pd.to_datetime(df['date'])
                self.data_source_active = f"Amazon S3 (s3://{self.bucket_name}/{s3_key})"
                return df, self.data_source_active
            except Exception as e:
                print(f"Notice: Could not load from S3 ({e}), falling back to local CSV.")

        if os.path.exists(local_path):
            df = pd.read_csv(local_path)
            df['date'] = pd.to_datetime(df['date'])
            self.data_source_active = f"Local CSV ({local_path})"
            return df, self.data_source_active

        return pd.DataFrame(), "No Data Source"

    def list_s3_buckets(self):
        if not self.is_connected:
            return []
        try:
            resp = self.s3_client.list_buckets()
            return [b['Name'] for b in resp.get('Buckets', [])]
        except Exception as e:
            print(f"Error listing buckets: {e}")
            return []

    def upload_file_to_s3(self, local_path, s3_key=None):
        if not self.is_connected:
            return False, "AWS credentials not configured. Enable AWS credentials to upload to real S3."
        if not self.bucket_name:
            return False, "Target S3 bucket name is not specified."
            
        s3_key = s3_key or f"raw-data/{os.path.basename(local_path)}"
        try:
            self.s3_client.upload_file(local_path, self.bucket_name, s3_key)
            return True, f"Successfully uploaded to s3://{self.bucket_name}/{s3_key}"
        except Exception as e:
            return False, f"Failed to upload to S3: {str(e)}"

    def read_csv_from_s3(self, s3_key):
        if not self.is_connected:
            return None, "AWS not connected."
        try:
            obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            df = pd.read_csv(io.BytesIO(obj['Body'].read()))
            return df, f"Successfully loaded s3://{self.bucket_name}/{s3_key}"
        except Exception as e:
            return None, f"Failed reading from S3: {str(e)}"

    def run_athena_query(self, query_string, output_location=None, max_wait_sec=45):
        """
        Executes query on real AWS Athena service.
        Requires an S3 output location: s3://<bucket>/athena-results/
        """
        if not self.is_connected:
            return None, "AWS Athena not connected."
            
        output_location = output_location or f"s3://{self.bucket_name}/athena-results/"
        try:
            resp = self.athena_client.start_query_execution(
                QueryString=query_string,
                QueryExecutionContext={'Database': self.athena_db},
                ResultConfiguration={'OutputLocation': output_location}
            )
            query_execution_id = resp['QueryExecutionId']

            # Poll for query completion
            start_time = time.time()
            while time.time() - start_time < max_wait_sec:
                status_resp = self.athena_client.get_query_execution(QueryExecutionId=query_execution_id)
                state = status_resp['QueryExecution']['Status']['State']
                
                if state == 'SUCCEEDED':
                    result_resp = self.athena_client.get_query_results(QueryExecutionId=query_execution_id)
                    # Convert Athena tabular format to DataFrame
                    rows = result_resp['ResultSet']['Rows']
                    if not rows:
                        return pd.DataFrame(), "Query succeeded (0 rows returned)."
                    
                    headers = [c.get('VarCharValue', f'col_{i}') for i, c in enumerate(rows[0]['Data'])]
                    data = []
                    for r in rows[1:]:
                        row_vals = [c.get('VarCharValue', '') for c in r['Data']]
                        data.append(row_vals)
                    df = pd.DataFrame(data, columns=headers)
                    return df, f"Athena query completed successfully in {round(time.time() - start_time, 2)}s"
                
                elif state in ['FAILED', 'CANCELLED']:
                    reason = status_resp['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                    return None, f"Athena Query {state}: {reason}"
                
                time.sleep(1)

            return None, f"Query timed out after {max_wait_sec} seconds."
        except Exception as e:
            return None, f"Athena execution exception: {str(e)}"
