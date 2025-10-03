# MFA Remember Me ID - Problema de Expiración

## 🔴 Problema Detectado

```
Error: {"trusted": false}
Step-up response did not indicate trusted status
Failed to mark session as MFA-trusted
```

## 🔍 Causa Raíz

El **Remember Me ID ha expirado o es inválido**. Esto puede pasar por:

1. **Expiración Natural**: Han pasado más de 30 días desde que se generó
2. **Cambio de Entorno**: El rememberMeId fue generado en sandbox pero ahora usas
   production (o viceversa)
3. **Revocación**: Fue revocado manualmente en Bill.com
4. **Formato Incorrecto**: El ID guardado está corrupto o incompleto

## ✅ Solución Implementada

He actualizado el código para que **automáticamente limpie el rememberMeId inválido** y
muestre un mensaje claro al usuario:

### Cambio en `billcom_service_abstract.py:606-614`

```python
# ANTES: Solo mostraba error genérico
if result.get("trusted"):
    return True
else:
    raise UserError(_("Failed to mark session as MFA-trusted"))

# DESPUÉS: Limpia rememberMeId y da instrucciones claras
if result.get("trusted"):
    return True
else:
    # Limpiar rememberMeId inválido
    config.sudo().write({"mfa_remember_me_id": False})
    raise UserError(_(
        "MFA Remember Me ID has expired or is invalid.\n\n"
        "Please use 'Setup MFA' button to obtain a new one.\n\n"
        "The Remember Me ID has been cleared from configuration."
    ))
```

## 🚀 Pasos para Resolver

### 1. Restart Odoo

```bash
docker-compose restart odoo
```

### 2. Volver a Setup MFA

Desde la configuración de Bill.com en Odoo:

1. Ve a: **Settings → Bill.com Configuration**
2. El campo **MFA Remember Me ID** ahora debe estar **vacío** (limpiado automáticamente)
3. Click en el botón **"Setup MFA (Automated)"**
4. Ingresa el código SMS de 6 dígitos que recibes
5. El nuevo Remember Me ID se guardará automáticamente

### 3. Test Connection

Después de hacer setup MFA:

1. Click en **"Test Connection"** en la configuración
2. Deberías ver logs como:
   ```
   ✅ Session successfully marked as MFA-trusted via step-up
   Connection test successful
   ```

### 4. Verificar en Logs

```bash
# Ver logs del proceso MFA
docker-compose logs -f odoo | grep -E "MFA|step-up|trusted"

# Deberías ver:
# Performing MFA step-up to mark session as trusted
# Step-up response status: 200
# Step-up response body: {"trusted":true}  ← Ahora debe ser true
# ✅ Session successfully marked as MFA-trusted via step-up
```

---

## 🔄 Ciclo de Vida del Remember Me ID

```
┌─────────────────────────────────────────────────────────────┐
│  1. Setup MFA (Primera vez o re-setup)                      │
│     POST /v3/mfa/challenge → challengeId                     │
│     POST /v3/mfa/challenge/validate → rememberMeId           │
│     Guardar en config.mfa_remember_me_id                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Uso Normal (siguientes 30 días)                         │
│     POST /v3/login → sessionId (normal)                      │
│     POST /v3/mfa/step-up + rememberMeId → trusted: true     │
│     ✅ Sesión MFA-trusted creada automáticamente            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Expiración (después de 30 días)                         │
│     POST /v3/mfa/step-up + rememberMeId → trusted: false    │
│     ❌ RememberMeId expirado o inválido                     │
│     Limpiar config.mfa_remember_me_id = False                │
│     Mostrar mensaje: "Please use Setup MFA button"          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
                   Volver a paso 1
```

---

## 📝 Verificación Post-Setup

### En Base de Datos

```sql
-- Verificar que Remember Me ID está guardado correctamente
SELECT
    name,
    mfa_remember_me_id IS NOT NULL as has_remember_me_id,
    LENGTH(mfa_remember_me_id) as id_length,
    mfa_device_name
FROM billcom_config
WHERE id = 1;

-- Resultado esperado:
-- has_remember_me_id: true
-- id_length: ~60-80 caracteres
-- mfa_device_name: "Odoo Integration"
```

### Test Manual desde Shell

```python
# Acceder a Odoo shell
docker-compose exec odoo odoo shell -d [database]

# Test MFA step-up
config = env['billcom.config'].sudo().get_config()
print(f"Remember Me ID configurado: {bool(config.mfa_remember_me_id)}")

# Test autenticación completa
service = env['billcom.service.abstract'].sudo()
try:
    token = service._get_token(config)
    print(f"✅ Token obtenido: {token[:20]}...")
    print("MFA step-up ejecutado correctamente")
except Exception as e:
    print(f"❌ Error: {e}")
```

---

## 🎯 Mejoras Implementadas

1. **Auto-limpieza**: El sistema automáticamente limpia rememberMeId inválidos
2. **Mensajes Claros**: El usuario sabe exactamente qué hacer
3. **No Bloqueo**: El sistema no se queda en estado inválido
4. **Logging Mejorado**: Más información en logs para debugging

---

## 🐛 Troubleshooting

### Error: "Setup MFA button no aparece"

```xml
<!-- Verificar en billcom_config_views.xml -->
<button
  name="action_setup_mfa"
  type="object"
  string="Setup MFA (Automated)"
  class="btn-primary"
  icon="fa-shield"
  attrs="{'invisible': [('mfa_remember_me_id', '!=', False)]}"
/>
```

El botón solo aparece cuando `mfa_remember_me_id` es False (vacío).

### Error: "No recibo código SMS"

- Verifica que el teléfono esté registrado en Bill.com
- Intenta desde Bill.com web UI para confirmar que SMS funciona
- Espera 5-10 minutos y vuelve a intentar

### Error: "BDC_1358: Too many attempts"

- Espera 5-10 minutos antes de volver a intentar
- No hagas múltiples intentos rápidos de validación
- Si persiste, contacta soporte de Bill.com

---

## 📚 Referencias

- [Bill.com MFA Documentation](https://developer.bill.com/hc/en-us/articles/360046953552)
- `claudedocs/MFA_QUICK_GUIDE.md` - Guía rápida de MFA
- `claudedocs/MFA_TROUBLESHOOTING.md` - Solución de problemas MFA
- `claudedocs/ARCHITECTURE_REDESIGN.md` - Arquitectura completa

---

## ✅ Checklist de Resolución

- [ ] Restart Odoo ejecutado
- [ ] Remember Me ID limpiado automáticamente
- [ ] Setup MFA ejecutado con nuevo código SMS
- [ ] Nuevo Remember Me ID guardado en config
- [ ] Test Connection exitoso
- [ ] Logs muestran `{"trusted": true}`
- [ ] Payments se pueden crear sin errores BDC_1361
