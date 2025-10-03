# Bill.com Funding Accounts - Use Case Documentation

## Overview

This document describes the architecture and workflow for managing Bill.com funding
accounts (organization bank accounts) and their integration with Odoo payments.

## Architecture

### Models

#### 1. `billcom.funding.account`

**Purpose**: Store Bill.com funding accounts (organization's bank accounts)

**Key Fields**:

- `billcom_id`: Unique ID from Bill.com API
- `bank_name`: Name of the bank (e.g., "Bank of America")
- `name_on_account`: Account holder name
- `account_number`: Masked account number (e.g., "****\*\*\*\*****0000")
- `routing_number`: Bank routing number
- `account_type`: CHECKING or SAVINGS
- `status`: VERIFIED, PENDING, UNVERIFIED, FAILED
- `is_default_payables`: Default account for vendor payments
- `is_default_receivables`: Default account for customer invoices
- `partner_bank_ids`: One2many relation to linked Odoo bank accounts

**Location**: `models/billcom_funding_account.py`

#### 2. `res.partner.bank` (Extended)

**Purpose**: Link Odoo bank accounts to Bill.com funding accounts

**New Field**:

- `billcom_funding_account_id`: Many2one relation to `billcom.funding.account`

**Location**: `models/res_partner.py`

### API Integration

#### Endpoint

```
GET /v3/funding-accounts/banks
```

#### Response Structure

```json
{
  "results": [
    {
      "id": "bac02ZTVOWXMVVAAicnz",
      "archived": false,
      "status": "VERIFIED",
      "routingNumber": "011401533",
      "accountNumber": "************0000",
      "nameOnAccount": "bofa",
      "type": "CHECKING",
      "ownerType": "BUSINESS",
      "bankName": "Bank of America",
      "default": {
        "payables": true,
        "receivables": true
      },
      "createdTime": "2025-09-19T16:24:43.000+00:00",
      "updatedTime": "2025-09-20T01:21:02.000+00:00"
    }
  ]
}
```

## Use Case Flow

### 1. Initial Setup - Import Funding Accounts

**Actor**: Accounting Manager

**Steps**:

1. Navigate to `Bill.com > Configuration > Funding Accounts`
2. Click "Sync from Bill.com" button
3. System calls `billcom.funding.account.sync_funding_accounts_from_billcom()`
4. Method fetches funding accounts from Bill.com API
5. For each funding account:
   - Check if exists (by `billcom_id`)
   - Create or update record with all fields
   - Mark default accounts based on API data
6. Display notification with results (created/updated/errors)

**Result**: All Bill.com funding accounts are imported into Odoo

### 2. Link Funding Account to Journal

**Actor**: Accounting Manager

**Steps**:

1. Navigate to `Accounting > Configuration > Journals`
2. Open a payment journal (e.g., "Bank")
3. Go to "Journal Entries" tab
4. Click on the Bank Account field
5. In the bank account form:
   - Select "Bill.com Funding Account" from dropdown
   - Choose from imported funding accounts (only VERIFIED accounts shown)
6. Save

**Result**: Journal's bank account is now linked to a Bill.com funding account

### 3. Create Payment with Funding Account

**Actor**: Accountant

**Steps**:

1. Create or register a vendor payment
2. Select journal linked to funding account
3. Confirm payment
4. System calls `account_payment._prepare_payment_data()`
5. Logic flow:
   ```python
   # Try to get funding account from journal's bank account
   if journal.bank_account_id.billcom_funding_account_id:
       use funding_account.billcom_id
   # If not found, search for default payables account
   else:
       search billcom.funding.account where:
           - is_default_payables = True
           - status = VERIFIED
           - company_id = current company
       use first result
   # If still not found, raise error
   if not funding_account_id:
       raise UserError("No funding account configured")
   ```
6. Payment data includes:
   ```json
   {
     "fundingAccount": {
       "type": "BANK_ACCOUNT",
       "id": "bac02ZTVOWXMVVAAicnz"
     }
   }
   ```
7. Send to Bill.com API

**Result**: Payment is created in Bill.com with correct funding account

## Configuration Options

### Option 1: Manual Configuration (Recommended)

- Import funding accounts from Bill.com
- Link specific funding account to each journal
- Full control over which account is used

### Option 2: Default Account (Automatic)

- Import funding accounts from Bill.com
- Set default in Bill.com (payables/receivables)
- System automatically uses default if no journal link exists

### Option 3: Mixed Approach

- Use manual configuration for main journals
- Rely on default for occasional use journals

## Menu Structure

```
Bill.com
├── Dashboard
├── Configuration
│   ├── Bill.com Configuration
│   ├── Funding Accounts  ← NEW
│   └── Sync Queue
├── Vendors
├── Bills
└── Payments
```

## Views

### Tree View

- Shows all funding accounts with key information
- Filters: Verified, Default Payables, Default Receivables, Archived
- Group by: Bank, Account Type, Status

### Form View

- Displays all funding account details
- Shows linked Odoo bank accounts
- "Sync from Bill.com" button to refresh data
- Read-only fields (data comes from Bill.com)

## Security

### Access Rights

- **Account Invoice Users**: Read access only
- **Account Managers**: Full access (CRUD)

### Record Rules

- Multi-company: Users see only funding accounts from their company
- Ondelete restrict: Cannot delete funding accounts linked to bank accounts

## Error Handling

### Common Errors

#### 1. No Funding Account Configured

**Error**: "No Bill.com funding account configured" **Solution**:

- Import funding accounts from Bill.com
- Link funding account to journal's bank account, OR
- Ensure default payables account exists

#### 2. Funding Accounts Not Synced

**Error**: Empty list in dropdown **Solution**: Click "Sync from Bill.com" button in
Funding Accounts menu

#### 3. Account Not Verified

**Issue**: Account doesn't appear in dropdown **Reason**: Only VERIFIED accounts are
selectable **Solution**: Verify account in Bill.com first

## API Methods

### `billcom.service.get_funding_accounts()`

**Purpose**: Fetch funding accounts from Bill.com API **Returns**: List of funding
account dictionaries **Used by**: Sync method

### `billcom.service.get_default_funding_account(account_type='payables')`

**Purpose**: Get default funding account for payables or receivables **Returns**:
Funding account dictionary or None **Used by**: Payment creation fallback (deprecated in
favor of database search)

### `billcom.funding.account.sync_funding_accounts_from_billcom()`

**Purpose**: Import/update all funding accounts from Bill.com **Returns**: Statistics
dictionary (created/updated/errors) **Called by**: UI button, cron job (if configured)

## Database Schema

### billcom_funding_account

```sql
CREATE TABLE billcom_funding_account (
    id SERIAL PRIMARY KEY,
    billcom_id VARCHAR NOT NULL,
    bank_name VARCHAR,
    name_on_account VARCHAR,
    account_number VARCHAR,
    routing_number VARCHAR,
    account_type VARCHAR,
    owner_type VARCHAR,
    status VARCHAR,
    is_default_payables BOOLEAN,
    is_default_receivables BOOLEAN,
    active BOOLEAN,
    archived BOOLEAN,
    company_id INTEGER REFERENCES res_company,
    UNIQUE(billcom_id, company_id)
);
```

### res_partner_bank (extended)

```sql
ALTER TABLE res_partner_bank
ADD COLUMN billcom_funding_account_id INTEGER
REFERENCES billcom_funding_account ON DELETE RESTRICT;
```

## Benefits

### 1. Separation of Concerns

- Bill.com data isolated in dedicated model
- Odoo data remains clean and independent
- Easy to extend or modify

### 2. Data Integrity

- Single source of truth from Bill.com
- Automatic synchronization
- Referential integrity with foreign keys

### 3. User Experience

- Easy to understand and configure
- Visual feedback with account details
- Autocomplete with verified accounts only

### 4. Flexibility

- Multiple configuration options
- Supports multi-company
- Works with or without manual configuration

### 5. Maintainability

- Clear architecture
- Well-documented code
- Easy to troubleshoot

## Future Enhancements

### Potential Additions

1. **Automatic Sync**: Cron job to regularly update funding accounts
2. **Sync History**: Track changes over time
3. **Balance Display**: Show account balances from Bill.com
4. **Multiple Defaults**: Support different defaults per company
5. **Audit Log**: Track which funding account was used for each payment

## Testing Checklist

- [ ] Import funding accounts from Bill.com
- [ ] Verify all fields are populated correctly
- [ ] Link funding account to journal
- [ ] Create payment without funding account link (test default)
- [ ] Create payment with funding account link (test specific)
- [ ] Verify correct funding account ID sent to API
- [ ] Test with multiple companies
- [ ] Test error handling (no accounts, unverified, etc.)
- [ ] Test security (user vs manager access)
- [ ] Test sync button functionality

## Troubleshooting

### Issue: Funding accounts not appearing

**Check**:

1. Have you synced from Bill.com?
2. Are accounts marked as VERIFIED in Bill.com?
3. Are you in the correct company?

### Issue: Wrong funding account used

**Check**:

1. Is journal's bank account linked to funding account?
2. If not, is there a default payables account?
3. Check logs for which account was selected

### Issue: Payment fails with 400 error

**Check**:

1. Is funding account ID valid?
2. Is account still active in Bill.com?
3. Check Bill.com API logs for details
