# import sys
from collections import OrderedDict
from pathlib import Path
from typing import List

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago

# sys.path.insert(1, '/home/jupyter/lib/merch')
from merch.calculators import calculate_age, calculate_payment_status
from merch.cleaners import lower, strip
from merch.operators import TemplatedPythonOperator
from merch.processors import create_dataset, process_data


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


data_sources = Variable.get('hw4_data_sources', deserialize_json=True)
data_path = Path(data_sources['data_path'])

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
        'conn_id': data_sources['orders_data']['conn_id'],
        'object_name': data_sources['orders_data']['endpoint'],
        'object_type': 'file',
        'dir_path': data_path,
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
        'conn_id': data_sources['status_data']['conn_id'],
        'object_name': data_sources['status_data']['endpoint'],
        'object_type': 'file',
        'dir_path': data_path,
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
        'conn_id': data_sources['shared_db_conn_id'],
        'object_name': data_sources['customers_data'],
        'object_type': 'table',
        'dir_path': data_path,
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
        'conn_id': data_sources['shared_db_conn_id'],
        'object_name': data_sources['goods_data'],
        'object_type': 'table',
        'dir_path': data_path,
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
        'conn_id': data_sources['private_db_conn_id']
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
