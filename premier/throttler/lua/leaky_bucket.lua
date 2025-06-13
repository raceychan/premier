-- Simplified leaky bucket implementation with bucket size support
local bucket_key = KEYS[1] -- The key for the bucket state

local now = tonumber(redis.call('TIME')[1])
local bucket_size = tonumber(ARGV[1])  -- Maximum bucket capacity
local quota = tonumber(ARGV[2])        -- Leak rate (requests per duration)
local duration = tonumber(ARGV[3])     -- Duration for leak rate

-- Get current bucket state: (last_leak_time, current_count)
local bucket_data = redis.call('HMGET', bucket_key, 'last_leak_time', 'current_count')
local last_leak_time = tonumber(bucket_data[1]) or now
local current_count = tonumber(bucket_data[2]) or 0

-- Calculate leak rate (requests per second)
local leak_rate = quota / duration
local elapsed = now - last_leak_time

-- Calculate how many tokens have leaked out
local leaked_tokens = math.floor(elapsed * leak_rate)
current_count = math.max(0, current_count - leaked_tokens)

-- Check if bucket is full
if current_count >= bucket_size then
    -- Return error code for bucket full (we'll handle this in Python)
    return -999
end

-- Calculate delay until next token can be processed
if current_count == 0 then
    -- Bucket is empty, can process immediately
    redis.call('HMSET', bucket_key, 'last_leak_time', now, 'current_count', 1)
    redis.call('EXPIRE', bucket_key, duration * 2) -- Set TTL for cleanup
    return -1
end

-- Add current request to bucket and calculate delay
local new_count = current_count + 1
redis.call('HMSET', bucket_key, 'last_leak_time', now, 'current_count', new_count)
redis.call('EXPIRE', bucket_key, duration * 2) -- Set TTL for cleanup

-- Delay is based on position in queue
local delay = (new_count - 1) / leak_rate
return delay
