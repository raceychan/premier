WITH
    DailyActiveUsers AS (
        SELECT
            DATE (time_id) AS active_date,
            user_id
        FROM
            t1
        GROUP BY
            DATE (time_id),
            user_id
    )
SELECT
    active_date,
    COUNT(DISTINCT user_id) OVER (
        ORDER BY
            active_date ROWS BETWEEN UNBOUNDED PRECEDING
            AND CURRENT ROW
    ) AS cumulative_active_users
FROM
    DailyActiveUsers
ORDER BY
    active_date;