# MFA Lazy Loading Implementation

## 🎯 Overview

MFA authentication is **ONLY** used for payment creation operations
(`POST /v3/payments`). All other operations (vendors, customers, bills, etc.) use
regular authentication without MFA.

This lazy loading approach:

- ✅ Reduces unnecessary MFA step-up operations
- ✅ Improves performance for non-payment operations
- ✅ Only triggers MFA when actually needed
- ✅ Follows Bill.com's recommended authentication flow

---

## 🔄 Two-Token System

### Regular Token (No MFA)

Used for:

- Vendors: `GET /v3/vendors`, `POST /v3/vendors`, `PATCH /v3/vendors/{id}`
- Customers: `GET /v3/customers`, `POST /v3/customers`, `PATCH /v3/customers/{id}`
- Bills: `GET /v3/bills`, `POST /v3/bills`, `PATCH /v3/bills/{id}`
- Bank Accounts: `GET /v3/vendors/{id}/bank-account`,
  `POST /v3/vendors/{id}/bank-account`
- Any other Bill.com API operations

**How it works**: `_get_token()` → `POST /v3/login` → sessionId (regular)

### MFA-Trusted Token

Used for:

- Payments: `POST /v3/payments` (CREATE ONLY)

**How it works**:

1. `_get_mfa_token()` → calls `_get_token()` first
2. Checks if `mfa_remember_me_id` is configured
3. Calls `_mfa_step_up()` which:
   - `GET /v3/login/session` → check mfaStatus
   - If mfaStatus != "COMPLETE" → `POST /v3/mfa/step-up`
4. Returns MFA-trusted sessionId

---

## 📂 Implementation Details

### File: `models/billcom_service_abstract.py`

#### Method: `_get_mfa_token()` (Lines 199-236)

```python
@api.model
def _get_mfa_token(self):
    """Get MFA-trusted token for payment operations

    This method ensures the session has MFA trust by:
    1. Getting regular token (or using cached one)
    2. Checking if rememberMeId is configured
    3. Checking MFA status via GET /v3/login/session
    4. Performing step-up if needed

    ONLY call this for operations requiring MFA (e.g., POST /v3/payments)
    """
    config = self._get_config()

    # Get regular token first (will use cached if valid)
    token = self._get_token()

    # Check if we have rememberMeId for step-up
    if not config.mfa_remember_me_id:
        raise UserError(_(
            "MFA authentication is required for payment creation.\n\n"
            "Please use 'Setup MFA' button to configure MFA."
        ))

    # Perform MFA step-up (will check status first and skip if already COMPLETE)
    self._mfa_step_up(config, token)

    return token
```

#### Method: `_execute_request()` - Smart Token Selection (Lines 260-277)

```python
def _execute_request(self, endpoint, method, data, params, config, ...):
    """Execute a single API request attempt"""
    # Determine if this is a payment creation operation requiring MFA
    is_payment_creation = (
        method == "POST" and
        endpoint.rstrip('/') == "payments"
    )

    # Get appropriate token based on operation type
    if is_payment_creation:
        _logger.info("Payment creation detected - using MFA-trusted token")
        token = self._get_mfa_token()
    else:
        # Regular operations use regular token (no MFA)
        token = self._get_token()

    # ... continue with request
```

#### Token Retry Logic (Lines 322-327)

When token expires (BDC_1361) and needs refresh:

```python
# Retry with appropriate token type (MFA if payment, regular otherwise)
if is_payment_creation:
    new_token = self._get_mfa_token()
else:
    new_token = config.token
```

---

## 🔍 Detection Logic

The system detects payment creation by checking:

```python
is_payment_creation = (
    method == "POST" and          # Creating (not reading)
    endpoint.rstrip('/') == "payments"  # Payments endpoint
)
```

**Matches**:

- `POST /v3/payments` ✅

**Does NOT match**:

- `GET /v3/payments` ❌ (reading, no MFA needed)
- `GET /v3/payments/{id}` ❌ (reading specific payment)
- `POST /v3/vendors` ❌ (different endpoint)
- `POST /v3/bills` ❌ (different endpoint)

---

## 📊 Flow Diagrams

### Payment Creation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  User creates payment in Odoo                                │
│  → account_payment.button_sync_to_billcom()                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  billcom.service._make_request("payments", POST, data)       │
│  → _execute_request()                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Detection: is_payment_creation = True                       │
│  (method=POST, endpoint=payments)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  token = _get_mfa_token()                                    │
│    ├─ Get regular token: _get_token()                        │
│    ├─ Check rememberMeId configured                          │
│    └─ Perform MFA step-up: _mfa_step_up()                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  _mfa_step_up(config, token)                                 │
│    ├─ GET /v3/login/session → mfaStatus                      │
│    ├─ If COMPLETE → return (skip step-up)                    │
│    └─ If not COMPLETE → POST /v3/mfa/step-up                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  POST /v3/payments with MFA-trusted sessionId                │
│  → Payment created successfully                              │
└─────────────────────────────────────────────────────────────┘
```

### Vendor Sync Flow (No MFA)

```
┌─────────────────────────────────────────────────────────────┐
│  User syncs vendor in Odoo                                   │
│  → res_partner.sync_to_billcom_vendor()                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  billcom.service._make_request("vendors", POST, data)        │
│  → _execute_request()                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Detection: is_payment_creation = False                      │
│  (method=POST, endpoint=vendors ≠ payments)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  token = _get_token()  ← Regular token, NO MFA               │
│    └─ POST /v3/login → sessionId                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  POST /v3/vendors with regular sessionId                     │
│  → Vendor created successfully (no MFA needed)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing

