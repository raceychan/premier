-- Sliding Window Lua script
local key = KEYS[1]
local quota, duration = tonumber(ARGV[1]), tonumber(ARGV[2])

local value = redis.call('HMGET', key, 'time', 'cnt')

local now = tonumber(redis.call('TIME')[1])
local time = tonumber(value[1]) or now
local cnt = tonumber(value[2]) or 0


local elapsed = now - time
local window_progress = elapsed % duration
local adjusted_cnt = math.max(0, cnt - math.floor(elapsed / duration) * quota)
local remains

if adjusted_cnt >= quota then
    remains = (duration - window_progress) + ((adjusted_cnt - quota + 1) / quota) * duration
else
    remains = -1
    redis.call('HMSET', key, 'time', now - window_progress, 'cnt', adjusted_cnt + 1)
    redis.call('EXPIRE', key, duration)
end

return remains
