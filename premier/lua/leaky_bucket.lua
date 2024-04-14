-- Check bucket state and calculate delay for the next token
local bucket_key = KEYS[1]            -- The key for the bucket state
local waiting_key = KEYS[2]           -- The key for tracking waiting tasks
local bucket_size = tonumber(ARGV[1]) -- NOTE: this has to be > 0
local quota = tonumber(ARGV[2])       -- NOTE: this has to be > 0
local duration = tonumber(ARGV[3])    -- NOTE: this has to be > 0
local now = tonumber(redis.call('TIME')[1])


local waiting_tasks = tonumber(redis.call('GET', waiting_key)) or 0
if waiting_tasks >= bucket_size then
    -- return redis.error_reply("Bucket is full. Cannot add more tasks.")
    return redis.error_reply("Bucket is full. Cannot add more tasks. queue size: " .. waiting_tasks)
end

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
    return -1                       -- Token is available immediately
elseif delay <= 0 then
    return -1                       -- Token is available but no need to reset time yet
else
    redis.call('INCR', waiting_key) -- Enqueue task, incrase queue size
    return delay
end
