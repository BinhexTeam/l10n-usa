# Payment Webhook Enhancement

## Overview

Enhanced payment webhook handling to process Bill.com payment notifications efficiently
using webhook payload data directly, eliminating unnecessary API calls.

## Payment Webhook Events

### payment.updated

Sent when payment status changes. Bill.com sends multiple `payment.updated`
notifications as the payment progresses through different states.

**Status Progression**:

1. `SCHEDULED` → Payment scheduled for processing
2. `PROCESSED` → Bill.com has processed the payment
3. `DELIVERED` → Payment delivered to vendor
4. `RETURNED` → Payment returned/failed (rare)

### payment.failed

Sent when payment creation or processing fails, includes detailed error information.

## Webhook Payload Structure

### payment.updated (SCHEDULED)

When payment is first created/scheduled:

```json
{
  "metadata": {
    "eventId": "{event_id}",
    "subscriptionId": "{subscription_id}",
    "organizationId": "{organization_id}",
    "eventType": "payment.updated",
    "version": "1"
  },
  "payment": {
    "id": "{payment_id}",
    "billIds": ["{bill_id}"],
    "transactionNumber": "{transaction_id}",
    "status": "SCHEDULED",
    "createdBy": "{user_id}",
    "createdTime": "2025-12-16T23:56:52.127+00:00",
    "updatedTime": "2025-12-17T23:56:52.127+00:00",
    "processDate": "2025-12-17",
    "funding": {
      "amount": 228.99,
      "currency": "USD",
      "fundingAccount": {
        "id": "bac01123ABC456DEF789",
        "type": "BANK_ACCOUNT",
        "name": "Noodle Soupsmith",
        "accountNumber": "************1111"
      }
    },
    "disbursement": {
      "arrivesByDate": "2025-12-20",
      "disbursementAccount": {} // Empty when not yet processed
    },
    "vendor": {
      "id": "{vendor_id}",
      "name": "Happy Music Supplies"
    },
    "billingType": "BILL_AUTOPAY"
  }
}
```

### payment.updated (PROCESSED)

When Bill.com starts processing the payment:

```json
{
  "payment": {
    "id": "{payment_id}",
    "status": "PROCESSED",
    "disbursement": {
      "amount": 228.99,
      "currency": "USD",
      "arrivesByDate": "2025-12-20",
      "disbursementAccount": {
        "type": "ACH",
        "accountNumber": "******333"
      }
    }
  }
}
```

**Key Changes from SCHEDULED**:

- `disbursementAccount` now contains payment method details
- `disbursement.amount` is populated
- Status changes to `PROCESSED`

### payment.failed

When payment fails:

```json
{
  "metadata": {
    "eventId": "{event_id}",
    "organizationId": "{organization_id}",
    "eventType": "payment.failed",
    "version": "1"
  },
  "payment": {
    "bills": [
      {
        "id": "{bill_id01}",
        "amount": 28.99
      },
      {
        "id": "{bill_id02}",
        "amount": 200
      }
    ],
    "transactionNumber": "{transaction_id}",
    "createdBy": "{user_id}",
    "createdTime": "2025-12-16T23:56:52.127+00:00",
    "updatedTime": "2025-12-16T23:56:52.127+00:00",
    "fundingAccount": {
      "id": "bac01123ABC456DEF789",
      "type": "BANK_ACCOUNT"
    },
    "vendor": {
      "id": "{vendor_id}",
      "name": "Happy Music Supplies"
    }
  },
  "errors": [
    {
      "code": "{error_code}",
      "message": "Bank account is inactive.",
      "timestamp": "2025-12-16T23:56:52.127+00:00"
    },
    {
      "code": "{error_code}",
      "message": "Bill ID not found.",
      "timestamp": "2025-12-16T23:56:52.127+00:00"
    }
  ]
}
```

## Payment Field Details

### Payment Object Fields

| Field               | Description                             | Example                               |
| ------------------- | --------------------------------------- | ------------------------------------- |
| `id`                | Bill.com payment ID (starts with `stp`) | `stp01ABC123`                         |
| `billIds`           | List of bill IDs being paid             | `["bil01XYZ"]`                        |
| `transactionNumber` | External transaction reference          | `TXN-2025-001`                        |
| `status`            | Payment status                          | `SCHEDULED`, `PROCESSED`, `DELIVERED` |
| `createdBy`         | User ID who created payment             | `006ABC123`                           |
| `processDate`       | Date payment will be processed          | `2025-12-17`                          |
| `billingType`       | Payment source                          | See Billing Types below               |

### Funding Object

```json
"funding": {
  "amount": 228.99,
  "currency": "USD",
  "fundingAccount": {
    "id": "bac01123ABC456DEF789",
    "type": "BANK_ACCOUNT",
    "name": "Noodle Soupsmith",
    "accountNumber": "************1111"
  }
}
```

**Funding Account Types**:

- `BANK_ACCOUNT`: Bank account with id, name, accountNumber
- `CARD_ACCOUNT`: Credit card with id, name, last4
- `WALLET`: Digital wallet (type only)
- `AP_CARD`: Accounts payable card with id

### Disbursement Object

```json
"disbursement": {
  "amount": 228.99,
  "currency": "USD",
  "arrivesByDate": "2025-12-20",
  "disbursementAccount": {
    "type": "ACH",
    "accountNumber": "******333"
  }
}
```

**Before Processing**:

- Only `arrivesByDate` is populated
- `disbursementAccount` is empty object `{}`

**After Processing Starts**:

- `amount` and `currency` populated
- `disbursementAccount` contains payment method details

