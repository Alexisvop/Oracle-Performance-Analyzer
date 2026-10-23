SELECT order_id, order_date, total_amount FROM orders WHERE status=:status ORDER BY order_date DESC, order_id DESC FETCH FIRST 20 ROWS ONLY;
