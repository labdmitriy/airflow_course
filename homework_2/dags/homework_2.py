from pathlib import Path
from datetime import datetime, timedelta
import csv
import json

import requests
from psycopg2 import sql

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.hooks.postgres_hook import PostgresHook
from airflow.hooks.http_hook import HttpHook


def download_file(conn_id, endpoint, dir_path):
    file_path = dir_path/endpoint.split('/')[-1]
    
    hook = HttpHook(http_conn_id=conn_id, method='GET')
    resp = hook.run(f'/{endpoint}')

    with open(file_path, 'w') as f:
        f.write(resp.content.decode('utf-8'))

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

def process_orders_data(conn_id, file_name, dir_path):
    print('process orders data')
    file_path = download_file(conn_id, file_name, dir_path)
    clean_file_path = clean_orders_data(file_path)
    return clean_file_path

def process_status_data(conn_id, file_name, dir_path):
    print('process status data')
    file_path = download_file(conn_id, file_name, dir_path)
    clean_file_path = clean_status_data(file_path)
    return clean_file_path

def process_customers_data(conn_id, table_name, dir_path):
    print('process customers data')
    file_path = get_table_data(conn_id, table_name, dir_path)
    clean_file_path = clean_customers_data(file_path)
    return clean_file_path

def process_goods_data(conn_id, table_name, dir_path):
    print('process goods data')
    file_path = get_table_data(conn_id, table_name, dir_path)
    clean_file_path = clean_goods_data(file_path)
    return clean_file_path

def create_schema(cur, schema_name):
    print(f'create schema {schema_name}')

    schema_id = sql.Identifier(schema_name)
    sql_query = sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(schema_id)
    cur.execute(sql_query)

def drop_table(cur, table_name):
    print(f'drop table {table_name}')

    table_id = sql.Identifier(table_name)
    sql_query = sql.SQL('DROP TABLE IF EXISTS {}').format(table_id)
    cur.execute(sql_query)

def create_table(cur, table_name, table_cols, constraint_cols=None):
    print(f'create table {table_name}')
    
    table_id = sql.Identifier(table_name)
    columns = ', '.join([f'{sql.Identifier(col_name).as_string(cur)} {col_type}' 
                         for (col_name, col_type) in table_cols.items()])
    columns_list = sql.SQL(columns)
    
    if constraint_cols is None:
        sql_text = 'CREATE TABLE IF NOT EXISTS {} ({})'
        sql_query = sql.SQL(sql_text).format(table_id, columns_list)
    else:
        constraints = [sql.Identifier(field) for field in constraint_cols]
        constraints_list =  sql.SQL(',').join(constraints)
                             
        sql_text = 'CREATE TABLE IF NOT EXISTS {} ({}, CONSTRAINT unq_rec UNIQUE ({}))'
        sql_query = sql.SQL(sql_text).format(table_id, columns_list, constraints_list)

    cur.execute(sql_query)

def save_table_data(cur, table_name, file_path):
    print(f'save table {table_name}')

    table_id = sql.Identifier(table_name)
    sql_query = sql.SQL("COPY {} FROM STDIN DELIMITER ',' CSV HEADER").format(table_id)

    with open(file_path, 'r') as f:
        cur.copy_expert(sql_query, f)

    return file_path

def generate_final_data(cur, target_statement):
    print('generate final data')
    cur.execute(target_statement)

def create_dataset(conn_id, target_table, target_statement, temp_tables):
    print('create dataset')

    pg_hook = PostgresHook(postgres_conn_id=conn_id)

    with pg_hook.get_conn() as conn:
        with conn.cursor() as cur:
            create_schema(cur, 'public')

            for table_name, table_info in temp_tables.items():
                drop_table(cur, table_name)
                create_table(cur, table_name, table_info['columns'])
                save_table_data(cur, table_name, table_info['file_path'])

            create_table(cur, target_table['name'], target_table['columns'], 
                         target_table['constraints'])
            
            generate_final_data(cur, target_statement)
            conn.commit()

DATA_PATH = Path('/home/jupyter/data')

CSV_CONN_ID = 'hw2_csv'
CSV_FILE_NAME = 'orders.csv'

API_CONN_ID = 'hw2_api'
API_ENDPOINT = 'b/5ed7391379382f568bd22822'

SHARED_DB_CONN_ID = 'hw2_shared_db'
PRIVATE_DB_CONN_ID = 'hw2_private_db'
CUSTOMERS_TABLE = 'customers'
GOODS_TABLE = 'goods'

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
    'name': 'final_data',
    'columns': {
        'name': 'char(50)',
        'age': 'integer',
        'good_title': 'char(100)',
        'date': 'timestamp',
        'payment_status': 'char(10)',
        'total_price': 'numeric',
        'amount': 'integer',
        'last_modified_at': 'timestamp',
    },
    'constraints': ['name', 'good_title', 'date']
}

TARGET_STATEMENT = '''
INSERT INTO final_data
SELECT 
	o.name,
	c.age,
	g.good_title,
	o.date,
	s.payment_status,
	g.price * o.amount AS total_price,
	o.amount,
	now() AS last_modified_at 
FROM orders_tmp o
LEFT JOIN status_tmp s USING (order_uuid)
LEFT JOIN customers_tmp c USING (email)
LEFT JOIN goods_tmp g USING (good_title)
ON CONFLICT ON CONSTRAINT unq_rec
DO UPDATE SET 
	payment_status=EXCLUDED.payment_status,
	last_modified_at=now() at time zone 'utc';
'''

default_args = {

}

dag = DAG(
    'homework_2',
    default_args=default_args,
    start_date=datetime(2020, 6, 6),
    catchup=False
)

process_orders_task = PythonOperator(
    task_id='process_orders_data',
    dag=dag,
    python_callable=process_orders_data,
    op_args=[CSV_CONN_ID, CSV_FILE_NAME, DATA_PATH]
)

process_status_task = PythonOperator(
    task_id='process_status_data',
    dag=dag,
    python_callable=process_status_data,
    op_args=[API_CONN_ID, API_ENDPOINT, DATA_PATH]
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
    op_args=[PRIVATE_DB_CONN_ID, TARGET_TABLE, TARGET_STATEMENT, TEMP_TABLES]
)

process_orders_task >> process_status_task >> process_customers_task >> process_goods_task >> create_dataset_task