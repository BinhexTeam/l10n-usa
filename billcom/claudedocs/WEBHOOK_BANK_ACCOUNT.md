# Bank Account Webhook Implementation

## Overview

Bank account webhook handling for Bill.com funding accounts, tracking account
verification status, default settings, and lifecycle events.

## Webhook Events

### bank-account.created

Sent when a new bank account is added to Bill.com.

### bank-account.updated

Sent when bank account properties change:

- **Status changes**: PENDING → VERIFIED, VERIFIED → NOT_VERIFIED, etc.
- **Archive state**: When account is archived/unarchived
- **Default settings**: When set as default for payables/receivables

### bank-account.archived

Sent when bank account is archived (though this is also reflected in
`bank-account.updated`).

## Payload Structure

### bank-account.created

```json
{
  "metadata": {
    "eventId": "{event_id}",
    "subscriptionId": "{subscription_id}",
    "organizationId": "{organization_id}",
    "eventType": "bank-account.created",
    "version": "1"
  },
  "bank-account": {
    "id": "{bankaccount_id}",
    "archived": true,
    "accountNumber": "*****2333",
    "nameOnAccount": "Noodle Soupsmith",
    "routingNumber": "074000010",
    "bankName": "Chase",
    "status": "PENDING",
    "createdBy": "{user_id}",
    "type": "CHECKING",
    "ownerType": "BUSINESS",
    "createdTime": "2025-12-16T23:15:23.127+00:00",
    "updatedTime": "2025-12-16T23:15:23.127+00:00",
    "default": {
      "payables": false,
      "receivables": false
    }
  }
}
```

### bank-account.updated (Status: PENDING → VERIFIED)

When verification succeeds, `archived` becomes `false`:

```json
{
  "bank-account": {
    "id": "{bankaccount_id}",
    "archived": false,
    "status": "VERIFIED",
    "updatedTime": "2025-12-19T23:15:23.127+00:00"
  }
}
```

### bank-account.updated (Status: VERIFIED → NOT_VERIFIED)

When verification fails, `archived` becomes `true`:

```json
{
  "bank-account": {
    "id": "{bankaccount_id}",
    "archived": true,
    "status": "NOT_VERIFIED",
    "updatedTime": "2025-12-20T23:15:23.127+00:00"
  }
}
```

### bank-account.updated (Default Settings)

When set as default for AP/AR operations:

```json
{
  "bank-account": {
    "id": "{bankaccount_id}",
    "archived": false,
    "status": "VERIFIED",
    "default": {
      "payables": true,
      "receivables": true
    }
  }
}
```

## Field Details

### Core Fields

| Field           | Type    | Description                                  | Example                  |
| --------------- | ------- | -------------------------------------------- | ------------------------ |
| `id`            | String  | Bill.com bank account ID (starts with `bac`) | `bac01ABC123`            |
| `archived`      | Boolean | Account archived status                      | `false`                  |
| `accountNumber` | String  | Masked account number                        | `*****2333`              |
| `nameOnAccount` | String  | Account holder name                          | `Noodle Soupsmith`       |
| `routingNumber` | String  | Bank routing number                          | `074000010`              |
| `bankName`      | String  | Bank name                                    | `Chase`                  |
| `status`        | String  | Verification status                          | See Status Values        |
| `type`          | String  | Account type                                 | `CHECKING` or `SAVINGS`  |
| `ownerType`     | String  | Owner type                                   | `BUSINESS` or `PERSONAL` |
| `createdBy`     | String  | User ID who created account                  | `006ABC123`              |

### Status Values

| Status         | Description                 | Archived |
| -------------- | --------------------------- | -------- |
| `VERIFIED`     | Account verified and active | `false`  |
| `NOT_VERIFIED` | Verification failed         | `true`   |
| `PENDING`      | Verification in progress    | `true`   |
| `BLOCKED`      | Account blocked             | `true`   |
| `EXPIRED`      | Verification expired        | `true`   |
| `INVALID`      | Invalid account details     | `true`   |
| `UNDEFINED`    | Unknown status              | Varies   |

### Default Settings

