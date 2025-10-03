# Chatter Notifications & Logger Improvements

## Overview

This document describes the implementation of chatter notifications for all
synchronization operations and improvements to logger messages for better debugging.

## Features Implemented

### 1. Chatter Notifications for Partners (Vendors/Customers)

**File**: `models/billcom_service.py`

#### Success Notifications

When a partner syncs successfully to Bill.com:

```html
<strong>Bill.com Sync Successful</strong> - Type: Vendor/Customer - Action:
Created/Updated - Bill.com ID: {id}
```

**Example**:

- Partner created → "Created" action
- Partner updated → "Updated" action

#### Error Notifications

When sync fails:

```html
<strong>Bill.com Sync Error</strong> Failed to sync vendor/customer to Bill.com Error:
{detailed_error_message}
```

#### Bank Account Warnings

When vendor bank account sync fails:

```html
<strong>Bill.com Bank Account Sync Warning</strong> Bank account synchronization failed:
{error}
```

### 2. Chatter Notifications for Bills/Invoices

**File**: `models/account_move.py`

#### Success Notifications (Odoo → Bill.com)

```html
<strong>Bill.com Sync Successful</strong> - Type: Bill/Invoice - Action: Created/Updated
- Bill.com ID: {id} - Document Number: {number}
```

#### Success Notifications (Bill.com → Odoo via Webhook)

```html
<strong>Synced from Bill.com</strong> - Type: Bill/Invoice - Action: Created/Updated -
Bill.com ID: {id} - Source: Webhook
```

#### Error Notifications

```html
<strong>Bill.com Sync Error</strong> Failed to sync document to Bill.com Error:
{detailed_error_message}
```

### 3. Chatter Notifications for Payments

**File**: `models/account_payment.py`

#### Success - New Payment Created

```html
<strong>Bill.com Payment Created</strong> - Bill.com ID: {id} - Status: {status} -
Confirmation #: {confirmation_number} - Transaction #: {transaction_number}
```

#### Info - Existing Payment Status Update

```html
<strong>Bill.com Payment Status Updated</strong> - Bill.com ID: {id} - Status: {status}
- Note: Payment already exists in Bill.com. API does not support updates.
```

#### Error Notifications

```html
<strong>Bill.com Payment Sync Error</strong> Failed to sync payment to Bill.com Error:
{detailed_error_message}
```

## Logger Improvements

### 1. HTTP Error Messages

**File**: `models/billcom_service_abstract.py` (lines 470-545)

#### Before

```python
_logger.error("Bill.com API error %s for URL: %s", status_code, url)
```

#### After

```python
_logger.error(
    "Bill.com API Error: Bad Request - Invalid data sent to Bill.com API\n"
    "Request: POST https://gateway.stage.bill.com/connect/v3/vendors\n"
    "Status Code: 400\n"
    "Error Details: {'code': 'BDC_1001', 'message': 'Invalid vendor name'}"
)
```

**Status Code Descriptions Added**:

- 400: Bad Request - Invalid data sent to Bill.com API
- 401: Unauthorized - Authentication failed or session expired
- 403: Forbidden - Insufficient permissions or session invalid
- 404: Not Found - Requested resource does not exist
- 429: Rate Limit Exceeded - Too many API requests
- 500: Internal Server Error - Bill.com API experiencing issues
- 502: Bad Gateway - Bill.com API temporarily unavailable
- 503: Service Unavailable - Bill.com API maintenance or overload

### 2. JSON Parsing Errors

#### Before

```python
_logger.error("JSON parsing error. Response content: %s", response.content)
```

#### After

```python
_logger.error(
    "Bill.com API Response Parsing Error\n"
    "Failed to parse JSON response from Bill.com\n"
    "URL: https://gateway.stage.bill.com/connect/v3/bills\n"
    "Response Length: 1523 bytes\n"
    "Error: Expecting value: line 1 column 1 (char 0)\n"
    "Response Preview: <html>..."
)
```

### 3. API-Level Errors

#### Before

```python
_logger.error("Bill.com API-level error: %s", error_message)
```

#### After

