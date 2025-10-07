# Bank Account Synchronization

## 📋 Overview

The Bill.com integration module provides bidirectional synchronization of vendor bank accounts between Odoo and Bill.com. This allows seamless payment processing by ensuring vendor payment information is consistent across both systems.

## 🔄 Synchronization Flow

### Bill.com → Odoo (Automatic)

When syncing vendors from Bill.com to Odoo, bank account information from the `paymentInformation` field is automatically processed and created/updated in Odoo.

**Trigger Points**:
- Vendor sync from Bill.com (wizard or cron job)
- Vendor webhook events (`vendor.created`, `vendor.updated`)

**Data Source**: Bill.com vendor `paymentInformation.bankAccount` structure:
```json
{
  "paymentInformation": {
    "payeeName": "John Doe",
    "payByType": "WALLET",
    "payBySubType": "NONE",
    "bankAccount": {
      "accountNumber": "************1111",
      "routingNumber": "011401533",
      "type": "CHECKING",
      "ownerType": "BUSINESS"
    }
  }
}
```

**Processing Logic**:
1. Checks if `paymentInformation.bankAccount` exists
2. Creates or finds bank (`res.bank`) using routing number (BIC)
3. Creates or updates partner bank account (`res.partner.bank`)
4. Handles masked account numbers intelligently:
   - If Bill.com returns masked number (`************1111`), preserves existing full number in Odoo
   - Only updates if full account number is provided
5. Stores Bill.com metadata: `payByType`, `payBySubType`, `accountType`, `ownerType`, `status`
6. Records last sync timestamp

### Odoo → Bill.com (Automatic & Manual)

When creating or updating vendors in Odoo, bank account information is automatically included in the vendor sync via the `paymentInformation` field.

**Primary Method - Included in Vendor Data**:
- When syncing a vendor to Bill.com, if the vendor has `bank_ids` configured, the first bank account is automatically included in the `paymentInformation` field
- This happens during vendor creation or update
- Requires vendor to have at least one bank account with account number and routing number

**Alternative Method - Direct Bank Account Sync**:
- Creating or updating a bank account directly triggers individual sync
- "Sync to Bill.com" button on bank account form for manual sync
- Useful for adding/updating bank accounts after vendor is already in Bill.com

**Data Sent to Bill.com (in vendor data)**:
```json
{
  "name": "Acme Corp",
  "accountType": "BUSINESS",
  "address": { /* address fields */ },
  "paymentInformation": {
    "payeeName": "John Doe",
    "bankAccount": {
      "nameOnAccount": "John Doe",
      "accountNumber": "1234567890",
      "routingNumber": "011401533",
      "type": "CHECKING",
      "ownerType": "BUSINESS"
    }
  }
}
```

**For international vendors**, additional fields are included:
```json
{
  "paymentInformation": {
    "payeeName": "John Doe",
    "bankCountry": "CA",
    "paymentCurrency": "CAD",
    "bankAccount": { /* ... */ }
  }
}
```

**When using separate bank account endpoint** (`/v3/vendors/{vendorId}/bank-account`):
```json
{
  "nameOnAccount": "John Doe",
  "accountNumber": "1234567890",
  "routingNumber": "011401533",
  "type": "CHECKING",
  "ownerType": "BUSINESS",
  "paymentCurrency": "USD"
}
```

**Processing Logic**:

**Method 1 - Via Vendor Data (Recommended)**:
1. Vendor sync checks if `bank_ids` exists
2. Validates bank account has account number and routing number
3. Includes `paymentInformation` field in vendor POST/PATCH request
4. Bill.com processes and links bank account to vendor
5. Updates `billcom_last_sync_date` on bank account record

**Method 2 - Direct Bank Account Sync**:
1. Validates partner is synced to Bill.com (`billcom_id` must exist)
2. Validates required fields (account number from `acc_number`, routing number from `bank_id.bic`)
3. Prepares Bill.com API payload with correct field names
4. Uses endpoint: `POST /v3/vendors/{vendorId}/bank-account` for creation
5. For updates: `PATCH /v3/vendors/{vendorId}/bank-account/{bankAccountId}` (if `billcom_vendor_bank_id` exists)
6. Stores Bill.com bank account ID (`billcom_vendor_bank_id`) and status after successful sync
7. Posts audit message to partner's chatter
8. Uses `skip_billcom_sync` context to prevent circular syncs

