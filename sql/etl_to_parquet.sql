-- ============================================================================
-- Project: Food Waste Analysis Dashboard Using AWS
-- Module: Athena CTAS ETL Pipeline to Partitioned Parquet
-- ============================================================================

DROP TABLE IF EXISTS food_waste_db.canteen_waste_parquet;

CREATE TABLE food_waste_db.canteen_waste_parquet
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    external_location = 's3://{BUCKET_NAME}/processed-data/parquet/',
    partitioned_by = ARRAY['year', 'month']
) AS
SELECT 
    record_id,
    date,
    location,
    meal_type,
    food_category,
    food_item,
    prepared_qty_kg,
    consumed_qty_kg,
    wasted_qty_kg,
    waste_percentage,
    cost_per_kg_inr,
    waste_cost_inr,
    waste_reason,
    substr(date, 1, 4) AS year,
    substr(date, 6, 2) AS month
FROM food_waste_db.canteen_waste;
