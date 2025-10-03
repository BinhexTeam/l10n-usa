# Invoice Customer Lookup Fix

## 🐛 Problem

When syncing invoices from Bill.com → Odoo, all invoices were failing with error:

```
Customer not found for invoice 00e02BZTBEBDFDESw5ko.
BILL Customer ID: None, Email: None, Name: None
Error: Customer must be synced first or created manually. BILL Customer ID: None
```

---

## 🔍 Root Cause

**File**: `models/billcom_service.py:1618-1620`

### ❌ Original Code (WRONG)

```python
customer_data = billcom_data.get('customer', {})
customer_billcom_id = customer_data.get('id') if isinstance(customer_data, dict) else billcom_data.get('customerId')
```

**Problem**:

1. Line tries to get nested `customer` object first: `billcom_data.get('customer', {})`
2. When `customer` doesn't exist, returns empty dict `{}`
3. `isinstance({}, dict)` → `True` (empty dict is still a dict!)
4. Tries `{}.get('id')` → `None`
5. **NEVER reaches** `billcom_data.get('customerId')`

### ✅ Bill.com API Response Format

According to actual API response from `/v3/invoices`:

```json
{
  "results": [
    {
      "id": "00e02BZTBEBDFDESw5ko",
      "invoiceNumber": "202502",
      "customerId": "0cu02TXNTXPYFNI16n6b",    ← DIRECT FIELD (not nested)
      "totalAmount": 79.98,
      "invoiceLineItems": [...]
    }
  ]
}
```

**Key Point**: Bill.com API returns `customerId` as a **direct field**, NOT a nested
`customer` object.

---

## ✅ Solution

**File**: `models/billcom_service.py:1618-1625`

```python
# Find customer - BILL API v3 returns customerId directly (not nested)
# Format: { "customerId": "0cu02TXNTXPYFNI16n6b", ... }
customer_billcom_id = billcom_data.get('customerId')

# Fallback: Try nested customer object (in case API changes or uses different format)
customer_data = billcom_data.get('customer', {})
if not customer_billcom_id and isinstance(customer_data, dict):
    customer_billcom_id = customer_data.get('id')
```

### Changes Made

1. **Primary**: Read `customerId` directly from invoice data
2. **Fallback**: If `customerId` not found, try nested `customer` object (for API
   compatibility)
3. **Define `customer_data` early**: Avoid "possibly unbound" errors in subsequent code

### Improved Error Message

```python
if not customer:
    _logger.error(
        "Customer not found for invoice %s. "
        "BILL Customer ID: %s. "
        "Please sync customers from Bill.com first.",
        billcom_invoice_id,
        customer_billcom_id or "None"
    )
    raise UserError(
        f"Customer with Bill.com ID '{customer_billcom_id}' not found in Odoo.\n\n"
        f"Please sync customers from Bill.com first using the sync wizard,\n"
        f"or create the customer manually and set their Bill.com ID."
    )
```

**Benefits**:

- Clear error message with actual customer ID
- Instructs user how to fix (sync customers first)
- Better logging for troubleshooting

---

## 🧪 Testing

### Test 1: Sync Invoices (Customers Already Synced)

**Prerequisites**:

- Customers synced from Bill.com (have `billcom_id` set)

**Steps**:

1. Open Accounting → Sync Wizard
2. Select "Invoice" sync type
3. Direction: "From Bill.com"
4. Click "Fetch & Process"

**Expected Result**:

- ✅ Invoices sync successfully
- ✅ Each invoice linked to correct customer via `customerId`
- ✅ No "Customer not found" errors

### Test 2: Sync Invoices (Customers NOT Synced)

**Prerequisites**:

- Customers NOT synced (missing from Odoo or no `billcom_id`)

**Steps**:

1. Try to sync invoices

**Expected Result**:

- ❌ Clear error message:

  ```
  Customer with Bill.com ID '0cu02TXNTXPYFNI16n6b' not found in Odoo.

  Please sync customers from Bill.com first using the sync wizard,
  or create the customer manually and set their Bill.com ID.
  ```

- Error includes actual customer ID (not "None")
- User knows exactly what to do

### Test 3: Sync Customers First, Then Invoices

**Steps**:

1. Sync Wizard → Select "Customer" → From Bill.com → Fetch & Process
2. Verify customers created with `billcom_id`
3. Sync Wizard → Select "Invoice" → From Bill.com → Fetch & Process

**Expected Result**:

- ✅ Customers sync successfully
- ✅ Invoices sync successfully
- ✅ Invoices correctly linked to customers

---

## 📊 API Structure Comparison

### Bills vs Invoices

**Bills** (Vendor Bills):

```json
{
  "vendor": {
    "id": "ven123",
    "name": "Vendor Name"
  }
}
```

**Invoices** (Customer Invoices):

```json
{
  "customerId": "0cu02TXNTXPYFNI16n6b"
}
```

**Difference**:

- Bills have nested `vendor` object with details
- Invoices have flat `customerId` field (ID only, no details)

This is why the original code worked for bills but failed for invoices.

---

## 🔄 Related Code

### Wizard: Fetching Invoices

**File**: `wizards/billcom_sync_wizard.py:661-693`

The wizard correctly fetches invoices with their `customerId`:

```python
def _fetch_invoices_from_billcom(self, service, config):
    params = {'status': 'OPEN,APPROVED,PAID'}
    response = service._make_request("invoices", method='GET', params=params)
    invoices_data = response.get('results', [])
    # Each invoice in invoices_data has 'customerId' field
```

No changes needed in wizard - it correctly receives the data.

### Service: Processing Invoices

**File**: `models/billcom_service.py:1609-1665`

Fixed `_process_invoice_from_billcom()` to correctly read `customerId`.

---

## 📚 Related Documentation

- Bill.com API: GET /v3/invoices
- `claudedocs/ARCHITECTURE_REDESIGN.md` - Service layer architecture
- `claudedocs/IMPLEMENTATION_STATUS.md` - Invoice sync implementation

---

## ✅ Verification

After fix:

```bash
# Restart Odoo
docker-compose restart odoo

# Watch logs
docker-compose logs -f odoo | grep -E "invoice|customer|BILL"

# In logs, you should see:
# "Customer found: [Customer Name] (Bill.com ID: 0cu02TXNTXPYFNI16n6b)"
# NOT: "Customer not found for invoice... BILL Customer ID: None"
```

---

## 🎯 Summary

| Aspect              | Before                 | After                               |
| ------------------- | ---------------------- | ----------------------------------- |
| **Customer Lookup** | ❌ Always None         | ✅ Correct ID from API              |
| **Invoice Sync**    | ❌ All fail            | ✅ All succeed (if customers exist) |
| **Error Messages**  | ❌ "Customer ID: None" | ✅ "Customer ID: 0cu02..."          |
| **User Guidance**   | ❌ Vague               | ✅ Clear instructions               |

**Result**: Invoice sync from Bill.com → Odoo now works correctly!