### Test 1: Vendor Sync (No MFA Required)

```bash
# Watch logs
docker-compose logs -f odoo | grep -E "token|MFA|vendor"

# In Odoo:
# 1. Go to Contacts
# 2. Create/edit vendor
# 3. Click "Sync to Bill.com"

# Expected logs:
# "Regular operations use regular token (no MFA)"
# NO logs about "Payment creation detected"
# NO logs about "_get_mfa_token"
# NO logs about "MFA step-up"
```

### Test 2: Payment Creation (MFA Required)

```bash
# Watch logs
docker-compose logs -f odoo | grep -E "token|MFA|payment"

# In Odoo:
# 1. Go to Accounting → Vendors → Bills
# 2. Create a bill, post it
# 3. Click "Register Payment"
# 4. Complete payment and validate

# Expected logs:
# "Payment creation detected - using MFA-trusted token"
# "Payment operation requested - ensuring MFA-trusted session"
# "Checking MFA status at: .../v3/login/session"
# "Current MFA status: INCOMPLETE" (or COMPLETE)
# If INCOMPLETE: "MFA status is 'INCOMPLETE' - performing step-up"
# If COMPLETE: "Session already has MFA COMPLETE status - no step-up needed"
# "✅ MFA-trusted token ready for payment operation"
```

### Test 3: MFA Not Configured

```bash
# Ensure MFA is NOT configured
# In Odoo: Settings → Bill.com Config → Clear "MFA Remember Me ID"

# Try to create payment
# Should fail with:
# "MFA authentication is required for payment creation.
#  Please use 'Setup MFA' button to configure MFA."
```

### Test 4: Multiple Operations

```bash
# Perform multiple operations in sequence:
# 1. Sync 3 vendors → Should use regular token 3 times (no MFA)
# 2. Create 1 payment → Should use MFA token 1 time
# 3. Sync 2 customers → Should use regular token 2 times (no MFA)

# Verify in logs:
# - 5 regular token uses
# - 1 MFA token use
# - Total 6 operations, only 1 with MFA
```

---

## 🔧 Troubleshooting

### Issue: "MFA authentication is required for payment creation"

**Cause**: No `mfa_remember_me_id` configured

**Solution**:

1. Go to Settings → Bill.com Configuration
2. Click "Setup MFA (Automated)"
3. Enter SMS code
4. Verify `mfa_remember_me_id` is saved

### Issue: Payment creation slow

**Cause**: MFA step-up happening every time

**Check logs for**:

```
"MFA status is 'INCOMPLETE' - performing step-up"
```

If you see this on EVERY payment, the session is not staying MFA-trusted.

**Solution**: Check that token is being cached properly in config.

### Issue: Regular operations failing

**Cause**: If ALL operations require MFA (misconfiguration)

**Check**: Detection logic should only match `POST /v3/payments` exactly

**Verify in code**: `billcom_service_abstract.py:265-268`

---

## 📚 Related Documentation

- `claudedocs/MFA_QUICK_GUIDE.md` - MFA setup guide
- `claudedocs/MFA_STEP_UP_FIX.md` - MFA status check implementation
- `claudedocs/MFA_REMEMBER_ME_EXPIRED.md` - Handle expired rememberMeId
- `claudedocs/DEPLOYMENT_GUIDE.md` - Complete deployment guide

---

## ✅ Benefits of Lazy MFA Loading

| Aspect               | Before                          | After                           |
| -------------------- | ------------------------------- | ------------------------------- |
| **Vendor Sync**      | MFA step-up every time          | No MFA (faster)                 |
| **Customer Sync**    | MFA step-up every time          | No MFA (faster)                 |
| **Bill Sync**        | MFA step-up every time          | No MFA (faster)                 |
| **Payment Creation** | MFA step-up every time          | MFA only when needed            |
| **Performance**      | Slow for all operations         | Fast for most operations        |
| **API Calls**        | Extra calls for every operation | Extra calls only for payments   |
| **Error Handling**   | Generic errors                  | Clear "MFA needed for payments" |

---

## 🎯 Summary

**Key Principle**: MFA is ONLY for `POST /v3/payments`, nothing else.

**Implementation**:

- Regular token: `_get_token()` for all operations
- MFA token: `_get_mfa_token()` ONLY for payment creation
- Smart detection: Check endpoint and method before choosing token type
- Token retry: Use appropriate token type when refreshing

**Result**: Faster, more efficient integration with clear separation of concerns.
