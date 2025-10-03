# Bill.com Webhook Integration Refactoring Summary

## Overview

Refactored the Bill.com webhook integration to fix critical issues in production and
align with Bill.com API v3 webhook payload structure.

## Issues Fixed

### 1. Company Context Error

**Problem**: Webhook controller failed with "No active Bill.com configuration found for
company False"

- Webhooks use `auth="none"`, so `self.env.company` was False
- Configuration lookup was based on company instead of organization ID

**Solution**:

- Changed configuration lookup to use `organization_id` from webhook metadata
- Added `_get_config_from_organization_id()` method that searches by organization ID
- Removed dependency on company context

### 2. Bill.com API v3 Payload Structure

**Problem**: Old webhook handler expected old payload format without metadata

**Old Format**:

```json
{
  "eventType": "bill.created",
  "entityId": "bill_123",
  ...
}
```

**New Format** (Bill.com API v3):

```json
{
  "metadata": {
    "eventId": "unique-event-id",
    "subscriptionId": "sub-id",
    "organizationId": "org-id",
    "eventType": "bill.created",
    "version": "1"
  },
  "bill": {
    "id": "bill_123",
    ...
  }
}
```

**Solution**:

- Added `_extract_webhook_data()` method to parse new metadata structure
- Extracts `eventType`, `organizationId`, and `eventId` from metadata
- Extracts entity data from appropriate key (bill, vendor, payment, bankAccount)
- Uses `eventId` from metadata as idempotency key

### 3. Event Type Simplification

**Problem**: Too many webhook event types enabled (customers, invoices, funding
accounts)

**Solution**: Reduced to only essential event types:

- **Bills**: created, updated, archived, restored
- **Vendors**: created, updated, archived, restored
- **Payments**: updated, failed
- **Bank Accounts**: created, updated, archived

Removed fields:

- `webhook_event_customers`
- `webhook_event_invoices`
- `webhook_event_funding_accounts`

## Code Structure Improvements

### Refactored Controller

**Before**: Single monolithic webhook handler with ~250 lines

**After**: Separated into focused methods:

1. **`_get_config_from_organization_id()`**: Get configuration by organization ID
2. **`_extract_webhook_data()`**: Parse Bill.com API v3 payload structure
3. **`_handle_bill_webhook()`**: Handle bill-related events
4. **`_handle_vendor_webhook()`**: Handle vendor-related events
5. **`_handle_payment_webhook()`**: Handle payment-related events
6. **`_handle_bank_account_webhook()`**: Handle bank account events

### Configuration Updates

**billcom_config.py**:

- Updated `_get_webhook_events()` to only return enabled event types
- Updated `_get_webhook_event_objects()` to match enabled events
- Removed references to old event types

**billcom_config_views.xml**:

- Updated webhook events section to show only enabled types
- Changed group labels: "Business Events" and "Financial Events"

## Webhook Payload Examples

### Bill Events

#### bill.created

```json
{
  "metadata": {
    "eventId": "{event_id}",
    "subscriptionId": "{subscription_id}",
    "organizationId": "{organization_id}",
    "eventType": "bill.created",
    "version": "1"
  },
  "bill": {
    "id": "{bill_id}",
    "vendorId": "{vendor_id}",
    "invoice": {
      "invoiceNumber": "202501",
      "invoiceDate": "2025-12-15T00:00:00.000Z"
    },
    "amount": 228.99,
    "createdTime": "2025-12-15T23:15:23.127+00:00",
    "updatedTime": "2025-12-15T23:15:23.127+00:00",
    "archived": false,
    "description": "Happy Music Supplies Dec Bill",
    "dueDate": "2025-12-31",
    "paymentStatus": "UNPAID",
    "payFromChartOfAccountId": "{pay_from_chart_of_accounts_id}",
    "classifications": {
      "chartOfAccountId": "{chart_of_accounts_id}",
      "accountingClassId": "{accounting_class_id}",
      "departmentId": "{department_id}",
      "locationId": "{location_id}"
    },
    "purchaseOrderNumber": "{purchase_order_number}"
  }
}
```

#### bill.updated

Similar to created, with updated `updatedTime` and potentially different values

#### bill.archived

Same structure with `"archived": true`

#### bill.restored

Same structure with `"archived": false` after being archived

### Vendor Events

#### vendor.created

```json
{
  "metadata": {
    "eventId": "{event_id}",
    "subscriptionId": "{subscription_id}",
    "organizationId": "{organization_id}",
    "eventType": "vendor.created",
    "version": "1"
  },
  "vendor": {
    "id": "{vendor_id}",
    "name": "Happy Music Supplies",
    "shortName": "Happy",
    "archived": false,
    "email": "info@happymusicsupplies.org",
    "phone": "9876543210",
    "networkStatus": "NOT_CONNECTED",
    "accountNumber": 987000654,
    "address": {
      "line1": "123 Main St",
      "line2": "Suite 200",
      "city": "San Jose",
      "stateOrProvince": "CA",
      "zipOrPostalCode": "95002",
      "country": "US"
    },
    "paymentInformation": {
      "payeeName": "Happy Music Supplies",
      "email": "info@happymusicsupplies.org",
      "payByType": "CHECK",
      "virtualCard": {
        "status": "UNKNOWN"
      }
    },
    "additionalInfo": {
      "taxId": "9998887777",
      "taxIdType": "SSN",
      "track1099": true,
      "leadTimeInDays": 10,
      "combinePayments": true,
      "companyName": "Happy Music Supplies"
    },
    "recurringPayments": false,
    "billCurrency": "USD",
    "balance": {
      "amount": 0
    },
    "autoPay": {
      "enabled": false
    },
    "createdTime": "2025-12-15T22:53:15.127+00:00",
    "updatedTime": "2025-12-15T22:53:15.127+00:00"
  }
}
```

