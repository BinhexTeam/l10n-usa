# Guía de Configuración de Webhooks Bill.com desde Odoo

## Descripción General

El sistema de webhooks de Bill.com permite recibir notificaciones en tiempo real cuando
ocurren cambios en Bill.com, manteniendo Odoo sincronizado automáticamente sin necesidad
de polling o sincronizaciones manuales.

## Arquitectura del Sistema

```
Bill.com → Webhook → Odoo Controller → Idempotency Check → Process Event → Update Odoo
                                      ↓
                              billcom.webhook.log (audit trail)
```

### Componentes:

1. **Bill.com API v3** - Envía webhooks cuando ocurren eventos
2. **Odoo Controller** (`/billcom/webhook`) - Recibe y valida webhooks
3. **Webhook Log** (`billcom.webhook.log`) - Previene duplicados y auditoría
4. **Sync Methods** - Actualizan registros en Odoo
5. **Configuración UI** - Gestión desde Odoo

## Flujo de Configuración desde Odoo UI

### Paso 1: Habilitar Webhooks

1. Ir a **Bill.com → Configuration → Settings**
2. En la sección **Webhook Integration**:
   - ✅ Activar **Enable Webhooks**
   - La **Webhook URL** se genera automáticamente: `https://tu-odoo.com/billcom/webhook`
   - El **Webhook Secret** se genera automáticamente al suscribirse (o puedes poner uno
     manualmente)

### Paso 2: Seleccionar Eventos

En la sección **Webhook Events**, selecciona los tipos de eventos que quieres recibir:

- **✅ Bill Events** - Facturas de proveedores (bills)

  - `bill.created`, `bill.updated`, `bill.archived`, `bill.restored`

- **✅ Vendor Events** - Proveedores

  - `vendor.created`, `vendor.updated`, `vendor.archived`, `vendor.restored`

- **☐ Customer Events** - Clientes

  - `customer.created`, `customer.updated`, `customer.archived`, `customer.restored`

- **☐ Invoice Events** - Facturas de cliente (invoices)

  - `invoice.created`, `invoice.updated`, `invoice.archived`, `invoice.restored`

- **✅ Payment Events** - Pagos

  - `payment.updated`, `payment.failed`

- **☐ Funding Account Events** - Cuentas de financiamiento
  - `bank-account.created`, `bank-account.updated`
  - `card-account.created`, `card-account.updated`

**💡 Recomendación**: Activar solo los eventos que realmente necesitas para reducir
tráfico.

### Paso 3: Suscribirse

1. Click en **"Subscribe to Webhooks"** en el header del formulario
2. El sistema automáticamente:
   - Genera un secret si no existe
   - Llama al API de Bill.com: `POST /v3/webhooks/subscriptions`
   - Envía la URL, secret, y lista de eventos
   - Guarda el `subscription_id` devuelto por Bill.com
   - Cambia el estado a **"Subscribed"** ✅

### Paso 4: Probar la Conexión (Opcional)

1. Click en **"Test Webhook"**
2. Bill.com enviará un webhook de prueba
3. Verificar en **Bill.com → Configuration → Webhook Logs** que se recibió correctamente

### Paso 5: Verificar y Sincronizar Estado

**Sincronizar Estado con Bill.com**:

1. Click en **"Sync Status"** para verificar la suscripción
2. El sistema:
   - Consulta todas las suscripciones en Bill.com
   - Verifica si tu suscripción existe
   - Detecta suscripciones huérfanas (con tu URL pero diferente ID)
   - Actualiza el estado automáticamente

**Ver Todas las Suscripciones**:

1. Click en **"View All Subscriptions"**
2. Muestra lista completa de suscripciones en Bill.com
3. Indica cuál es la tuya con ✓ (OURS)
4. Útil para detectar suscripciones duplicadas o huérfanas

### Paso 6: Monitoreo

- **Estado de Suscripción**: Se muestra con badge de colores

  - 🟢 **Subscribed** - Activo y funcionando
  - 🔵 **Not Subscribed** - No configurado
  - 🔴 **Error** - Problema con la suscripción

- **Webhook Logs**: Menu **Bill.com → Configuration → Webhook Logs**

  - Ver todos los webhooks recibidos
  - Estado: received → processing → success/error
  - Payload completo en JSON
  - Mensajes de error si falló el procesamiento

