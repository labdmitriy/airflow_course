INSERT INTO {{ var.json.project_target_table.table_name }}
SELECT
  url
FROM 
  {{ var.json.project_temp_table.table_name }}
ON CONFLICT ON CONSTRAINT {{ var.json.project_target_table.constraint_name }}
DO UPDATE SET
    last_modified_at=now() at time zone 'utc';