## 🔧 Configuration Fields

### res.partner.bank Model Extensions

| Field | Type | Description |
|-------|------|-------------|
| `billcom_vendor_bank_id` | Char | Bill.com vendor bank account ID (readonly) |
| `billcom_pay_by_type` | Selection | Payment method: WALLET, CHECK, BANK_ACCOUNT, AP_CARD |
| `billcom_pay_by_subtype` | Selection | Payment subtype: NONE, ACH, WIRE, VIRTUAL_CARD, etc. |
| `billcom_account_type` | Selection | Account type: CHECKING, SAVINGS |
| `billcom_owner_type` | Selection | Owner type: BUSINESS, PERSONAL |
| `billcom_account_status` | Char | Bill.com account status (readonly) |
| `billcom_last_sync_date` | Datetime | Last synchronization timestamp (readonly) |

## 🎯 Use Cases

### Case 1: New Vendor from Bill.com
1. Vendor is synced from Bill.com to Odoo
2. If vendor has `paymentInformation.bankAccount`, bank account is automatically created in Odoo
3. Bank account includes all Bill.com metadata
4. Ready for payment processing

### Case 2: New Vendor in Odoo (with bank account)
1. Create vendor in Odoo
2. Add bank account to vendor in Odoo (before syncing to Bill.com)
3. Sync vendor to Bill.com
4. Bank account is automatically included in vendor data via `paymentInformation`
5. Bill.com creates vendor with payment capabilities enabled
6. Ready for payment processing

### Case 2b: New Vendor in Odoo (add bank later)
1. Create vendor in Odoo and sync to Bill.com (without bank account)
2. Later, add bank account to vendor in Odoo
3. Bank account automatically syncs via direct endpoint OR re-sync vendor
4. Bill.com updates vendor with payment information
5. Ready for payment processing

### Case 3: Update Bank Account in Odoo
1. Vendor already synced to Bill.com with bank account
2. Update account number or routing number in Odoo
3. Changes automatically sync to Bill.com
4. Bill.com updates existing bank account record
5. Status and timestamp updated in Odoo

### Case 4: Masked Account Numbers
1. Vendor synced from Bill.com with masked account (`************1111`)
2. Odoo preserves any existing full account number
3. If no existing number, displays masked version
4. When full number added in Odoo, syncs to Bill.com
5. Future syncs from Bill.com preserve full number in Odoo

## 🚨 Important Considerations

### ⚠️ Bill.com Restrictions (Error BDC_1233)

**CRITICAL**: The separate bank account endpoint (`/v3/vendors/{vendorId}/bank-account`) can **ONLY** be used when:
- ✅ Vendor does NOT have existing `paymentInformation`
- ✅ Vendor has NO pending invite
- ✅ Vendor has NO pending bank account
- ✅ Vendor is NOT international (or use paymentInformation method)

**If vendor already has payment info**, you will get error:
```
BDC_1233: The vendor is not eligible to setup an epayment either because
there is a pending vendor invite, a pending bank account, the vendor is
already setup for epayment or the vendor is an international vendor.
```

**Solution**:
1. **DO NOT** use separate bank account sync if vendor already synced with `paymentInformation`
2. **ALWAYS** update bank account by re-syncing entire vendor
3. Vendor sync will update `paymentInformation` automatically

### Security and Masked Data

Bill.com returns masked account numbers for security:
- Format: `************1111` (last 4 digits visible)
- Odoo intelligently preserves full account numbers
- Never overwrites full number with masked version

### Circular Sync Prevention

The module uses `skip_billcom_sync` context flag to prevent infinite loops:
```python
# Example: Update without triggering sync
bank_account.with_context(skip_billcom_sync=True).write({
    'billcom_vendor_bank_id': response['id']
})
```

