# Amazon QuickSight Dashboard Setup Guide

This guide describes how to configure Amazon QuickSight for business intelligence reporting on the canteen food waste dataset stored in Amazon S3 and cataloged in AWS Glue / Amazon Athena.

---

## 1. Prerequisites and IAM / S3 Permissions

QuickSight requires IAM permissions to access Amazon S3 buckets and Amazon Athena:

1. Sign in to the AWS Management Console and navigate to **Amazon QuickSight**.
2. If this is your first time, click **Sign up for QuickSight** (Standard or Enterprise edition).
3. In QuickSight, click your profile icon (top right) > **Manage QuickSight**.
4. In the left navigation menu, click **Security & permissions**.
5. Under **QuickSight access to AWS services**, click **Manage** / **Add or remove**.
6. Check **Amazon Athena**.
7. Check **Amazon S3**:
   - In the pop-up modal, select your project bucket (`s3://food-waste-canteen-*`).
   - Check **Write permission for Athena workgroup** for the `athena-results/` path.
8. Click **Save**.

---

## 2. Creating the Athena Data Source in QuickSight

1. In the QuickSight home screen, click **Datasets** in the left menu.
2. Click **New dataset** (top right).
3. Select **Athena** as the data source.
4. Set **Data source name**: `FoodWasteAthenaSource`.
5. Set **Athena workgroup**: `[primary]`.
6. Click **Create data source**.
7. In the database dropdown, select:
   - **Catalog**: `AwsDataCatalog`
   - **Database**: `food_waste_db`
   - **Table**: `canteen_waste` (or `canteen_waste_parquet`)
8. Select **Import to SPICE for quicker analysis** (or **Directly query your data**).
9. Click **Visualize**.

---

## 3. Building the 5 Dashboard Visuals

### Visual 1: Total Waste KPI
- **Visual type**: KPI
- **Value**: `wasted_qty_kg` (Aggregation: Sum)
- **Formatting**: Set units to kg (e.g. `8,128.6 kg`).

### Visual 2: Overall Waste Percentage KPI
- **Calculated field**: Create field named `Waste_Percentage`:
  ```
  sum({wasted_qty_kg}) / sum({prepared_qty_kg}) * 100
  ```
- **Visual type**: KPI
- **Value**: `Waste_Percentage` (Format as percentage with 2 decimals).

### Visual 3: Food Waste by Location
- **Visual type**: Horizontal Bar Chart
- **Y axis**: `location`
- **Value**: `wasted_qty_kg` (Aggregation: Sum)
- **Color**: `waste_cost_inr` (Aggregation: Sum)

### Visual 4: Waste by Food Category
- **Visual type**: Donut Chart
- **Group/Color**: `food_category`
- **Value**: `wasted_qty_kg` (Aggregation: Sum)

### Visual 5: Daily Preparation vs. Waste Trend
- **Visual type**: Line Chart
- **X axis**: `date`
- **Value**: `prepared_qty_kg` (Sum) and `wasted_qty_kg` (Sum)

---

## 4. Publishing the Dashboard

1. In the top navigation bar, click **Share** > **Publish dashboard**.
2. Enter the dashboard name: `Campus Food Waste Analytics Dashboard`.
3. Click **Publish dashboard**.
4. The dashboard is now accessible to campus dining managers and university stakeholders.
