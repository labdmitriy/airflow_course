from pathlib import Path
from functools import reduce
from typing import List, Dict, Callable, Union
from collections import OrderedDict
import json
import csv
from datetime import datetime, timedelta

from psycopg2 import sql

# from airflow import DAG
# from airflow.operators.python_operator import PythonOperator
from airflow.hooks.postgres_hook import PostgresHook
from airflow.hooks.http_hook import HttpHook


FieldType = Union[str, int, float, datetime, None]




def strip(field: str) -> str:
    return field.strip()


def lower(field: str) -> str:
    return field.lower()


def apply_func(value: FieldType, func: Callable) -> FieldType:
    return func(value)


def clean_line(line: Dict, clean_map: Dict) -> Dict:
    clean_fields = {
        field_name: reduce(apply_func, clean_funcs, line[field_name])
        for field_name, clean_funcs in clean_map.items()
    }
    return {**line, **clean_fields}


def load_csv_data(
    file_path: Path,
    field_names: List,
    skip_header: bool = True
) -> List:
    with open(file_path) as f:
        if skip_header:
            next(f)

        reader = csv.DictReader(f, fieldnames=field_names)
        data = list(reader)

    return data


def load_json_data(file_path: Path, id_name: str) -> List:
    with open(file_path) as f:
        json_data = json.loads(f.read())

    data = []

    for row_id, row_data in json_data.items():
        row = {}
        row[id_name] = row_id

        for key, value in row_data.items():
            row[key] = value

        data.append(row)

    return data


def load_data(
    file_path: Path,
    file_type: str,
    field_names: List
) -> List:
    if file_type == 'csv':
        data = load_csv_data(file_path, field_names)
    elif file_type == 'json':
        id_name = field_names[0]
        data = load_json_data(file_path, id_name)

    return data


def calculate_payment_status(line: Dict) -> str:
    print(line)
    return 'success' if line['success'] is True else 'failure'


def calculate_age(line: Dict) -> int:
    DAYS_IN_YEAR = 365.25
    DATE_TIME_FORMAT = '%Y-%m-%d'

    now = datetime.now()
    birth_date = datetime.strptime(line['birth_date'], DATE_TIME_FORMAT)
    age = (now - birth_date) // timedelta(days=DAYS_IN_YEAR)

    return age


def gen_fields(line: Dict, gen_map: OrderedDict) -> Dict:
    new_fields = {key: func(line) for key, func in gen_map.items()}
    return {**line, **new_fields}


def clean_data(
    file_path: Path,
    file_type: str,
    field_names: List,
    clean_map: OrderedDict,
    gen_map: OrderedDict
) -> Path:
    clean_file_path = file_path.parent/f'{file_path.stem}_clean.csv'
    selected_field_names = list(clean_map.keys()) + list(gen_map.keys())

    data = load_data(file_path, file_type, field_names)

    with open(clean_file_path, 'w') as f_clean:
        writer = csv.DictWriter(f_clean,
                                fieldnames=selected_field_names,
                                extrasaction='ignore')
        writer.writeheader()

        for line in data:
            line = clean_line(line, clean_map)
            line = gen_fields(line, gen_map)
            writer.writerow(line)

    return clean_file_path


class PostgresDB:
    def __init__(self, conn_id: str) -> None:
        self.hook = PostgresHook(postgres_conn_id=conn_id)

    def save_table_to_file(
        self,
        table_name: str,
        dir_path: Path
    ) -> Path:
        file_path = dir_path/f'{table_name}.csv'

        table_id = sql.Identifier(table_name)
        sql_text = 'COPY (SELECT * FROM {}) TO STDOUT WITH CSV HEADER'
        sql_query = sql.SQL(sql_text).format(table_id)

        self.hook.copy_expert(sql_query, file_path)

        return file_path

    def load_table_from_file(
        self, 
        table_name: str, 
        file_path: Path
    ) -> Path:
        table_id = sql.Identifier(table_name)
        sql_text = "COPY {} FROM STDIN DELIMITER ',' CSV HEADER"
        sql_query = sql.SQL(sql_text).format(table_id)

        self.hook.copy_expert(sql_query, file_path)

        return file_path

    def create_schema(self, schema_name: str) -> None:
        schema_id = sql.Identifier(schema_name)
        sql_query = sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(schema_id)

        with self.hook.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query)

    def create_table(self, table_info: Dict) -> None:
        table_name = table_info['table_name']
        table_cols = table_info['table_cols']
        constraint_name = table_info.get('constraint_name')
        constraint_cols = table_info.get('constraint_cols')

        table_id = sql.Identifier(table_name)

        with self.hook.get_conn() as conn:
            with conn.cursor() as cur:
                cols = [f'{sql.Identifier(col_name).as_string(cur)} {col_type}'
                        for (col_name, col_type) in table_cols.items()]
                cols_list = sql.SQL(','.join(cols))

                if constraint_name is None or constraint_cols is None:
                    sql_text = 'CREATE TABLE IF NOT EXISTS {} ({})'
                    sql_query = sql.SQL(sql_text).format(table_id, cols_list)
                else:
                    constraint_id = sql.Identifier(constraint_name)
                    constraints = [sql.Identifier(field) 
                                   for field in constraint_cols]
                    constraints_list = sql.SQL(',').join(constraints)

                    sql_text = 'CREATE TABLE IF NOT EXISTS {} ({}, CONSTRAINT {} UNIQUE ({}))'
                    sql_query = sql.SQL(sql_text).format(
                        table_id,
                        cols_list,
                        constraint_id,
                        constraints_list
                    )

                cur.execute(sql_query)

    def drop_table(self, table_name: str) -> None:
        table_id = sql.Identifier(table_name)
        sql_query = sql.SQL('DROP TABLE IF EXISTS {}').format(table_id)

        with self.hook.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query)

    def execute(self, sql_query: str) -> None:
        with self.hook.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query)

            conn.commit()