```json
"default": {
  "payables": true,   // Default for Accounts Payable (AP) operations
  "receivables": true // Default for Accounts Receivable (AR) operations
}
```

## Status Flow

### Successful Verification Flow

```
CREATE ACCOUNT
    ↓
PENDING (archived=true)
    ↓ (micro-deposits verified)
VERIFIED (archived=false)
    ↓ (set as default)
VERIFIED + default.payables=true
```

### Failed Verification Flow

```
CREATE ACCOUNT
    ↓
PENDING (archived=true)
    ↓ (verification failed)
NOT_VERIFIED (archived=true)
    ↓ (account blocked)
BLOCKED (archived=true)
```

## Webhook Triggers

### Creation Triggers

- New bank account added via Bill.com UI
- New bank account added via API
- Micro-deposit verification initiated

### Update Triggers

**Status Changes**:

- PENDING → VERIFIED (micro-deposits verified)
- VERIFIED → NOT_VERIFIED (re-verification failed)
- Any status → BLOCKED (account flagged)
- Any status → EXPIRED (verification timeout)

**Default Setting Changes**:

- Set as default for payables (AP)
- Set as default for receivables (AR)
- Unset as default

**Archive State Changes**:

- Manual archive/unarchive
- Automatic archive on verification failure

## Implementation

### Handler Method

```python
def _handle_bank_account_webhook(self, event_type, entity_id, entity_data, config):
    """Handle bank-account-related webhook events"""
    bank_account_id = entity_data.get("id")
    status = entity_data.get("status")
    archived = entity_data.get("archived", False)

    if event_type == "bank-account.created":
        # Log new account creation

    elif event_type == "bank-account.updated":
        # Handle status changes
        if status == "VERIFIED" and not archived:
            # Account verified and activated
        elif status == "NOT_VERIFIED" and archived:
            # Verification failed

        # Handle default settings
        if default_settings.get("payables"):
            # Set as default for AP
        if default_settings.get("receivables"):
            # Set as default for AR
```

### Logging Examples

**Account Created**:

```
INFO: New bank account created - Bank: Chase, Type: CHECKING, Owner: BUSINESS, Account: *****2333
```

**Account Verified**:

```
INFO: Bank account bac01ABC123 VERIFIED and activated - Noodle Soupsmith at Chase
```

**Verification Failed**:

```
WARNING: Bank account bac01ABC123 verification FAILED - account archived
```

**Set as Default**:

```
INFO: Bank account bac01ABC123 set as DEFAULT for PAYABLES (AP)
```

## Integration with Odoo

### Current Implementation

- Webhook received and logged
- Status changes tracked in logs
- Default settings monitored

### Future Enhancement (TODO)

Sync to Odoo `res.partner.bank`:

```python
# Find or create partner bank account
partner_bank = env['res.partner.bank'].search([
    ('billcom_bank_account_id', '=', bank_account_id)
], limit=1)

if not partner_bank:
    # Create new bank account
    partner_bank = env['res.partner.bank'].create({
        'acc_number': account_number,
        'partner_id': partner_id,
        'bank_name': bank_name,
        'billcom_bank_account_id': bank_account_id,
    })

# Update status and settings
partner_bank.write({
    'billcom_status': status,
    'billcom_default_payables': default_settings.get('payables'),
    'billcom_default_receivables': default_settings.get('receivables'),
    'active': not archived,
})
```

## Status-Archive Relationship

### Active Accounts

- `VERIFIED` + `archived=false` → Active, usable account

### Inactive Accounts

- `PENDING` + `archived=true` → Awaiting verification
- `NOT_VERIFIED` + `archived=true` → Verification failed
- `BLOCKED` + `archived=true` → Account blocked
- `EXPIRED` + `archived=true` → Verification expired

### Key Rule

When `archived=true`, the account **cannot be used** for payments/receivables regardless
of status.

## Use Cases

### 1. Account Verification Tracking

Monitor bank account verification progress:

- Created → PENDING
- PENDING → VERIFIED (success)
- PENDING → NOT_VERIFIED (failure)

### 2. Default Account Management

Track which account is default for operations:

- AP operations (payables)
- AR operations (receivables)
- Changes to default settings

### 3. Account Lifecycle Management

