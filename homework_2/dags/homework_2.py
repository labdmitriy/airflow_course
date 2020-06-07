from pathlib import Path
from datetime import datetime, timedelta
import csv
import json

import requests
import psycopg2
from psycopg2 import sql

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.hooks.postgres_hook import PostgresHook

def download_file(url, dir_path):
    file_name = url.split('/')[-1]
    file_path = dir_path/file_name

    with requests.get(url) as r:
        r.raise_for_status()
        
        with open(file_path, 'w') as f:
            f.write(r.content.decode('utf-8'))
        
    return file_path

def clean_field(field):
    return field.strip()

def clean_orders_data(file_path):
    clean_file_path = file_path.parent/f'{file_path.stem}_clean.csv'
    field_names = ('order_id', 'order_uuid', 'good_title', 
                   'date', 'amount', 'name', 'email')
    selected_field_names = ('order_uuid', 'good_title', 'date', 
                            'amount', 'name', 'email')

    with open(file_path) as f:
        next(f)
        reader = csv.DictReader(f, fieldnames=field_names)

        with open(clean_file_path, 'w') as f_clean:
            writer = csv.DictWriter(f_clean, 
                                    fieldnames=selected_field_names, 
                                    extrasaction='ignore')
            writer.writeheader()
            
            for line in reader:
                line = {key: clean_field(line[key]) for key in line}
                writer.writerow(line)
                
    return clean_file_path

def clean_status_data(file_path):
    with open(file_path) as f:
        status_data = json.loads(f.read())

    clean_file_path = file_path.parent/f'{file_path.stem}_clean.csv'
    selected_field_names = ('order_uuid', 'payment_status')

    with open(clean_file_path, 'w') as f_clean:
        writer = csv.DictWriter(f_clean, fieldnames=selected_field_names)

        writer.writeheader() 

        for order_uuid, status in status_data.items():
            payment_status = 'success' if status['success'] is True else 'failure'

            status_row = {
                'order_uuid': clean_field(order_uuid),
                'payment_status': payment_status
            }

            writer.writerow(status_row)
            
    return clean_file_path

def get_table_data(conn_id, table_name, dir_path):
    file_path = dir_path/f'{table_name}.csv'

    pg_hook = PostgresHook(postgres_conn_id=conn_id)
    
    table_id = sql.Identifier(table_name)
    sql_query = sql.SQL("COPY (SELECT * FROM {}) TO STDOUT WITH CSV HEADER").format(table_id)

    pg_hook.copy_expert(sql_query, file_path)
    
    return file_path

def calculate_age(birth_date, datetime_format):
    DAYS_IN_YEAR = 365.25
    age = (datetime.now() - datetime.strptime(birth_date, datetime_format)) // timedelta(days=DAYS_IN_YEAR)
    return age

def clean_customers_data(file_path):
    clean_file_path = file_path.parent/f'{file_path.stem}_clean.csv'
    field_names = ('id', 'name', 'birth_date', 'gender', 'email')
    selected_field_names = ('email', 'age')
    datetime_format = '%Y-%m-%d'

    with open(file_path) as f:
        next(f)
        reader = csv.DictReader(f, fieldnames=field_names)

        with open(clean_file_path, 'w') as f_clean:
            writer = csv.DictWriter(f_clean, 
                                    fieldnames=selected_field_names, 
                                    extrasaction='ignore')
            writer.writeheader()
            
            for line in reader:
                line = {key: clean_field(line[key]) for key in line}
                line['age'] = calculate_age(line['birth_date'], datetime_format)
                writer.writerow(line)
                
    return clean_file_path

def clean_goods_data(file_path):
    clean_file_path = file_path.parent/f'{file_path.stem}_clean.csv'
    field_names = ('id', 'good_title', 'price')
    selected_field_names = ('good_title', 'price')

    with open(file_path) as f:
        next(f)
        reader = csv.DictReader(f, fieldnames=field_names)

        with open(clean_file_path, 'w') as f_clean:
            writer = csv.DictWriter(f_clean, 
                                    fieldnames=selected_field_names, 
                                    extrasaction='ignore')
            writer.writeheader()
            
            for line in reader:
                line = {key: clean_field(line[key]) for key in line}
                writer.writerow(line)
                
    return clean_file_path

def process_orders_data(url, dir_path):
    file_path = download_file(url, dir_path)
    clean_file_path = clean_orders_data(file_path)
    return clean_file_path

def process_status_data(url, dir_path):
    file_path = download_file(url, dir_path)
    clean_file_path = clean_status_data(file_path)
    return clean_file_path

def process_customers_data(conn_id, table_name, dir_path):
    file_path = get_table_data(conn_id, table_name, dir_path)
    clean_file_path = clean_customers_data(file_path)
    return clean_file_path