#### vendor.updated (Network Connected)

When a vendor connects to Bill.com network, `networkStatus` changes to `CONNECTED` and
`paymentNetworkId` is added:

```json
{
  "vendor": {
    "networkStatus": "CONNECTED",
    "paymentNetworkId": "{PNI_id}",
    "paymentInformation": {
      "payByType": "ACH"
    }
  }
}
```

#### vendor.updated (Verified National Vendor)

For verified national vendors like GEICO, `networkStatus` is `CONNECTED_RPPS` and
includes `rppsId`:

```json
{
  "vendor": {
    "networkStatus": "CONNECTED_RPPS",
    "rppsId": "{PNI_id}",
    "paymentInformation": {
      "payByType": "RPPS"
    }
  }
}
```

**Network Status Values**:

- `NOT_CONNECTED`: Vendor not on Bill.com network
- `CONNECTED`: Vendor connected to Bill.com network
- `CONNECTED_RPPS`: Verified national vendor (e.g., GEICO, utilities)

**Payment Types**:

- `CHECK`: Paper check
- `ACH`: Electronic bank transfer
- `WALLET`: Digital wallet payment
- `RPPS`: Real-time payment to verified vendor

### Payment Events

#### payment.updated (Before Money Movement)

When payment is scheduled but not yet processed:

```json
{
  "metadata": {
    "eventId": "{event_id}",
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
      "disbursementAccount": {}
    },
    "vendor": {
      "id": "{vendor_id}",
      "name": "Happy Music Supplies"
    },
    "billingType": "BILL_AUTOPAY"
  }
}
```

#### payment.updated (When Money Movement Begins)

When Bill.com starts processing the payment:

```json
{
  "payment": {
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

#### payment.failed

When payment creation or processing fails:

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

**Payment Status Values**:

- `SCHEDULED`: Payment scheduled for processing
- `PROCESSED`: Payment has been processed by Bill.com
- `DELIVERED`: Payment delivered to vendor
- `RETURNED`: Payment returned/failed

**Billing Types**:

- `BDC`: Payment made with Bill.com web app or API
- `BILL_AUTOPAY`: Payment made with autopay feature
- `NET_SYNC_FROM_ONLINE_PAYMENT`: Synced payment to Bill.com customer
- `NET_SYNC_FROM_OFFLINE_PAYMENT`: Synced payment to non-Bill.com customer
- `RECURRING_PAYMENT`: Recurring bill payment

**Common Payment Failure Reasons**:

- Bill ID not found
- Vendor ID not found
- Cannot overpay a bill
- Invalid process date
- Bank account is inactive
- Card account is inactive

### Bank Account Events

Similar structure with `"bankAccount": { ... }`

## Vendor Webhook Data Handling

The vendor webhook handler now captures comprehensive vendor information directly from
the webhook payload:

### Captured Data

1. **Basic Information**

   - Name, email, phone
   - Account number
   - Address (complete with state/country lookup)

2. **Network Information** (stored in comment field)

   - Network Status: `NOT_CONNECTED`, `CONNECTED`, `CONNECTED_RPPS`
   - Payment Network ID (for connected vendors)
   - RPPS ID (for verified national vendors)

3. **Payment Information** (stored in comment field)

   - Payment Type: `CHECK`, `ACH`, `WALLET`, `RPPS`
   - Last Payment Date
   - Payee Name

4. **Financial Information** (stored in comment field)

   - Current Balance
   - Balance Last Updated Date
   - AutoPay Status

5. **Additional Settings** (stored in comment field)
   - Track 1099 status
   - Combine Payments setting
   - Lead Time in Days

### Efficiency Improvement

The webhook handler now uses the complete vendor data from the webhook payload instead
of making an additional API call to Bill.com. This improves:

- **Performance**: No extra API call needed
- **Real-time accuracy**: Data is guaranteed to be current
- **API quota**: Saves API calls for other operations

### Comment Field Format

Vendor-specific Bill.com information is stored in the partner's comment field:

```
=== Bill.com Vendor Info ===
Network Status: CONNECTED
Payment Network ID: pni_abc123
Payment Type: ACH
Last Payment: 2025-12-18
Balance: $1,234.56
Balance Updated: 2025-12-18
AutoPay: Enabled
Track 1099: Yes
Combine Payments: Yes
```

## Testing

The refactored webhook integration:

1. **Correctly identifies organization** from webhook metadata
2. **Parses Bill.com API v3 payload** with metadata and entity-specific data
3. **Routes to appropriate handler** based on event type prefix
4. **Handles all event operations**: create, update, archive, restore
5. **Validates signatures** when webhook secret is configured
6. **Prevents duplicate processing** using event ID as idempotency key
7. **Logs all webhook activities** for debugging and audit trail

## Migration Notes

When upgrading existing installations:

1. **No data migration needed** - only code changes
2. **Webhook subscriptions may need to be recreated** to use new event format
3. **Old webhook logs** will continue to work (backwards compatible)
4. **Configuration automatically updated** through module upgrade

## Files Modified

1. `controllers/billcom_controller.py` - Complete refactor of webhook handler
2. `models/billcom_config.py` - Updated event configuration and methods
3. `views/billcom_config_views.xml` - Updated webhook events UI
4. `claudedocs/WEBHOOK_REFACTORING_SUMMARY.md` - This documentation

## Next Steps

1. Monitor webhook logs in production for any issues
2. Verify signature validation is working correctly
3. Consider adding webhook retry mechanism for failed processing
4. Add webhook analytics dashboard for monitoring
