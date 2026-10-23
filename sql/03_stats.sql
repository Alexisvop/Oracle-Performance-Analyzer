BEGIN
    DBMS_STATS.GATHER_TABLE_STATS(
        ownname => 'ORACLE_SPA', tabname => :table_name,
        estimate_percent => NULL, method_opt => 'FOR ALL COLUMNS SIZE 1',
        degree => 1, cascade => TRUE, no_invalidate => FALSE
    );
END;