Handle account state changes:

- New accounts (creation)
- Active accounts (verified, not archived)
- Inactive accounts (archived or failed verification)
- Blocked accounts (flagged by Bill.com)

### 4. Compliance and Audit

Log all bank account events:

- Who created the account
- When verification occurred
- Status change history
- Default setting changes

## Common Scenarios

### Scenario 1: New Account Added

```
1. User adds bank account in Bill.com
2. bank-account.created webhook → status: PENDING, archived: true
3. Bill.com sends micro-deposits
4. User verifies micro-deposits
5. bank-account.updated webhook → status: VERIFIED, archived: false
```

### Scenario 2: Verification Failed

```
1. User adds bank account
2. bank-account.created webhook → status: PENDING
3. Verification fails (incorrect amounts, timeout, etc.)
4. bank-account.updated webhook → status: NOT_VERIFIED, archived: true
```

### Scenario 3: Set as Default

```
1. User sets account as default for AP
2. bank-account.updated webhook → default.payables: true
3. Previous default account receives webhook → default.payables: false
```

### Scenario 4: Account Blocked

```
1. Bill.com flags suspicious activity
2. bank-account.updated webhook → status: BLOCKED, archived: true
3. Account cannot be used for any operations
```

## Testing

### Test Cases

1. **New Account Creation**

   - Verify webhook received
   - Check PENDING status
   - Confirm archived=true

2. **Successful Verification**

   - Verify status changes to VERIFIED
   - Check archived=false
   - Confirm account usable

3. **Failed Verification**

   - Verify status changes to NOT_VERIFIED
   - Check archived=true
   - Confirm account blocked

4. **Default Settings**

   - Set as default for AP → payables=true
   - Set as default for AR → receivables=true
   - Unset default → both=false

5. **Account Blocked**
   - Verify BLOCKED status
   - Check archived=true
   - Confirm alerts logged

## Security Considerations

### Account Number Masking

- Bill.com masks account numbers in webhooks
- Format: `*****2333` (last 4 digits visible)
- Routing numbers are unmasked

### Sensitive Data Handling

- Never log full account numbers
- Routing numbers can be logged (public data)
- Account holder names can be logged

### Status Validation

- Always verify `archived` flag before using account
- Check `status` is `VERIFIED` for payments
- Validate default settings for operations

## Error Handling

### Missing Data

```python
status = entity_data.get("status", "UNDEFINED")
archived = entity_data.get("archived", False)
account_number = entity_data.get("accountNumber", "N/A")
```

### Invalid Status

```python
if status not in VALID_STATUSES:
    _logger.warning("Unknown bank account status: %s", status)
    # Handle as UNDEFINED
```

### Webhook Processing Errors

```python
try:
    # Process bank account webhook
except Exception as e:
    _logger.error("Error processing bank account webhook: %s", str(e))
    # Mark webhook log as error
    # Continue processing other webhooks
```

## Performance

### Webhook Volume

- Low frequency (account changes are rare)
- Typically 1-5 webhooks per account lifecycle
- No performance concerns

### Database Impact

- Future sync to res.partner.bank (one record per account)
- Minimal database overhead
- No complex queries needed

## Monitoring

### Key Metrics

- Account creation rate
- Verification success rate
- Failed verification count
- Blocked account count
- Default account changes

### Alerts

- BLOCKED status (security concern)
- NOT_VERIFIED status (user action needed)
- Multiple EXPIRED accounts (process issue)

## Files Modified

1. **controllers/billcom_controller.py**

   - Added `_handle_bank_account_webhook()` method
   - Comprehensive status tracking
   - Default settings monitoring
   - Archive state handling

2. **claudedocs/WEBHOOK_BANK_ACCOUNT.md** (this file)
   - Complete bank account webhook documentation
   - Status flow diagrams
   - Integration guidelines

## Next Steps

### Immediate

- ✅ Webhook logging implemented
- ✅ Status tracking active
- ✅ Documentation complete

### Future Enhancements

1. Sync to Odoo res.partner.bank
2. Alert creation for blocked accounts
3. Dashboard widget for account status
4. Verification status tracking UI
5. Automatic retry for failed verifications
