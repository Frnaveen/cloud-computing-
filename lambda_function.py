"""
AWS Lambda Function: Food Waste Data Validation and Pre-processing Pipeline
Course: B.Tech Cloud Computing Project
Module: Serverless Event-Driven Data Validation

Trigger: Amazon S3 (s3:ObjectCreated:*) on prefix 'raw-data/'
Action: Validates food waste CSV dataset, checks schema integrity and business logic,
        flags anomalies, and outputs cleaned data / metrics to 'processed-data/'.
"""

import json
import csv
import io
import os
import re
from datetime import datetime
import boto3

AWS_REGION = os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'ap-south-1'))
s3_client = boto3.client('s3', region_name=AWS_REGION)
sns_client = boto3.client('sns', region_name=AWS_REGION)

# Required columns for the food waste dataset
REQUIRED_COLUMNS = [
    'record_id',
    'date',
    'location',
    'meal_type',
    'food_category',
    'food_item',
    'prepared_qty_kg',
    'consumed_qty_kg',
    'wasted_qty_kg',
    'waste_percentage',
    'cost_per_kg_inr',
    'waste_cost_inr'
]

VALID_MEAL_TYPES = {'Breakfast', 'Lunch', 'Snacks', 'Dinner'}
HIGH_WASTE_THRESHOLD_PERCENT = 25.0  # Alert threshold (flags anomalies above 25% waste)


def validate_record(row, row_idx):
    """
    Validates a single row against schema and business logic rules.
    Returns: (is_valid, error_message, is_anomaly)
    """
    # 1. Missing columns check
    for col in REQUIRED_COLUMNS:
        if col not in row or row[col] is None or str(row[col]).strip() == '':
            return False, f"Row {row_idx}: Missing required field '{col}'", False

    # 2. Date validation (YYYY-MM-DD)
    try:
        datetime.strptime(row['date'].strip(), '%Y-%m-%d')
    except ValueError:
        return False, f"Row {row_idx}: Invalid date format '{row['date']}', expected YYYY-MM-DD", False

    # 3. Numeric values check
    try:
        prepared = float(row['prepared_qty_kg'])
        consumed = float(row['consumed_qty_kg'])
        wasted = float(row['wasted_qty_kg'])
        waste_pct = float(row['waste_percentage'])
        cost_per_kg = float(row['cost_per_kg_inr'])
        waste_cost = float(row['waste_cost_inr'])
    except ValueError as e:
        return False, f"Row {row_idx}: Non-numeric value encountered: {e}", False

    # 4. Logical assertions
    if prepared <= 0:
        return False, f"Row {row_idx}: prepared_qty_kg ({prepared}) must be greater than 0", False

    if wasted < 0:
        return False, f"Row {row_idx}: wasted_qty_kg ({wasted}) cannot be negative", False

    if wasted > prepared:
        return False, f"Row {row_idx}: wasted_qty_kg ({wasted}) exceeds prepared_qty_kg ({prepared})", False

    if cost_per_kg < 0 or waste_cost < 0:
        return False, f"Row {row_idx}: Costs cannot be negative", False

    # 5. Anomaly flag (High waste threshold)
    is_anomaly = waste_pct >= HIGH_WASTE_THRESHOLD_PERCENT

    return True, None, is_anomaly


