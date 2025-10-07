# Bill.com Payment Process Date Handling

## 📋 Overview

The `processDate` field in Bill.com payments determines when funds will be withdrawn from the funding account. Understanding when it's required and how to set it correctly is crucial for successful payment processing.

## 🎯 When processDate is Required

According to Bill.com API v3 documentation:

| Funding Account Type | processDate Required? | Notes |
|---------------------|----------------------|-------|
| **WALLET** | ✅ **YES** | Always required |
| **AP_CARD** | ✅ **YES** | Always required |
| **BANK_ACCOUNT** | ❌ No | Optional - Bill.com auto-sets to next available date if not provided |
| **CHECK** | ❌ No | Optional - Bill.com auto-sets to next available date if not provided |

## 📅 Format Requirements

**Required format**: `YYYY-MM-DD` (ISO 8601 date string)

✅ **Correct examples**:
- `"2025-10-15"`
- `"2025-12-31"`

❌ **Incorrect examples**:
- `"10/15/2025"` (US format - not accepted)
- `"15-10-2025"` (DD-MM-YYYY - not accepted)
- `2025-10-15` (Date object - must be string)

## ⏰ 2 Business Day Rule

**Important**: When adding a new vendor bank account, Bill.com requires 2 business days for verification.

For payments to vendors with newly added bank accounts:
- `processDate` **must be at least 2 business days from today**
- Business days exclude weekends (Saturday/Sunday)
- Public holidays are not automatically excluded (simple calculation)

### Examples

If today is **Monday, October 6, 2025**:
- ✅ Minimum `processDate`: **Wednesday, October 8, 2025** (+2 business days)
- ❌ **Tuesday, October 7, 2025** is too soon (only 1 business day)

If today is **Thursday, October 9, 2025**:
- ✅ Minimum `processDate`: **Monday, October 13, 2025** (skips weekend)
- ❌ **Friday, October 10, 2025** is too soon

If today is **Friday, October 10, 2025**:
- ✅ Minimum `processDate`: **Tuesday, October 14, 2025** (skips weekend)
- Weekend days don't count as business days

## 🔧 Implementation in Odoo

### Automatic Handling

The module automatically handles `processDate` based on funding account type:

```python
# From account_payment.py

# WALLET and AP_CARD: processDate is REQUIRED
if funding_type in ["WALLET", "AP_CARD"]:
    if self.billcom_process_date:
        process_date = fields.Date.to_string(self.billcom_process_date)
    else:
        # Default to today (may need manual adjustment for new vendors)
        process_date = fields.Date.to_string(fields.Date.today())

# BANK_ACCOUNT, CHECK: processDate is OPTIONAL
else:
    if self.billcom_process_date:
        # User explicitly set a date
        process_date = fields.Date.to_string(self.billcom_process_date)
    else:
        # Let Bill.com auto-set to next available date
        process_date = None
```

### Manual Process Date Setting

#### Option 1: Set Date Directly

In the payment form:
1. Select funding account type (WALLET or AP_CARD)
2. The "Process Date" field becomes visible and required
3. Manually enter the desired date

#### Option 2: Use "+2 Business Days" Button

In the payment form:
1. Click the **"Set +2 Business Days"** button next to Process Date field
2. The system automatically calculates 2 business days ahead
3. Date is set and displayed with a success notification

This is especially useful for:
- New vendor bank accounts requiring verification
- Ensuring compliance with Bill.com's 2-day rule
- Avoiding API errors due to dates being too soon

### Helper Method

The module provides a helper method you can call programmatically:

```python
payment = self.env['account.payment'].browse(payment_id)

# Calculate 2 business days ahead
min_date = payment._calculate_business_days_ahead(days=2)

# Set process date
payment.billcom_process_date = min_date
```

## 🚨 Common Errors

### Error 1: Missing processDate for WALLET/AP_CARD

**Error from Bill.com**:
```json
{
  "code": "BDC_XXXX",
  "message": "processDate is required for WALLET/AP_CARD funding types"
}
```

**Solution**:
- Set `billcom_process_date` field in the payment
- Or use the "+2 Business Days" button

### Error 2: processDate Too Soon for New Vendor

**Error from Bill.com**:
```json
{
  "code": "BDC_1152",
  "message": "Invalid Process Date. Vendor bank account requires 2 business days for verification."
}
```

**Solution**:
- Click "+2 Business Days" button to auto-calculate
- Or manually set date at least 2 business days ahead

### Error 3: Invalid Date Format

**Error from Bill.com**:
```json
{
  "code": "BDC_XXXX",
  "message": "Invalid date format. Expected YYYY-MM-DD"
}
```

**Solution**:
- Don't manually construct date strings
- Always use `fields.Date.to_string()` or the UI date picker
- The module handles format conversion automatically

## 📊 Field Visibility Rules

In the payment form, the Process Date field is:

| Condition | Visible? | Required? |
|-----------|----------|-----------|
| Funding Type = WALLET | ✅ Yes | ✅ Yes |
| Funding Type = AP_CARD | ✅ Yes | ✅ Yes |
| Funding Type = BANK_ACCOUNT | ❌ No | ❌ No |
| Funding Type = CHECK | ❌ No | ❌ No |

## 💡 Best Practices

### For WALLET Payments
1. ✅ Always set a specific `processDate`
2. ✅ Consider business days when scheduling
3. ✅ Coordinate with cash flow planning

### For AP_CARD Payments
1. ✅ Always set a specific `processDate`
2. ✅ Consider card billing cycles
3. ✅ Ensure sufficient credit limit

### For New Vendor Bank Accounts
1. ✅ Use "+2 Business Days" button automatically
2. ✅ Inform vendor of initial delay (first payment only)
3. ✅ Subsequent payments process faster

### For Regular Bank Account Payments
1. ✅ Leave `processDate` empty to use Bill.com's next available date
2. ✅ Or set specific date if needed for cash flow planning
3. ✅ Bill.com will schedule optimally if not specified

## 🔍 Troubleshooting

### Problem: Payment fails with date error
**Steps**:
1. Check funding account type
2. If WALLET/AP_CARD, ensure `processDate` is set
3. If new vendor, ensure date is +2 business days
4. Verify date format is YYYY-MM-DD

### Problem: Can't see Process Date field
**Steps**:
1. Check `billcom_funding_account_type` field
2. Change to WALLET or AP_CARD to make field visible
3. Field is intentionally hidden for other types

### Problem: Date is in the past
**Steps**:
1. Bill.com rejects past dates
2. Use current date or future date only
3. Click "+2 Business Days" for safe default

## 📚 Related Documentation

- [Bill.com API v3 - Payments](https://developer.bill.com/hc/en-us/articles/360035196552-Create-a-payment)
- [Bill.com - Funding Accounts](https://developer.bill.com/hc/en-us/articles/360035196872-Funding-accounts)
- [Odoo Payment Module](./README.md#payments)

## 🔗 Code References

- Payment model: `models/account_payment.py:142` (`_prepare_payment_data`)
- Process date logic: `models/account_payment.py:161-188`
- Business days helper: `models/account_payment.py:94-116`
- UI button action: `models/account_payment.py:118-140`
- View definition: `views/account_payment_views.xml:61-79`
