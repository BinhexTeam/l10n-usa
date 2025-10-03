# Webhook URL Fix - Final Solution

## Problem Summary

Bill.com webhooks were generating incorrect URLs:

❌ **Generated**:
`https://gateway.stage.bill.com/connect/connect-events/v3/subscriptions` ✅
**Expected**: `https://gateway.stage.bill.com/connect-events/v3/subscriptions`

## Root Cause

Bill.com has **two separate API bases**:

1. **Main API**: `https://gateway.stage.bill.com/connect/v3/...`

   - For: bills, vendors, customers, payments, invoices

2. **Webhook API**: `https://gateway.stage.bill.com/connect-events/v3/...`
   - For: webhook subscriptions

The `_build_api_url()` method only worked for the main API.

## Solution: `webhook:` Prefix Convention

### Implementation

Modified `_build_api_url()` to detect webhook endpoints using a `webhook:` prefix:

```python
def _build_api_url(self, config, endpoint):
    """Build the complete API URL

    Webhooks use a different base URL: connect-events instead of connect
    """
    # Check if this is a webhook endpoint
    if endpoint.startswith("webhook:"):
        # Remove the webhook: prefix and use connect-events base
        actual_endpoint = endpoint.replace("webhook:", "")
        base_url = config.api_url.replace("/connect", "/connect-events")
        return f"{base_url.rstrip('/')}/v3/{actual_endpoint.lstrip('/')}"

    # Standard API endpoint
    return f"{config.api_url.rstrip('/')}/v3/{endpoint.lstrip('/')}"
```

### How It Works

```python
# Webhook endpoint with prefix
service._make_request("webhook:subscriptions")
# → Detects "webhook:" prefix
# → Changes base from "/connect" to "/connect-events"
# → Result: https://gateway.stage.bill.com/connect-events/v3/subscriptions ✅

# Normal endpoint (no prefix)
service._make_request("bills")
# → No "webhook:" prefix detected
# → Uses normal base "/connect"
# → Result: https://gateway.stage.bill.com/connect/v3/bills ✅
```

## All Updated Endpoints

### 1. Create Subscription

```python
# Before
service._make_request("connect-events/v3/subscriptions", ...)
# → https://gateway.stage.bill.com/connect/v3/connect-events/v3/subscriptions ❌

# After
service._make_request("webhook:subscriptions", ...)
# → https://gateway.stage.bill.com/connect-events/v3/subscriptions ✅
```

### 2. Delete Subscription

```python
# Before
service._make_request(f"webhooks/subscriptions/{id}", method="DELETE")
# → https://gateway.stage.bill.com/connect/v3/webhooks/subscriptions/{id} ❌

# After
service._make_request(f"webhook:subscriptions/{id}", method="DELETE")
# → https://gateway.stage.bill.com/connect-events/v3/subscriptions/{id} ✅
```

### 3. Test Webhook

```python
# Before
service._make_request(f"webhooks/subscriptions/{id}/test", ...)
# → https://gateway.stage.bill.com/connect/v3/webhooks/subscriptions/{id}/test ❌

# After
service._make_request(f"webhook:subscriptions/{id}/test", ...)
# → https://gateway.stage.bill.com/connect-events/v3/subscriptions/{id}/test ✅
```

### 4. List Subscriptions

```python
# Before
service._make_request("connect-events/v3/subscriptions", method="GET")
# → https://gateway.stage.bill.com/connect/v3/connect-events/v3/subscriptions ❌

# After
service._make_request("webhook:subscriptions", method="GET")
# → https://gateway.stage.bill.com/connect-events/v3/subscriptions ✅
```

## Files Modified

### 1. `models/billcom_service_abstract.py`

- Modified `_build_api_url()` to detect `webhook:` prefix
- Automatically switches base URL for webhook endpoints

### 2. `models/billcom_config.py`

- `button_subscribe_webhooks()`: Changed to `webhook:subscriptions`
- `button_unsubscribe_webhooks()`: Changed to `webhook:subscriptions/{id}`
- `button_test_webhook()`: Changed to `webhook:subscriptions/{id}/test`
- `button_sync_webhook_status()`: Changed to `webhook:subscriptions`
- `button_view_all_subscriptions()`: Changed to `webhook:subscriptions`

## Benefits

✅ **Clean Convention**: Simple `webhook:` prefix clearly indicates webhook endpoints ✅
**Centralized Logic**: All URL building logic in one place (`_build_api_url`) ✅ **No
Code Duplication**: Reuses existing request logic ✅ **Easy to Extend**: Future webhook
endpoints just need the prefix ✅ **Backwards Compatible**: Normal endpoints work
exactly as before

## Testing Checklist

- [ ] Subscribe to webhooks → Should return subscription ID
- [ ] Sync webhook status → Should list subscriptions
- [ ] View all subscriptions → Should show subscription details
- [ ] Test webhook → Should send test event
- [ ] Unsubscribe → Should remove subscription
- [ ] Verify URLs in logs are correct (no duplicate paths)

## URL Verification

Check logs for correct URLs:

```
✅ POST https://gateway.stage.bill.com/connect-events/v3/subscriptions
✅ GET  https://gateway.stage.bill.com/connect-events/v3/subscriptions
✅ DELETE https://gateway.stage.bill.com/connect-events/v3/subscriptions/{id}
✅ POST https://gateway.stage.bill.com/connect-events/v3/subscriptions/{id}/test
```

Should **NOT** see:

```
❌ https://gateway.stage.bill.com/connect/v3/connect-events/...
❌ https://gateway.stage.bill.com/connect/connect-events/...
❌ https://gateway.stage.bill.com/connect/v3/webhooks/...
```

## Status

✅ **Fixed**: All webhook endpoints now use correct URL ✅ **Convention**: `webhook:`
prefix for webhook endpoints ✅ **Tested**: Logic verified in `_build_api_url()` 🧪
**Pending**: End-to-end testing with Bill.com API
