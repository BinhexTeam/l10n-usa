# Bill.com Integration - Rediseño de Arquitectura

## Objetivo

Centralizar TODAS las conexiones y sincronizaciones en `billcom_service.py` para tener
una arquitectura robusta, mantenible y consistente.

## Principios de Diseño

1. **Separation of Concerns**: Cada capa tiene una responsabilidad específica
2. **Single Source of Truth**: `billcom_service.py` es el ÚNICO punto de contacto con la
   API de Bill.com
3. **Delegation Pattern**: Los modelos delegan TODA la lógica de sincronización al
   servicio
4. **Error Handling Consistency**: Manejo de errores uniforme en toda la aplicación
5. **API Versioning**: URLs correctas según Bill.com API v3

## Capas de la Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                      │
│  - Controllers (webhooks, API endpoints)                     │
│  - Views (forms, wizards)                                    │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     BUSINESS LOGIC LAYER                     │
│  - Models (res_partner, account_move, account_payment)      │
│  - Simple delegation methods ONLY                            │
│  - NO API calls, NO complex logic                            │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER (Core)                      │
│  billcom_service.py - CENTRALIZED API LOGIC                 │
│  ├─ Connection Management                                    │
│  ├─ Synchronization Logic                                    │
│  ├─ Data Transformation                                      │
│  ├─ Error Handling                                           │
│  └─ Retry Logic                                              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 ABSTRACT SERVICE LAYER                       │
│  billcom_service_abstract.py                                 │
│  ├─ Authentication (including MFA)                           │
│  ├─ Token Management                                         │
│  ├─ HTTP Request Handling                                    │
│  └─ Low-level API Communication                              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     EXTERNAL API                             │
│            Bill.com API v3 (HTTPS/REST)                      │
└─────────────────────────────────────────────────────────────┘
```

## Métodos Centralizados en billcom_service.py

### 1. Partner Synchronization

```python
# TO Bill.com (Odoo → Bill.com)
sync_partner(partner, partner_type)          # Single partner sync
sync_vendor_bank_account(partner)            # Bank account sync

# FROM Bill.com (Bill.com → Odoo)
sync_partners_from_billcom(partner_type)     # Bulk sync from Bill.com
sync_partner_from_billcom_by_id(id, type)    # Single partner by ID

# Cron Jobs
sync_partners_cron()                         # Scheduled sync
```

### 2. Bill Synchronization

```python
# TO Bill.com
sync_bill(move)                              # Single bill sync
sync_bills_by_domain(domain)                 # Bulk bill sync

# FROM Bill.com
sync_bills_from_billcom()                    # Get bills from Bill.com
sync_bill_status(move)                       # Update bill status
```

### 3. Payment Synchronization

```python
# TO Bill.com
create_payment(payment_data)                 # Create payment
sync_payment(payment)                        # Sync payment status

