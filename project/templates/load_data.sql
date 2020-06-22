INSERT INTO url_update_history
SELECT
  url
FROM 
  url_update_history_tmp
ON CONFLICT ON CONSTRAINT url_unq
DO UPDATE SET
    last_modified_at=now() at time zone 'utc';