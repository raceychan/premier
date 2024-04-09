-- Fixed Window Lua script
local key = KEYS[1]
local quota, duration = tonumber(ARGV[1]), tonumber(ARGV[2])

local now = tonumber(redis.call('TIME')[1])
local value = redis.call('HMGET', key, 'time', 'cnt')
local time, cnt = tonumber(value[1]), tonumber(value[2])

if not time or not cnt or now > time then
    -- Start new window
    redis.call('HMSET', key, 'time', now + duration, 'cnt', 1)
    redis.call('EXPIRE', key, duration)
    return -1
end

if cnt >= quota then
    -- Window quota exceeded
    return time - now
end

-- Increment count and return success
redis.call('HINCRBY', key, 'cnt', 1)
return -1
