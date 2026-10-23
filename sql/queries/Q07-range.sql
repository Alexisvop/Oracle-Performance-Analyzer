SELECT order_id, order_date, total_amount FROM orders WHERE order_date>=:day AND order_date<:next_day ORDER BY order_id;
