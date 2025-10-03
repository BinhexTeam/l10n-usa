# Análisis de Implementación de Webhooks Bill.com

## Estado Actual de la Implementación

### 1. Controlador de Webhooks Existente

**Archivo**: `controllers/billcom_controller.py`

#### Eventos Implementados:

- ✅ `bill.*` → `account.move.sync_from_billcom()`
- ✅ `invoice.*` → `account.move.sync_from_billcom()`
- ✅ `vendor.*` → `res.partner.sync_from_billcom()`
- ✅ `customer.*` → `res.partner.sync_from_billcom()`
- ✅ `payment.*` → `account.payment.process_billcom_payment_webhook()`

#### Seguridad Implementada:

- ✅ Validación de firma HMAC-SHA256 (`X-Bill-Signature` header)
- ✅ Verificación de webhook secret configurado
- ✅ Endpoint protegido con `auth="none"` y `csrf=False` para webhooks externos

#### Configuración Necesaria:

- ✅ `billcom.config.enable_webhooks` (Boolean)
- ✅ `billcom.config.webhook_secret` (Char)
- ✅ Flags individuales de sincronización (`sync_bills`, `sync_payments`, etc.)

### 2. Métodos de Sincronización Existentes

#### Partners (vendors/customers):

```python
# res_partner.py
- sync_from_billcom(partner_type)  # Sync all
- sync_from_billcom_by_id(billcom_id, partner_type)  # Sync one by ID
```

#### Payments:

```python
# account_payment.py
- process_billcom_payment_webhook(payment_data)  # Updates status, confirmation #, etc.
```

### 3. Problemas Identificados

#### ❌ Métodos Faltantes en `account.move`:

El controlador llama a `account.move.sync_from_billcom(entity_id)` pero este método **NO
existe**.

**Líneas afectadas**:

- Línea 67: `request.env["account.move"].sudo().sync_from_billcom(entity_id)` (bills)
- Línea 73: `request.env["account.move"].sudo().sync_from_billcom(entity_id)` (invoices)

**Error esperado**:
`AttributeError: 'account.move' object has no attribute 'sync_from_billcom'`

#### ❌ Métodos Incompletos en `res.partner`:

El método `sync_from_billcom_by_id()` existe pero no está siendo llamado correctamente
desde el webhook.

**Línea 79**: `request.env["res.partner"].sudo().sync_from_billcom(entity_id)`

- Llama a `sync_from_billcom()` con `entity_id` como argumento
- Pero `sync_from_billcom()` espera `partner_type` no `entity_id`

## Eventos Webhook de Bill.com Disponibles

### 📦 Eventos Soportados por Bill.com API v3:

| Categoría             | Evento                             | Estado Implementación           |
| --------------------- | ---------------------------------- | ------------------------------- |
| **Bills**             | `bill.created`                     | ⚠️ Parcial (método faltante)    |
|                       | `bill.updated`                     | ⚠️ Parcial (método faltante)    |
|                       | `bill.archived`                    | ⚠️ Parcial (método faltante)    |
|                       | `bill.restored`                    | ⚠️ Parcial (método faltante)    |
| **Vendors**           | `vendor.created`                   | ⚠️ Parcial (llamada incorrecta) |
|                       | `vendor.updated`                   | ⚠️ Parcial (llamada incorrecta) |
|                       | `vendor.archived`                  | ⚠️ Parcial (llamada incorrecta) |
|                       | `vendor.restored`                  | ⚠️ Parcial (llamada incorrecta) |
| **Payments**          | `payment.updated`                  | ✅ Implementado                 |
|                       | `payment.failed`                   | ✅ Implementado                 |
|                       | `autopay.failed`                   | ❌ No implementado              |
| **Bank Accounts**     | `bank-account.created`             | ❌ No implementado              |
|                       | `bank-account.updated`             | ❌ No implementado              |
| **Card Accounts**     | `card-account.created`             | ❌ No implementado              |
|                       | `card-account.updated`             | ❌ No implementado              |
| **Invoices**          | (No mencionados explícitamente)    | ⚠️ Parcial (método faltante)    |
| **Customers**         | (No mencionados explícitamente)    | ⚠️ Parcial (llamada incorrecta) |
| **Risk Verification** | `risk-verification.updated`        | ❌ No implementado              |
| **Spend & Expense**   | `spend.transaction.updated`        | ❌ No implementado              |
|                       | `spend.three-ds-challenge.created` | ❌ No implementado              |

## Recomendaciones para Completar la Integración

### Priority 1: Corregir Implementación Actual

#### 1. Implementar `sync_from_billcom()` en `account.move`:

