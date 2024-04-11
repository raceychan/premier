-- Check bucket state and calculate delay for the next token
local bucket_key = KEYS[1]  -- The key for the bucket state
local waiting_key = KEYS[2] -- The key for tracking waiting tasks
local quota = tonumber(ARGV[1])
local duration = tonumber(ARGV[2])
local bucket_size = tonumber(ARGV[3])
local now = tonumber(redis.call('TIME')[1])

local last_execution_time = tonumber(redis.call('GET', bucket_key))
if not last_execution_time then
    redis.call('SET', bucket_key, now)
    return -1 -- Token is available immediately
end

local elapsed = now - last_execution_time
local leak_rate = quota / duration
local delay = (1 / leak_rate) - elapsed

local waiting_tasks = tonumber(redis.call('GET', waiting_key)) or 0
if waiting_tasks >= bucket_size then
    return redis.error_reply("Bucket is full. Cannot add more tasks.")
end

-- If the delay is negative, it means a token is available now
if delay <= 0 then
    redis.call('SET', bucket_key, now) -- Reset the last execution time
    redis.call('INCR', waiting_key)    -- Increment waiting tasks
    return -1
else
    redis.call('INCR', waiting_key) -- Increment waiting tasks for later execution
    return delay
end
