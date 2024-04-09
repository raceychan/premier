-- Token Bucket Lua script
local key = KEYS[1]
local quota, duration = tonumber(ARGV[1]), tonumber(ARGV[2])

local bucket = redis.call('HMGET', key, 'last_token_time', 'tokens')
local last_refill_time, tokens = tonumber(bucket[1]), tonumber(bucket[2])

local now = tonumber(redis.call('TIME')[1])
if not last_refill_time then
    last_refill_time, tokens = now, quota
end


local elapsed = now - last_refill_time
local refill_rate = quota / duration
local new_tokens = math.min(quota, tokens + elapsed * refill_rate)

if new_tokens < 1 then
    -- Token refill needed
    return (1 - new_tokens) / refill_rate
end

-- Update tokens and last token time
redis.call('HMSET', key, 'last_token_time', now, 'tokens', new_tokens - 1)
return -1
