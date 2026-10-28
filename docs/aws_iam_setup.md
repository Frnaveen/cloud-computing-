# AWS IAM Least-Privilege Setup Guide

This document explains how to attach the least-privilege policy defined in `docs/aws_iam_policy.json` to your AWS IAM user or deployment role.

---

## 1. Overview of Permissions

The policy grants permissions restricted to the resources required by this project:
- **Amazon S3:** Bucket lifecycle, reading raw telemetry, writing validated/partitioned data, and Athena query result storage (prefixed with `food-waste-*`).
- **AWS Lambda:** Creating, configuring, invoking, and deleting the data validation function (`food-waste-*`).
- **IAM PassRole:** Passing execution roles for Lambda, SageMaker, and App Runner scoped specifically to `food-waste-*`.
- **Amazon Athena & AWS Glue:** Database creation, table registration, and query execution against the data lake.
- **Amazon CloudWatch Logs:** Collecting telemetry and operational metrics.
- **Amazon SNS:** Creating and publishing alerts for high-waste anomalies (`food-waste-*`).
- **Amazon SageMaker:** Executing scikit-learn model training jobs and managing model artifacts.
- **Amazon ECR & AWS App Runner:** Housing container images and hosting the web dashboard.
- **AWS Budgets:** Creating cost guardrails and alerting thresholds.

---

## 2. Attaching via AWS Management Console

1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/) as an administrator.
2. Navigate to **IAM (Identity and Access Management)** > **Policies**.
3. Click **Create policy**.
4. In the policy editor, select the **JSON** tab.
5. Paste the contents of [`docs/aws_iam_policy.json`](./aws_iam_policy.json).
6. Click **Next**.
7. Name the policy: `FoodWasteProjectPolicy`.
8. Description: `Least-privilege policy for Food Waste Analysis project pipeline.`
9. Click **Create policy**.
10. Navigate to **Users**, select your IAM user, go to the **Permissions** tab, click **Add permissions** > **Attach policies directly**, search for `FoodWasteProjectPolicy`, and click **Add permissions**.

---

## 3. Attaching via AWS CLI

If using an administrator profile with the AWS CLI:

```bash
# 1. Create the customer managed policy
aws iam create-policy \
    --policy-name FoodWasteProjectPolicy \
    --policy-document file://docs/aws_iam_policy.json \
    --description "Least-privilege policy for Food Waste Analysis project"

# 2. Attach the policy to your IAM user (replace YOUR_IAM_USERNAME)
aws iam attach-user-policy \
    --user-name YOUR_IAM_USERNAME \
    --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/FoodWasteProjectPolicy
```
