# Webhook API Endpoint Fix

## Errors Found

### 1. Duplicate URL Path (404 Error)

```
URL generada: https://gateway.stage.bill.com/connect/v3/connect-events/v3/subscriptions
URL correcta:  https://gateway.stage.bill.com/connect-events/v3/subscriptions
```

**Problema**: Se estaba duplicando la ruta porque:

- URL base: `https://gateway.stage.bill.com/connect`
- `_build_api_url()` agrega: `/v3/` + endpoint
- Endpoint usado: `connect-events/v3/subscriptions`
- Resultado: `/connect/v3/connect-events/v3/subscriptions` ❌

### 2. Formato JSON Incorrecto

**Antes (Incorrecto):**

```json
{
  "name": "Odoo Webhook",
  "status": {
    "events": [...]  // ❌ Eventos dentro de status
  },
  "notificationUrl": "..."
}
```

**Después (Correcto según Bill.com API):**

```json
{
  "name": "Odoo Webhook",
  "status": {
    "enabled": true  // ✅ Status solo tiene enabled
  },
  "events": [...],   // ✅ Eventos al nivel principal
  "notificationUrl": "..."
}
```

### 3. Versión de Eventos Incorrecta

**Antes:** `"version": "1.0"` ❌ **Después:** `"version": "1"` ✅

## Root Cause

Bill.com tiene **dos APIs diferentes** con URLs base distintas:

1. **API Principal** (bills, vendors, payments, etc.):

   - URL: `https://gateway.stage.bill.com/connect/v3/...`
   - Ejemplos: `/bills`, `/vendors`, `/payments`

2. **Webhook API** (subscriptions):
   - URL: `https://gateway.stage.bill.com/connect-events/v3/...`
   - Ejemplos: `/subscriptions`

El problema es que el método `_build_api_url()` solo funciona para la API principal, no
para webhook API.

## Solution

### Opción Implementada: Prefijo `webhook:` para Endpoints

Modificar `_build_api_url()` para detectar endpoints de webhook usando el prefijo
`webhook:` y cambiar automáticamente la URL base de `/connect` a `/connect-events`.

#### Cómo funciona:

```python
def _build_api_url(self, config, endpoint):
    """Build the complete API URL

    Webhooks use a different base URL: connect-events instead of connect
    """
    # Check if this is a webhook endpoint
    if endpoint.startswith("webhook:"):
        # Remove the webhook: prefix and use connect-events base
        actual_endpoint = endpoint.replace("webhook:", "")
        base_url = config.api_url.replace("/connect", "/connect-events")
        return f"{base_url.rstrip('/')}/v3/{actual_endpoint.lstrip('/')}"

    # Standard API endpoint
    return f"{config.api_url.rstrip('/')}/v3/{endpoint.lstrip('/')}"
```

#### Ejemplo de Uso:

```python
# Endpoint webhook
service._make_request("webhook:subscriptions", method="POST")
# → https://gateway.stage.bill.com/connect-events/v3/subscriptions ✅

# Endpoint normal
service._make_request("bills", method="GET")
# → https://gateway.stage.bill.com/connect/v3/bills ✅
```

### Cambios Realizados

#### 1. `_build_api_url()` - Modificado en `billcom_service_abstract.py`

```python
def _build_api_url(self, config, endpoint):
    """Build the complete API URL

    Webhooks use a different base URL: connect-events instead of connect
    """
    # Check if this is a webhook endpoint
    if endpoint.startswith("webhook:"):
        # Remove the webhook: prefix and use connect-events base
        actual_endpoint = endpoint.replace("webhook:", "")
        base_url = config.api_url.replace("/connect", "/connect-events")
        return f"{base_url.rstrip('/')}/v3/{actual_endpoint.lstrip('/')}"

    # Standard API endpoint
    return f"{config.api_url.rstrip('/')}/v3/{endpoint.lstrip('/')}"
```

#### 2. `button_subscribe_webhooks()` - Crear Suscripción

```python
# Formato JSON corregido
subscription_data = {
    "name": f"Odoo Webhook - {self.company_id.name}",
    "status": {
        "enabled": True  # ✅ Agregado
    },
    "events": event_objects,  # ✅ Movido fuera de status
    "notificationUrl": self.webhook_url,
}

# Endpoint con prefijo webhook:
response = service._make_request(
    "webhook:subscriptions",  # ✅ webhook: prefix
    method="POST",
    data=subscription_data,
    extra_headers={"X-Idempotent-Key": idempotency_key},
)
```

#### 3. `button_unsubscribe_webhooks()` - Eliminar Suscripción

