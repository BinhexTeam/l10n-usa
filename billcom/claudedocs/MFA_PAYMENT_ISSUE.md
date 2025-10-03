# MFA Payment Issue - Bill.com

## 🚨 Problema Actual

### Error en Creación de Pagos desde Odoo → Bill.com

**Error**: `BDC_1361: Untrusted session`

**Log del Error**:

```
2025-10-02 17:56:48,382 1 WARNING: Session expired (BDC_1361) - invalidating token and refreshing
2025-10-02 17:56:49,718 1 INFO: Token refreshed successfully, retrying request
2025-10-02 17:56:52,156 1 ERROR: Bill.com API error 403 for URL: https://gateway.stage.bill.com/connect/v3/payments
Error details: [{'timestamp': '2025-10-02T17:56:51.933+00:00', 'code': 'BDC_1361', 'severity': 'ERROR', 'category': 'DOWNSTREAM', 'message': 'Untrusted session.', 'params': {}}]
```

### Causa Raíz

Según la documentación de Bill.com API v3:

> **👍 Creating a payment is an MFA-trusted operation**
>
> Creating a payment requires an MFA-trusted API session. See MFA setup in the API
> reference for information about the BILL MFA process.

**El endpoint `/v3/payments` requiere una sesión MFA-trusted**, no solo un token
regular.

### Comportamiento Actual del Código ❌

1. El código detecta `BDC_1361: Untrusted session`
2. **Incorrectamente** asume que es "Session expired"
3. Invalida el token y solicita uno nuevo
4. Reintenta con el nuevo token
5. Falla nuevamente con el mismo error
6. Ciclo infinito de refresh token sin éxito

### Fix Aplicado ✅

**Archivo**: `models/billcom_service_abstract.py`

```python
# Check for expired session - refresh token and retry once
if response.status_code == 403:
    error_details = self._extract_error_details(response)

    if isinstance(error_details, list):
        for error in error_details:
            if isinstance(error, dict) and error.get('code') == 'BDC_1361':
                error_message = error.get('message', '')

                # BDC_1361 can mean two things:
                # 1. "Untrusted session" = MFA required (cannot be fixed with token refresh)
                # 2. "Session expired" = Token expired (can be fixed with token refresh)

                if 'untrusted' in error_message.lower():
                    _logger.error("MFA-trusted session required (BDC_1361: Untrusted session). This endpoint requires MFA authentication.")
                    _logger.error("Payment creation requires MFA setup. Please configure MFA for this Bill.com account.")
                    # Don't retry - this won't be fixed by token refresh
                    break
                else:
                    _logger.warning("Session expired (BDC_1361) - invalidating token and refreshing")
                    # ... existing refresh logic
```

**Resultado**:

- ✅ Ya NO intenta refresh token innecesariamente cuando es error de MFA
- ✅ Log claro indicando que se requiere MFA
- ✅ Evita ciclos infinitos de retry

## 🔧 Solución: MFA-Trusted Session

### Opción 1: Device Trust (Recomendado)

Bill.com permite "recordar" un dispositivo para evitar MFA en cada operación.

**Proceso**:

1. **Primera vez** (manual en Bill.com UI):

   - Usuario inicia sesión en Bill.com web
   - Completa MFA (código SMS/app)
   - Marca checkbox "Trust this device" / "Remember this device"
   - Bill.com genera un `deviceId` trusted

2. **Autenticación API con Device Trust**:

   ```json
   POST /v3/login
   {
     "userName": "user@company.com",
     "password": "password",
     "orgId": "{organization_id}",
     "deviceId": "{trusted_device_id}"  // <-- Key!
   }
   ```

3. **Resultado**:
   - Token obtenido es MFA-trusted
   - Puede crear pagos sin MFA adicional
   - Válido mientras dispositivo esté trusted

**Implementación en Odoo**:

```python
# En billcom_config.py
mfa_device_id = fields.Char(
    string="MFA Device ID",
    help="Trusted device ID from Bill.com for MFA-free operations",
)

# En billcom_service_abstract.py - authenticate()
def authenticate(self, config):
    """Authenticate with Bill.com API v3"""
    login_url = f"{config.api_url}/v3/login"

    login_data = {
        "userName": config.billcom_username,
        "password": config.billcom_password,
        "orgId": config.organization_id,
        "devKey": config.billcom_dev_key,
    }

    # Add device ID if configured for MFA-trusted session
    if config.mfa_device_id:
        login_data["deviceId"] = config.mfa_device_id
        _logger.info("Using trusted device ID for MFA-free authentication")

    # ... rest of authentication
```

### Opción 2: MFA Flow Completo (Más Complejo)

Si no hay device trust, implementar flujo MFA completo:

1. **Login inicial** → `mfaRequired: true`
2. **Request MFA code** → Bill.com envía SMS/app
3. **Submit MFA code** → `POST /v3/mfa/verify`
4. **Get trusted token** → Crear pagos

**Problema**: Requiere intervención del usuario en cada autenticación.

### Opción 3: Usar Bill.com Web para Pagos (Workaround)

- Crear bills en Odoo
- Sincronizar bills a Bill.com
- Usuario crea pagos manualmente en Bill.com UI
- Webhooks notifican pagos a Odoo

**Ventaja**: Sin MFA en API **Desventaja**: No automatizado

## 📋 Recomendación Inmediata

### Paso 1: Obtener Trusted Device ID

**Proceso Manual** (una sola vez):

