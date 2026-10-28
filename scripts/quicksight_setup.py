"""
Script: scripts/quicksight_setup.py
Description: Programmatically sets up Amazon QuickSight Data Source and Dataset
             connected to Amazon Athena (food_waste_db.canteen_waste).
"""

import os
import sys
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


def setup_quicksight_resources(session, region, account_id, athena_db='food_waste_db'):
    print("=" * 70)
    print("Setting Up Amazon QuickSight Data Source & Dataset...")
    print(f"Account ID: {account_id}")
    print(f"Region:     {region}")
    print(f"Database:   {athena_db}")
    print("=" * 70)

    qs = session.client('quicksight', region_name=region)
    data_source_id = "food-waste-athena-datasource"
    dataset_id = "food-waste-canteen-dataset"

    # 1. Create Athena Data Source in QuickSight
    data_source_params = {
        'AwsAccountId': account_id,
        'DataSourceId': data_source_id,
        'Name': 'FoodWasteAthenaSource',
        'Type': 'ATHENA',
        'DataSourceParameters': {
            'AthenaParameters': {
                'WorkGroup': 'primary'
            }
        },
        'Permissions': [
            {
                'Principal': f"arn:aws:quicksight:{region}:{account_id}:user/default/{account_id}",
                'Actions': [
                    'quicksight:DescribeDataSource',
                    'quicksight:DescribeDataSourcePermissions',
                    'quicksight:PassDataSource',
                    'quicksight:UpdateDataSource',
                    'quicksight:DeleteDataSource',
                    'quicksight:UpdateDataSourcePermissions'
                ]
            }
        ]
    }

    try:
        print(f"Creating QuickSight Athena Data Source: {data_source_id}...")
        resp = qs.create_data_source(**data_source_params)
        ds_arn = resp['Arn']
        print(f"Data source created: {ds_arn}")
    except ClientError as e:
        code = e.response['Error']['Code']
        if code == 'ResourceExistsException':
            print(f"Data source '{data_source_id}' already exists.")
            ds_arn = f"arn:aws:quicksight:{region}:{account_id}:datasource/{data_source_id}"
        elif code in ['AccessDeniedException', 'QuickSightUserNotFoundException']:
            print(f"QuickSight configuration notice: {e.response['Error']['Message']}")
            print("To complete QuickSight setup via console, refer to: docs/quicksight_setup.md")
            return False
        else:
            print(f"Notice on QuickSight data source: {e}")
            print("Refer to docs/quicksight_setup.md for manual console steps.")
            return False

    # 2. Create QuickSight Dataset
    physical_table_map = {
        'CanteenWasteTable': {
            'RelationalTable': {
                'DataSourceArn': ds_arn,
                'Catalog': 'AwsDataCatalog',
                'Schema': athena_db,
                'Name': 'canteen_waste',
                'InputColumns': [
                    {'Name': 'record_id', 'Type': 'STRING'},
                    {'Name': 'record_date', 'Type': 'STRING'},
                    {'Name': 'location', 'Type': 'STRING'},
                    {'Name': 'meal_type', 'Type': 'STRING'},
                    {'Name': 'food_category', 'Type': 'STRING'},
                    {'Name': 'food_item', 'Type': 'STRING'},
                    {'Name': 'prepared_qty_kg', 'Type': 'DECIMAL'},
                    {'Name': 'consumed_qty_kg', 'Type': 'DECIMAL'},
                    {'Name': 'wasted_qty_kg', 'Type': 'DECIMAL'},
                    {'Name': 'waste_percentage', 'Type': 'DECIMAL'},
                    {'Name': 'cost_per_kg_inr', 'Type': 'DECIMAL'},
                    {'Name': 'waste_cost_inr', 'Type': 'DECIMAL'},
                    {'Name': 'waste_reason', 'Type': 'STRING'}
                ]
            }
        }
    }

    dataset_params = {
        'AwsAccountId': account_id,
        'DataSetId': dataset_id,
        'Name': 'CanteenFoodWasteDataset',
        'PhysicalTableMap': physical_table_map,
        'ImportMode': 'DIRECT_QUERY'
    }

    try:
        print(f"Creating QuickSight Dataset: {dataset_id}...")
        d_resp = qs.create_data_set(**dataset_params)
        print(f"Dataset created: {d_resp['Arn']}")
        print("\nQuickSight resources ready for dashboard visualization.")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceExistsException':
            print(f"Dataset '{dataset_id}' already exists.")
            return True
        else:
            print(f"Notice on QuickSight dataset creation: {e}")
            print("Refer to docs/quicksight_setup.md for visual builder walkthrough.")
            return False


def main():
    env = load_env()
    region = os.getenv('AWS_DEFAULT_REGION', env.get('AWS_DEFAULT_REGION', 'ap-south-1'))
    athena_db = os.getenv('ATHENA_DB', env.get('ATHENA_DB', 'food_waste_db'))

    try:
        session = boto3.Session(region_name=region)
        sts = session.client('sts')
        caller = sts.get_caller_identity()
        account_id = caller['Account']

        setup_quicksight_resources(session, region, account_id, athena_db)

    except (NoCredentialsError, ClientError) as e:
        print(f"AWS not connected: {e}")
        print("QuickSight setup script will execute once AWS credentials are configured.")
        print("See docs/quicksight_setup.md for full step-by-step instructions.")


if __name__ == '__main__':
    main()
