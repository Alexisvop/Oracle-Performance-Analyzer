SELECT order_id, customer_id, order_date, total_amount FROM orders WHERE customer_id = :customer_id AND order_date >= :start_date AND order_date < :end_date ORDER BY order_id;