```python
# Endpoint con prefijo webhook:
service._make_request(
    f"webhook:subscriptions/{self.webhook_subscription_id}",  # ✅ webhook: prefix
    method="DELETE",
)
```

#### 4. `button_test_webhook()` - Probar Webhook

```python
# Endpoint con prefijo webhook:
response = service._make_request(
    f"webhook:subscriptions/{self.webhook_subscription_id}/test",  # ✅ webhook: prefix
    method="POST",
    data=test_data,
)
```

#### 5. `button_sync_webhook_status()` - Listar Suscripciones

```python
# Endpoint con prefijo webhook:
response = service._make_request(
    "webhook:subscriptions",  # ✅ webhook: prefix
    method="GET",
    params={"max": 100},
)
```

#### 6. `button_view_all_subscriptions()` - Ver Todas

```python
# Endpoint con prefijo webhook:
response = service._make_request(
    "webhook:subscriptions",  # ✅ webhook: prefix
    method="GET",
    params={"max": 100},
)
```

#### 4. `_get_webhook_event_objects()` - Versión de Eventos

```python
# Antes
{"type": "bill.created", "version": "1.0"}  # ❌

# Después
{"type": "bill.created", "version": "1"}    # ✅
```

## Alternativas Consideradas

### Opción A: Modificar `_build_api_url()` (No implementada)

```python
def _build_api_url(self, config, endpoint):
    # Detectar si es webhook API
    if endpoint.startswith("webhooks/") or "connect-events" in endpoint:
        base = config.api_url.replace("/connect", "/connect-events")
        return f"{base.rstrip('/')}/v3/{endpoint.lstrip('/')}"
    return f"{config.api_url.rstrip('/')}/v3/{endpoint.lstrip('/')}"
```

**Rechazada**: Más complejo y modifica lógica core.

### Opción B: Crear método separado `_make_webhook_request()` (No implementada)

```python
def _make_webhook_request(self, endpoint, method="GET", ...):
    # Construir URL específica para webhooks
    webhook_url = self.api_url.replace("/connect", "/connect-events")
    ...
```

**Rechazada**: Duplica código y lógica de retry.

### Opción C: Navegación relativa `..` (✅ Implementada)

```python
webhook_endpoint = "../connect-events/v3/subscriptions"
```

**Ventajas**:

- ✅ Mínimo cambio en código existente
- ✅ No modifica métodos core
- ✅ Funciona con requests/urllib
- ✅ Fácil de entender

## Testing

Para verificar que funciona:

1. **Verificar URL generada** (revisar logs):

   ```
   ✅ https://gateway.stage.bill.com/connect-events/v3/subscriptions
   ❌ https://gateway.stage.bill.com/connect/v3/connect-events/v3/subscriptions
   ```

2. **Verificar JSON enviado**:

   ```json
   {
     "name": "Odoo Webhook - Company",
     "status": {"enabled": true},
     "events": [
       {"type": "bill.created", "version": "1"},
       {"type": "bill.updated", "version": "1"}
     ],
     "notificationUrl": "https://..."
   }
   ```

3. **Probar suscripción**:
   - Click en "Subscribe" → Debe crear suscripción exitosamente
   - Click en "Sync Status" → Debe listar suscripciones
   - Click en "View All" → Debe mostrar todas las suscripciones

## Bill.com API v3 Reference

### Formato Correcto de Suscripción

```json
{
  "name": "string", // Nombre descriptivo
  "status": {
    "enabled": true // Estado habilitado/deshabilitado
  },
  "events": [
    // Array de eventos
    {
      "type": "bill.created", // Tipo de evento
      "version": "1" // Versión como string "1"
    }
  ],
  "notificationUrl": "string" // URL del webhook
}
```

### Endpoints Webhook

- **POST** `/connect-events/v3/subscriptions` - Crear
- **GET** `/connect-events/v3/subscriptions` - Listar
- **GET** `/connect-events/v3/subscriptions/{id}` - Obtener
- **DELETE** `/connect-events/v3/subscriptions/{id}` - Eliminar

### Headers Requeridos

```
sessionId: {token}
devKey: {dev_key}
Content-Type: application/json
X-Idempotent-Key: {uuid4}  // Para POST
```

## Status

✅ **Fixed**:

- URL endpoint corregida usando navegación relativa `..`
- Formato JSON corregido según Bill.com API
- Versión de eventos corregida a `"1"`
- Todos los métodos webhook actualizados

🧪 **Pending Testing**:

- Crear suscripción
- Listar suscripciones
- Ver todas las suscripciones
- Verificar webhooks recibidos