def download_file(
    conn_id: str,
    endpoint: str,
    dir_path: Path
) -> Path:
    file_name = endpoint.split('/')[-1]
    file_path = dir_path/file_name

    hook = HttpHook(http_conn_id=conn_id, method='GET')
    resp = hook.run(str(endpoint))

    with open(file_path, 'w') as f:
        f.write(resp.content.decode('utf-8'))

    return file_path


def download_table_data(
    conn_id: str,
    table_name: str,
    dir_path: Path
) -> Path:
    pg_db = PostgresDB(conn_id)
    file_path = pg_db.save_table_to_file(table_name, dir_path)

    return file_path


def create_dataset(
    conn_id: str,
    target_sql: str,
    target_table: Dict,
    temp_tables: List
) -> None:
    pg_db = PostgresDB(conn_id)

    for table_info in temp_tables:
        table_name = table_info['table_name']
        table_file_path = table_info['table_file_path']

        pg_db.drop_table(table_name)
        pg_db.create_table(table_info)
        pg_db.load_table_from_file(table_name, table_file_path)

    pg_db.create_table(target_table)
    pg_db.execute(target_sql)


DATA_PATH = Path('/home/jupyter/data')

# ORDERS_CONN_ID = 'hw4_orders_data'
# ORDERS_ENDPOINT = Path('orders.csv')

# orders_field_names: List = ['order_id', 'order_uuid', 'good_title',
#                             'date', 'amount', 'name', 'email']
# orders_clean_map: OrderedDict = OrderedDict({
#     'order_uuid': [strip, lower],
#     'good_title': [strip],
#     'date': [strip],
#     'amount': [strip],
#     'name': [strip],
#     'email': [strip, lower]
# })
# orders_gen_map: OrderedDict = OrderedDict()

# file_path = download_file(ORDERS_CONN_ID, ORDERS_ENDPOINT, DATA_PATH)
# clean_file_path = clean_data(
#     file_path=file_path,
#     file_type='csv',
#     field_names=orders_field_names,
#     clean_map=orders_clean_map,
#     gen_map=orders_gen_map)
# print(clean_file_path)


# STATUS_CONN_ID = 'hw4_status_data'
# STATUS_ENDPOINT = Path('/b/5ed7391379382f568bd22822')

# status_field_names: List = ['order_uuid']
# status_clean_map: OrderedDict = OrderedDict({
#     'order_uuid': [strip, lower]
# })
# status_gen_map: OrderedDict = OrderedDict({
#     'payment_status': calculate_payment_status
# })

# file_path = download_file(STATUS_CONN_ID, STATUS_ENDPOINT, DATA_PATH)
# clean_file_path = clean_data(
#     file_path=file_path,
#     file_type='json',
#     field_names=status_field_names,
#     clean_map=status_clean_map,
#     gen_map=status_gen_map)
# print(clean_file_path)

SHARED_DB_CONN_ID = 'hw2_shared_db'
PRIVATE_DB_CONN_ID = 'hw2_private_db'
CUSTOMERS_TABLE = 'customers'
GOODS_TABLE = 'goods'

# shared_db = PostgresDB(SHARED_DB_CONN_ID)

# customers_field_names: List = ['id', 'name', 'birth_date', 'gender', 'email']
# customers_clean_map: OrderedDict = OrderedDict({
#     'email': [strip, lower]
# })
# customers_gen_map: OrderedDict = OrderedDict({
#     'age': calculate_age
# })

