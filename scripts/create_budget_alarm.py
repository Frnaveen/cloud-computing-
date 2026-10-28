"""
Script: create_budget_alarm.py
Description: Creates an AWS Budget of 10 USD with an email alert for project cost monitoring.
"""

import sys
import argparse
import boto3
from botocore.exceptions import ClientError


def create_budget(email, budget_limit=10.0):
    sts_client = boto3.client('sts')
    try:
        account_id = sts_client.get_caller_identity()['Account']
    except Exception as e:
        print(f"Error fetching AWS caller identity: {e}")
        return False

    budgets_client = boto3.client('budgets')
    budget_name = "food-waste-project-monthly-budget"

    budget_definition = {
        'BudgetName': budget_name,
        'BudgetLimit': {
            'Amount': str(float(budget_limit)),
            'Unit': 'USD'
        },
        'TimeUnit': 'MONTHLY',
        'BudgetType': 'COST',
        'CostTypes': {
            'IncludeTax': True,
            'IncludeSubscription': True,
            'UseBlended': False,
            'IncludeRefund': False,
            'IncludeCredit': False,
            'IncludeUpfront': True,
            'IncludeRecurring': True,
            'IncludeOtherSubscription': True,
            'IncludeSupport': True,
            'IncludeDiscount': True,
            'UseAmortized': False
        }
    }

    notifications_with_subscribers = [
        {
            'Notification': {
                'NotificationType': 'ACTUAL',
                'ComparisonOperator': 'GREATER_THAN',
                'Threshold': 80.0,
                'ThresholdType': 'PERCENTAGE',
                'NotificationState': 'ALARM'
            },
            'Subscribers': [
                {
                    'SubscriptionType': 'EMAIL',
                    'Address': email
                }
            ]
        },
        {
            'Notification': {
                'NotificationType': 'ACTUAL',
                'ComparisonOperator': 'GREATER_THAN',
                'Threshold': 100.0,
                'ThresholdType': 'PERCENTAGE',
                'NotificationState': 'ALARM'
            },
            'Subscribers': [
                {
                    'SubscriptionType': 'EMAIL',
                    'Address': email
                }
            ]
        }
    ]

    try:
        print(f"Creating monthly budget '{budget_name}' of {budget_limit} USD for account {account_id}...")
        budgets_client.create_budget(
            AccountId=account_id,
            Budget=budget_definition,
            NotificationsWithSubscribers=notifications_with_subscribers
        )
        print(f"Budget successfully created. Alerts will be sent to: {email}")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'DuplicateRecordException':
            print(f"Budget '{budget_name}' already exists. Updating existing budget...")
            budgets_client.update_budget(
                AccountId=account_id,
                NewBudget=budget_definition
            )
            print("Budget updated successfully.")
            return True
        else:
            print(f"Failed to create budget: {e.response['Error']['Message']}")
            return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Create AWS Budget Alarm")
    parser.add_argument("--email", required=False, help="Email address to receive budget alarm notifications")
    parser.add_argument("--limit", default=10.0, type=float, help="Budget limit in USD (default: 10.0)")
    args = parser.parse_args()

    email_addr = args.email
    if not email_addr:
        email_addr = input("Enter notification email address for the 10 USD budget alarm: ").strip()

    if not email_addr:
        print("Error: An email address is required to configure budget notifications.")
        sys.exit(1)

    success = create_budget(email_addr, args.limit)
    sys.exit(0 if success else 1)
