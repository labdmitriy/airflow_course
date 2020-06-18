from datetime import datetime, timedelta
from random import random
from time import sleep

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python_operator import PythonOperator


SLA_PERIOD = 30


def canary(
    failure_ratio: float,
    sla_miss_ratio: float,
    sleep_time: float,
    **context
) -> None:
    if random() < failure_ratio:
        raise AirflowException()

    if random() < sla_miss_ratio:
        print(f'Sleep {sleep_time} seconds')
        sleep(sleep_time)


def on_failure_callback(context):
    task_instance = context['ti']
    task_id = task_instance.task_id
    dag_id = task_instance.dag_id
    message = 'Failure in DAG: {}, task: {} at {}\n'

    with open('/home/jupyter/data/canary_callback', 'a+') as f:
        f.write(message.format(dag_id, task_id, datetime.now()))


def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    task_instance = blocking_tis[0]
    task_id = task_instance.task_id
    dag_id = task_instance.dag_id
    message = 'SLA missed in DAG: {}, task: {} at {}\n'

    with open('/home/jupyter/data/canary_callback', 'a+') as f:
        f.write(message.format(dag_id, task_id, datetime.now()))


default_args = {
    'start_date': datetime.now()
}

dag = DAG(
    dag_id='homework_5_3',
    schedule_interval='*/5 * * * *',
    default_args=default_args,
    on_failure_callback=on_failure_callback,
    sla_miss_callback=sla_miss_callback,
    catchup=False
)

canary_task = PythonOperator(
    task_id='canary',
    python_callable=canary,
    op_kwargs={
        'failure_ratio': 0.1,
        'sla_miss_ratio': 0.1,
        'sleep_time': SLA_PERIOD + 5
    },
    sla=timedelta(seconds=SLA_PERIOD),
    provide_context=True,
    dag=dag
)

canary_task

if __name__ == '__main__':
    dag.clear(reset_dag_runs=True)
    dag.run()
