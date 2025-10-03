# Webhook Testing Guide

## Overview

Complete test suite for Bill.com webhook integration with simulated Bill.com events.

## Test Coverage

### ✅ Test Cases Implemented

#### 1. **Bill Events**

- `test_webhook_bill_created` - Create new bill from webhook
- `test_webhook_bill_updated` - Update existing bill
- `test_webhook_bill_archived` - Archive bill (set active=False)

#### 2. **Vendor Events**

- `test_webhook_vendor_created` - Create new vendor
- `test_webhook_vendor_updated` - Update existing vendor

#### 3. **Customer Events**

- `test_webhook_customer_created` - Create new customer

#### 4. **Payment Events**

- `test_webhook_payment_updated` - Update payment status

#### 5. **Security & Validation**

- `test_webhook_invalid_signature` - Reject invalid HMAC signatures
- `test_webhook_missing_signature` - Handle missing signature header
- `test_webhook_idempotency` - Prevent duplicate processing

#### 6. **Error Handling**

- `test_webhook_error_handling` - Graceful error handling when sync fails

#### 7. **Comprehensive Coverage**

- `test_webhook_all_event_types` - All 16 event types processed

## Running the Tests

### Quick Test (Only Webhooks)

```bash
# Run only webhook controller tests
docker-compose exec odoo odoo -i billcom --test-enable --test-tags billcom --stop-after-init -d test_db
```

### Full Test Suite

```bash
# Run all billcom tests
docker-compose exec odoo odoo -i billcom --test-enable --stop-after-init -d test_db
```

### Specific Test Method

```bash
# Run single test method
docker-compose exec odoo python3 -m pytest \
  /odoo/custom/src/l10n-usa/billcom/tests/test_billcom_controller.py::TestBillcomWebhookController::test_webhook_bill_created
```

### With Coverage Report

```bash
docker-compose exec odoo coverage run --source=/odoo/custom/src/l10n-usa/billcom \
  --omit=*/tests/* odoo -i billcom --test-enable --stop-after-init -d test_db

docker-compose exec odoo coverage report
docker-compose exec odoo coverage html
```

## Test Data Structure

### Bill Created Payload

```json
{
  "idempotencyKey": "bill-created-12345",
  "eventType": "bill.created",
  "entityId": "bill_abc123",
  "timestamp": "2025-10-02T10:00:00Z",
  "organizationId": "test_org_id",
  "data": {
    "id": "bill_abc123",
    "vendorId": "test_vendor_123",
    "amount": 250.5,
    "invoiceNumber": "INV-001",
    "invoiceDate": "2025-10-02",
    "dueDate": "2025-11-01"
  }
}
```

### Vendor Created Payload

```json
{
  "idempotencyKey": "vendor-created-22222",
  "eventType": "vendor.created",
  "entityId": "vendor_xyz789",
  "timestamp": "2025-10-02T10:00:00Z",
  "organizationId": "test_org_id",
  "data": {
    "id": "vendor_xyz789",
    "name": "New Vendor Inc",
    "email": "newvendor@example.com",
    "isActive": true
  }
}
```

### Payment Updated Payload

```json
{
  "idempotencyKey": "payment-updated-55555",
  "eventType": "payment.updated",
  "entityId": "payment_pqr321",
  "timestamp": "2025-10-02T10:00:00Z",
  "organizationId": "test_org_id",
  "data": {
    "id": "payment_pqr321",
    "status": "PAID",
    "amount": 100.0
  }
}
```

## Test Scenarios

### Scenario 1: Bill Created

```python
# Simulates Bill.com sending bill.created webhook
payload = {
    "eventType": "bill.created",
    "entityId": "bill_abc123",
    ...
}
signature = hmac.sha256(secret, payload).hexdigest()

# Send to webhook endpoint
POST /billcom/webhook
Headers: X-Bill-Signature: {signature}
Body: {payload}

# Expected:
# ✅ account.move.sync_from_billcom() called
# ✅ Webhook log created with state=success
# ✅ Response 200 OK
```

### Scenario 2: Idempotency Check

```python
# Send same webhook twice
webhook_1 = send_webhook(payload)  # ✅ Processes
webhook_2 = send_webhook(payload)  # ✅ Ignored (duplicate)

# Verify:
# - Only 1 webhook log exists
# - sync_from_billcom() called only once
```

### Scenario 3: Invalid Signature

```python
payload = {...}
invalid_sig = "wrong_signature"

# Send with invalid signature
POST /billcom/webhook
Headers: X-Bill-Signature: {invalid_sig}

# Expected:
# ✅ Webhook logged with signature_valid=False
# ✅ Processing skipped
# ✅ Response 200 OK (still accepted)
```

### Scenario 4: Bill Archived

```python
# Send bill.archived event
payload = {"eventType": "bill.archived", "entityId": "bill_123"}

# Expected:
# ✅ Bill found by billcom_id
# ✅ Bill.active set to False
# ✅ Webhook log state=success
```

## Signature Validation

### How Signatures Are Generated

```python
import hmac
import hashlib
import json

def generate_signature(payload, secret):
    """Generate HMAC-SHA256 signature"""
    payload_str = json.dumps(payload)
    signature = hmac.new(
        secret.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature
```

### Test Usage

```python
# In test
payload = {"eventType": "bill.created", ...}
signature = self._generate_signature(payload)

response = self.url_open(
    "/billcom/webhook",
    data=json.dumps(payload),
    headers={
        "Content-Type": "application/json",
        "X-Bill-Signature": signature,
    }
)
```

## Expected Behavior

### Successful Webhook Processing

