-- The naive-UTC casts above assume the session timezone is UTC. Fail loudly if it isn't.
SELECT current_timezone() AS tz
WHERE current_timezone() NOT IN ('UTC', 'Etc/UTC')
