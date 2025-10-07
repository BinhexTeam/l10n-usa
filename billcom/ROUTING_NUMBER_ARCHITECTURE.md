# Routing Number Architecture

## 🏛️ Correct Architecture

### Conceptual Model

In the US banking system:
- **Routing Number (ABA)**: Identifies the **BANK** (9-digit number)
  - Same for ALL accounts at that bank/branch
  - Should be stored in `res.bank`

- **Account Number**: Identifies the **CUSTOMER'S ACCOUNT** at the bank
  - Unique per customer
  - Should be stored in `res.partner.bank`

### Implementation

#### res.bank (Bank Entity)
```python
class ResBank(models.Model):
    _inherit = "res.bank"

    routing_number = fields.Char(
        string="Routing Number",
        help="Bank routing number (for US banks)"
    )
```

#### res.partner.bank (Bank Account Entity)
```python
class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    routing_number = fields.Char(
        related="bank_id.routing_number",
        readonly=False,
        string="Bill.com Routing Number",
        help="Bank routing number (for US banks)",
        copy=False,
    )
```

## 🔄 Compatibility with l10n_us

### The Problem

The `l10n_us` module adds `aba_routing` field to `res.partner.bank` instead of `res.bank`:
- **Architecturally incorrect**: Routing number is a bank property, not account property
- **Practical reason**: Works without properly configured `res.bank` records
- **Legacy support**: Many installations don't maintain bank records

### Our Solution

**Priority-based routing number resolution**:

```python
routing_number = (
    bank.routing_number                                           # 1️⃣ Preferred: Our field in res.bank
    or (bank.aba_routing if hasattr(bank, "aba_routing") else None)  # 2️⃣ Fallback: l10n_us field
    or (bank.bank_id.routing_number if bank.bank_id else None)      # 3️⃣ From related bank
)
```

**This approach**:
- ✅ Uses correct architecture when available
- ✅ Falls back to l10n_us field for compatibility
- ✅ Doesn't break existing installations
- ✅ Gradual migration path to correct model

## 📊 Data Flow

### Creating Bank Account for Bill.com

```
┌─────────────────────────────────────────┐
│  User enters routing number in Odoo     │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Stored in res.bank.routing_number      │
│  (or res.partner.bank.aba_routing if    │
│   using l10n_us)                        │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Priority resolution in code:           │
│  1. bank.routing_number                 │
│  2. bank.aba_routing (l10n_us)         │
│  3. bank.bank_id.routing_number        │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Sent to Bill.com API in                │
│  paymentInformation.bankAccount.        │
│  routingNumber                          │
└─────────────────────────────────────────┘
```

### Syncing from Bill.com

```
┌─────────────────────────────────────────┐
│  Bill.com returns routingNumber         │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Search for bank by routing_number      │
│  in res.bank                            │
└────────────────┬────────────────────────┘
                 │
                 ▼
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   ┌─────────┐      ┌──────────┐
   │  Found  │      │ Not Found│
   └────┬────┘      └─────┬────┘
        │                 │
        │                 ▼
        │          ┌──────────────────┐
        │          │  Create res.bank │
        │          │  with routing_   │
        │          │  number          │
        │          └────────┬─────────┘
        │                   │
        └───────┬───────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│  Create/update res.partner.bank         │
│  linked to res.bank                     │
│  (routing_number accessible via         │
│   related field)                        │
└─────────────────────────────────────────┘
```

## 🔧 Implementation Details

### Files Modified

1. **models/res_partner.py**
   - Lines 208-211: Added `routing_number` to `res.bank`
   - Lines 229-235: Added related `routing_number` to `res.partner.bank`
   - Lines 100-105: Priority-based routing number in `_prepare_partner_data()`
   - Lines 333-338: Priority-based routing number in `sync_bank_account_to_billcom()`
   - Lines 354-359: Priority-based routing number in bank account data prep

2. **models/billcom_service.py**
   - Lines 634-640: Priority-based routing number in `sync_vendor_bank_account()`
   - Lines 1796-1807: Search/create bank by `routing_number`

3. **views/res_bank_views.xml**
   - Lines 10-11: Added `routing_number` field to bank form

4. **views/res_partner_bank_views.xml**
   - Lines 20-22: Display `routing_number` in bank account form

5. **__manifest__.py**
   - Line 12: Added dependency on `l10n_us` for compatibility
   - Line 41: Added `res_bank_views.xml`

## ✅ Benefits

### Architectural Benefits
1. **Correct Data Model**: Bank properties in bank entity, account properties in account entity
2. **Data Integrity**: One source of truth for routing numbers (the bank)
3. **Reduced Redundancy**: No duplicate routing numbers across multiple accounts

### Operational Benefits
1. **Easy Bank Updates**: Change routing number once in bank, affects all accounts
2. **Better Validation**: Can validate routing number at bank level
3. **Clearer Relationships**: Clear bank-account hierarchy

### Integration Benefits
1. **Bill.com Compatibility**: Works seamlessly with Bill.com API requirements
2. **l10n_us Compatibility**: Falls back gracefully to existing fields
3. **Migration Path**: Smooth transition from old to new architecture

## 📝 Usage Examples

### Creating a Bank Account (Recommended Way)

```python
# 1. Create or find bank with routing number
bank = env['res.bank'].create({
    'name': 'Chase Bank',
    'routing_number': '021000021',  # Stored at bank level ✅
})

# 2. Create bank account linked to bank
bank_account = env['res.partner.bank'].create({
    'partner_id': partner.id,
    'acc_number': '1234567890',
    'bank_id': bank.id,
    # routing_number is automatically available via related field
})

# 3. Access routing number
print(bank_account.routing_number)  # '021000021' (from bank)
```

### Legacy Compatibility (l10n_us)

```python
# If using l10n_us module, aba_routing still works
bank_account = env['res.partner.bank'].create({
    'partner_id': partner.id,
    'acc_number': '1234567890',
    'aba_routing': '021000021',  # Old way, still supported
})

# Code automatically prioritizes fields:
# 1. bank.routing_number (if available)
# 2. bank.aba_routing (fallback)
# 3. bank.bank_id.routing_number (double fallback)
```

## 🎯 Migration Strategy

For existing installations with `aba_routing`:

1. **Phase 1 - Dual Support** (Current)
   - Support both `routing_number` (correct) and `aba_routing` (legacy)
   - Priority-based resolution
   - No breaking changes

2. **Phase 2 - Data Migration** (Future)
   - Script to migrate `aba_routing` to bank-level `routing_number`
   - Create missing `res.bank` records
   - Link accounts to correct banks

3. **Phase 3 - Cleanup** (Future)
   - Remove `aba_routing` dependency
   - Enforce `routing_number` at bank level
   - Full architectural compliance

## 📚 References

- [ABA Routing Number (Wikipedia)](https://en.wikipedia.org/wiki/ABA_routing_transit_number)
- [Bill.com Bank Account API](https://developer.bill.com/reference/createvendorbankaccount)
- [Odoo res.bank Model](https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/models/res_bank.py)
- [l10n_us Module](https://github.com/odoo/odoo/blob/16.0/addons/l10n_us/models/res_partner_bank.py)
