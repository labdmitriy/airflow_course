select * from {{ ti.xcom_pull(task_ids='push_xcom') }};
select * from {{ params.my_var }}