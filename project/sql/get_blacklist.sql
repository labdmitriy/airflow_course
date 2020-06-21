SELECT
  url
FROM 
  url_update_history
WHERE
  last_modified_at >  now() at time zone 'utc' - INTERVAL '10 MINUTES';