- **Verificación Periódica**: Ejecutar "Sync Status" semanalmente
  - Detecta suscripciones eliminadas en Bill.com
  - Encuentra suscripciones huérfanas
  - Auto-adopta suscripciones con tu URL

## Gestión de Suscripciones

### Desuscribirse

1. Click en **"Unsubscribe"** en el header
2. El sistema llama: `DELETE /v3/webhooks/subscriptions/{subscriptionId}`
3. Limpia el `subscription_id` y vuelve a estado **"Not Subscribed"**

### Actualizar Eventos

Para cambiar los eventos suscritos:

1. **Desuscribirse** primero
2. Cambiar la selección de eventos
3. **Suscribirse** de nuevo

Bill.com no permite actualizar una suscripción existente, hay que recrearla.

### Re-suscribirse después de Error

Si el estado es **"Error"**:

1. Revisar el campo **"Last Webhook Error"** para ver qué falló
2. Corregir el problema (credenciales, URL, etc.)
3. Click en **"Subscribe to Webhooks"** de nuevo

## Detalles Técnicos de Implementación

### Campos Agregados a `billcom.config`

```python
# Estado y configuración
webhook_subscription_id = fields.Char(readonly=True)  # ID de Bill.com
webhook_url = fields.Char(compute='_compute_webhook_url')  # Auto-generada
webhook_subscription_state = fields.Selection([...])  # Estado actual
webhook_last_error = fields.Text(readonly=True)  # Último error

# Selección de eventos
webhook_event_bills = fields.Boolean(default=True)
webhook_event_vendors = fields.Boolean(default=True)
webhook_event_customers = fields.Boolean(default=False)
webhook_event_invoices = fields.Boolean(default=False)
webhook_event_payments = fields.Boolean(default=True)
webhook_event_funding_accounts = fields.Boolean(default=False)
```

### Métodos Implementados

#### `button_subscribe_webhooks()`

```python
def button_subscribe_webhooks(self):
    # 1. Validar que webhooks estén habilitados
    # 2. Generar secret si no existe
    # 3. Obtener lista de eventos seleccionados
    # 4. Llamar API: POST /v3/webhooks/subscriptions
    # 5. Guardar subscription_id
    # 6. Actualizar estado a 'subscribed'
```

#### `button_unsubscribe_webhooks()`

```python
def button_unsubscribe_webhooks(self):
    # 1. Validar que exista subscription_id
    # 2. Llamar API: DELETE /v3/webhooks/subscriptions/{id}
    # 3. Limpiar subscription_id
    # 4. Actualizar estado a 'not_subscribed'
```

#### `button_test_webhook()`

```python
def button_test_webhook(self):
    # 1. Validar que exista subscription_id
    # 2. Llamar API: POST /v3/webhooks/subscriptions/{id}/test
    # 3. Notificar al usuario que revise logs
```

#### `_get_webhook_events()`

```python
def _get_webhook_events(self):
    # Construye array de eventos basado en checkboxes
    events = []
    if self.webhook_event_bills:
        events.extend(['bill.created', 'bill.updated', ...])
    # ... etc
    return events
```

## Formato de Llamadas al API de Bill.com

### Crear Suscripción

```http
POST /v3/webhooks/subscriptions
Content-Type: application/json
Authorization: sessionId {token}
devKey: {dev_key}

{
  "url": "https://tu-odoo.com/billcom/webhook",
  "events": [
    "bill.created",
    "bill.updated",
    "vendor.created",
    "payment.updated"
  ],
  "secret": "generated-secret-key-32-chars"
}
```

**Respuesta**:

```json
{
  "id": "sub_1234567890",
  "url": "https://tu-odoo.com/billcom/webhook",
  "events": [...],
  "status": "active",
  "createdAt": "2025-10-02T12:00:00Z"
}
```

### Eliminar Suscripción

```http
DELETE /v3/webhooks/subscriptions/sub_1234567890
Authorization: sessionId {token}
devKey: {dev_key}
```

### Probar Webhook

```http
POST /v3/webhooks/subscriptions/sub_1234567890/test
Content-Type: application/json
Authorization: sessionId {token}
devKey: {dev_key}

{
  "eventType": "bill.updated"
}
```

## Sistema de Idempotencia

### ¿Qué es?

Idempotencia asegura que si Bill.com envía el mismo webhook 2 veces (por retry, red,
etc.), Odoo lo procesa solo 1 vez.

### Cómo Funciona

