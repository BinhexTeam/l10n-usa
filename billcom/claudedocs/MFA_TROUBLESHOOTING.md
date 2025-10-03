# MFA Troubleshooting Guide - Bill.com

## Error: 400 Bad Request en /v3/mfa/challenge

### Posibles Causas

#### 1. MFA No Configurado en Bill.com

**Síntoma**: Error 400 al generar challenge

**Verificación**:

```bash
# Ver logs de Odoo
docker-compose logs odoo | grep "MFA"

# Debe mostrar:
# "Performing basic login for MFA flow"
# "Basic login successful, session ID obtained"
# ERROR si falla en challenge
```

**Solución**:

1. Login en Bill.com web (https://app.stage.bill.com o https://app.bill.com)
2. Ir a: **Settings → Security → Multi-Factor Authentication**
3. **Habilitar MFA** si no está activo
4. **Agregar número de teléfono**
5. **Verificar teléfono** con código SMS
6. Reintentar en Odoo

#### 2. Sesión No Válida para MFA

**Síntoma**: Login exitoso pero challenge falla

**Causa**: Algunas organizaciones requieren permisos especiales para MFA API

**Solución**:

1. Verificar que el usuario tenga permisos de administrador en Bill.com
2. Contactar Bill.com support para habilitar MFA API en la organización
3. Verificar que `organizationId` sea correcto

#### 3. Headers Incorrectos

**Síntoma**: Error 400 inmediato

**Verificación**: Ver logs para headers enviados:

```
Request URL: https://gateway.stage.bill.com/connect/v3/mfa/challenge
Request headers: {'accept': 'application/json', 'content-type': 'application/json', 'sessionId': '...', 'devKey': '...'}
Response status: 400
Response body: {...}
```

**Solución**: Ya corregido en código - ahora envía `json={}` (body vacío)

#### 4. API v3 vs API v2

**Síntoma**: Endpoint no encontrado o método no soportado

**Verificación**:

```python
# En Odoo shell
config = env['billcom.config'].search([('active', '=', True)], limit=1)
print(config.api_url)

# Debe ser:
# Sandbox: https://gateway.stage.bill.com/connect
# Production: https://gateway.bill.com/connect
```

**Solución**: Verificar que `environment` esté configurado correctamente

## Diagnóstico Paso a Paso

### 1. Verificar Configuración Básica

```python
# En Odoo shell
config = env['billcom.config'].search([('active', '=', True)], limit=1)

# Verificar datos
print(f"Environment: {config.environment}")
print(f"API URL: {config.api_url}")
print(f"Organization ID: {config.organization_id}")
print(f"Has dev_key: {bool(config.dev_key)}")
print(f"Has username: {bool(config.username)}")
print(f"Has password: {bool(config.password)}")
```

### 2. Test Login Básico

```python
# En Odoo shell
service = env['billcom.service']

try:
    session_id = service._basic_login(config)
    print(f"✅ Login successful: {session_id[:20]}...")
except Exception as e:
    print(f"❌ Login failed: {e}")
```

### 3. Test MFA Challenge Manual

```python
# En Odoo shell
import requests

# Usar session_id del paso anterior
session_id = "..."  # del paso 2

url = f"{config.api_url}/v3/mfa/challenge"
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "sessionId": session_id,
    "devKey": config.dev_key,
}

response = requests.post(url, json={}, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
```

### 4. Verificar MFA en Bill.com

**Método 1: Via API (Get MFA Phones)**

```python
# En Odoo shell
import requests

url = f"{config.api_url}/v3/mfa/phones"
headers = {
    "accept": "application/json",
    "sessionId": session_id,  # del login
    "devKey": config.dev_key
}

response = requests.get(url, headers=headers)
phones = response.json().get('results', [])

for phone in phones:
    print(f"Type: {phone['type']}, Last 4: {phone['last4digits']}, Primary: {phone['primary']}")

# Si lista vacía → MFA no configurado
```

**Método 2: Via Web**

1. Login en Bill.com
2. Settings → Security → MFA
3. Verificar que haya teléfono registrado

## Errores Específicos y Soluciones

### Error: "MFA is not enabled for this organization"

**Solución**:

1. Login como administrador en Bill.com
2. Settings → Security
3. Enable MFA for organization
4. Configure at least one phone number

### Error: "Invalid session"

**Solución**:

1. Verificar que `_basic_login()` devuelve sessionId válido
2. No usar deviceId en login básico (solo username/password)
3. Verificar que session no haya expirado

### Error: "Phone number required"

**Solución**:

1. Bill.com Settings → Security → MFA
2. Add phone number
3. Verify with SMS code
4. Reintentar en Odoo

### Error: "MFA challenge already exists"

**Solución**:

1. Esperar 5 minutos (challenge expira)
2. O usar endpoint de cleanup (si existe)
3. Reintentar

### Error: "BDC_1358: Too many token response attempts"

**Causa**: Demasiados intentos de validación con código incorrecto

**Mensaje completo**:

```json
{
  "code": "BDC_1358",
  "message": "2-Step Verification too many token response attempts."
}
```

**Solución**:

1. **Esperar 5-10 minutos** - Bill.com desbloquea automáticamente
2. **Nuevo Challenge** - Click "Setup MFA" de nuevo (genera nuevo challenge)
3. **Verificar código** - Asegurar que código SMS sea el correcto y actual
4. **Un intento** - Ingresar código correcto en primer intento

**Alternativa (Manual Device ID)**:

1. Login en Bill.com web
2. Completar MFA → "Trust this device"
3. Copiar deviceId de cookies
4. Configurar en Odoo → MFA Device ID

**Prevención**:

- No intentar códigos expirados (>5 min)
- Verificar código antes de enviar
- Usar "Resend Code" si dudas
- Máximo 3 intentos por challenge

## Alternativa: Usar Device ID (Método Manual)

Si MFA challenge continúa fallando, usar Device ID:

```python
# 1. Login en Bill.com web con MFA
# 2. Marcar "Trust this device"
# 3. Extraer deviceId de cookies
# 4. Configurar en Odoo:

config.write({'mfa_device_id': 'el_device_id_extraido'})

# Ahora pagos funcionarán sin MFA challenge
```

Ver: `MFA_QUICK_GUIDE.md` para detalles

## Logs Útiles

### Login Exitoso + Challenge Exitoso

```
INFO: Performing basic login for MFA flow
INFO: Basic login successful, session ID obtained
INFO: MFA challenge generated successfully: ch_abc123...
```

### Login Exitoso + Challenge Fallido

```
INFO: Performing basic login for MFA flow
INFO: Basic login successful, session ID obtained
ERROR: Failed to generate MFA challenge: 400 Client Error: Bad Request
ERROR: Request URL: https://gateway.stage.bill.com/connect/v3/mfa/challenge
ERROR: Response body: {"error": "MFA not configured"}
```

## Contactar Bill.com Support

Si problema persiste:

**Email**: support@bill.com

**Asunto**: API v3 MFA Challenge Issue - Organization [ID]

**Información a incluir**:

- Organization ID
- Environment (Sandbox/Production)
- Error exacto recibido
- Request/Response logs
- Si MFA está configurado en UI

**Preguntar**:

- ¿Está MFA API habilitado para nuestra organización?
- ¿Hay permisos especiales requeridos?
- ¿Podemos obtener un Device ID permanente?

## Checklist de Verificación

- [ ] MFA habilitado en Bill.com Settings
- [ ] Al menos un teléfono verificado
- [ ] Usuario tiene permisos de administrador
- [ ] Organization ID correcto en Odoo
- [ ] API URL correcto (sandbox vs production)
- [ ] Dev Key válido
- [ ] Username/Password correctos
- [ ] Login básico funciona (test en shell)
- [ ] SessionId se obtiene correctamente
- [ ] Headers incluyen sessionId y devKey

## Solución Rápida

Si todo falla y necesitas pagos YA:

**Opción A**: Usar Device ID (5 minutos, método manual)

```
Ver: MFA_QUICK_GUIDE.md
```

**Opción B**: Desactivar requirement de MFA

```python
# TEMPORAL - solo para testing
# NO para producción
config.write({'mfa_device_id': 'temporary_bypass'})
# Esto causará error pero permite testing de otros features
```

**Opción C**: Contactar Bill.com para Device ID permanente

```
support@bill.com
"Request permanent device ID for API integration"
```

---

**Siguiente paso**: Verificar logs de Odoo después de probar "Setup MFA" de nuevo

```bash
docker-compose logs odoo | tail -50 | grep -E "MFA|challenge|login"
```
