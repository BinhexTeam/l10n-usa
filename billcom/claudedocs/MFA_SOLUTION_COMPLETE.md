# MFA Solution Complete - Bill.com Payments

## 🎯 Soluciones Disponibles para MFA

### Opción 1: MFA Step-Up (⭐ RECOMENDADO - Más Simple)

**Endpoint**: `POST /v3/mfa/step-up`

**Ventaja**: Convierte sesión actual en MFA-trusted sin deviceId ni flujo MFA completo.

**Proceso**:

1. Login normal con `/v3/login` → obtiene sessionId
2. Llamar `/v3/mfa/step-up` con `rememberMeId` + `device`
3. Sesión actual se marca como MFA-trusted
4. Crear pagos sin problemas

**Implementación**:

```python
def _mfa_step_up(self, config, session_id):
    """Convert current session to MFA-trusted using step-up"""
    step_up_url = f"{config.api_url}/v3/mfa/step-up"

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "sessionId": session_id,
        "devKey": config.dev_key
    }

    payload = {
        "rememberMeId": config.mfa_remember_me_id,  # 30-day MFA ID
        "device": config.mfa_device_name or "Odoo Integration"
    }

    response = requests.post(step_up_url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()

    result = response.json()

    if result.get("trusted"):
        _logger.info("Session successfully marked as MFA-trusted via step-up")
        return True
    else:
        raise UserError(_("Failed to mark session as MFA-trusted"))
```

**Flujo Completo**:

```python
def authenticate(self, config):
    # 1. Login normal
    session_id = self._login(config)

    # 2. Si hay rememberMeId configurado, hacer step-up
    if config.mfa_remember_me_id:
        self._mfa_step_up(config, session_id)

    # 3. Sesión ahora es MFA-trusted
    return session_id
```

**¿Cómo obtener rememberMeId?**:

- Se genera cuando haces MFA challenge/validate con `rememberMe: true`
- Válido por 30 días
- Una vez obtenido, reutilizarlo en step-up

### Opción 2: Device ID en Login (Simple pero requiere setup manual)

**Endpoint**: `POST /v3/login` con `deviceId`

**Proceso**:

```python
payload = {
    "userName": config.username,
    "password": config.password,
    "orgId": config.organization_id,
    "devKey": config.dev_key,
    "deviceId": config.mfa_device_id  # <-- Trusted device
}
```

**Cómo obtener deviceId**:

1. Login manual en Bill.com web
2. Completar MFA y marcar "Trust this device"
3. Extraer deviceId del browser
4. Configurar en Odoo

### Opción 3: MFA Challenge/Validate Flow (Completo pero complejo)

**Flujo Completo**:

1. **Setup Phone** (una vez):

```python
POST /v3/mfa/setup
{
    "phone": "+1234567890",
    "type": "TEXT",  # o "VOICE"
    "primary": true
}
# Response: {"setupId": "..."}
```

2. **Validate Phone**:

```python
POST /v3/mfa/validate
{
    "setupId": "...",
    "token": "123456"  # Código SMS recibido
}
```

3. **Generate Challenge** (cada sesión):

```python
POST /v3/mfa/challenge
# Response: {"challengeId": "..."}
# SMS enviado automáticamente
```

4. **Validate Challenge**:

```python
POST /v3/mfa/challenge/validate
{
    "challengeId": "...",
    "token": "123456",
    "rememberMe": true  # <-- Genera rememberMeId
}
# Response: {"sessionId": "...", "rememberMeId": "..."}
```

5. **Guardar rememberMeId** para futuros step-ups

## 🚀 Implementación Recomendada (Step-Up)

### 1. Agregar Campos en billcom_config.py

```python
# MFA Step-Up fields
mfa_remember_me_id = fields.Char(
    string="MFA Remember Me ID",
    help="30-day MFA ID for step-up authentication. "
         "Generated from MFA challenge/validate with rememberMe=true",
    tracking=True,
)

mfa_device_name = fields.Char(
    string="MFA Device Name",
    default="Odoo Integration",
    help="Friendly name for this integration device",
)
```

### 2. Modificar authenticate() en billcom_service_abstract.py