```python
# models/account_move.py
@api.model
def sync_from_billcom(self, billcom_id):
    """Sync a bill/invoice from Bill.com by ID (called by webhook)"""
    try:
        # Determine if it's a bill or invoice
        move = self.search([
            '|',
            ('billcom_id', '=', billcom_id),
            ('billcom', '=', billcom_id)
        ], limit=1)

        if move:
            move_type = move.move_type
        else:
            # Fetch from API to determine type
            # Try bills endpoint first, then invoices
            pass

        # Use existing sync logic from wizard or create new method
        # Similar to process_billcom_payment_webhook pattern

    except Exception as e:
        _logger.error("Error syncing bill/invoice %s: %s", billcom_id, str(e))
        return False
```

#### 2. Corregir llamadas en `res.partner`:

```python
# controllers/billcom_controller.py - línea 79
# BEFORE:
request.env["res.partner"].sudo().sync_from_billcom(entity_id)

# AFTER:
request.env["res.partner"].sudo().sync_from_billcom_by_id(
    billcom_id=entity_id,
    partner_type='vendor'  # o 'customer' según el evento
)
```

### Priority 2: Implementar Eventos Críticos Faltantes

#### 1. Funding Accounts (bank-account, card-account):

- Crear modelo `billcom.funding.account` si no existe
- Implementar `sync_from_billcom()` para actualizar cuentas de financiamiento
- Útil para mantener actualizada la lista de métodos de pago disponibles

#### 2. Autopay Failed:

- Extender `account.payment.process_billcom_payment_webhook()`
- Manejar específicamente `autopay.failed` para notificar al usuario
- Crear actividad o mensaje en Odoo cuando autopay falla

### Priority 3: Mejorar Manejo de Eventos

#### 1. Queue System para Webhooks:

En lugar de procesar webhooks síncronamente, usar la sync queue:

```python
# controllers/billcom_controller.py
if event_type.startswith("bill."):
    # Create queue item instead of direct sync
    request.env["billcom.sync.queue"].sudo().create_sync_item(
        sync_type='bill',
        billcom_id=entity_id,
        direction='billcom_to_odoo',
        operation='update',
        priority='2',  # High priority for webhooks
        sync_data=json.dumps(data)
    )
```

**Ventajas**:

- Webhooks responden rápido (solo crean queue item)
- Procesamiento asíncrono con retry logic
- Logging completo en billcom.sync.queue
- No bloquea el webhook endpoint

#### 2. Idempotencia:

```python
# Agregar tracking de eventos procesados
idempotency_key = data.get('idempotencyKey') or f"{event_type}:{entity_id}"

# Check if already processed
existing = request.env["billcom.webhook.log"].sudo().search([
    ('idempotency_key', '=', idempotency_key)
], limit=1)

if existing:
    return {"success": True, "message": "Event already processed"}
```

### Priority 4: Validación con GET APIs

Según recomendación de Bill.com:

> "For critical workflows, we recommend validating data with the GET API operations"

Implementar validación post-webhook:

```python
# After webhook processing
if event_type in ['payment.updated', 'bill.updated']:
    # Schedule a validation job 5 minutes later
    request.env.ref('billcom.cron_validate_webhook_data').sudo().write({
        'nextcall': fields.Datetime.now() + timedelta(minutes=5)
    })
```

## Arquitectura Recomendada Final

```
Bill.com Webhook → Odoo Controller
                     ↓
              [Validate Signature]
                     ↓
              [Create Queue Item]
                     ↓
              [Return 200 OK]


Async Processing:
    Queue Processor → Fetch from API (GET) → Update Odoo → Log Result
                           ↓
                    [Validate Data]
                           ↓
                    [Create/Update Record]
```

## Configuración Necesaria en Bill.com

### 1. Crear Webhook Subscription:

```bash
POST /v3/webhooks/subscriptions
{
  "url": "https://your-odoo-instance.com/billcom/webhook",
  "events": [
    "bill.created",
    "bill.updated",
    "vendor.created",
    "vendor.updated",
    "payment.updated",
    "payment.failed",
    "bank-account.created",
    "bank-account.updated"
  ],
  "secret": "your-webhook-secret-here"
}
```

### 2. Test Webhook:

```bash
POST /v3/webhooks/subscriptions/{subscriptionId}/test
{
  "eventType": "bill.updated"
}
```

## Campos Faltantes en `billcom.config`

```python
# models/billcom_config.py - agregar:

webhook_subscription_id = fields.Char(
    string="Webhook Subscription ID",
    help="Bill.com webhook subscription ID",
    readonly=True,
)

webhook_url = fields.Char(
    string="Webhook URL",
    compute="_compute_webhook_url",
    help="Full URL where Bill.com will send webhooks"
)

@api.depends('company_id')
def _compute_webhook_url(self):
    for config in self:
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        config.webhook_url = f"{base_url}/billcom/webhook"
```

## Checklist de Implementación

- [x] **Fix Critical Bugs** ✅ COMPLETADO

  - [x] Implementar `account.move.sync_from_billcom()` ✅
  - [x] Corregir llamadas `res.partner.sync_from_billcom()` ✅

