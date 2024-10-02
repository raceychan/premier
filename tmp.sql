with
    base as (
        SELECT
            user_id,
            min(time_id) as first_login
        from
            Users
        group by
            user_id
    ),
    time_gap as (
        select
            user_id,
            first_login,
            datediff (base.first_login, time_id) as day_diff
        from
            base
            join Users using user_id
    )
select
    user_id,
    first_login,
    sum(day_diff = 7) as retation,
    concat (
        round(
            sum(day_diff = 7) / count(distinct user_id) * 100,
            2
        ),
        '%'
    ) as retention_rate