def process_csv_content(csv_text):
    """
    Parses and validates CSV text content.
    Returns: summary dict with validation results and cleaned rows.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    
    # Check headers
    if not reader.fieldnames:
        return {
            'success': False,
            'error': 'Empty CSV file or missing headers',
            'total_rows': 0,
            'valid_rows': 0,
            'invalid_rows': 0,
            'anomalies_detected': 0,
            'errors': ['Empty CSV file']
        }

    missing_headers = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
    if missing_headers:
        return {
            'success': False,
            'error': f"CSV missing required columns: {missing_headers}",
            'total_rows': 0,
            'valid_rows': 0,
            'invalid_rows': 0,
            'anomalies_detected': 0,
            'errors': [f"Missing required columns: {missing_headers}"]
        }

    total_rows = 0
    valid_records = []
    errors = []
    anomalies = []

    for idx, row in enumerate(reader, start=2): # Line 1 is header
        total_rows += 1
        is_valid, err, is_anomaly = validate_record(row, idx)
        if not is_valid:
            errors.append(err)
        else:
            valid_records.append(row)
            if is_anomaly:
                anomalies.append({
                    'record_id': row.get('record_id'),
                    'location': row.get('location'),
                    'food_item': row.get('food_item'),
                    'waste_percentage': float(row.get('waste_percentage', 0)),
                    'wasted_qty_kg': float(row.get('wasted_qty_kg', 0)),
                    'waste_cost_inr': float(row.get('waste_cost_inr', 0))
                })

    return {
        'success': len(errors) == 0,
        'total_rows': total_rows,
        'valid_rows': len(valid_records),
        'invalid_rows': len(errors),
        'anomalies_detected': len(anomalies),
        'errors': errors[:10], # Cap preview to first 10 errors
        'anomalies': anomalies,
        'valid_records': valid_records
    }


def lambda_handler(event, context=None):
    """
    AWS Lambda Entry Point.
    Handles both S3 Event notifications and direct test payloads.
    """
    print(f"Received Lambda invocation event: {json.dumps(event, default=str)}")
    
    # Check if this is an S3 event
    if 'Records' in event and len(event['Records']) > 0 and 's3' in event['Records'][0]:
        s3_record = event['Records'][0]['s3']
        bucket_name = s3_record['bucket']['name']
        object_key = s3_record['object']['key']
        print(f"Processing S3 trigger from Bucket: {bucket_name}, Key: {object_key}")
        
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            csv_content = response['Body'].read().decode('utf-8')
        except Exception as e:
            error_msg = f"Failed to fetch object {object_key} from bucket {bucket_name}: {str(e)}"
            print(error_msg)
            return {
                'statusCode': 500,
                'body': json.dumps({'error': error_msg})
            }
            
        validation_result = process_csv_content(csv_content)
        
        # If valid, optionally write to processed-data/ prefix
        if validation_result['success'] and validation_result['valid_rows'] > 0:
            processed_key = object_key.replace('raw-data/', 'processed-data/')
            if processed_key == object_key:
                processed_key = f"processed-data/{os.path.basename(object_key)}"
                
            try:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=processed_key,
                    Body=csv_content.encode('utf-8'),
                    ContentType='text/csv'
                )
                print(f"Successfully copied validated data to {processed_key}")
            except Exception as e:
                print(f"Warning: Could not save to processed-data: {e}")
                
        return {
            'statusCode': 200 if validation_result['success'] else 400,
            'body': json.dumps({
                'message': 'S3 CSV validation completed',
                'bucket': bucket_name,
                'key': object_key,
                'summary': {
                    'total_rows': validation_result['total_rows'],
                    'valid_rows': validation_result['valid_rows'],
                    'invalid_rows': validation_result['invalid_rows'],
                    'anomalies_detected': validation_result['anomalies_detected']
                },
                'errors': validation_result['errors']
            })
        }

    # Direct payload mode (for local testing, CI/CD, or manual test invocation)
    elif 'csv_content' in event:
        validation_result = process_csv_content(event['csv_content'])
        return {
            'statusCode': 200 if validation_result['success'] else 400,
            'body': json.dumps(validation_result, default=str)
        }
    
    # Direct local file path mode (convenient for local CLI / app invocation)
    elif 'file_path' in event:
        file_path = event['file_path']
        if not os.path.exists(file_path):
            return {
                'statusCode': 404,
                'body': json.dumps({'error': f"File not found: {file_path}"})
            }
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        validation_result = process_csv_content(content)
        return {
            'statusCode': 200 if validation_result['success'] else 400,
            'body': json.dumps({
                'file_path': file_path,
                'total_rows': validation_result['total_rows'],
                'valid_rows': validation_result['valid_rows'],
                'invalid_rows': validation_result['invalid_rows'],
                'anomalies_detected': validation_result['anomalies_detected'],
                'errors': validation_result['errors'],
                'anomalies_sample': validation_result['anomalies'][:5]
            }, default=str)
        }

    return {
        'statusCode': 400,
        'body': json.dumps({'error': 'Unsupported event format. Provide S3 event, csv_content, or file_path.'})
    }


if __name__ == '__main__':
    # Local verification test when run directly
    sample_file = os.path.join(os.path.dirname(__file__), 'data', 'food_waste.csv')
    if os.path.exists(sample_file):
        print(f"Running local Lambda validation test against {sample_file}...")
        res = lambda_handler({'file_path': sample_file})
        print("Lambda Result:")
        print(json.dumps(json.loads(res['body']), indent=2))
    else:
        print(f"File {sample_file} not found for local test.")
