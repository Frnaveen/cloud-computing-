# Project Screenshots Checklist

This directory contains visual demonstration artifacts for the Food Waste Analysis Platform. Use the checklist below to capture and save screenshots for report and evaluation appendices.

---

## Required Screenshots Checklist

| Figure # | Target Component | Filename | Description / What to Capture |
|---|---|---|---|
| **Figure 1** | Amazon S3 Bucket | `01_s3_bucket.png` | AWS S3 Console showing bucket prefixes: `raw-data/`, `processed-data/`, and `athena-results/`. |
| **Figure 2** | AWS Lambda Trigger | `02_lambda_trigger.png` | AWS Lambda Console showing function `food-waste-validator` with active S3 bucket event trigger. |
| **Figure 3** | CloudWatch Logs | `03_cloudwatch_logs.png` | CloudWatch Log Stream under `/aws/lambda/food-waste-validator` showing execution latency and records processed. |
| **Figure 4** | Athena Query Editor | `04_athena_query_results.png` | Amazon Athena Console showing successful query execution and tabular results against `food_waste_db.canteen_waste`. |
| **Figure 5** | S3 Parquet Output | `05_parquet_output.png` | S3 Console showing partitioned Parquet files under `s3://.../processed-data/parquet/year=2026/month=.../`. |
| **Figure 6** | SageMaker Job | `06_sagemaker_training.png` | SageMaker Console showing training job status or artifact upload to `s3://.../models/`. |
| **Figure 7** | QuickSight Dashboard | `07_quicksight_dashboard.png` | QuickSight visual interface showing KPIs, location bar chart, and category donut chart. |
| **Figure 8** | AWS App Runner | `08_apprunner_url.png` | App Runner Console showing active service status and default domain URL. |
| **Figure 9** | GitHub Actions Run | `09_github_actions_run.png` | GitHub Actions workflow execution showing passing `test-and-validate` job and `deploy` job. |
| **Figure 10** | Streamlit Analytics Tab | `10_streamlit_analytics.png` | Dashboard Tab 1 showing executive KPI cards and Plotly trend/category charts. |
| **Figure 11** | Streamlit Pipeline Tab | `11_streamlit_pipeline.png` | Dashboard Tab 2 showing interactive Lambda runner output with anomaly counts. |
| **Figure 12** | Streamlit Athena Studio | `12_streamlit_athena.png` | Dashboard Tab 3 showing query selection, SQL editor, and result table with CSV download. |
| **Figure 13** | Streamlit ML Forecast Tab | `13_streamlit_ml_forecast.png` | Dashboard Tab 4 showing model comparison metrics table and interactive waste prediction form. |
| **Figure 14** | Streamlit Dataset Explorer | `14_streamlit_dataset.png` | Dashboard Tab 5 showing dataset table viewer, row count, and schema dictionary. |
| **Figure 15** | Streamlit Design FAQ Tab | `15_streamlit_faq.png` | Dashboard Tab 6 showing project overview, pipeline summary, and architecture FAQs. |
