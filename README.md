# Food Waste Analysis Dashboard Using AWS
### B.Tech Cloud Computing Project

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.62.0-red)
![AWS S3](https://img.shields.io/badge/AWS-Amazon%20S3-orange)
![AWS Lambda](https://img.shields.io/badge/AWS-Lambda%20Serverless-ff9900)
![AWS Athena](https://img.shields.io/badge/AWS-Amazon%20Athena-232f3e)
![AWS Glue](https://img.shields.io/badge/AWS-Glue%20Catalog-purple)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ed)
![CI/CD](https://img.shields.io/badge/GitHub%20Actions-CI%2FCD-green)

---

## 1. Executive Summary & Problem Statement

College canteens and hostel messes cater to thousands of students and staff daily. Due to unpredictable day-to-day attendance fluctuations (caused by exam schedules, semester breaks, weekend leaves, and timetable variations), kitchen administrations frequently face **forecasting errors**. This leads to:
1. **Severe Food Wastage:** Thousands of kilograms of cooked grains, curries, and dairy items discarded into landfills.
2. **Economic Inefficiency:** Substantial institutional budget loss in raw materials, LPG, and labor.
3. **Environmental Carbon Footprint:** Anaerobic decomposition of organic waste producing methane gas.

This project implements an **event-driven, serverless cloud analytics pipeline using Amazon Web Services (AWS)** to ingest daily food preparation and wastage telemetry, perform schema and business logic validation, execute distributed SQL analytics using **Amazon Athena**, and visualize actionable operational insights using an interactive **Streamlit and Plotly dashboard**.

---

## 2. Cloud Architecture & Pipeline Flow

```mermaid
flowchart TD
    subgraph Data_Ingestion["1. Data Ingestion Layer"]
        A[Canteen POS / Daily Log CSV] -->|Upload via Boto3 / API| B[(Amazon S3 Bucket\ns3://bucket/raw-data/)]
    end

    subgraph Serverless_Validation["2. Event-Driven Validation Layer"]
        B -->|s3:ObjectCreated:* Event| C[AWS Lambda Function\nlambda_function.py]
        C -->|Schema Check & Logical Validation| D{Valid Data?}
        D -->|Yes| E[(Amazon S3 Bucket\ns3://bucket/processed-data/)]
        D -->|Anomaly > 25% Waste| F[Alert Notification\nCloudWatch / SNS]
    end

    subgraph Catalog_and_Query["3. Catalog & Query Engine"]
        E --> G[AWS Glue Data Catalog\nfood_waste_db.canteen_waste]
        G --> H[Amazon Athena\nServerless Presto / Trino SQL Engine]
    end

    subgraph Visualization_Layer["4. Analytics & BI Layer"]
        H --> I[Streamlit Interactive Web Dashboard]
        H -.-> J[Amazon QuickSight\n(Optional Enterprise BI)]
        I --> K[Canteen Administration & Inventory Planners]
    end
```

### AWS Service Roles:
- **Amazon S3 (Simple Storage Service):** Acts as the centralized cloud Data Lake storing raw canteen telemetry, validated records, and Athena query output caches.
- **AWS Lambda:** Serverless compute triggered by S3 uploads to perform data sanitization, verify constraints (`wasted_qty <= prepared_qty`), and flag high-waste anomalies.
- **AWS Glue Data Catalog:** Manages table metadata, column schemas, and partition mapping for Athena.
- **Amazon Athena:** Executes distributed serverless ANSI SQL queries in-place against S3 files without requiring a provisioned database.
- **Docker & GitHub Actions:** Provides repeatable containerization and continuous integration with automated pytest validation.

---

## 3. Repository Structure

```
.
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions automated test & build workflow
├── data/
│   └── food_waste.csv             # 630-row realistic campus canteen food waste dataset
├── sql/
│   └── food_waste_analysis.sql    # Amazon Athena DDL and analytical SQL queries
├── tests/
│   ├── test_data_validation.py    # Unit tests for schema validation and Lambda logic
│   └── test_app.py                # Unit tests for SQL queries and AWS fallback
├── app.py                         # Streamlit interactive analytics dashboard
├── aws_manager.py                 # AWS Boto3 abstraction with offline fallback
├── aws_setup.py                   # Automated AWS resource provisioning CLI script
├── lambda_function.py             # AWS Lambda serverless validation handler
├── Dockerfile                     # Container definition for Streamlit app
├── docker-compose.yml             # Single-command container deployment
├── requirements.txt               # Pinned Python package dependencies
├── README.md                      # Project documentation and quickstart guide
└── PROJECT_REPORT.md              # Comprehensive project report
```

---

## 4. Quickstart & Local Execution

### Prerequisites
- Python 3.10+ (Tested on Python 3.11, 3.12, 3.14)
- Pip

### 1. Clone & Install Dependencies
```bash
# Navigate to project folder
cd "cloud computing"

# Install required packages
pip install -r requirements.txt
```

### 2. Run the Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

> **Note on AWS Credentials:**
> - If AWS credentials **are not configured**, the app runs automatically in **Local / Education Demo Mode**, executing identical Presto/Athena SQL queries via DuckDB and simulating S3/Lambda operations without errors or cloud costs.
> - To connect to live AWS, simply expand the **AWS Cloud Configuration** drawer in the sidebar and enter your credentials, or run `aws configure`.

---

## 5. Automated Testing

Run the full pytest suite:
```bash
pytest tests/ -v
```
All 11 tests validate:
- Dataset existence and schema integrity.
- Logical rules (`wasted_qty <= prepared_qty`, positive quantities).
- Lambda function validation handler, error catching, and anomaly detection.
- Presto / Athena SQL query execution.
- Graceful AWS offline fallback.

---

## 6. Docker Deployment

### Run using Docker Compose:
```bash
docker compose up --build
```
Access at `http://localhost:8501`.

### Run using Docker CLI:
```bash
docker build -t food-waste-analysis .
docker run -p 8501:8501 food-waste-analysis
```

---

## 7. Connecting Real AWS Services (Optional)

If you have an active AWS account and wish to deploy cloud resources:

1. Configure AWS CLI:
   ```bash
   aws configure
   # Enter AWS Access Key ID, Secret Access Key, Region (e.g. us-east-1)
   ```

2. Run the Automated AWS Setup Script:
   ```bash
   python3 aws_setup.py
   ```
   This will:
   - Create an Amazon S3 Bucket: `s3://food-waste-canteen-<timestamp>/`.
   - Upload `data/food_waste.csv` to `raw-data/`.
   - Create the AWS Glue / Athena database `food_waste_db`.
   - Execute table creation DDL in Amazon Athena.
   - Package `lambda_deployment_package.zip` ready for Lambda upload.

---

## 8. Design FAQ

1. **Why choose Amazon Athena over Amazon RDS / MySQL?**
   - *Athena is serverless:* No server provisioning, patching, or scaling required.
   - *Cost model:* Pay only per query ($5/TB scanned), unlike RDS which charges 24/7 for running virtual instances.
   - *Data Lake native:* Queries S3 files in place without ETL overhead.

2. **What does AWS Lambda validate in this pipeline?**
   - Verifies all 12 required columns exist and data types are valid.
   - Enforces business logic: `prepared_qty > 0`, `wasted_qty >= 0`, `wasted_qty <= prepared_qty`.
   - Flags high-waste anomalies where waste percentage exceeds 25%.

3. **How does AWS Glue integrate with Amazon Athena?**
   - Glue Data Catalog acts as the central schema metadata store. Athena queries reference table definitions registered in Glue.

---

## 9. References & Official AWS Documentation
- [Amazon S3 Documentation](https://docs.aws.amazon.com/s3/)
- [AWS Lambda Developer Guide](https://docs.aws.amazon.com/lambda/)
- [Amazon Athena User Guide](https://docs.aws.amazon.com/athena/)
- [AWS Glue Data Catalog](https://docs.aws.amazon.com/glue/)
- [Streamlit Documentation](https://docs.streamlit.io/)