```python
def authenticate(self, config):
    """Authenticate with Bill.com API v3 with MFA support"""
    auth_url = f"{config.api_url}/v3/login"

    payload = {
        "organizationId": config.organization_id,
        "devKey": config.dev_key,
        "username": config.username,
        "password": config.password,
    }

    # Option 1: Use device ID if configured
    if config.mfa_device_id:
        payload["deviceId"] = config.mfa_device_id
        _logger.info("Authenticating with trusted device ID")

    headers = {"accept": "application/json", "content-type": "application/json"}
    response = requests.post(auth_url, json=payload, headers=headers, timeout=40)
    response.raise_for_status()

    result = response.json()
    session_id = result.get("sessionId")

    if not session_id:
        raise UserError(_("No session ID received from Bill.com API"))

    # Option 2: Use step-up if rememberMeId configured
    if not config.mfa_device_id and config.mfa_remember_me_id:
        _logger.info("Performing MFA step-up to mark session as trusted")
        self._mfa_step_up(config, session_id)

    # Store token
    config.sudo().write({
        'token': session_id,
        'token_expiry': fields.Datetime.now() + timedelta(hours=1),
    })

    return session_id

def _mfa_step_up(self, config, session_id):
    """Convert current session to MFA-trusted using step-up"""
    step_up_url = f"{config.api_url}/v3/mfa/step-up"

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "sessionId": session_id,
        "devKey": config.dev_key
    }

    payload = {
        "rememberMeId": config.mfa_remember_me_id,
        "device": config.mfa_device_name or "Odoo Integration"
    }

    try:
        response = requests.post(step_up_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()

        if result.get("trusted"):
            _logger.info("Session successfully marked as MFA-trusted via step-up")
            return True
        else:
            _logger.error("Step-up failed to mark session as trusted")
            raise UserError(_("Failed to mark session as MFA-trusted"))

    except requests.exceptions.RequestException as e:
        _logger.error("MFA step-up request failed: %s", str(e))

        # If rememberMeId expired, clear it
        if "expired" in str(e).lower() or "invalid" in str(e).lower():
            config.sudo().write({'mfa_remember_me_id': False})
            _logger.warning("RememberMeId expired or invalid - cleared from config")

        raise UserError(_("MFA step-up failed: %s") % str(e))
```

### 3. Método para Obtener rememberMeId (Primera vez)

```python
def perform_initial_mfa_setup(self, config):
    """Perform initial MFA setup to get rememberMeId (one-time)"""

    # 1. Login normal
    session_id = self._basic_login(config)

    # 2. Generate MFA challenge
    challenge_url = f"{config.api_url}/v3/mfa/challenge"
    headers = {
        "sessionId": session_id,
        "devKey": config.dev_key,
        "content-type": "application/json"
    }

    response = requests.post(challenge_url, headers=headers, timeout=30)
    result = response.json()
    challenge_id = result.get("challengeId")

    _logger.info("MFA challenge generated: %s. Check phone for code.", challenge_id)

    # 3. User receives SMS, returns to validate
    # This would be a wizard or separate action
    return {
        'type': 'ir.actions.act_window',
        'name': 'Enter MFA Code',
        'res_model': 'billcom.mfa.wizard',
        'view_mode': 'form',
        'target': 'new',
        'context': {
            'default_challenge_id': challenge_id,
            'default_session_id': session_id,
            'default_config_id': config.id,
        }
    }

def validate_mfa_and_get_remember_me_id(self, config, challenge_id, mfa_code):
    """Validate MFA code and get rememberMeId"""
    validate_url = f"{config.api_url}/v3/mfa/challenge/validate"

    headers = {
        "sessionId": config.token,
        "devKey": config.dev_key,
        "content-type": "application/json"
    }

    payload = {
        "challengeId": challenge_id,
        "token": mfa_code,
        "rememberMe": True  # <-- Key! Generate rememberMeId
    }

    response = requests.post(validate_url, json=payload, headers=headers, timeout=30)
    result = response.json()

    remember_me_id = result.get("rememberMeId")

    if remember_me_id:
        # Store for future step-ups
        config.sudo().write({
            'mfa_remember_me_id': remember_me_id
        })
        _logger.info("RememberMeId obtained and stored: %s", remember_me_id[:10] + "...")
        return True
    else:
        raise UserError(_("Failed to obtain rememberMeId from MFA validation"))
```

### 4. Wizard para Capturar MFA Code