1. **Webhook llega** → Controller extrae `eventType` y `entityId`
2. **Genera idempotency_key**: `"{eventType}:{entityId}"`
   - Ejemplo: `"bill.updated:00e02RCAEIGKRSEZw7ri"`
3. **Busca en `billcom.webhook.log`** si ya existe esa key
4. **Si existe** → Retorna `{"success": true, "message": "Already processed"}`
5. **Si no existe** → Crea log, procesa webhook, marca como success

### Modelo `billcom.webhook.log`

```python
idempotency_key = fields.Char(required=True, index=True)
event_type = fields.Char(required=True)
entity_id = fields.Char(required=True)
webhook_data = fields.Text()  # JSON completo
state = fields.Selection([
    ('received', 'Received'),
    ('processing', 'Processing'),
    ('success', 'Success'),
    ('error', 'Error'),
])
error_message = fields.Text()
signature_valid = fields.Boolean()
```

### Limpieza Automática

```python
# Método para limpiar logs viejos (llamar desde cron)
def cleanup_old_logs(self, days=30):
    cutoff_date = now() - timedelta(days=days)
    old_logs = self.search([
        ('create_date', '<', cutoff_date),
        ('state', '=', 'success')
    ])
    old_logs.unlink()
```

## Validación de Seguridad

### Firma HMAC-SHA256

Bill.com firma cada webhook con el secret compartido:

1. Bill.com calcula: `HMAC-SHA256(payload, secret)`
2. Envía en header: `X-Bill-Signature: sha256={hash}`
3. Odoo recalcula el hash con el mismo payload y secret
4. Compara con `hmac.compare_digest()` (timing-safe)
5. Si coinciden → webhook válido ✅
6. Si no coinciden → rechaza con 403 ❌

```python
def _validate_webhook_signature(self, payload, signature, secret):
    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature.replace('sha256=', ''))
```

## Casos Especiales

### Suscripciones Huérfanas

**¿Qué es una suscripción huérfana?**

- Suscripción en Bill.com con tu URL de Odoo
- Pero con un `subscription_id` diferente al guardado en Odoo
- Puede ocurrir si se borra la configuración en Odoo pero no en Bill.com

**Detección Automática**:

1. Click en **"Sync Status"**
2. Si encuentra una huérfana con tu URL exacta → **Auto-adopta** ✅
3. Si encuentra múltiples huérfanas → Avisa para limpieza manual

**Adopción de Huérfanas**:

```python
# El sistema hace esto automáticamente:
if orphaned_subscription.url == self.webhook_url:
    self.webhook_subscription_id = orphaned_subscription.id
    self.webhook_subscription_state = 'subscribed'
    # ¡Listo! Ahora está conectado de nuevo
```

### Suscripciones Eliminadas en Bill.com

**Escenario**: Alguien eliminó la suscripción directamente en Bill.com portal

**Detección**:

1. **"Sync Status"** no encuentra el `subscription_id` en la lista
2. Automáticamente marca estado como **Error** 🔴
3. Muestra mensaje: "Subscription not found in Bill.com"

**Solución**:

1. Click **"Unsubscribe"** (limpia el estado local)
2. Click **"Subscribe to Webhooks"** de nuevo
3. Nueva suscripción creada ✅

### Múltiples Suscripciones con la Misma URL

**Problema**: Varias suscripciones apuntando a la misma URL de Odoo

**Detección**:

1. **"View All Subscriptions"** muestra la lista completa
2. Busca duplicados con tu URL

**Solución**:

1. Identificar cuál es la correcta (la que tiene ✓ OURS)
2. Eliminar las demás manualmente:
   ```bash
   # Desde Bill.com portal o API:
   DELETE /v3/connect-events/subscriptions/{id_duplicado}
   ```

## Troubleshooting

### Problema: No se puede suscribir

**Síntomas**: Error al hacer click en "Subscribe to Webhooks"

**Causas posibles**:

1. **No hay conexión con Bill.com** → Probar "Test Connection" primero
2. **URL incorrecta** → Verificar que `web.base.url` esté configurado correctamente
3. **No hay eventos seleccionados** → Seleccionar al menos 1 tipo de evento
4. **Token expirado** → El sistema refresca automáticamente, reintentar

**Solución**:

- Revisar logs de Odoo: `grep "webhook" odoo.log`
- Revisar campo "Last Webhook Error"