1. ✅ Receive webhook POST request
2. ✅ Validate HMAC signature
3. ✅ Check idempotency (prevent duplicates)
4. ✅ Create webhook log (state=processing)
5. ✅ Extract event type and entity ID
6. ✅ Call appropriate sync method:
   - `bill.*` → `account.move.sync_from_billcom()`
   - `vendor.*` → `res.partner.sync_from_billcom_by_id(..., 'vendor')`
   - `customer.*` → `res.partner.sync_from_billcom_by_id(..., 'customer')`
   - `payment.*` → `account.payment.sync_from_billcom_by_id()`
7. ✅ Update webhook log (state=success)
8. ✅ Return 200 OK

### Error Handling

1. ✅ Invalid signature → Log with signature_valid=False
2. ✅ Duplicate webhook → Skip processing, return success
3. ✅ Sync error → Log with state=error, error_message
4. ✅ Always return 200 OK (Bill.com requirement)

## Mocked Methods

Tests use mocking to avoid actual Bill.com API calls:

```python
# Mock account.move sync
with patch.object(
    type(self.env["account.move"]),
    "sync_from_billcom"
) as mock_sync:
    mock_sync.return_value = self.vendor_bill
    # Test webhook
    ...
    # Verify sync was called
    mock_sync.assert_called_once_with("bill_abc123")
```

## Webhook Log Verification

Every test verifies webhook log creation:

```python
# Find webhook log
webhook_log = self.env["billcom.webhook.log"].search([
    ("idempotency_key", "=", payload["idempotencyKey"])
])

# Assertions
self.assertEqual(len(webhook_log), 1)
self.assertEqual(webhook_log.event_type, "bill.created")
self.assertEqual(webhook_log.state, "success")
self.assertTrue(webhook_log.signature_valid)
self.assertEqual(webhook_log.entity_id, "bill_abc123")
```

## Continuous Integration

### GitHub Actions Example

```yaml
- name: Run Webhook Tests
  run: |
    docker-compose exec -T odoo odoo \
      -i billcom \
      --test-enable \
      --test-tags billcom \
      --stop-after-init \
      -d test_db
```

### Pre-commit Hook

```bash
#!/bin/bash
# Run tests before commit
docker-compose exec odoo odoo \
  -i billcom \
  --test-enable \
  --test-tags billcom \
  --stop-after-init \
  -d test_db || exit 1
```

## Debugging Failed Tests

### View Test Logs

```bash
docker-compose logs odoo | grep -A 20 "test_webhook"
```

### Interactive Debugging

```python
# Add breakpoint in test
import pdb; pdb.set_trace()

# Run test
docker-compose exec odoo odoo -i billcom --test-enable --test-tags billcom
```

### Check Webhook Logs

```python
# In Odoo shell
self.env['billcom.webhook.log'].search([]).mapped('state')
# See all webhook processing states
```

## Common Issues & Solutions

### Issue 1: Signature Validation Fails

**Problem**: Valid signature rejected **Solution**: Ensure secret matches
`billcom_config.webhook_secret`

```python
# Check secret
print(self.billcom_config.webhook_secret)
```

### Issue 2: Idempotency Not Working

**Problem**: Duplicate webhooks processed **Solution**: Check idempotencyKey uniqueness

```python
# Each test should use unique key
payload["idempotencyKey"] = f"test-{timestamp()}"
```

### Issue 3: Mock Not Called

**Problem**: `mock_sync.assert_called_once()` fails **Solution**: Verify event routing
logic

```python
# Check event type mapping in controller
if event_type == "bill.created":
    self.env["account.move"].sync_from_billcom(entity_id)
```

## Manual Testing (Optional)

### Using curl

```bash
# Generate signature (Python)
python3 << 'EOF'
import hmac, hashlib, json
payload = {"eventType": "bill.created", "entityId": "test_123"}
secret = "test_webhook_secret"
sig = hmac.new(secret.encode(), json.dumps(payload).encode(), hashlib.sha256).hexdigest()
print(f"Signature: {sig}")
print(f"Payload: {json.dumps(payload)}")
EOF

# Send webhook
curl -X POST http://localhost:8069/billcom/webhook \
  -H "Content-Type: application/json" \
  -H "X-Bill-Signature: {signature}" \
  -d '{"eventType":"bill.created","entityId":"test_123"}'
```

### Using Postman

1. Set URL: `http://localhost:8069/billcom/webhook`
2. Method: POST
3. Headers:
   - `Content-Type: application/json`
   - `X-Bill-Signature: {generate using pre-request script}`
4. Body (raw JSON):

```json
{
  "idempotencyKey": "manual-test-001",
  "eventType": "bill.created",
  "entityId": "test_bill_id",
  "timestamp": "2025-10-02T10:00:00Z",
  "organizationId": "test_org_id"
}
```

## Test Results Interpretation

### Success Output

```
test_webhook_bill_created ... ok
test_webhook_bill_updated ... ok
test_webhook_bill_archived ... ok
test_webhook_vendor_created ... ok
test_webhook_idempotency ... ok
test_webhook_invalid_signature ... ok
...
----------------------------------------------------------------------
Ran 12 tests in 2.345s

OK
```

### Failure Example

```
FAIL: test_webhook_bill_created
AssertionError: mock_sync not called
Expected: sync_from_billcom('bill_abc123')
Actual: Not called
```

## Next Steps

1. ✅ Run tests to verify webhook controller
2. ✅ Check all tests pass
3. ✅ Review webhook logs in Odoo
4. ✅ Test with real Bill.com webhooks (staging)
5. ✅ Monitor production webhook processing

## Summary

- **12 test methods** covering all webhook scenarios
- **Simulated Bill.com payloads** for bills, vendors, customers, payments
- **HMAC signature validation** tested
- **Idempotency** verified
- **Error handling** covered
- **Webhook logs** validated

All tests use mocked data and methods - no actual Bill.com API calls required! 🚀
