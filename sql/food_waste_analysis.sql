-- ============================================================================
-- Project: Food Waste Analysis Dashboard Using AWS (B.Tech Cloud Computing Project)
-- Service: Amazon Athena (Serverless SQL Analytics on Amazon S3)
-- Database: food_waste_db
-- Source Data: s3://<your-s3-bucket-name>/raw-data/food_waste.csv
-- Engine: Amazon Athena (Presto / Trino SQL)
-- ============================================================================

-- ============================================================================
-- 1. DATABASE SETUP
-- ============================================================================
CREATE DATABASE IF NOT EXISTS food_waste_db
COMMENT 'College Canteen Food Waste Analytics Database';

-- ============================================================================
-- 2. DDL: EXTERNAL TABLE CREATION
-- Note: Replace 'food-waste-analysis-bucket-2026' with your actual S3 bucket name.
-- ============================================================================
DROP TABLE IF EXISTS food_waste_db.canteen_waste;

CREATE EXTERNAL TABLE IF NOT EXISTS food_waste_db.canteen_waste (
    record_id STRING,
    record_date STRING,
    location STRING,
    meal_type STRING,
    food_category STRING,
    food_item STRING,
    prepared_qty_kg DOUBLE,
    consumed_qty_kg DOUBLE,
    wasted_qty_kg DOUBLE,
    waste_percentage DOUBLE,
    cost_per_kg_inr DOUBLE,
    waste_cost_inr DOUBLE,
    waste_reason STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
ESCAPED BY '\\'
LINES TERMINATED BY '\n'
LOCATION 's3://food-waste-analysis-bucket-2026/raw-data/'
TBLPROPERTIES ('skip.header.line.count'='1');


-- ============================================================================
-- 3. CORE ANALYTICAL QUERIES (RUN IN ATHENA CONSOLE OR DASHBOARD)
-- ============================================================================

-- Query 1: Overall Summary KPIs
-- Calculates total food prepared, consumed, wasted, overall waste % and total financial loss.
SELECT 
    COUNT(record_id) AS total_meal_logs,
    ROUND(SUM(prepared_qty_kg), 2) AS total_prepared_kg,
    ROUND(SUM(consumed_qty_kg), 2) AS total_consumed_kg,
    ROUND(SUM(wasted_qty_kg), 2) AS total_wasted_kg,
    ROUND((SUM(wasted_qty_kg) / SUM(prepared_qty_kg)) * 100, 2) AS overall_waste_percentage,
    ROUND(SUM(waste_cost_inr), 2) AS total_financial_loss_inr,
    ROUND(AVG(waste_percentage), 2) AS avg_meal_waste_pct
FROM food_waste_db.canteen_waste;


-- Query 2: Location-Wise Waste Ranking
-- Identifies which dining facility (Hostel Mess, Main Canteen, Food Court) produces the most waste.
SELECT 
    location,
    COUNT(record_id) AS total_records,
    ROUND(SUM(prepared_qty_kg), 1) AS prepared_kg,
    ROUND(SUM(consumed_qty_kg), 1) AS consumed_kg,
    ROUND(SUM(wasted_qty_kg), 1) AS wasted_kg,
    ROUND((SUM(wasted_qty_kg) / SUM(prepared_qty_kg)) * 100, 2) AS waste_pct,
    ROUND(SUM(waste_cost_inr), 2) AS total_loss_inr
FROM food_waste_db.canteen_waste
GROUP BY location
ORDER BY wasted_kg DESC;


-- Query 3: Category-Wise Food Waste Analysis
-- Analyzes waste across Grains, Curries, Bakery, Breakfast, and Dairy items.
SELECT 
    food_category,
    COUNT(record_id) AS items_logged,
    ROUND(SUM(prepared_qty_kg), 1) AS prepared_kg,
    ROUND(SUM(wasted_qty_kg), 1) AS wasted_kg,
    ROUND((SUM(wasted_qty_kg) / SUM(prepared_qty_kg)) * 100, 2) AS waste_percentage,
    ROUND(SUM(waste_cost_inr), 2) AS cost_loss_inr,
    ROUND(AVG(cost_per_kg_inr), 2) AS avg_item_cost_per_kg
FROM food_waste_db.canteen_waste
GROUP BY food_category
ORDER BY cost_loss_inr DESC;


-- Query 4: Top 10 Most Wasted Food Items (Cost & Quantity Impact)
-- Critical for canteen managers to identify specific dishes that cause maximum loss.
SELECT 
    food_item,
    food_category,
    ROUND(SUM(prepared_qty_kg), 1) AS total_prepared_kg,
    ROUND(SUM(wasted_qty_kg), 1) AS total_wasted_kg,
    ROUND(AVG(waste_percentage), 2) AS avg_waste_pct,
    ROUND(SUM(waste_cost_inr), 2) AS total_waste_cost_inr
FROM food_waste_db.canteen_waste
GROUP BY food_item, food_category
ORDER BY total_waste_cost_inr DESC
LIMIT 10;


-- Query 5: Meal-Type Breakdown (Breakfast vs Lunch vs Snacks vs Dinner)
-- Evaluates which meal session has the worst forecasting mismatch.
SELECT 
    meal_type,
    ROUND(SUM(prepared_qty_kg), 1) AS prepared_kg,
    ROUND(SUM(wasted_qty_kg), 1) AS wasted_kg,
    ROUND((SUM(wasted_qty_kg) / SUM(prepared_qty_kg)) * 100, 2) AS waste_percentage,
    ROUND(SUM(waste_cost_inr), 2) AS financial_loss_inr
FROM food_waste_db.canteen_waste
GROUP BY meal_type
ORDER BY financial_loss_inr DESC;


-- Query 6: Primary Reasons for Food Waste
-- Categorizes operational reasons (e.g. Over-preparation vs Low Footfall).
SELECT 
    waste_reason,
    COUNT(record_id) AS incident_count,
    ROUND(SUM(wasted_qty_kg), 1) AS total_wasted_kg,
    ROUND(SUM(waste_cost_inr), 2) AS total_cost_inr,
    ROUND((SUM(wasted_qty_kg) / (SELECT SUM(wasted_qty_kg) FROM food_waste_db.canteen_waste)) * 100, 2) AS share_of_total_waste_pct
FROM food_waste_db.canteen_waste
GROUP BY waste_reason
ORDER BY total_wasted_kg DESC;


-- Query 7: High-Waste Anomaly Detection (Threshold > 25% Waste)
-- Flags critical operations requiring immediate management intervention.
SELECT 
    record_id,
    record_date,
    location,
    meal_type,
    food_item,
    prepared_qty_kg,
    wasted_qty_kg,
    waste_percentage,
    waste_cost_inr,
    waste_reason
FROM food_waste_db.canteen_waste
WHERE waste_percentage >= 25.0
ORDER BY waste_percentage DESC, waste_cost_inr DESC
LIMIT 20;


-- Query 8: Advanced Window Function - Top Wasted Item per Location
-- Uses DENSE_RANK() OVER (PARTITION BY ... ORDER BY ...) to show highest wasted dish for each mess.
WITH ranked_items AS (
    SELECT 
        location,
        food_item,
        food_category,
        ROUND(SUM(wasted_qty_kg), 1) AS total_wasted_kg,
        ROUND(SUM(waste_cost_inr), 2) AS total_waste_cost_inr,
        DENSE_RANK() OVER (PARTITION BY location ORDER BY SUM(wasted_qty_kg) DESC) AS rank_in_location
    FROM food_waste_db.canteen_waste
    GROUP BY location, food_item, food_category
)
SELECT 
    location,
    food_item,
    food_category,
    total_wasted_kg,
    total_waste_cost_inr
FROM ranked_items
WHERE rank_in_location = 1
ORDER BY total_wasted_kg DESC;
