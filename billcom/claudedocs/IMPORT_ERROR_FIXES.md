# Bill.com Import Error Fixes

## Issues Identified from Import Log

Based on the import log from Bill.com wizard sync, two critical errors were preventing
bills and invoices from being created:

### Error 1: Journal Configuration for Vendor Bills

**Error Message**: `No journal could be found in company YourCompany for vendor bills`

**Affected**: 20 bills failed to import

**Root Cause**:

- Bill creation code was missing `journal_id` field in the values dictionary
- Odoo requires a journal to create accounting moves (bills/invoices)
- Without explicit journal specification, Odoo tries to find default journal and fails
  if none configured

**Solution**: Added automatic journal lookup before creating bills:

```python
# Get default vendor bill journal
company = vendor.company_id or self.env.company
journal = self.env['account.journal'].search([
    ('type', '=', 'purchase'),
    ('company_id', '=', company.id),
], limit=1)

if not journal:
    raise UserError(f"No purchase journal found for company {company.name}. Please configure a purchase journal.")

# Add journal_id to bill values
bill_vals = {
    'move_type': 'in_invoice',
    'partner_id': vendor.id,
    'journal_id': journal.id,  # <-- Added
    # ... other fields
}
```

**Locations Fixed**:

1. `_process_bill_from_billcom()` method (line 1491-1514) - New queue-based sync
2. `sync_bills_from_billcom()` method (line 751-774) - Legacy sync

### Error 2: Invoice Customer ID Missing

**Error Messages**:

- `Customer with BILL ID None not found for invoice`
- `Customer must be synced first. BILL Customer ID: None`

**Affected**: 10 invoices failed to import

**Root Cause**: According to Bill.com API v3 documentation, invoices can be created in
two ways:

1. With existing customer: Uses `customer.id` field (starts with "0cu")
2. With new customer: Uses `name` and `email` fields instead of ID

The original code only checked for `customer.id` or `customerId`, failing when these
were None.

**Solution**: Enhanced customer lookup with fallback logic:

```python
# Try to find customer by BILL ID
customer = None
if customer_billcom_id:
    customer = self.env['res.partner'].search([
        ('billcom_id', '=', customer_billcom_id),
        ('customer_rank', '>', 0)
    ], limit=1)

# If no customer ID or not found, try by email or name
if not customer:
    customer_email = customer_data.get('email') if isinstance(customer_data, dict) else billcom_data.get('email')
    customer_name = customer_data.get('name') if isinstance(customer_data, dict) else billcom_data.get('name')

    if customer_email:
        customer = self.env['res.partner'].search([
            ('email', '=', customer_email),
            ('customer_rank', '>', 0)
        ], limit=1)

    if not customer and customer_name:
        customer = self.env['res.partner'].search([
            ('name', '=', customer_name),
            ('customer_rank', '>', 0)
        ], limit=1)

if not customer:
    _logger.error(f"Customer not found for invoice {billcom_invoice_id}. BILL Customer ID: {customer_billcom_id}, Email: {customer_data.get('email')}, Name: {customer_data.get('name')}")
    raise UserError(f"Customer must be synced first or created manually. BILL Customer ID: {customer_billcom_id}")
```

**Locations Fixed**:

- `_process_invoice_from_billcom()` method (line 1606-1637)

### Error 3: Journal Configuration for Customer Invoices

**Similar to Error 1, but for invoices**

**Solution**: Added automatic journal lookup for customer invoices:

```python
# Get default customer invoice journal
company = customer.company_id or self.env.company
journal = self.env['account.journal'].search([
    ('type', '=', 'sale'),
    ('company_id', '=', company.id),
], limit=1)

if not journal:
    raise UserError(f"No sale journal found for company {company.name}. Please configure a sale journal.")

# Add journal_id to invoice values
invoice_vals = {
    'move_type': 'out_invoice',
    'partner_id': customer.id,
    'journal_id': journal.id,  # <-- Added
    # ... other fields
}
```

**Locations Fixed**:

1. `_process_invoice_from_billcom()` method (line 1643-1666) - New queue-based sync
2. `sync_invoices_from_billcom()` method (line 886-909) - Legacy sync

## Bill.com API v3 Reference

### Invoices - Customer Identification

From Bill.com API v3 docs:

> In your POST /v3/invoices, set the required fields:
>
> - **id**: BILL-generated ID of the customer you want to associate the invoice to. This
>   value begins with 0cu.
> - **To create a new customer with the invoice, set name and email instead of a
>   customer id.**

This explains why some invoices have `customerId: None` - they were created with
customer name/email instead of ID.

### Bills - Required Fields

From Bill.com API v3 docs:

> - **vendorId**: BILL-generated ID of the vendor you want to pay. The value begins
>   with 009.
> - **dueDate**: Bill due date. The value is in the yyyy-MM-dd format.
> - **billLineItems**: In the billLineItems array, set amount as the bill line item
>   amount.
> - **invoiceNumber**: Bill invoice number.
> - **invoiceDate**: Bill invoice sent date.

Bills always have vendorId, but journals are Odoo-specific requirement not in Bill.com
API.

## Testing Recommendations

### For Bills

1. Ensure at least one purchase journal exists for each company:

   - Go to Accounting → Configuration → Journals
   - Create a purchase journal if none exists
   - Type: Purchase
   - Company: Select company

2. Test bill import:
   - Run Bill.com wizard import
   - Verify bills are created without journal errors
   - Check that `journal_id` is populated on created bills

### For Invoices

1. Ensure at least one sale journal exists for each company:

   - Go to Accounting → Configuration → Journals
   - Create a sale journal if none exists
   - Type: Sales
   - Company: Select company

2. Test invoice import scenarios:

   - **Scenario 1**: Invoice with customer ID → should find customer by billcom_id
   - **Scenario 2**: Invoice with customer email → should find customer by email
   - **Scenario 3**: Invoice with customer name → should find customer by name
   - **Scenario 4**: Invoice with no matching customer → should fail with clear error
     message

3. Verify invoice creation:
   - Run Bill.com wizard import
   - Verify invoices are created without journal or customer errors
   - Check that `journal_id` and `partner_id` are populated

## Performance Impact

**Minimal Performance Impact**:

- Journal lookup is one additional search per bill/invoice
- Searches are indexed (type + company_id)
- Journal results can be cached if needed

**Error Handling Improvements**:

- Clear error messages for missing journals
- Detailed error messages for missing customers
- Fallback customer lookup prevents unnecessary failures

## Files Modified

1. **models/billcom_service.py**:
   - `_process_bill_from_billcom()` - Added journal lookup for new queue-based bill sync
   - `sync_bills_from_billcom()` - Added journal lookup for legacy bill sync
   - `_process_invoice_from_billcom()` - Added journal lookup and enhanced customer
     lookup
   - `sync_invoices_from_billcom()` - Added journal lookup for legacy invoice sync

## Deployment Notes

### Upgrade Steps

```bash
# Update module
docker-compose exec odoo odoo -u billcom -d your_database
```

### Post-Upgrade Verification

1. Check that purchase journals exist for all companies
2. Check that sale journals exist for all companies
3. Run import wizard to test bill/invoice creation
4. Monitor logs for any journal or customer errors

### Configuration Requirements

**Before importing bills/invoices**:

- ✅ Purchase journal configured for vendor bills
- ✅ Sale journal configured for customer invoices
- ✅ Customers synced or created in Odoo before importing invoices

**Optional Optimization**:

- Configure default purchase journal in billcom.config
- Configure default sale journal in billcom.config
- This would eliminate journal search on each import