### Problema: Webhooks no llegan

**Síntomas**: Subscribed pero no se crean logs en Webhook Logs

**Causas posibles**:

1. **Firewall bloqueando** → Asegurar que puerto 443/80 esté abierto
2. **URL incorrecta** → Copiar webhook_url y probarlo con `curl`
3. **SSL inválido** → Bill.com requiere HTTPS válido
4. **Eventos no ocurren** → Crear un bill en Bill.com para generar evento

**Solución**:

```bash
# Probar webhook endpoint
curl -X POST https://tu-odoo.com/billcom/webhook \
  -H "Content-Type: application/json" \
  -d '{"eventType": "bill.updated", "entityId": "test123"}'
```

### Problema: Webhooks llegan pero fallan

**Síntomas**: Logs en "error" state

**Causas posibles**:

1. **Firma inválida** → Verificar webhook_secret
2. **Partner no existe** → Crear vendor/customer primero en Odoo
3. **Permisos** → Controller usa `.sudo()`, pero revisar permisos de modelo

**Solución**:

- Ver error en Webhook Log → campo "Error Message"
- Buscar en logs de Odoo el traceback completo

### Problema: Duplicados procesados

**Síntomas**: Mismo webhook procesado 2+ veces

**Causas posibles**:

1. **Idempotency key diferente** → Revisar formato `eventType:entityId`
2. **Logs borrados** → No ejecutar cleanup muy frecuente

**Solución**:

- Verificar campo `idempotency_key` en logs
- Asegurar que Bill.com envía `entityId` consistente

## Mejores Prácticas

### 1. Configuración Inicial

✅ **DO**:

- Habilitar webhooks solo después de sincronizar datos iniciales
- Seleccionar solo eventos necesarios
- Probar con "Test Webhook" antes de producción
- Configurar SSL válido en Odoo

❌ **DON'T**:

- No habilitar todos los eventos si no los necesitas
- No exponer webhook endpoint sin HTTPS
- No compartir el webhook_secret

### 2. Monitoreo

✅ **DO**:

- Revisar Webhook Logs semanalmente
- Configurar alertas para estado "error"
- Limpiar logs viejos cada mes (cron job)

❌ **DON'T**:

- No ignorar webhooks en error
- No borrar logs hasta investigar errores

### 3. Mantenimiento

✅ **DO**:

- Re-suscribir después de cambios en eventos
- Actualizar secret periódicamente (cada 6 meses)
- Documentar cambios en configuración

❌ **DON'T**:

- No modificar webhook_subscription_id manualmente
- No desactivar webhooks sin desuscribirse primero

## Resumen de Ventajas del Sistema

| Característica                | Beneficio                               |
| ----------------------------- | --------------------------------------- |
| **Configuración desde UI**    | No necesita ir a Bill.com portal        |
| **Auto-generación de Secret** | Seguridad automática sin esfuerzo       |
| **Selección de Eventos**      | Control fino de qué sincronizar         |
| **Idempotencia Automática**   | Previene duplicados sin código extra    |
| **Webhook Logs**              | Auditoría completa y debugging fácil    |
| **Estado Visual**             | Badge muestra estado de suscripción     |
| **Test Webhook**              | Validación antes de producción          |
| **Manejo de Errores**         | Re-suscripción fácil después de errores |

## Archivos del Sistema

### Modelos

- `models/billcom_config.py` - Configuración y métodos de suscripción
- `models/billcom_webhook_log.py` - Tracking y idempotencia

### Controladores

- `controllers/billcom_controller.py` - Endpoint `/billcom/webhook`

### Vistas

- `views/billcom_config_views.xml` - UI de configuración con botones
- `views/billcom_webhook_log_views.xml` - UI de logs

### Seguridad

- `security/ir.model.access.csv` - Permisos para webhook.log

## Próximos Pasos (Opcional)

### Mejoras Sugeridas:

1. **Dashboard de Webhooks**

   - Gráfico de webhooks por tipo
   - Tasa de éxito/error
   - Tiempo promedio de procesamiento

2. **Alertas Automáticas**

   - Email cuando webhook falla X veces
   - Notificación cuando suscripción expira

3. **Sincronización Selectiva**

   - Filtros avanzados: "Solo bills > $1000"
   - Reglas de procesamiento condicional

4. **Multi-tenant**
   - Suscripciones por organización en Bill.com
   - Webhook endpoints con company_id en URL