1. Login en Bill.com Sandbox: https://app.stage.bill.com
2. Completar MFA si se solicita
3. Marcar "Trust this device" / "Remember me"
4. Inspeccionar cookies/storage del browser para obtener `deviceId`
5. **O** usar Bill.com Support para obtener deviceId de la cuenta

### Paso 2: Configurar en Odoo

```python
# En Bill.com Configuration
mfa_device_id = "device_xyz123..."  # El ID obtenido
```

### Paso 3: Modificar Autenticación

```python
# Ya existe el campo mfa_device_id en billcom_config.py
# Solo necesita agregarse al login request:

def authenticate(self, config):
    login_data = {
        "userName": config.billcom_username,
        "password": config.billcom_password,
        "orgId": config.organization_id,
        "devKey": config.billcom_dev_key,
    }

    # Add trusted device ID if configured
    if config.mfa_device_id:
        login_data["deviceId"] = config.mfa_device_id

    # ... rest remains the same
```

## 🎯 Solución Completa (Para Implementar)

### Archivo: `models/billcom_service_abstract.py`

**Cambios Necesarios**:

1. **Modificar `authenticate()` para incluir deviceId**:

```python
def authenticate(self, config):
    """Authenticate with Bill.com API v3 using trusted device if available"""
    login_url = f"{config.api_url}/v3/login"

    login_data = {
        "userName": config.billcom_username,
        "password": config.billcom_password,
        "orgId": config.organization_id,
        "devKey": config.billcom_dev_key,
    }

    # Include trusted device ID for MFA-free authentication
    if config.mfa_device_id:
        login_data["deviceId"] = config.mfa_device_id
        _logger.info("Authenticating with trusted device ID for MFA-free session")

    headers = {"Content-Type": "application/json", "devKey": config.billcom_dev_key}

    try:
        response = requests.post(login_url, json=login_data, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()

        # Check for MFA requirement
        if result.get("mfaRequired") and not result.get("sessionId"):
            if config.mfa_device_id:
                _logger.error("Trusted device ID rejected. Device may no longer be trusted.")
                raise UserError(_("MFA device not trusted. Please re-authenticate in Bill.com UI and update device ID."))
            else:
                _logger.error("MFA required but no device ID configured")
                raise UserError(_("MFA required for payment creation. Please configure a trusted device ID."))

        # Extract token
        session_id = result.get("sessionId")
        # ... rest of logic
```

2. **Agregar campo en UI** (`views/billcom_config_views.xml`):

```xml
<field name="mfa_device_id" password="True" />
```

### Archivo: `models/billcom_config.py`

**El campo ya existe** ✅:

```python
mfa_device_id = fields.Char(
    string="MFA Device ID",
    help="Device ID for MFA authentication",
    tracking=True,
)
```

Solo necesita:

- Hacerse visible en la UI
- Agregar help text más claro
- Posiblemente agregar validación

## 📝 Documentación para Usuario

### Cómo Obtener el Trusted Device ID

#### Método 1: Browser Developer Tools

1. Abrir Bill.com en Chrome/Firefox
2. Login con credenciales
3. Completar MFA y marcar "Trust this device"
4. Abrir Developer Tools (F12)
5. Application/Storage → Cookies o Local Storage
6. Buscar cookie/storage con nombre "deviceId" o similar
7. Copiar el valor

#### Método 2: Bill.com Support

1. Contactar Bill.com support
2. Solicitar trusted device ID para API integration
3. Proporcionar organization ID
4. Support puede generar/proveer deviceId

#### Método 3: API Response (Primera MFA)

1. Hacer login con MFA completo via API
2. En respuesta de `/v3/mfa/verify` exitoso
3. Guardar `deviceId` retornado
4. Usar ese ID en futuros logins

## ⚠️ Consideraciones de Seguridad

### Device Trust Expiration

- Device trust puede expirar después de cierto tiempo
- Bill.com puede revocar device trust por políticas de seguridad
- Cambios en políticas MFA de la organización pueden invalidar trust

### Manejo de Errores

```python
if 'untrusted' in error_message.lower() and config.mfa_device_id:
    # Device ID ya no es válido
    config.write({'mfa_device_id': False})
    _logger.warning("Device ID no longer trusted - cleared from configuration")
    raise UserError(_("Device trust expired. Please re-authenticate and update MFA Device ID."))
```

### Rotación de Device ID

- Implementar proceso para renovar device ID periódicamente
- Notificar admin cuando device trust está por expirar
- Proceso automatizado para re-trust device

## 🚀 Estado Actual

### ✅ Completado

1. Detección correcta de "Untrusted session" vs "Session expired"
2. No más intentos innecesarios de refresh token
3. Logs claros indicando requisito de MFA
4. Campo `mfa_device_id` existe en modelo

### 🔄 Pendiente

1. Modificar `authenticate()` para incluir `deviceId` en login
2. Hacer campo `mfa_device_id` visible en UI
3. Documentar proceso para obtener device ID
4. Agregar validación de device ID
5. Implementar manejo de device trust expiration

### 📖 Documentación Necesaria

1. Guía paso a paso para obtener trusted device ID
2. Proceso de configuración en Odoo
3. Troubleshooting para errores MFA
4. Proceso de renovación de device trust

## 🎯 Próximos Pasos

1. **Implementar deviceId en authenticate()** (código arriba)
2. **Actualizar UI** para mostrar campo mfa_device_id
3. **Crear guía** para obtener device ID
4. **Testing** con device ID real
5. **Documentar** proceso completo

Una vez implementado, los pagos desde Odoo → Bill.com funcionarán sin problemas de MFA.