# file_path = shared_db.load_table_data(CUSTOMERS_TABLE, DATA_PATH)
# clean_file_path = clean_data(
#     file_path=file_path,
#     file_type='csv',
#     field_names=customers_field_names,
#     clean_map=customers_clean_map,
#     gen_map=customers_gen_map
# )
# print(clean_file_path)

# goods_field_names: List = ['id', 'good_title', 'price']
# goods_clean_map: OrderedDict = OrderedDict({
#     'good_title': [strip],
#     'price': [strip]
# })
# goods_gen_map: OrderedDict = OrderedDict()

# file_path = shared_db.load_table_data(GOODS_TABLE, DATA_PATH)
# clean_file_path = clean_data(
#     file_path=file_path,
#     file_type='csv',
#     field_names=goods_field_names,
#     clean_map=goods_clean_map,
#     gen_map=goods_gen_map
# )
# print(clean_file_path)

private_db = PostgresDB(PRIVATE_DB_CONN_ID)
# TEST_TABLE = {
#     'table_name': 'test_table',
#     'table_cols': {
#         'order_uuid': 'varchar(50)',
#         'good_title': 'varchar(100)',
#         'date': 'timestamp',
#         'amount': 'integer',
#         'name': 'varchar(50)',
#         'email': 'varchar(50)'
#     },
#     'constraint_name': 'test_unq_col',
#     'constraint_cols': ['name', 'good_title', 'date']
# }

# private_db.drop_table('test_table')
# private_db.create_table(TEST_TABLE)
# private_db.load_table_from_file('test_table', DATA_PATH/'orders_clean.csv')
# private_db.save_table_to_file('test_table', DATA_PATH)

TEMP_TABLES = [
    {
        'table_name': 'hw4_orders_tmp',
        'table_file_path': DATA_PATH/'orders_clean.csv',
        'table_cols': {
            'order_uuid': 'varchar(50)',
            'good_title': 'varchar(100)',
            'date': 'timestamp',
            'amount': 'integer',
            'name': 'varchar(50)',
            'email': 'varchar(50)'
        }
    },
    {
        'table_name': 'hw4_status_tmp',
        'table_file_path': DATA_PATH/'5ed7391379382f568bd22822_clean.csv',
        'table_cols': {
            'order_uuid': 'varchar(50)',
            'payment_status': 'varchar(10)'
        }
    },
    {
        'table_name': 'hw4_customers_tmp',
        'table_file_path': DATA_PATH/'customers_clean.csv',
        'table_cols': {
            'email': 'varchar(50)',
            'age': 'integer'
        }
    },
    {
        'table_name': 'hw4_goods_tmp',
        'table_file_path': DATA_PATH/'goods_clean.csv',
        'table_cols': {
            'good_title': 'varchar(100)',
            'price': 'numeric'
        }
    }
]

TARGET_TABLE = {
    'table_name': 'hw4_final_data',
    'table_cols': {
        'name': 'varchar(50)',
        'age': 'integer',
        'good_title': 'varchar(100)',
        'date': 'timestamp',
        'payment_status': 'varchar(10)',
        'total_price': 'numeric',
        'amount': 'integer',
        'last_modified_at': 'timestamp',
    },
    'constraint_name': 'hw4_unq_rec',
    'constraint_cols': ['name', 'good_title', 'date']
}

TARGET_SQL = '''
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
ON CONFLICT ON CONSTRAINT hw4_unq_rec
DO UPDATE SET
    payment_status=EXCLUDED.payment_status,
    last_modified_at=now() at time zone 'utc';
'''

# create_dataset(
#     PRIVATE_DB_CONN_ID,
#     TARGET_SQL,
#     TARGET_TABLE,
#     TEMP_TABLES
# )


def download_data(
    conn_id: str,
    object_name: str,
    object_type: str,
    dir_path: Path
) -> Path:
    if object_type == 'file':
        file_path = download_file(conn_id, object_name, dir_path)
    elif object_type == 'table':
        file_path = download_table_data(conn_id, object_name, dir_path)

    return file_path


def process_data(
    conn_id: str,
    object_name: str,
    object_type: str,
    dir_path: Path,
    file_type: str,
    field_names: List,
    clean_map: OrderedDict,
    gen_map: OrderedDict
) -> Path:
    file_path = download_data(
        conn_id,
        object_name,
        object_type,
        dir_path
    )
    clean_file_path = clean_data(
        file_path,
        file_type,
        field_names,
        clean_map,
        gen_map
    )
    return clean_file_path
