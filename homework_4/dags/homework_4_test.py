import sys
from collections import OrderedDict
from pathlib import Path
from typing import List

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago


sys.path.insert(1, '/home/jupyter/lib/merch')
from merch.calculators import calculate_age, calculate_payment_status
from merch.cleaners import lower, strip
from merch.processors import process_data, create_dataset
from merch.operators import TemplatedPythonOperator


DATA_PATH = Path('/home/jupyter/data')

ORDERS_CONN_ID = 'hw4_orders_data'
ORDERS_ENDPOINT = 'orders.csv'
STATUS_CONN_ID = 'hw4_status_data'
STATUS_ENDPOINT = '/b/5ed7391379382f568bd22822'
SHARED_DB_CONN_ID = 'hw2_shared_db'
PRIVATE_DB_CONN_ID = 'hw2_private_db'
CUSTOMERS_TABLE = 'customers'
GOODS_TABLE = 'goods'

orders_field_names: List = ['order_id', 'order_uuid', 'good_title',
                            'date', 'amount', 'name', 'email']
orders_clean_map: OrderedDict = OrderedDict({
    'order_uuid': [strip, lower],
    'good_title': [strip],
    'date': [strip],
    'amount': [strip],
    'name': [strip],
    'email': [strip, lower]
})
orders_gen_map: OrderedDict = OrderedDict()

status_field_names: List = ['order_uuid']
status_clean_map: OrderedDict = OrderedDict({
    'order_uuid': [strip, lower]
})
status_gen_map: OrderedDict = OrderedDict({
    'payment_status': calculate_payment_status
})

customers_field_names: List = ['id', 'name', 'birth_date', 'gender', 'email']
customers_clean_map: OrderedDict = OrderedDict({
    'email': [strip, lower]
})
customers_gen_map: OrderedDict = OrderedDict({
    'age': calculate_age
})

goods_field_names: List = ['id', 'good_title', 'price']
goods_clean_map: OrderedDict = OrderedDict({
    'good_title': [strip],
    'price': [strip]
})
goods_gen_map: OrderedDict = OrderedDict()


default_args = {
    'start_date': days_ago(1)
}

dag = DAG(
    dag_id='homework_4_test',
    schedule_interval='@once',
    default_args=default_args,
    catchup=False,
    template_searchpath='/home/jupyter/airflow_course/homework_4/templates',
)

process_orders_task = PythonOperator(
    task_id='process_orders',
    python_callable=process_data,
    op_kwargs={
        'conn_id': ORDERS_CONN_ID,
        'object_name': ORDERS_ENDPOINT,
        'object_type': 'file',
        'dir_path': DATA_PATH,
        'file_type': 'csv',
        'field_names': orders_field_names,
        'clean_map': orders_clean_map,
        'gen_map': orders_gen_map
    },
    provide_context=True,
    dag=dag
)

process_status_task = PythonOperator(
    task_id='process_status',
    python_callable=process_data,
    op_kwargs={
        'conn_id': STATUS_CONN_ID,
        'object_name': STATUS_ENDPOINT,
        'object_type': 'file',
        'dir_path': DATA_PATH,
        'file_type': 'json',
        'field_names': status_field_names,
        'clean_map': status_clean_map,
        'gen_map': status_gen_map
    },
    dag=dag
)

process_customers_task = PythonOperator(
    task_id='process_customers',
    python_callable=process_data,
    op_kwargs={
        'conn_id': SHARED_DB_CONN_ID,
        'object_name': CUSTOMERS_TABLE,
        'object_type': 'table',
        'dir_path': DATA_PATH,
        'file_type': 'csv',
        'field_names': customers_field_names,
        'clean_map': customers_clean_map,
        'gen_map': customers_gen_map
    },
    dag=dag
)

process_goods_task = PythonOperator(
    task_id='process_goods',
    python_callable=process_data,
    op_kwargs={
        'conn_id': SHARED_DB_CONN_ID,
        'object_name': GOODS_TABLE,
        'object_type': 'table',
        'dir_path': DATA_PATH,
        'file_type': 'csv',
        'field_names': goods_field_names,
        'clean_map': goods_clean_map,
        'gen_map': goods_gen_map
    },
    dag=dag
)

create_dataset_task = TemplatedPythonOperator(
    task_id='create_dataset',
    python_callable=create_dataset,
    op_kwargs={
        'conn_id': PRIVATE_DB_CONN_ID
    },
    provide_context=True,
    templates_dict={'target_sql': 'target_sql.sql',
                    'target_table': 'target_table.json',
                    'temp_tables': 'temp_tables.json'},
    dag=dag
)

(process_orders_task >> process_status_task >>
 process_customers_task >> process_goods_task >>
 create_dataset_task)

if __name__ == '__main__':
    dag.clear(reset_dag_runs=True)
    dag.run()