### Required Fields for Sync

**Odoo → Bill.com requires**:
- Partner must have `billcom_id` (synced to Bill.com)
- Partner must have `is_sync_to_billcom = True`
- Bank account must have `acc_number` (account number)
- Bank account must have `bank_id` with `bic` field populated (routing number)
- Optionally: `acc_holder_name` (falls back to partner name if not provided)

**Bill.com → Odoo requires**:
- `paymentInformation.bankAccount.routingNumber` (minimum)
- Account number optional (can be masked)

### Field Defaults

If not specified in Odoo, defaults are applied when syncing to Bill.com:
- `type` (billcom_account_type): `CHECKING`
- `ownerType` (billcom_owner_type): `BUSINESS` if partner is a company, `PERSONAL` otherwise
- `paymentCurrency`: Uses `currency_id.name` from bank account, defaults to `USD` if not set
- `nameOnAccount`: Uses `acc_holder_name`, falls back to partner name if not provided

**Note**: The `billcom_pay_by_type` and `billcom_pay_by_subtype` fields are metadata stored from Bill.com responses but are NOT sent when creating bank accounts. These fields are populated when syncing FROM Bill.com.

## 📖 User Guide

### Viewing Bank Account Sync Status

1. Navigate to **Contacts** → Select synced vendor
2. Go to **Accounting** tab → **Bank Accounts**
3. Open bank account record
4. "Bill.com Vendor Bank Account" section shows:
   - Bill.com bank account ID
   - Payment method configuration
   - Account type and owner type
   - Sync status and last sync date

### Manual Sync to Bill.com

1. Open bank account record for synced vendor
2. Click **"Sync to Bill.com"** button in header
3. System validates requirements
4. Sends bank account to Bill.com API
5. Updates Odoo with Bill.com ID and status
6. Posts confirmation message to partner chatter

### Troubleshooting

**Problem**: Bank account not syncing to Bill.com

**Check**:
1. Is partner synced to Bill.com? (`billcom_id` field populated)
2. Is `is_sync_to_billcom` enabled on partner?
3. Does bank account have account number and routing number?
4. Check Odoo logs for error messages

**Problem**: Account number showing as masked

**Solution**:
- Bill.com returns masked numbers for security
- Enter full account number in Odoo
- Click "Sync to Bill.com" to send full number
- Full number preserved in Odoo for future use

**Problem**: Changes not syncing automatically

**Check**:
1. Bank accounts do NOT auto-sync on create/write (by design)
2. Must re-sync vendor to update via `paymentInformation`
3. Or use manual "Sync to Bill.com" button (only if vendor has NO payment info)
4. Check Odoo logs for instructions

**Problem**: Error BDC_1233 when syncing bank account

**Solution**:
1. This means vendor already has `paymentInformation` in Bill.com
2. **Cannot** use separate bank account endpoint
3. **Must** update bank in Odoo, then re-sync entire vendor
4. Vendor sync will update `paymentInformation` field automatically

## 🔗 API Endpoints Used

### Bill.com API v3 Endpoints

**Create Vendor Bank Account**:
```
POST /v3/vendors/{vendorId}/bank-account
```

**Update Vendor Bank Account**:
```
PATCH /v3/vendors/{vendorId}/bank-account/{bankAccountId}
```

**Get Vendor Bank Account**:
```
GET /v3/vendors/{vendorId}/bank-account
```

**Delete Vendor Bank Account**:
```
DELETE /v3/vendors/{vendorId}/bank-account
```

**Get Vendor (includes paymentInformation)**:
```
GET /v3/vendors/{id}
```

