INSERT INTO {{ var.json.hw4_target_table.table_name }}
SELECT
    o.name,
    c.age,
    g.good_title,
    o.date,
    s.payment_status,
    g.price * o.amount AS total_price,
    o.amount,
    now() AS last_modified_at
FROM {{ var.json.hw4_temp_tables.orders_table }} o
LEFT JOIN {{ var.json.hw4_temp_tables.status_table }} s USING (order_uuid)
LEFT JOIN {{ var.json.hw4_temp_tables.customers_table }} c USING (email)
LEFT JOIN {{ var.json.hw4_temp_tables.goods_table }} g USING (good_title)
ON CONFLICT ON CONSTRAINT {{ var.json.hw4_target_table.constraint_name }}
DO UPDATE SET
    payment_status=EXCLUDED.payment_status,
    last_modified_at=now() at time zone 'utc';