```python
# models/billcom_mfa_wizard.py
class BillcomMfaWizard(models.TransientModel):
    _name = 'billcom.mfa.wizard'
    _description = 'Bill.com MFA Code Entry'

    challenge_id = fields.Char(required=True)
    session_id = fields.Char(required=True)
    config_id = fields.Many2one('billcom.config', required=True)
    mfa_code = fields.Char(string="MFA Code", required=True, size=6)

    def action_validate(self):
        service = self.env['billcom.service']
        service.validate_mfa_and_get_remember_me_id(
            self.config_id,
            self.challenge_id,
            self.mfa_code
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('MFA Setup Complete'),
                'message': _('RememberMeId has been saved. Payment creation is now enabled.'),
                'type': 'success',
                'sticky': False,
            }
        }
```

### 5. UI Updates (billcom_config_views.xml)

```xml
<!-- MFA Section -->
<group string="MFA Configuration">
    <field name="mfa_device_id" password="True" placeholder="Device ID (Option 1)" />
    <field
    name="mfa_remember_me_id"
    password="True"
    placeholder="Remember Me ID (Option 2)"
  />
    <field name="mfa_device_name" placeholder="Odoo Integration" />
    <button
    name="perform_initial_mfa_setup"
    string="Setup MFA (First Time)"
    type="object"
    class="btn-primary"
    attrs="{'invisible': [('mfa_remember_me_id', '!=', False)]}"
  />
</group>
```

## 📋 Flujo de Usuario Final

### Setup Inicial (Una vez)

**Opción A: Device ID (Manual)**

1. Login en Bill.com web
2. Completar MFA, marcar "Trust device"
3. Copiar deviceId del browser
4. Pegar en Odoo → MFA Device ID

**Opción B: Step-Up (Semi-automático)**

1. En Odoo → Bill.com Config
2. Click "Setup MFA (First Time)"
3. Recibir SMS con código
4. Ingresar código en wizard
5. rememberMeId guardado automáticamente
6. Válido por 30 días

### Uso Diario

**Con Device ID**:

- Login usa deviceId
- Sesión automáticamente MFA-trusted
- Crear pagos sin problemas

**Con Remember Me ID**:

- Login normal
- Step-up automático con rememberMeId
- Sesión MFA-trusted
- Crear pagos sin problemas

### Renovación (cada 30 días)

**Remember Me ID expira**:

1. Sistema detecta expiración en step-up
2. Clear rememberMeId automático
3. Botón "Setup MFA" aparece de nuevo
4. Usuario repite proceso (2 minutos)

## ✅ Ventajas de Cada Opción

### Device ID

- ✅ Setup muy simple (copiar/pegar)
- ✅ No expira (mientras device trusted)
- ❌ Requiere acceso al browser
- ❌ Manual para obtener

### Remember Me ID + Step-Up

- ✅ Semi-automatizado desde Odoo
- ✅ No requiere browser access
- ✅ Proceso guiado con wizard
- ❌ Expira cada 30 días
- ❌ Requiere renovación periódica

### Recomendación Final

**Para Producción**: Use ambos

1. Configurar Remember Me ID como primario (step-up)
2. Device ID como fallback
3. Si Remember Me expira, step-up usa Device ID
4. Usuario puede renovar Remember Me cuando quiera

## 🎯 Estado de Implementación

### ✅ Ya Implementado

- Detección de "Untrusted session"
- No más retry loops
- Device ID support en authenticate()
- Campo mfa_device_id en UI
- Mensajes de error claros

### 🔄 Por Implementar (Opcional)

- [ ] Método `_mfa_step_up()`
- [ ] Campos `mfa_remember_me_id` y `mfa_device_name`
- [ ] Wizard para MFA code entry
- [ ] Botón "Setup MFA" en config
- [ ] Auto-renovación de Remember Me ID

### 📝 Documentación

- [x] MFA_PAYMENT_ISSUE.md
- [x] MFA_SOLUTION_COMPLETE.md (este documento)
- [ ] User guide para setup MFA

## 🚀 Próximos Pasos

### Mínimo para Funcionar (Ya está)

1. ✅ Usuario obtiene deviceId manualmente
2. ✅ Configura en Odoo
3. ✅ Pagos funcionan

### Mejorar UX (Opcional)

1. Implementar step-up con wizard
2. Auto-renovación de Remember Me
3. Notificaciones de expiración
4. Proceso totalmente desde Odoo

**La solución actual ya permite crear pagos si el usuario configura deviceId.** 🎉
