"""Closed, read-only Phase 3 catalog and independent deterministic expectations."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from heapq import nlargest
from pathlib import Path
from oracle_spa.config import ConfigError

@dataclass(frozen=True)
class Query:
    name: str
    sql: str
    binds: tuple
    columns: tuple
    question: str
    hypothesis: str
    future: str
    ordered: bool = True

CATALOG = {
 'Q01': Query('Customer by email', 'SELECT customer_id, full_name, email FROM customers WHERE email = :email', ('email',), ('number','text','text'), 'How selective is an email lookup?', 'Email has no experimental index; PK alone does not index email.', 'Email index; not implemented.', False),
 'Q02': Query('Customer orders by date', 'SELECT order_id, customer_id, order_date, total_amount FROM orders WHERE customer_id = :customer_id AND order_date >= :start_date AND order_date < :end_date ORDER BY order_id', ('customer_id','start_date','end_date'), ('number','number','date','number'), 'How does a customer/date filter access orders?', 'Customer skew affects cardinality; no customer/date index exists.', 'Composite index column order; not implemented.'),
 'Q03': Query('Sales in date range', 'SELECT order_id, order_date, total_amount FROM orders WHERE order_date >= :start_date AND order_date < :end_date ORDER BY order_id', ('start_date','end_date'), ('number','date','number'), 'How many orders and booked amounts fall in the interval?', 'Broad interval can favor full scan.', 'Date access selectivity; not implemented.'),
 'Q04': Query('Orders and items', 'SELECT o.order_id, i.order_item_id, i.product_id, i.quantity, i.unit_price FROM orders o JOIN order_items i ON i.order_id=o.order_id WHERE o.customer_id=:customer_id ORDER BY o.order_id, i.order_item_id', ('customer_id',), ('number',)*5, 'Which join serves a frequent customer?', 'Optimizer chooses join; item FK is not indexed by a separate index.', 'FK index/join alternatives; not implemented.'),
 'Q05': Query('Booked sales by category', 'SELECT p.category, SUM(i.quantity), SUM(i.quantity*i.unit_price) FROM products p JOIN order_items i ON i.product_id=p.product_id JOIN orders o ON o.order_id=i.order_id WHERE o.order_date>=:start_date AND o.order_date<:end_date GROUP BY p.category ORDER BY p.category', ('start_date','end_date'), ('text','number','number'), 'How are line amounts aggregated by category?', 'Join and grouping estimates depend on category distribution.', 'Aggregation/index alternatives; not implemented.'),
 'Q06': Query('Frequent versus rare status', 'SELECT order_id, status, total_amount FROM orders WHERE status=:status ORDER BY order_id', ('status',), ('number','text','number'), 'How do status frequencies compare to estimates?', 'SIZE 1 statistics have no frequency histogram.', 'Histograms; not implemented.'),
 'Q07': Query('Calendar-day predicate', 'SELECT order_id, order_date, total_amount FROM orders WHERE TRUNC(order_date)=:day ORDER BY order_id', ('day',), ('number','date','number'), 'Is TRUNC(date) equivalent to a half-open day interval?', 'Function changes predicate form, not required result semantics.', 'Function-based/date index; not implemented.'),
 'Q08': Query('Latest twenty orders', 'SELECT order_id, order_date, total_amount FROM orders WHERE status=:status ORDER BY order_date DESC, order_id DESC FETCH FIRST 20 ROWS ONLY', ('status',), ('number','date','number'), 'How is deterministic Top-N implemented?', 'PK breaks date ties; optimizer may use sort/stopkey equivalents.', 'Ordering index; not implemented.'),
}
RANGE_SQL = 'SELECT order_id, order_date, total_amount FROM orders WHERE order_date>=:day AND order_date<:next_day ORDER BY order_id'

def get_query(query_id, variant='baseline'):
    if query_id not in CATALOG or variant not in variants(query_id):
        raise ConfigError('Unknown query or variant; use list-queries. Arbitrary SQL is not accepted.')
    return CATALOG[query_id]

def variants(query_id):
    return ('baseline','rare') if query_id=='Q06' else ('baseline','range') if query_id=='Q07' else ('baseline',)

def sql_for(query_id, variant='baseline'):
    q=get_query(query_id,variant)
    return RANGE_SQL if query_id=='Q07' and variant=='range' else q.sql

def validate_binds(query_id,variant,binds):
    q=get_query(query_id,variant)
    required=set(q.binds) | ({'next_day'} if query_id=='Q07' and variant=='range' else set())
    if set(binds)!=required: raise ConfigError('Bind names differ from catalog contract.')
    for key,value in binds.items():
        valid = (type(value) is int and value>0) if key=='customer_id' else (type(value) is datetime and value.tzinfo is None and value.microsecond==0) if key in ('start_date','end_date','day','next_day') else (type(value) is str and 0<len(value)<=160 and all(ord(c)>=32 for c in value))
        if not valid: raise ConfigError('Invalid bind type or value.')
    if 'status' in binds and binds['status'] not in ('NEW','PAID','SHIPPED','CANCELLED'): raise ConfigError('Invalid status.')
    if 'start_date' in binds and binds['start_date']>=binds['end_date']: raise ConfigError('Invalid date interval.')
    if 'day' in binds and binds['day']!=binds['day'].replace(hour=0,minute=0,second=0): raise ConfigError('Day must be midnight.')
    if 'next_day' in binds and binds['next_day']!=binds['day']+timedelta(days=1): raise ConfigError('Expected next calendar day.')

def choose_binds(connection,dataset):
    with connection.cursor() as cur:
        cur.execute('SELECT email FROM customers ORDER BY customer_id FETCH FIRST 1 ROW ONLY'); email=cur.fetchone()[0]
        cur.execute('SELECT customer_id,COUNT(*) FROM orders GROUP BY customer_id ORDER BY COUNT(*) DESC,customer_id FETCH FIRST 1 ROW ONLY'); customer,count=cur.fetchone()
        cur.execute('SELECT status,COUNT(*) FROM orders GROUP BY status ORDER BY COUNT(*) DESC,status'); statuses=cur.fetchall()
        cur.execute('SELECT TRUNC(order_date),COUNT(*) FROM orders GROUP BY TRUNC(order_date) ORDER BY COUNT(*) DESC,TRUNC(order_date) FETCH FIRST 1 ROW ONLY'); day,day_count=cur.fetchone()
    return {'email':email,'customer_id':customer,'start_date':dataset.reference-timedelta(days=90),'end_date':dataset.reference,'status':statuses[0][0],'rare_status':statuses[-1][0],'day':day,'next_day':day+timedelta(days=1)}, {'customer_order_count':count,'day_order_count':day_count,'status_counts':dict(statuses),'status_proportions':{s:n/dataset.counts['orders'] for s,n in statuses},'selection':'First synthetic email, most frequent customer, last 90 days before fixed reference, busiest day, most/least frequent observed status; ties deterministic.'}

def binds_for(query_id,variant,selected):
    q=get_query(query_id,variant)
    b={k:selected[k] for k in q.binds}
    if variant=='rare': b['status']=selected['rare_status']
    if variant=='range': b['next_day']=selected['next_day']
    validate_binds(query_id,variant,b)
    return b

def expected_rows(query_id,binds,dataset):
    if query_id=='Q01':
        yield from ((r[0],r[1],r[2]) for r in dataset.customers() if r[2]==binds['email']); return
    if query_id=='Q08':
        for r in nlargest(20,(o for o,_ in dataset.order_groups() if o[3]==binds['status']),key=lambda r:(r[2],r[0])): yield (r[0],r[2],r[4])
        return
    categories={p[0]:p[1] for p in dataset.products()} if query_id=='Q05' else {}
    totals={}
    for o,items in dataset.order_groups():
        in_range = 'start_date' in binds and binds['start_date']<=o[2]<binds['end_date']
        if query_id=='Q02' and in_range and o[1]==binds['customer_id']: yield (o[0],o[1],o[2],o[4])
        elif query_id=='Q03' and in_range: yield (o[0],o[2],o[4])
        elif query_id=='Q04' and o[1]==binds['customer_id']:
            for i in items: yield (o[0],i[0],i[2],i[3],i[4])
        elif query_id=='Q05' and in_range:
            for i in items:
                category=categories[i[2]];qty,amount=totals.get(category,(0,Decimal(0)))
                totals[category]=(qty+i[3],amount+i[3]*i[4])
        elif query_id=='Q06' and o[3]==binds['status']: yield (o[0],o[3],o[4])
        elif query_id=='Q07' and binds['day']<=o[2]<binds['day']+timedelta(days=1): yield (o[0],o[2],o[4])
    if query_id=='Q05':
        for category,(qty,amount) in sorted(totals.items()):yield (category,qty,amount)
