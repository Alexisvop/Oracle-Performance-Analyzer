SELECT order_id, order_date, total_amount FROM orders WHERE order_date >= :start_date AND order_date < :end_date ORDER BY order_id;
