# MFA Step-Up Fix - Verificación de Estado

## 🔍 Problema Identificado

El código no estaba siguiendo el flujo correcto de Bill.com para MFA step-up:

### ❌ Flujo Incorrecto (ANTES)

```python
1. Login → sessionId
2. MFA step-up directamente → ❌ Falla con {"trusted": false}
```

### ✅ Flujo Correcto (DESPUÉS)

```python
1. Login → sessionId
2. GET /v3/login/session → Verificar mfaStatus
3. Si mfaStatus != "COMPLETE" → POST /v3/mfa/step-up
```

## 📝 Referencia Oficial

Según la documentación de Bill.com y el código de ejemplo oficial:

```python
# Código de ejemplo de Bill.com
mfa_status_url = "https://gateway.stage.bill.com/connect/v3/login/session"
mfa_status_response = requests.get(mfa_status_url, headers=mfa_status_headers)
mfa_status = json.loads(mfa_status_response.text)['mfaStatus']

# MFA step-up SOLO si mfaStatus != "COMPLETE"
if mfa_status != "COMPLETE":
    mfa_stepup_response = requests.post(mfa_stepup_url, ...)
```

## ✅ Cambios Implementados

### Archivo: `billcom_service_abstract.py:560-641`

```python
def _mfa_step_up(self, config, session_id):
    """Convert current session to MFA-trusted using step-up"""
    try:
        # NUEVO: Step 1 - Check current MFA status
        status_url = f"{config.api_url}/v3/login/session"
        status_headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "sessionId": session_id,
            "devKey": config.dev_key,
        }

        _logger.info("Checking MFA status at: %s", status_url)
        status_response = requests.get(status_url, headers=status_headers, timeout=30)

        if status_response.status_code != 200:
            raise UserError(_("Failed to check MFA status: %s") % status_response.text)

        status_result = status_response.json()
        mfa_status = status_result.get("mfaStatus")
        _logger.info("Current MFA status: %s", mfa_status)

        # NUEVO: Step 2 - If already COMPLETE, skip step-up
        if mfa_status == "COMPLETE":
            _logger.info("✅ Session already has MFA COMPLETE status - no step-up needed")
            return True

        # Step 3 - Perform MFA step-up (solo si no es COMPLETE)
        _logger.info("MFA status is '%s' - performing step-up", mfa_status)
        step_up_url = f"{config.api_url}/v3/mfa/step-up"

        # ... resto del código de step-up
```

## 🔄 Nuevo Flujo Completo

```
┌─────────────────────────────────────────────────────────────┐
│  1. Login Básico                                             │
│     POST /v3/login                                           │
│     → sessionId (sin MFA)                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  2. NUEVO: Verificar Estado MFA                             │
│     GET /v3/login/session                                    │
│     → mfaStatus: "COMPLETE" o "INCOMPLETE"                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
              ┌────────┴────────┐
              │                 │
    mfaStatus == "COMPLETE"    mfaStatus != "COMPLETE"
              │                 │
              ▼                 ▼
┌─────────────────────┐  ┌─────────────────────────────────────┐
│  ✅ Ya tiene MFA    │  │  3. Hacer MFA Step-Up               │
│  No hacer nada      │  │     POST /v3/mfa/step-up            │
│  return True        │  │     body: { rememberMeId, device }  │
└─────────────────────┘  │     → {"trusted": true}             │
                         └─────────────────────────────────────┘
```

## 📊 Estados MFA Posibles

| Estado           | Significado                  | Acción           |
| ---------------- | ---------------------------- | ---------------- |
| `COMPLETE`       | Sesión ya tiene MFA completo | ✅ Skip step-up  |
| `INCOMPLETE`     | Sesión necesita MFA          | 🔄 Hacer step-up |
| `REQUIRED`       | MFA obligatorio              | 🔄 Hacer step-up |
| `null` / ausente | Sin información              | 🔄 Hacer step-up |

## 🐛 Por Qué Fallaba Antes

**Causa Root**: Hacer step-up SIN verificar estado causaba que Bill.com rechazara la
operación porque:

1. La sesión ya podría tener MFA completo → step-up innecesario retorna
   `{"trusted": false}`