```python
_logger.error(
    "Bill.com API-level Error\n"
    "Error Code: BDC_1109\n"
    "Error Message: Session is invalid. Please log in.\n"
    "URL: https://gateway.stage.bill.com/connect/v3/payments\n"
    "Full Response: {'status': 'error', 'errorCode': 'BDC_1109', ...}"
)
```

### 4. Authentication Errors

**File**: `models/billcom_service_abstract.py` (lines 180-222)

#### Before

```python
_logger.error("HTTP error during Bill.com authentication: %s", str(e))
_logger.error("Response content: %s", response.content)
```

#### After

```python
_logger.error(
    "Bill.com Authentication HTTP Error\n"
    "Organization ID: 00U029fj02dje\n"
    "API URL: https://gateway.stage.bill.com/connect\n"
    "Status Code: 401\n"
    "Error: Unauthorized\n"
    "Response: {\"error\": \"Invalid credentials\"}"
)
```

### 5. MFA Configuration Errors

#### Before

```python
_logger.error("MFA required for payment but rememberMeId not configured")
```

#### After

```python
_logger.error(
    "Bill.com MFA Configuration Required\n"
    "Payment creation requires MFA-trusted session\n"
    "Organization: 00U029fj02dje\n"
    "Action Required: Configure MFA using 'Setup MFA' button\n"
    "Documentation: claudedocs/MFA_QUICK_GUIDE.md"
)
```

### 6. Webhook Sync Errors

**File**: `models/account_move.py` (lines 321-343)

#### Before

```python
except Exception:
    pass  # Silent failure
```

#### After

```python
except Exception as e:
    _logger.debug("Document %s not found in bills endpoint: %s", billcom_id, str(e))
    pass

# Final error message
_logger.error(
    "Could not fetch document %s from Bill.com - tried both bills and invoices endpoints",
    billcom_id
)
```

## Benefits

### For Users

1. **Visibility**: Clear notifications in chatter show sync status
2. **Audit Trail**: Complete history of sync operations per record
3. **Error Awareness**: Immediate notification when sync fails
4. **Action Guidance**: Errors include what happened and why

### For Developers/Support

1. **Better Debugging**: Structured error messages with context
2. **Faster Troubleshooting**: All relevant info in one log entry
3. **Error Classification**: HTTP codes with human-readable descriptions
4. **Request Tracing**: Full request/response details in logs

## Message Format Standards

### Chatter Messages

- Use HTML formatting for readability
- Use `<strong>` for titles
- Use `<ul><li>` for structured data
- Use `<em>` for secondary info
- Always include error details when available

### Logger Messages

- Use multi-line format with `\n`
- Include context (Organization, URL, Request type)
- Include error classification
- Include actionable information
- Use ERROR for failures requiring attention
- Use WARNING for non-critical issues
- Use DEBUG for diagnostic information

## Testing Recommendations

### Test Chatter Notifications

1. Create/update a vendor → Check chatter for success message
2. Sync vendor with invalid data → Check chatter for error message
3. Create payment without MFA → Check chatter for configuration error
4. Webhook creates bill → Check chatter for "Synced from Bill.com" message

### Test Logger Improvements

1. Force 401 error → Check logs for descriptive authentication error
2. Send invalid JSON → Check logs for parsing error with preview
3. Trigger rate limit → Check logs for 429 description
4. Test webhook with invalid ID → Check debug logs for endpoint attempts

## Files Modified

1. `models/billcom_service.py`

   - Lines 107-194: Partner sync with chatter notifications

2. `models/account_move.py`

   - Lines 191-240: Bill/Invoice sync with chatter notifications
   - Lines 403-446: Webhook sync with chatter notifications
   - Lines 321-343: Improved error logging for webhooks

3. `models/account_payment.py`

   - Lines 259-349: Payment sync with chatter notifications

4. `models/billcom_service_abstract.py`
   - Lines 470-545: Improved HTTP error logging
   - Lines 180-222: Improved authentication error logging
   - Lines 259-275: Improved MFA error logging

## Migration Notes

- No database migration required
- Messages appear automatically on next sync
- Existing records won't have historical notifications
- All future syncs will be tracked in chatter

## Performance Impact

- Minimal: `message_post()` is async in Odoo
- Chatter entries indexed by Odoo automatically
- No impact on sync performance
- Logger improvements add negligible overhead
