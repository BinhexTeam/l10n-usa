# Guía Rápida: Solucionar Error de Pagos (MFA)

## 🚨 Error Actual

```
BDC_1361: Untrusted session
Payment creation requires MFA authentication
```

## ✅ Solución Rápida (5 minutos)

### Opción 1: Device ID desde Browser (Más Rápido)

1. **Login en Bill.com**

   - Ir a: https://app.stage.bill.com (sandbox)
   - O: https://app.bill.com (producción)
   - Ingresar credenciales

2. **Completar MFA**

   - Ingresar código de SMS/App
   - ✅ Marcar checkbox "Trust this device" o "Remember me"

3. **Obtener Device ID**

   - Presionar F12 (Developer Tools)
   - Ir a: Application → Cookies
   - Buscar cookie con nombre "deviceId" o "device_id"
   - Copiar el valor (ejemplo: `abc123xyz456...`)

4. **Configurar en Odoo**

   - Ir a: Bill.com Configuration
   - Pegar en campo "MFA Device ID"
   - Guardar

5. **¡Listo!**
   - Crear pago desde Odoo
   - Debe funcionar sin error

### Opción 2: Solicitar a Bill.com Support

1. **Email a support@bill.com**:

   ```
   Asunto: Request Trusted Device ID for API Integration

   Hello,

   We need a trusted device ID for our Bill.com API integration.

   Organization ID: {tu_org_id}
   Environment: Sandbox/Production

   Please provide a deviceId that we can use for MFA-free payment creation via API.

   Thank you!
   ```

2. **Configurar el ID recibido**
   - Bill.com responde con deviceId
   - Configurar en Odoo → Bill.com Config → MFA Device ID

### Opción 3: Verificar MFA ya Configurado

Antes de todo, verificar si ya hay MFA configurado:

```python
# En Odoo shell o mediante código
config = env['billcom.config'].search([('active', '=', True)], limit=1)

# Obtener lista de teléfonos MFA
import requests

url = f"{config.api_url}/v3/mfa/phones"
headers = {
    "accept": "application/json",
    "sessionId": config.token,
    "devKey": config.dev_key
}

response = requests.get(url, headers=headers)
phones = response.json().get('results', [])

# Ver teléfonos configurados
for phone in phones:
    print(f"Type: {phone['type']}, Last 4: {phone['last4digits']}, Primary: {phone['primary']}")

# Si hay teléfonos, MFA ya está configurado
# Solo necesitas el device ID o remember me ID
```

## 🔍 Diagnóstico del Problema

### ¿Por qué falla?

Bill.com requiere **sesión MFA-trusted** para crear pagos. Hay 3 formas de obtenerla:

1. **Device ID** (trusted device) → Usado en login
2. **Remember Me ID** (30 días) → Usado en step-up
3. **MFA Challenge/Validate** (cada vez) → Flujo completo

**Tu código actual** usa opción 1 (Device ID), pero no está configurado.

### ¿Cómo verificar si funcionará?

Después de configurar Device ID:

1. **Test Connection** en Bill.com Config
2. Ver log: `"Authenticating with trusted device ID for MFA-free session"`
3. Si aparece: ✅ Device ID válido
4. Si no aparece o error: ❌ Device ID inválido/expirado

## 📋 Checklist de Verificación

Antes de crear pago:

- [ ] Bill.com Config activa
- [ ] Token no expirado
- [ ] Organization ID correcto
- [ ] **MFA Device ID configurado** ← ESTO FALTA
- [ ] Purchase journal existe
- [ ] Vendor sincronizado

## 🔧 Troubleshooting

### Error persiste después de configurar Device ID

**Causa**: Device ID ya no está trusted

**Solución**:

1. Login de nuevo en Bill.com web
2. Completar MFA
3. Marcar "Trust device" de nuevo
4. Obtener nuevo Device ID
5. Actualizar en Odoo

### No encuentro Device ID en cookies

**Alternativa 1**: Local Storage

- Developer Tools → Application → Local Storage
- Buscar "deviceId", "device", "mfa"

**Alternativa 2**: Network Tab

- Developer Tools → Network
- Hacer login con MFA
- Buscar request a `/v3/login`
- Ver Response → buscar "deviceId"

**Alternativa 3**: Bill.com Support

- Más confiable
- Garantizado funcional

### Device ID se invalida frecuentemente

**Causa**: Políticas de seguridad de Bill.com

**Solución**:

- Usar Remember Me ID + Step-Up (opción avanzada)
- O contactar Bill.com para device permanente

## 🎯 Resumen

**Para solucionar AHORA**:

1. Obtener Device ID (3 métodos arriba)
2. Configurar en Odoo
3. ¡Pagos funcionarán!

**Si no puedes obtener Device ID**:

- Contactar Bill.com support
- O implementar flujo MFA completo (más complejo)

**El código ya está listo**, solo falta la configuración del Device ID.

---

## 📞 Contacto Bill.com Support

**Email**: support@bill.com **Asunto**: API Integration - Trusted Device ID Request
**Info a proporcionar**:

- Organization ID
- Environment (Sandbox/Production)
- Purpose: API payment creation
- Request: Trusted device ID for MFA-free operations

**Tiempo de respuesta**: 1-2 días hábiles

---

## ✅ Verificación Final

Después de configurar Device ID, hacer test:

```python
# Test en Odoo shell
config = env['billcom.config'].search([('active', '=', True)], limit=1)

# Ver si device ID configurado
print(f"Device ID: {config.mfa_device_id[:10]}..." if config.mfa_device_id else "NOT CONFIGURED")

# Test connection
config.test_connection()

# Si no hay error → ✅ Configurado correctamente
# Si error MFA → ❌ Device ID inválido
```

**¡Con Device ID configurado, todo funcionará!** 🎉
