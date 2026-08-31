-- Sliding-window rate limiter Lua script
-- Keys:
--   KEYS[1] = key (per-customer sorted set)
-- Args:
--   ARGV[1] = quota (integer)
--   ARGV[2] = window_ms (integer, milliseconds)
--   ARGV[3] = member id (unique string for this request)

local key = KEYS[1]
local quota = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local member = ARGV[3]

-- Get server time (seconds, microseconds)
local t = redis.call('TIME')
local now_ms = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local window_start = now_ms - window_ms

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

-- Current count in window
local count = tonumber(redis.call('ZCARD', key))

if count < quota then
  -- Allow the request: add timestamped member
  redis.call('ZADD', key, now_ms, member)
  -- Ensure key expires after window to avoid stale keys
  redis.call('PEXPIRE', key, window_ms)
  local remaining = quota - (count + 1)
  -- Return allowed, remaining, limit, retry_after (0)
  return {1, tostring(remaining), tostring(quota), tostring(0)}
else
  -- Rejected: compute retry-after using oldest entry
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local oldest_ms = tonumber(oldest[2])
  local retry_ms = window_ms - (now_ms - oldest_ms)
  if retry_ms < 0 then
    retry_ms = 0
  end
  local retry_sec = math.floor((retry_ms + 999) / 1000) -- ceil to seconds
  return {0, tostring(0), tostring(quota), tostring(retry_sec)}
end
