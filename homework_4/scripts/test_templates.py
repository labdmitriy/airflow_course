from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago


class TemplatedPythonOperator(PythonOperator):
    template_ext = ('.sql', '.json')


def push_func():
    return 'table_name'


def pull_func(task, **context):
    print(context)


default_args = {
    'start_date': days_ago(1)
}

dag = DAG(
    dag_id='test_templates',
    schedule_interval='@once',
    default_args=default_args,
    catchup=False,
    template_searchpath='/home/jupyter/airflow_course/homework_4/templates'
)

push_task = TemplatedPythonOperator(
    task_id='push_xcom',
    python_callable=push_func,
    dag=dag
)

DATA_PATH = '/home/jupyter/data'

pull_task = TemplatedPythonOperator(
    task_id='pull_xcom',
    templates_dict={
        'target_sql': 'target_sql.sql',
        'temp_tables': 'temp_tables.json'
    },
    params={'data_path': DATA_PATH},
    python_callable=pull_func,
    provide_context=True,
    dag=dag
)

push_task >> pull_task

if __name__ == '__main__':
    dag.clear(reset_dag_runs=True)
    dag.run()
