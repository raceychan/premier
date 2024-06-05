-- Check bucket state and calculate delay for the next token
local bucket_key = KEYS[1] -- The key for the bucket state

local now = tonumber(redis.call('TIME')[1])
local quota = tonumber(ARGV[1])    -- NOTE: this has to be > 0
local duration = tonumber(ARGV[2]) -- NOTE: this has to be > 0


local last_execution_time = tonumber(redis.call('GET', bucket_key))
if not last_execution_time then
    redis.call('SET', bucket_key, now)
    return -1 -- Token is available immediately
end

local elapsed = now - last_execution_time
local leak_rate = quota / duration
local delay = (1 / leak_rate) - elapsed
if delay <= 0 then
    redis.call('SET', bucket_key, now)
    return -1 -- Token is available
else
    return delay
end
