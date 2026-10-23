SELECT order_id, status, total_amount FROM orders WHERE status=:status ORDER BY order_id;
