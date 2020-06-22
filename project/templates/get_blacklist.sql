SELECT
  url
FROM 
  {{ var.json.project_target_table.table_name }}
WHERE
  last_modified_at >  now() at time zone 'utc' - INTERVAL '10 MINUTES';