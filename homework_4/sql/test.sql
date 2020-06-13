--	 public;
--
--DROP TABLE IF EXISTS orders_tmp;
--CREATE TABLE IF NOT EXISTS orders_tmp (
--    order_uuid  char(50),
--    good_title  char(100),
--    date		timestamp,
--    amount		integer,
--    name		char(50),
--    email		char(50)
--);
--
--
--DROP TABLE IF EXISTS status_tmp;
--CREATE TABLE IF NOT EXISTS status_tmp (
--    order_uuid  	char(50),
--    payment_status 	char(10)
--);
--
--
--DROP TABLE IF EXISTS customers_tmp;
--CREATE TABLE IF NOT EXISTS customers_tmp (
--    email       char(50),
--    age         integer
--);
--
--
--DROP TABLE IF EXISTS goods_tmp;	
--CREATE TABLE IF NOT EXISTS goods_tmp (
--    good_title  char(100),
--    price 		numeric
--);
--
--
--SELECT count(*) FROM orders_tmp;
--SELECT count(*) FROM status_tmp;
--SELECT count(*) FROM customers_tmp;
--SELECT count(*) FROM goods_tmp;
--
--
--DROP TABLE IF EXISTS final_data;	
--CREATE TABLE IF NOT EXISTS final_data (
--    name				char(50),
--	age					integer,	
--	good_title			char(100),
--	date				timestamp,
--	payment_status		char(10),
--	total_price			numeric,
--	amount				integer,
--	last_modified_at	timestamp,
--	CONSTRAINT hw4_unq_rec UNIQUE(name, good_title, date)
--);

INSERT INTO hw4_final_data
SELECT 
	o.name,
	c.age,
	g.good_title,
	o.date,
	s.payment_status,
	g.price * o.amount AS total_price,
	o.amount,
	now() AS last_modified_at 
FROM hw4_orders_tmp o
LEFT JOIN hw4_status_tmp s USING (order_uuid)
LEFT JOIN hw4_customers_tmp c USING (email)
LEFT JOIN hw4_goods_tmp g USING (good_title)
ON CONFLICT ON CONSTRAINT unq_rec
DO UPDATE SET 
	payment_status=EXCLUDED.payment_status,
	last_modified_at=now() at time zone 'utc';
	
COMMIT;

SELECT count(*) FROM hw4_final_data;
SELECT * FROM hw4_final_data;
SELECT * FROM hw4_final_data
WHERE age IS null;

UPDATE hw4_status_tmp
SET payment_status='changed'
WHERE order_uuid='b0f525e1-42a7-4726-ba05-3569515f61aa';
COMMIT;
SELECT *
FROM hw4_status_tmp
WHERE order_uuid='b0f525e1-42a7-4726-ba05-3569515f61aa';

