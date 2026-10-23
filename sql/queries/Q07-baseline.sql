SELECT order_id, order_date, total_amount FROM orders WHERE TRUNC(order_date)=:day ORDER BY order_id;