2. El rememberMeId está expirado → sin verificación previa, no se detecta a tiempo
3. Falta contexto del estado actual → imposible saber si el problema es de estado o de
   rememberMeId

## ✅ Beneficios del Nuevo Flujo

1. **Optimización**: Si `mfaStatus == "COMPLETE"`, skip step-up (más rápido)
2. **Debugging**: Logs muestran el estado MFA actual para mejor troubleshooting
3. **Cumplimiento**: Sigue el flujo oficial de Bill.com
4. **Claridad**: Mensajes de error más específicos según el estado

## 🧪 Testing

### Test Manual

```bash
# Restart Odoo
docker-compose restart odoo

# Ver logs del flujo completo
docker-compose logs -f odoo | grep -E "MFA|step-up|mfaStatus"
```

### Logs Esperados (Caso Exitoso)

```
Checking MFA status at: https://gateway.stage.bill.com/connect/v3/login/session
Current MFA status: INCOMPLETE
MFA status is 'INCOMPLETE' - performing step-up
Step-up URL: https://gateway.stage.bill.com/connect/v3/mfa/step-up
Step-up response status: 200
Step-up response body: {"trusted":true}
✅ Session successfully marked as MFA-trusted via step-up
```

### Logs Esperados (Ya Tiene MFA)

```
Checking MFA status at: https://gateway.stage.bill.com/connect/v3/login/session
Current MFA status: COMPLETE
✅ Session already has MFA COMPLETE status - no step-up needed
```

### Logs Esperados (RememberMeId Expirado)

```
Checking MFA status at: https://gateway.stage.bill.com/connect/v3/login/session
Current MFA status: INCOMPLETE
MFA status is 'INCOMPLETE' - performing step-up
Step-up response body: {"trusted":false}
RememberMeId appears to be expired or invalid - cleared from config
Error: MFA Remember Me ID has expired or is invalid. Please use 'Setup MFA' button
```

## 🎯 Próximos Pasos

1. **Restart Odoo**

   ```bash
   docker-compose restart odoo
   ```

2. **Setup MFA de Nuevo** (si rememberMeId expiró)

   - Settings → Bill.com Configuration
   - Click "Setup MFA"
   - Ingresar código SMS

3. **Test Connection**

   - Click "Test Connection"
   - Verificar logs muestran el nuevo flujo

4. **Test Pago**
   - Crear un pago de prueba
   - Verificar que se crea sin errores BDC_1361

## 📚 Referencias

- [Bill.com MFA Documentation](https://developer.bill.com/hc/en-us/articles/360046953552)
- [Bill.com Login Session Endpoint](https://developer.bill.com/reference/get_v3-login-session)
- [Bill.com MFA Step-Up Endpoint](https://developer.bill.com/reference/post_v3-mfa-step-up)
- `claudedocs/MFA_REMEMBER_ME_EXPIRED.md` - Guía de expiración
- `claudedocs/MFA_QUICK_GUIDE.md` - Guía rápida MFA

## 🔍 Debug Checklist

Si aún falla después de este fix:

- [ ] Logs muestran `Checking MFA status`
- [ ] Logs muestran `mfaStatus: INCOMPLETE` o `COMPLETE`
- [ ] Si COMPLETE → skip step-up
- [ ] Si INCOMPLETE → ejecuta step-up
- [ ] Step-up retorna `{"trusted": true}`
- [ ] RememberMeId tiene ~60-80 caracteres
- [ ] RememberMeId no tiene espacios o caracteres extraños
- [ ] Entorno (sandbox/production) coincide con donde se generó rememberMeId

## ✨ Resumen de Mejoras

| Aspecto                    | Antes            | Después                       |
| -------------------------- | ---------------- | ----------------------------- |
| **Verificación de Estado** | ❌ No            | ✅ Sí (GET /v3/login/session) |
| **Optimización**           | Siempre step-up  | Skip si ya COMPLETE           |
| **Logs**                   | Básicos          | Detallados con estado MFA     |
| **Error Messages**         | Genéricos        | Específicos según estado      |
| **Cumplimiento API**       | ❌ No sigue docs | ✅ Sigue flujo oficial        |