def process_goods_data(conn_id, table_name, dir_path):
    file_path = get_table_data(conn_id, table_name, dir_path)
    clean_file_path = clean_goods_data(file_path)
    return clean_file_path

def drop_table(cur, table_name):
    print(f'drop table {table_name}')

    table_id = sql.Identifier(table_name)
    sql_query = sql.SQL('DROP TABLE IF EXISTS {}').format(table_id)
    cur.execute(sql_query)

def create_table(cur, table_name, table_cols):
    print(f'create table {table_name}')
    
    table_id = sql.Identifier(table_name)
    fields = ', '.join([f'{sql.Identifier(col_name).as_string(cur)} {col_type}' 
                        for (col_name, col_type) in table_cols.items()])

    columns_list = sql.SQL(fields)
    
    sql_query = sql.SQL('CREATE TABLE IF NOT EXISTS {} ({})').format(table_id, columns_list)
    cur.execute(sql_query)

def save_table_data(cur, table_name, file_path):
    print(f'save table {table_name}')

    table_id = sql.Identifier(table_name)
    sql_query = sql.SQL("COPY {} FROM STDIN DELIMITER ',' CSV HEADER").format(table_id)

    with open(file_path, 'r') as f:
        cur.copy_expert(sql_query, f)

    return file_path

def create_dataset(conn_id, target_table, temp_tables):
    # create schema if not exists
    pg_hook = PostgresHook(postgres_conn_id=conn_id)

    with pg_hook.get_conn() as conn:
        with conn.cursor() as cur:
            for table_name, table_info in temp_tables.items():
                drop_table(cur, table_name)
                create_table(cur, table_name, table_info['columns'])
                save_table_data(cur, table_name, table_info['file_path'])

    # drop & create tmp tables
    # insert rows to tmp tables
    # create results table if not exists
    # insert data to results table from tmp tables

default_args = {

}

dag = DAG(
    'homework_2',
    default_args=default_args,
    start_date=datetime(2020, 6, 6),
    catchup=False
)

DATA_PATH = Path('/home/jupyter/data')
CSV_URL = 'https://airflow101.python-jitsu.club/orders.csv'
JSON_URL = 'https://api.jsonbin.io/b/5ed7391379382f568bd22822'
SHARED_DB_CONN_ID = 'hw2_shared_db'
PRIVATE_DB_CONN_ID = 'hw2_private_db'
CUSTOMERS_TABLE = 'customers'
GOODS_TABLE = 'goods'
DATASET_TABLE = 'final_data'
TEMP_TABLES = {
    'orders_tmp': {
        'file_path': DATA_PATH/'orders_clean.csv',
        'columns': {
            'order_uuid': 'char(50)',
            'good_title': 'char(100)',
            'date': 'timestamp',
            'amount': 'integer',
            'name': 'char(50)',
            'email': 'char(50)'
        }
    },
    'status_tmp': {
        'file_path': DATA_PATH/'5ed7391379382f568bd22822_clean.csv',
        'columns': {
            'order_uuid': 'char(50)',
            'payment_status': 'char(10)'
        }
    },
    'customers_tmp': {
        'file_path': DATA_PATH/'customers_clean.csv',
        'columns': {
            'email': 'char(50)',
            'age': 'integer'
        }
    },
    'goods_tmp': {
        'file_path': DATA_PATH/'goods_clean.csv',
        'columns': {
            'good_title': 'char(100)',
            'price': 'numeric'
        }
    }
}


TARGET_TABLE = {
    'final_data': {
        'name': 'char(50)',
        'age': 'integer',
        'good_title': 'char(100)',
        'date': 'timestamp',
        'payment_status': 'char(10)',
        'total_price': 'numeric',
        'amount': 'integer',
        'last_modified_at': 'tim'
    }
}

process_orders_task = PythonOperator(
    task_id='process_orders_data',
    dag=dag,
    python_callable=process_orders_data,
    op_args=[CSV_URL, DATA_PATH]
)

process_status_task = PythonOperator(
    task_id='process_status_data',
    dag=dag,
    python_callable=process_status_data,
    op_args=[JSON_URL, DATA_PATH]
)

process_customers_task = PythonOperator(
    task_id='process_customers_data',
    dag=dag,
    python_callable=process_customers_data,
    op_args=[SHARED_DB_CONN_ID, CUSTOMERS_TABLE, DATA_PATH]
)

process_goods_task = PythonOperator(
    task_id='process_goods_data',
    dag=dag,
    python_callable=process_goods_data,
    op_args=[SHARED_DB_CONN_ID, GOODS_TABLE, DATA_PATH]
)

create_dataset_task = PythonOperator(
    task_id='create_dataset',
    dag=dag,
    python_callable=create_dataset,
    op_args=[PRIVATE_DB_CONN_ID, TARGET_TABLE, TEMP_TABLES]
)

process_orders_task >> process_status_task >> process_customers_task >> process_goods_task >> create_dataset_task