**Reference**: [Bill.com Create Vendor Bank Account API](https://developer.bill.com/reference/createvendorbankaccount)

## 📊 Audit Trail

All bank account sync operations create audit messages in the partner's chatter:

**Successful Sync**:
```
Bank Account Synced to Bill.com
- Bank: Chase Bank
- Account: ****1111
- Bill.com ID: vba01XXXXXX
- Status: VERIFIED
```

**From Bill.com**:
```
Bank Account Synced from Bill.com
- Bank: Chase Bank (011401533)
- Pay By: BANK_ACCOUNT (ACH)
- Account Type: CHECKING
- Owner Type: BUSINESS
```

## 🔍 Code References

- Bank account model: `models/res_partner.py:171-410` (ResPartnerBank class)
- Bank account fields: `models/res_partner.py:186-245` (Bill.com vendor bank account fields)
- **Prepare vendor data with paymentInformation**: `models/res_partner.py:94-141` (includes bank account in vendor data)
- Sync to Bill.com (from bank account): `models/res_partner.py:247-363` (`sync_bank_account_to_billcom`)
- Sync to Bill.com (from vendor - alternative): `models/billcom_service.py:511-716` (`sync_vendor_bank_account`)
- Sync from Bill.com: `models/billcom_service.py:1732-1827` (`_sync_partner_bank_account`)
- Vendor sync logic: `models/billcom_service.py:145-164` (handles paymentInformation in response)
- Create override: `models/res_partner.py:365-381`
- Write override: `models/res_partner.py:383-410`
- View definition: `views/res_partner_bank_views.xml:14-48`
- Server action: `views/res_partner_bank_views.xml:4-12`

## 💡 Best Practices

### For Administrators

1. **Recommended Workflow**: Add bank account to vendor BEFORE syncing to Bill.com (uses paymentInformation method)
2. **Alternative Workflow**: Sync vendor first, then add bank account (uses separate endpoint)
3. **Verify routing numbers** before syncing (invalid routing = API error)
4. **Monitor sync logs** for masked vs full account number handling
5. **Use manual sync button** if automatic sync fails
6. **Check partner chatter** for sync confirmation messages
7. **For international vendors**: Ensure country and currency are set correctly on bank account

### Choosing Sync Method

**Use paymentInformation Method (STRONGLY Recommended)** when:
- Creating new vendors with known bank account info
- Bank account is available before Bill.com sync
- Want to enable payments in single operation
- **Updating existing bank account** (re-sync vendor)
- Vendor is international
- **ALWAYS for updates** (avoids BDC_1233 error)

**Use Direct Bank Account Sync (ONLY in rare cases)** when:
- Vendor exists in Bill.com **WITHOUT** any `paymentInformation`
- First time adding bank account to vendor that was created without payment info
- **WARNING**: Will fail with BDC_1233 if vendor already has payment configuration

### Recommended Workflow

**New Vendor with Bank Account**:
```
1. Create vendor in Odoo
2. Add bank account to vendor
3. Sync vendor to Bill.com → paymentInformation included automatically ✅
```

**Update Bank Account**:
```
1. Update bank account fields in Odoo
2. Re-sync vendor to Bill.com → paymentInformation updated ✅
```

**Wrong Approach (Will Fail)**:
```
1. Vendor already in Bill.com with paymentInformation
2. Update bank account in Odoo
3. Click "Sync to Bill.com" on bank account → ERROR BDC_1233 ❌
```

### For Developers

1. **Always use context flag** when updating bank accounts programmatically:
   ```python
   bank.with_context(skip_billcom_sync=True).write(vals)
   ```

2. **Preserve existing data** when processing masked numbers:
   ```python
   is_masked = "*" in account_number
   if is_masked and existing_bank.acc_number:
       # Keep existing full number
       pass
   ```

3. **Handle API errors gracefully** with try/except and logging:
   ```python
   try:
       record.sync_bank_account_to_billcom()
   except Exception as e:
       _logger.warning(f"Sync failed: {e}. Can retry manually.")
   ```

4. **Validate requirements** before syncing:
   ```python
   if not partner.billcom_id or not partner.is_sync_to_billcom:
       return  # Skip sync
   ```

## 📚 Related Documentation

- [Bill.com Vendor Bank Accounts API](https://developer.bill.com/hc/en-us/articles/360035196872)
- [Payment Processing](./PROCESS_DATE.md)
- [Partner Matching](./PARTNER_MATCHING.md)
- [Webhook Integration](./README.md#webhooks)
