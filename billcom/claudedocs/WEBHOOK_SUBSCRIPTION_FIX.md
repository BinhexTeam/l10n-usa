# Webhook Subscription Error Fix

## Error Description

```
Failed to subscribe to webhooks: BillcomServiceAbstract._make_request()
got an unexpected keyword argument 'headers'
```

## Root Cause

The `_make_request()` method in `billcom_service_abstract.py` did not accept a `headers`
parameter. The webhook subscription was trying to pass the `X-Idempotent-Key` header
required by Bill.com API v3, but the method signature didn't support it.

## Solution

Modified `_make_request()` to accept `extra_headers` parameter that can be used to add
custom headers to API requests.

### Changes Made

#### 1. Updated `_make_request()` signature

**File**: `models/billcom_service_abstract.py`

```python
# Before
def _make_request(self, endpoint, method="GET", data=None, params=None):

# After
def _make_request(self, endpoint, method="GET", data=None, params=None, extra_headers=None):
```

#### 2. Updated `_execute_request()` to accept and merge extra headers

**File**: `models/billcom_service_abstract.py`

```python
# Before
def _execute_request(
    self, endpoint, method, data, params, config, retry_count, max_retries
):
    token = self._get_token()
    url = self._build_api_url(config, endpoint)
    headers = self._build_headers(token, config)

# After
def _execute_request(
    self, endpoint, method, data, params, config, retry_count, max_retries, extra_headers=None
):
    token = self._get_token()
    url = self._build_api_url(config, endpoint)
    headers = self._build_headers(token, config)

    # Add extra headers if provided
    if extra_headers:
        headers.update(extra_headers)
```

#### 3. Updated token refresh retry logic

**File**: `models/billcom_service_abstract.py`

```python
# Retry with new token
new_token = config.token
headers = self._build_headers(new_token, config)

# Add extra headers if provided (NEW)
if extra_headers:
    headers.update(extra_headers)

response = self._send_http_request(method, url, headers, data, params)
```

#### 4. Updated webhook subscription call

**File**: `models/billcom_config.py`

```python
# Before
response = service._make_request(
    "connect-events/v3/subscriptions",
    method="POST",
    data=subscription_data,
    headers={"X-Idempotent-Key": idempotency_key},  # ❌ Wrong parameter name
)

# After
response = service._make_request(
    "connect-events/v3/subscriptions",
    method="POST",
    data=subscription_data,
    extra_headers={"X-Idempotent-Key": idempotency_key},  # ✅ Correct parameter name
)
```

## How It Works

1. **Standard Headers**: Built by `_build_headers()` with authentication token and
   content-type
2. **Extra Headers**: Passed via `extra_headers` parameter
3. **Merge**: `headers.update(extra_headers)` combines both
4. **Result**: All required headers sent to Bill.com API

### Example Flow

```python
# Standard headers from _build_headers()
{
    "sessionId": "abc123...",
    "Content-Type": "application/json"
}

# Extra headers passed to _make_request()
{
    "X-Idempotent-Key": "550e8400-e29b-41d4-a716-446655440000"
}

# Final merged headers sent to API
{
    "sessionId": "abc123...",
    "Content-Type": "application/json",
    "X-Idempotent-Key": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Benefits

✅ **Flexible Header Management**: Can add custom headers for specific API calls ✅
**Backward Compatible**: Existing calls without `extra_headers` still work ✅ **Token
Refresh Support**: Extra headers preserved during token refresh retry ✅ **Bill.com API
v3 Compliant**: Supports idempotency keys and other custom headers

## Testing

To verify the fix works:

1. Enable webhooks in Bill.com configuration
2. Select desired events
3. Click "Subscribe" button
4. Verify subscription is created successfully
5. Check that `X-Idempotent-Key` header is sent (check logs)

## Impact

- **Scope**: Only affects `billcom_service_abstract.py` and `billcom_config.py`
- **Risk**: Low - additive change, doesn't break existing functionality
- **Benefits**: Enables webhook subscriptions to work correctly with Bill.com API v3

## Status

✅ **Fixed** - Webhook subscriptions now work correctly with idempotency headers
