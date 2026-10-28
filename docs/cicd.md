# Continuous Integration & Continuous Deployment (CI/CD) Guide

This repository uses GitHub Actions (`.github/workflows/ci.yml`) to automatically test, validate, build, and deploy the Food Waste Analysis platform to AWS.

---

## 1. Workflow Pipeline Stages

The workflow executes across two main stages:

### Stage 1: `test-and-validate` (Runs on Pull Requests and Pushes)
- **Environment Setup:** Python 3.11 with cached pip dependencies.
- **Code Linting & Syntax:** Flake8 check for syntax errors and verification that all modules compile.
- **Unit Testing:** Executes `pytest tests/ -v` covering 14 test cases across data integrity, Lambda validation rules, Presto SQL aggregations, and ML pipelines.
- **Docker Build Verification:** Builds the container image to ensure reproducible local and cloud packaging.

### Stage 2: `deploy` (Runs on pushes to `main` branch after tests pass)
- **Credential Configuration:** Configures AWS IAM credentials securely using GitHub Secrets.
- **Serverless Function Update:** Packages `lambda_function.py` and updates the `food-waste-validator` AWS Lambda function.
- **Container Registry Push:** Authenticates to Amazon ECR, builds the production container, and pushes `food-waste-dashboard:latest`.

---

## 2. Required GitHub Secrets

To enable the automated deployment stage, configure the following secrets in your GitHub repository:

1. In your GitHub repository, navigate to **Settings** > **Secrets and variables** > **Actions**.
2. Click **New repository secret**.
3. Add the following secrets:

| Secret Name | Description | Example Value |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Your IAM user access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | Your IAM user secret access key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | Target AWS deployment region | `ap-south-1` |

---

## 3. Security Considerations
- Credentials are stored encrypted by GitHub and never logged in workflow outputs.
- Pull requests from external forks do not have access to these secrets.
- The IAM user associated with these keys should use the least-privilege policy defined in `docs/aws_iam_policy.json`.
