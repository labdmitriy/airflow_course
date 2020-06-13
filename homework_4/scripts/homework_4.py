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


def download_file(conn_id: str, endpoint: Path, dir_path: Path) -> Path:
    file_path = dir_path/endpoint.name

    hook = HttpHook(http_conn_id=conn_id, method='GET')
    resp = hook.run(str(endpoint))

    with open(file_path, 'w') as f:
        f.write(resp.content.decode('utf-8'))

    return file_path


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


def get_table_data(
    conn_id: str,
    table_name: str,
    dir_path: Path
) -> Path:
    file_path = dir_path/f'{table_name}.csv'

    pg_hook = PostgresHook(postgres_conn_id=conn_id)

    table_id = sql.Identifier(table_name)
    sql_text = 'COPY (SELECT * FROM {}) TO STDOUT WITH CSV HEADER'
    sql_query = sql.SQL(sql_text).format(table_id)

    pg_hook.copy_expert(sql_query, file_path)

    return file_path


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

# customers_field_names: List = ['id', 'name', 'birth_date', 'gender', 'email']
# customers_clean_map: OrderedDict = OrderedDict({
#     'email': [strip, lower]
# })
# customers_gen_map: OrderedDict = OrderedDict({
#     'age': calculate_age
# })

# file_path = get_table_data('hw2_shared_db', CUSTOMERS_TABLE, DATA_PATH)
# clean_file_path = clean_data(
#     file_path=file_path,
#     file_type='csv',
#     field_names=customers_field_names,
#     clean_map=customers_clean_map,
#     gen_map=customers_gen_map
# )
# print(clean_file_path)

goods_field_names: List = ['id', 'good_title', 'price']
goods_clean_map: OrderedDict = OrderedDict({
    'good_title': [strip],
    'price': [strip]
})
goods_gen_map: OrderedDict = OrderedDict()

file_path = get_table_data('hw2_shared_db', GOODS_TABLE, DATA_PATH)
clean_file_path = clean_data(
    file_path=file_path,
    file_type='csv',
    field_names=goods_field_names,
    clean_map=goods_clean_map,
    gen_map=goods_gen_map
)
print(clean_file_path)
