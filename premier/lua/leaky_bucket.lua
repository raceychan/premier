-- Check bucket state and calculate delay for the next token
local bucket_key = KEYS[1]  -- The key for the bucket state
local waiting_key = KEYS[2] -- The key for tracking waiting tasks
local now = tonumber(redis.call('TIME')[1])

local bucket_size = tonumber(ARGV[1]) -- NOTE: this has to be > 0
local quota = tonumber(ARGV[2])       -- NOTE: this has to be > 0
local duration = tonumber(ARGV[3])    -- NOTE: this has to be > 0


local last_execution_time = tonumber(redis.call('GET', bucket_key))
if not last_execution_time then
    redis.call('SET', bucket_key, now)
    return -1 -- Token is available immediately
end

local elapsed = now - last_execution_time
local leak_rate = quota / duration
local delay = (1 / leak_rate) - elapsed


if elapsed >= duration then
    redis.call('SET', bucket_key, now)
    return -1 -- Token is available immediately
elseif delay <= 0 then
    return -1 -- Token is available but no need to reset time yet
else
    return delay
end
