from datetime import datetime,timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from oracle_spa.queries import CATALOG,get_query,variants,sql_for,validate_binds,expected_rows
from oracle_spa.execution import compare_results,json_value
from oracle_spa.plans import parse_display,safe_code,verify_cursor_identity,actual_cursor_plan
from oracle_spa.data_generator import Dataset
from oracle_spa.config import ConfigError
from oracle_spa.db import DiagnosticError

def test_catalog_files_and_allowlist():
    assert set(CATALOG)=={f'Q{i:02d}' for i in range(1,9)}
    for key,q in CATALOG.items():
        assert q.question and q.hypothesis and q.future and q.columns
        for variant in variants(key):
            sql=sql_for(key,variant)
            assert sql.startswith('SELECT ') and ';' not in sql
            assert (Path('sql/queries')/(key+'-'+variant+'.sql')).read_text()==sql+';\n'
    for key,v in [('DROP TABLE CUSTOMERS','baseline'),('Q01','rare'),('Q07','anything')]:
        with pytest.raises(ConfigError):get_query(key,v)

def test_bind_types_exact_names_and_dates():
    day=datetime(2026,10,1)
    validate_binds('Q07','range',{'day':day,'next_day':day+timedelta(days=1)})
    for b in ({'email':'x','extra':1},{'email':3},{'email':'x\n'}):
        with pytest.raises(ConfigError):validate_binds('Q01','baseline',b)
    with pytest.raises(ConfigError):validate_binds('Q07','range',{'day':day,'next_day':day})
    with pytest.raises(ConfigError):validate_binds('Q02','baseline',{'customer_id':True,'start_date':day,'end_date':day+timedelta(days=1)})

def test_exact_multisets_order_duplicates_and_hash():
    a=[(1,),(1,),(2,)];b=[(2,),(1,),(1,)]
    assert compare_results(iter(a),iter(b),False)['rows']==3
    with pytest.raises(DiagnosticError):compare_results(iter(a),iter(b),True)
    with pytest.raises(DiagnosticError):compare_results(iter(a),iter([(1,),(2,),(2,)]),False)
    assert compare_results(iter(a),iter(a),False)['result_sha256']!=compare_results(iter([(1,),(2,),(2,)]),iter([(1,),(2,),(2,)]),False)['result_sha256']
    assert compare_results([(Decimal('1.00'),)],[(1,)],True)['rows']==1

def test_date_serialization_and_expected_top_n():
    assert json_value(datetime(2026,10,1))=='2026-10-01T00:00:00'
    d=Dataset('tiny');orders=[o for o,_ in d.order_groups() if o[3]=='PAID']
    expected=sorted(orders,key=lambda r:(r[2],r[0]),reverse=True)[:20]
    assert list(expected_rows('Q08',{'status':'PAID'},d))==[(o[0],o[2],o[4]) for o in expected]

def test_plan_parsing_redaction_and_association():
    assert parse_display(['Plan hash value: 123'])['plan_hash']==123
    assert parse_display(['no plan'])['plan_hash'] is None
    assert safe_code(RuntimeError('secret'))=='NOT AVAILABLE'
    assert verify_cursor_identity([('123456789abcd',0,'SELECT 1')],'SELECT 1')==('123456789abcd',0)
    for rows in ([],[('123456789abcd',0,'OTHER')],[('123456789abcd',0,'SELECT 1')]*2):
        with pytest.raises(DiagnosticError):verify_cursor_identity(rows,'SELECT 1')

def test_cursor_unavailable_is_not_actual(monkeypatch):
    monkeypatch.setattr('oracle_spa.plans.assert_identity',lambda c:None)
    monkeypatch.setattr('oracle_spa.plans.cursor_availability',lambda c:{'V$SQL':'ORA-00942'})
    r=actual_cursor_plan(MagicMock(),'Q01')
    assert r['type']=='NOT AVAILABLE' and r['status']=='NOT VERIFIED' and 'operators' not in r

def test_list_queries_needs_no_credentials(capsys):
    from oracle_spa.cli import main
    assert main(['list-queries'])==0
    assert 'Q08' in capsys.readouterr().out
    with pytest.raises(SystemExit):main(['run','--query','Q01','--repeats','not-an-integer'])


def test_statement_id_oracle_limit():
    from oracle_spa.plans import new_statement_id
    a,b=new_statement_id(),new_statement_id()
    assert len(a)==30 and a!=b and a.startswith('OSPA_')

def test_grouped_money_and_day_boundary_expectations():
    d=Dataset('tiny');start=datetime(2025,1,1);end=d.reference
    groups=list(expected_rows('Q05',{'start_date':start,'end_date':end},d))
    orders=list(d.order_groups())
    assert sum(r[2] for r in groups)==sum(o[4] for o,items in orders if start<=o[2]<end)
    day=orders[0][0][2].replace(hour=0,minute=0,second=0)
    rows=list(expected_rows('Q07',{'day':day},d))
    assert rows and all(day<=r[1]<day+timedelta(days=1) for r in rows)

def test_result_description_guard(monkeypatch):
    monkeypatch.setattr('oracle_spa.execution.inspect_schema',lambda c, allowed_indexes=():'ready')
    from oracle_spa.execution import run_query
    c=MagicMock();cur=c.cursor.return_value.__enter__.return_value
    cur.description=[]
    with pytest.raises(DiagnosticError,match='column count'):
        run_query(c,'Q01',context=(Dataset('small'),{'selected':{'email':'customer00000001@example.invalid'}}))