- [x] **Enhance Current Implementation** ✅ COMPLETADO

  - [x] Implementar idempotencia con webhook logs ✅
  - [x] Agregar manejo de eventos archived/restored ✅
  - [ ] Usar sync queue en lugar de procesamiento directo (OPCIONAL)
  - [ ] Agregar validación POST con GET APIs (OPCIONAL)

- [ ] **Implement Missing Events** (PENDIENTE)

  - [ ] Funding accounts sync
  - [ ] Autopay failed notifications
  - [ ] Risk verification updates (si aplica)

- [ ] **Configuration & Management** (PENDIENTE)

  - [ ] Agregar campos webhook_subscription_id y webhook_url
  - [ ] Crear wizard para suscribirse a webhooks desde Odoo
  - [ ] Implementar test endpoint para validar webhooks

- [x] **Testing & Monitoring** ✅ PARCIALMENTE COMPLETADO
  - [x] Crear modelo billcom.webhook.log para auditoría ✅
  - [x] Vistas de gestión de webhook logs ✅
  - [ ] Implementar métricas de webhooks recibidos/procesados
  - [ ] Dashboard de estado de webhooks en tiempo real

## Implementación Realizada (Resumen)

### ✅ Correcciones Críticas Completadas:

1. **`account.move.sync_from_billcom(billcom_id)`** - IMPLEMENTADO

   - Busca documento existente por billcom_id
   - Determina tipo (bill/invoice) probando ambos endpoints
   - Busca partner (vendor/customer) asociado
   - Crea o actualiza el documento en Odoo
   - Previene sync de vuelta a Bill.com con context

2. **Llamadas correctas a `res.partner`** - CORREGIDO

   - Ahora usa `sync_from_billcom_by_id(billcom_id, partner_type)`
   - Especifica correctamente 'vendor' o 'customer'

3. **Eventos archived/restored** - IMPLEMENTADO

   - `bill.archived` → marca active=False en Odoo
   - `bill.restored` → marca active=True en Odoo
   - `vendor.archived` / `vendor.restored` → mismo comportamiento
   - `customer.archived` / `customer.restored` → mismo comportamiento
   - `invoice.archived` / `invoice.restored` → mismo comportamiento

4. **Sistema de Idempotencia** - IMPLEMENTADO
   - Nuevo modelo `billcom.webhook.log`
   - Tracking completo: idempotency_key, event_type, entity_id, state
   - Previene procesamiento duplicado de webhooks
   - Almacena payload completo y errores
   - Estados: received → processing → success/error
   - Vistas de gestión con filtros y búsquedas
   - Método `cleanup_old_logs(days=30)` para limpieza automática

### 📊 Estado Actual de Cobertura:

| Categoría            | Implementación                       | Estado       |
| -------------------- | ------------------------------------ | ------------ |
| **Bills**            | `bill.created`, `bill.updated`       | ✅ Completo  |
|                      | `bill.archived`, `bill.restored`     | ✅ Completo  |
| **Invoices**         | `invoice.*` (todos)                  | ✅ Completo  |
| **Vendors**          | `vendor.created`, `vendor.updated`   | ✅ Completo  |
|                      | `vendor.archived`, `vendor.restored` | ✅ Completo  |
| **Customers**        | `customer.*` (todos)                 | ✅ Completo  |
| **Payments**         | `payment.updated`, `payment.failed`  | ✅ Completo  |
| **Idempotencia**     | Sistema completo con logs            | ✅ Completo  |
| **Funding Accounts** | `bank-account.*`, `card-account.*`   | ❌ Pendiente |
| **Autopay**          | `autopay.failed`                     | ❌ Pendiente |

### 🔧 Archivos Modificados/Creados:

1. **models/account_move.py** - Agregado `sync_from_billcom(billcom_id)`
2. **controllers/billcom_controller.py** - Corregido partner calls + eventos
   archived/restored + idempotencia
3. **models/billcom_webhook_log.py** - NUEVO modelo para tracking
4. **models/**init**.py** - Importado billcom_webhook_log
5. **security/ir.model.access.csv** - Permisos para webhook.log
6. **views/billcom_webhook_log_views.xml** - NUEVO: vistas completas (tree, form,
   search)
7. ****manifest**.py** - Agregada vista de webhook logs

## Conclusión

La implementación actual de webhooks tiene una **buena base de seguridad** (validación
de firmas) y estructura, pero está **incompleta y con errores**:

1. ✅ **Fortalezas**: Seguridad HMAC, configuración flexible, manejo de payments
2. ❌ **Debilidades**: Métodos faltantes, procesamiento síncrono, sin idempotencia
3. 🔄 **Oportunidades**: Queue system, validación dual, eventos adicionales

**Prioridad inmediata**: Corregir bugs críticos en `account.move` y `res.partner` antes
de habilitar webhooks en producción.