# FROM Bill.com
sync_payments_from_billcom()                 # Get payments
update_payment_status(payment_id)            # Update from webhook
```

### 4. Webhook Handlers

```python
handle_webhook(webhook_data)                 # Main webhook router
process_vendor_webhook(data)                 # Vendor events
process_bill_webhook(data)                   # Bill events
process_payment_webhook(data)                # Payment events
```

## Bill.com API v3 Endpoints

### Vendors/Customers

- `POST /v3/vendors` - Create vendor
- `GET /v3/vendors` - List vendors
- `GET /v3/vendors/{id}` - Get vendor
- `PATCH /v3/vendors/{id}` - Update vendor
- `DELETE /v3/vendors/{id}` - Delete vendor

- `POST /v3/customers` - Create customer
- `GET /v3/customers` - List customers
- `GET /v3/customers/{id}` - Get customer
- `PATCH /v3/customers/{id}` - Update customer

### Bank Accounts

- `POST /v3/vendors/{id}/bank-account` - Create vendor bank account
- `GET /v3/vendors/{id}/bank-account` - Get vendor bank account
- `DELETE /v3/vendors/{id}/bank-account` - Delete vendor bank account

### Bills

- `POST /v3/bills` - Create bill
- `GET /v3/bills` - List bills
- `GET /v3/bills/{id}` - Get bill
- `PATCH /v3/bills/{id}` - Update bill
- `DELETE /v3/bills/{id}` - Delete bill

### Payments

- `POST /v3/payments` - Create payment (requires MFA-trusted session)
- `GET /v3/payments` - List payments
- `GET /v3/payments/{id}` - Get payment
- `PATCH /v3/payments/{id}` - Update payment

### Authentication & MFA

- `POST /v3/login` - Basic authentication
- `POST /v3/mfa/challenge` - Generate MFA challenge
- `POST /v3/mfa/challenge/validate` - Validate MFA code
- `POST /v3/mfa/step-up` - Upgrade session to MFA-trusted

## Delegation Pattern in Models

### ❌ ANTES (Código disperso)

```python
# res_partner.py
def sync_to_billcom(self):
    endpoint = "vendors" if self.supplier_rank else "customers"
    data = self._prepare_partner_data()
    result = self.env["billcom.service"]._make_request(endpoint, "POST", data)
    # 50+ lines of processing logic...
```

### ✅ DESPUÉS (Delegación limpia)

```python
# res_partner.py
def sync_to_billcom(self, partner_type="vendor"):
    """Sync partner to Bill.com - delegates to service"""
    service = self.env["billcom.service"]
    return service.sync_partner(self, partner_type)
```

## Error Handling Strategy

### 1. Webhook Errors

- **Fix**: Usar `request.get_json_data()` en lugar de `request.jsonrequest`
- **Fix**: Verificar `if webhook_log:` antes de llamar `webhook_log.mark_error()`
- **Rationale**: Evitar AttributeError cuando webhook_log es None

### 2. API Errors

- Capturar errores específicos de Bill.com (BDC_xxxx codes)
- Logging consistente en todos los niveles
- UserError con mensajes claros para el usuario
- Retry logic para errores transitorios

### 3. MFA Errors

- BDC_1358: Too many attempts → Wait 5-10 minutes
- BDC_1361: Untrusted session → Perform MFA step-up
- BDC_1374: Expired token → Request new MFA challenge

## URLs Correctas por Tipo

### Vendors

```python
# Create
POST /v3/vendors
body: {vendor_data}

# Update
PATCH /v3/vendors/{vendor_id}
body: {updated_data}

# Get
GET /v3/vendors/{vendor_id}

# Bank Account
POST /v3/vendors/{vendor_id}/bank-account
GET /v3/vendors/{vendor_id}/bank-account
```

### Customers

```python
# Create
POST /v3/customers
body: {customer_data}

# Update
PATCH /v3/customers/{customer_id}
body: {updated_data}
```

## Testing Strategy

1. **Unit Tests**: Probar cada método del servicio individualmente
2. **Integration Tests**: Probar flujo completo Odoo ↔ Bill.com
3. **Error Tests**: Simular errores de API y verificar manejo
4. **MFA Tests**: Verificar flujo completo de MFA setup y step-up

## Migration Path

1. ✅ Fix webhook JSON request error
2. ✅ Fix webhook error handling
3. ✅ Move sync logic from models to service
4. ⏳ Add missing service methods
5. ⏳ Update all URL endpoints
6. ⏳ Test all synchronization flows
7. ⏳ Document API usage patterns

## Benefits

1. **Maintainability**: Un solo lugar para cambiar lógica de API
2. **Consistency**: Mismo patrón de error handling en todos lados
3. **Testability**: Fácil de hacer unit tests del servicio
4. **Debugging**: Logs centralizados, fácil de rastrear
5. **Scalability**: Fácil agregar nuevos endpoints
6. **Documentation**: Arquitectura clara y documentada