### Billing Types

| Type                            | Description                               |
| ------------------------------- | ----------------------------------------- |
| `BDC`                           | Payment made with Bill.com web app or API |
| `BILL_AUTOPAY`                  | Payment made with autopay feature         |
| `NET_SYNC_FROM_ONLINE_PAYMENT`  | Synced from Bill.com customer payment     |
| `NET_SYNC_FROM_OFFLINE_PAYMENT` | Synced from non-Bill.com customer payment |
| `RECURRING_PAYMENT`             | Recurring bill payment                    |

## Implementation

### Payment Handler Methods

#### \_handle_payment_webhook()

Main entry point that routes to specific handlers:

- Checks if payment sync is enabled
- Routes `payment.failed` to `_handle_payment_failed()`
- Routes `payment.updated` to `_handle_payment_updated()`

#### \_handle_payment_failed()

Handles payment failures:

- Extracts vendor information
- Logs error messages with codes
- Can optionally create Odoo activities for failed payments

```python
def _handle_payment_failed(self, payment_data):
    vendor_info = payment_data.get("vendor", {})
    errors = payment_data.get("errors", [])
    transaction_number = payment_data.get("transactionNumber")

    error_messages = [
        f"{err.get('message', 'Unknown error')} ({err.get('code', 'N/A')})"
        for err in errors
    ]

    _logger.error(
        "Payment failed for vendor %s (transaction: %s). Errors: %s",
        vendor_info.get("name", "Unknown"),
        transaction_number,
        "; ".join(error_messages)
    )
```

#### \_handle_payment_updated()

Handles payment status updates:

- Uses webhook data directly (no API call)
- Logs payment status and details
- Processes based on status (SCHEDULED, PROCESSED, etc.)
- Calls existing `process_billcom_payment_webhook()` if available

```python
def _handle_payment_updated(self, entity_id, payment_data):
    payment_status = payment_data.get("status")

    if payment_status == "SCHEDULED":
        # Log scheduled payment with arrives-by date

    elif payment_status == "PROCESSED":
        # Log processed payment with disbursement details

    # Try to process with existing Odoo method
    try:
        result = request.env["account.payment"].sudo().process_billcom_payment_webhook(
            payment_data
        )
    except AttributeError:
        # Method doesn't exist, just log
```

## Common Payment Errors

### Bank/Card Account Issues

- `Bank account is inactive`
- `Card account is inactive`
- Insufficient funds

### Data Issues

- `Bill ID not found`
- `Vendor ID not found`
- Invalid process date

### Business Logic Issues

- `Cannot overpay a bill`
- Duplicate payment attempt
- Invalid payment amount

## Benefits

### 1. Performance Improvement

- **No Extra API Calls**: Uses webhook payload directly
- **Faster Processing**: Immediate status updates
- **Reduced Latency**: No API round-trip delay

### 2. Real-time Accuracy

- **Guaranteed Current Data**: Webhook data is always up-to-date
- **Event-Driven**: Captures exact state at status change
- **No Sync Lag**: Immediate notification of changes

### 3. API Efficiency

- **Saves API Quota**: One less API call per payment update
- **Better Scaling**: Handles high payment volumes
- **Resource Optimization**: Reduces Bill.com API load

### 4. Error Handling

- **Detailed Error Messages**: Complete error information from webhook
- **Proactive Alerts**: Immediate notification of failures
- **Debugging Support**: Transaction numbers and error codes

## Payment Status Tracking

### Status Flow

```
CREATE PAYMENT
    ↓
SCHEDULED (Webhook 1)
    ↓ (Bill.com processes)
PROCESSED (Webhook 2)
    ↓ (Money movement)
DELIVERED (Webhook 3)
    ↓
COMPLETE
```

### Webhook Triggers

1. **Payment Created** → `payment.updated` with `SCHEDULED`
2. **Processing Starts** → `payment.updated` with `PROCESSED`
3. **Payment Delivered** → `payment.updated` with `DELIVERED`
4. **Payment Fails** → `payment.failed` with error details

## Testing Scenarios

1. **Payment Scheduled**

   - Webhook contains funding account info
   - Disbursement has only `arrivesByDate`
   - Status is `SCHEDULED`

2. **Payment Processing**

   - Webhook contains disbursement details
   - `disbursementAccount` populated
   - Status changes to `PROCESSED`

3. **Payment Delivered**

   - Final status update
   - Payment complete
   - Status is `DELIVERED`

4. **Payment Failed**
   - Separate `payment.failed` event
   - Contains error array
   - No payment ID (payment wasn't created)

## Future Enhancements

### Potential Improvements

1. **Activity Creation**

   - Create Odoo activities for payment failures
   - Link activities to related bills
   - Notify responsible users

2. **Payment Tracking**

   - Store payment status history
   - Track status transitions
   - Audit trail for payments

3. **Dashboard Integration**

   - Real-time payment status widget
   - Failed payment alerts
   - Payment processing metrics

4. **Automatic Retry**
   - Configure retry logic for failed payments
   - Backoff strategy for retries
   - Maximum retry limits

## Files Modified

1. `controllers/billcom_controller.py`

   - Enhanced `_handle_payment_webhook()`
   - Added `_handle_payment_failed()`
   - Added `_handle_payment_updated()`

2. `claudedocs/WEBHOOK_REFACTORING_SUMMARY.md`

   - Added payment webhook payload examples
   - Documented payment status values
   - Added billing types and error cases

3. `claudedocs/WEBHOOK_PAYMENT_ENHANCEMENT.md` (this file)
   - Complete payment webhook documentation
