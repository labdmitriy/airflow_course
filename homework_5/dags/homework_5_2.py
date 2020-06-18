from functools import partial
from pathlib import Path

from airflow import DAG
from airflow.models import Variable
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.python_operator import (BranchPythonOperator,
                                               PythonOperator)
from airflow.utils.dates import days_ago

from merch.calculators import calculate_age, calculate_payment_status
from merch.callbacks import on_failure_callback
from merch.checkers import check_datetime_field, check_db, check_num_field
from merch.cleaners import lower, strip
from merch.operators import TemplatedPythonOperator
from merch.processors import create_dataset, process_data


orders_info = {
    'field_names': ['order_id', 'order_uuid', 'good_title',
                    'date', 'amount', 'name', 'email'],
    'clean_map': {
        'order_uuid': [strip, lower],
        'good_title': [strip],
        'date': [strip],
        'amount': [strip],
        'name': [strip],
        'email': [strip, lower]
    },
    'check_map': {
        'date': [check_datetime_field],
        'amount': [check_num_field]
    },
    'gen_map': {}
}

status_info = {
    'field_names': ['order_uuid'],
    'clean_map': {
        'order_uuid': [strip, lower]
    },
    'check_map': {},
    'gen_map': {
        'payment_status': calculate_payment_status
    }
}

customers_info = {
    'field_names': ['id', 'name', 'birth_date', 'gender', 'email'],
    'clean_map': {
        'email': [strip, lower]
    },
    'check_map': {},
    'gen_map': {
        'age': calculate_age
    }
}

goods_info = {
    'field_names': ['id', 'good_title', 'price'],
    'clean_map': {
         'good_title': [strip],
         'price': [strip]
    },
    'check_map': {
        'price': [check_num_field]
    },
    'gen_map': {}
}

data_sources = Variable.get('hw4_data_sources', deserialize_json=True)
data_path = Path(data_sources['data_path'])

default_args = {
    'start_date': days_ago(1)
}

token_id = Variable.get('HW3_TELEGRAM_BOT_TOKEN_TEST')
chat_id = Variable.get('HW3_TELEGRAM_CHAT_ID_TEST')

dag = DAG(
    dag_id='homework_5_2',
    schedule_interval='@once',
    default_args=default_args,
    catchup=False,
    on_failure_callback=partial(on_failure_callback, token_id, chat_id),
    template_searchpath='/home/jupyter/airflow_course/homework_4/templates'
)

process_orders_task = PythonOperator(
    task_id='process_orders',
    python_callable=process_data,
    op_kwargs={
        'conn_id': data_sources['orders_data']['conn_id'],
        'object_name': data_sources['orders_data']['endpoint'],
        'object_type': 'file',
        'dir_path': data_path,
        'file_type': 'csv',
        'field_names': orders_info['field_names'],
        'clean_map': orders_info['clean_map'],
        'check_map': orders_info['check_map'],
        'gen_map': orders_info['gen_map']
    },
    provide_context=True,
    dag=dag
)

process_status_task = PythonOperator(
    task_id='process_status',
    python_callable=process_data,
    op_kwargs={
        'conn_id': data_sources['status_data']['conn_id'],
        'object_name': data_sources['status_data']['endpoint'],
        'object_type': 'file',
        'dir_path': data_path,
        'file_type': 'json',
        'field_names': status_info['field_names'],
        'clean_map': status_info['clean_map'],
        'check_map': status_info['check_map'],
        'gen_map': status_info['gen_map']
    },
    provide_context=True,
    dag=dag
)

process_customers_task = PythonOperator(
    task_id='process_customers',
    python_callable=process_data,
    op_kwargs={
        'conn_id': data_sources['shared_db_conn_id'],
        'object_name': data_sources['customers_data'],
        'object_type': 'table',
        'dir_path': data_path,
        'file_type': 'csv',
        'field_names': customers_info['field_names'],
        'clean_map': customers_info['clean_map'],
        'check_map': customers_info['check_map'],
        'gen_map': customers_info['gen_map']
    },
    provide_context=True,
    dag=dag
)

process_goods_task = PythonOperator(
    task_id='process_goods',
    python_callable=process_data,
    op_kwargs={
        'conn_id': data_sources['shared_db_conn_id'],
        'object_name': data_sources['goods_data'],
        'object_type': 'table',
        'dir_path': data_path,
        'file_type': 'csv',
        'field_names': goods_info['field_names'],
        'clean_map': goods_info['clean_map'],
        'check_map': goods_info['check_map'],
        'gen_map': goods_info['gen_map']
    },
    provide_context=True,
    dag=dag
)

create_dataset_task = TemplatedPythonOperator(
    task_id='create_dataset',
    python_callable=create_dataset,
    op_kwargs={
        'conn_id': data_sources['private_db_conn_id']
    },
    provide_context=True,
    templates_dict={
        'target_sql': 'target_sql.sql',
        'target_table': 'target_table.json',
        'temp_tables': 'temp_tables.json'
    },
    dag=dag
)

check_db_task = BranchPythonOperator(
    task_id='check_db',
    python_callable=check_db,
    op_kwargs={
        'conn_id': data_sources['shared_db_conn_id'],
        'success_task_name': 'process_orders',
        'failed_task_name': 'db_not_reachable'
    },
    dag=dag
)

db_not_reachable_task = DummyOperator(
    task_id='db_not_reachable',
    dag=dag
)

all_success_task = DummyOperator(
    task_id='all_success',
    dag=dag
)

check_db_task >> [process_orders_task, db_not_reachable_task]
(process_orders_task >> process_status_task >>
 process_customers_task >> process_goods_task >>
 create_dataset_task) >> all_success_task
