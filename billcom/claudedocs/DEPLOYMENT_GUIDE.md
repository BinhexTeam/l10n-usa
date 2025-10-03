# Guía de Deployment - Bill.com Integration

## ✅ Cambios Completados

### 1. Errores Críticos Corregidos

**controllers/billcom_controller.py**:

- ✅ Línea 489: `request.jsonrequest` → `request.get_json_data()`
- ✅ Líneas 569, 574, 579: `if 'webhook_log' in locals():` → `if webhook_log:`

### 2. Refactorización Arquitectónica

**models/res_partner.py**:

- ✅ Eliminadas 150+ líneas de lógica duplicada
- ✅ Implementado patrón de delegación limpio
- ✅ Todos los métodos ahora delegan a billcom_service

**models/billcom_service.py**:

- ✅ Agregados 3 métodos centralizados:
  - `sync_partners_from_billcom()` (líneas 2070-2239)
  - `sync_partners_cron()` (líneas 2242-2280)
  - `sync_partner_from_billcom_by_id()` (líneas 2283-2394)

### 3. Arquitectura Final

```
Controllers (webhooks)
    ↓
Models (delegación simple)
    ↓
billcom_service.py (TODA la lógica API)
    ↓
billcom_service_abstract.py (autenticación, tokens)
    ↓
Bill.com API v3
```

---

## 🚀 Pasos para Deployment

### 1. Verificar Cambios

```bash
# Ver archivos modificados
cd /home/adruban/Workspace/Doodba_ENV/O16/odoo/custom/src/l10n-usa/billcom

git status

# Debería mostrar:
# modified:   controllers/billcom_controller.py
# modified:   models/res_partner.py
# modified:   models/billcom_service.py
```

### 2. Restart Odoo

```bash
# Desde el directorio del proyecto Doodba
docker-compose restart odoo

# Ver logs
docker-compose logs -f odoo
```

### 3. Upgrade del Módulo

```bash
# Opción 1: Desde línea de comandos
docker-compose exec odoo odoo -u billcom -d [nombre_base_datos] --stop-after-init

# Opción 2: Desde UI de Odoo
# Apps → billcom → Upgrade
```

### 4. Verificar Logs

```bash
# Filtrar logs de billcom
docker-compose logs -f odoo | grep billcom

# Buscar errores
docker-compose logs odoo | grep -i error | grep billcom
```

---

## 🧪 Testing

### Test 1: Webhook Básico

```bash
# Test endpoint webhook
curl -X POST http://localhost:8069/billcom/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event": {
      "eventType": "vendor.created",
      "organizationId": "your-org-id"
    },
    "vendor": {
      "id": "ven-test-123",
      "name": "Test Vendor"
    }
  }'

# Debería retornar JSON sin errores
# Verificar en logs que se procesó correctamente
```

### Test 2: Sincronización de Vendor

Desde Odoo Shell:

```python
# Acceder a shell
docker-compose exec odoo odoo shell -d [database_name]

# En el shell de Odoo:
env = self.env

# Test sync individual vendor
service = env['billcom.service'].sudo()
partner = env['res.partner'].search([('name', '=', 'Test Vendor')], limit=1)
result = service.sync_partner(partner, 'vendor')
print(f"Sync result: {result}")

# Test sync desde Bill.com
count = service.sync_partners_from_billcom('vendor')
print(f"Synced {count} vendors from Bill.com")
```

### Test 3: Cron Job

```python
# En Odoo shell
service = env['billcom.service'].sudo()
result = service.sync_partners_cron()
print(f"Cron execution: {result}")

# Verificar que se sincronizaron vendors y customers
```

### Test 4: MFA y Pagos

```python
# Verificar que MFA está configurado
config = env['billcom.config'].sudo().get_config()
print(f"MFA Remember Me ID: {config.mfa_remember_me_id[:20]}..." if config.mfa_remember_me_id else "Not configured")

# Crear un pago de prueba (requiere MFA)
# Desde UI: Accounting → Vendors → Bill → Register Payment
# Verificar logs para confirmar que step-up se ejecuta
```

---

## 🔍 Verificación de URLs

### URLs Correctas Implementadas

✅ **Vendors**:

- `POST /v3/vendors` - Create
- `GET /v3/vendors` - List
- `GET /v3/vendors/{id}` - Get one
- `PATCH /v3/vendors/{id}` - Update

✅ **Customers**:

- `POST /v3/customers` - Create
- `GET /v3/customers` - List
- `GET /v3/customers/{id}` - Get one
- `PATCH /v3/customers/{id}` - Update

✅ **Bank Accounts**:

- `POST /v3/vendors/{id}/bank-account`
- `GET /v3/vendors/{id}/bank-account`

### Verificar en Logs

```bash
# Buscar llamadas API en logs
docker-compose logs odoo | grep "Bill.com API request" | tail -20

# Debería mostrar URLs como:
# POST https://gateway.stage.bill.com/connect/v3/vendors
# PATCH https://gateway.stage.bill.com/connect/v3/vendors/ven123456
```

---

## 🐛 Troubleshooting

### Error: "No module named 'billcom.service'"

```bash
# Restart Odoo y upgrade
docker-compose restart odoo
docker-compose exec odoo odoo -u billcom -d [db] --stop-after-init
```

### Error: Webhook sigue fallando

```bash
# Verificar que los cambios están aplicados
docker-compose exec odoo grep "get_json_data" /opt/odoo-server/extra_addons/oca/l10n-usa/billcom/controllers/billcom_controller.py

# Debería mostrar la línea con request.get_json_data()
```

### Error: Partners no sincronizan

```python
# Verificar configuración
config = env['billcom.config'].sudo().get_config()
print(f"Sync vendors enabled: {config.sync_vendors}")
print(f"Sync customers enabled: {config.sync_customers}")
print(f"API URL: {config.api_url}")

# Test manual
service = env['billcom.service'].sudo()
try:
    result = service.sync_partners_from_billcom('vendor')
    print(f"Success: {result} vendors synced")
except Exception as e:
    print(f"Error: {e}")
```

---

## 📊 Monitoreo Post-Deployment

### Logs a Monitorear

```bash
# Ver logs en tiempo real
docker-compose logs -f odoo | grep -E "billcom|Bill.com"

# Buscar errores específicos
docker-compose logs odoo | grep -E "ERROR.*billcom|CRITICAL.*billcom"

# Verificar webhooks procesados
docker-compose logs odoo | grep "Received Bill.com webhook"

# Verificar sincronizaciones
docker-compose logs odoo | grep "Synced.*from Bill.com"
```

### Verificar en Base de Datos

```sql
-- Partners sincronizados recientemente
SELECT name, billcom_id, last_sync_date, billcom_sync_state
FROM res_partner
WHERE is_sync_to_billcom = true
ORDER BY last_sync_date DESC
LIMIT 10;

-- Webhooks procesados
SELECT event_type, entity_id, status, created_at
FROM billcom_webhook_log
ORDER BY created_at DESC
LIMIT 20;
```

---

## ✅ Checklist de Deployment

- [ ] Cambios verificados en archivos
- [ ] Odoo reiniciado (`docker-compose restart odoo`)
- [ ] Módulo actualizado (`odoo -u billcom`)
- [ ] Logs verificados sin errores
- [ ] Test webhook ejecutado correctamente
- [ ] Test sync vendor/customer funciona
- [ ] Test cron job ejecuta sin errores
- [ ] URLs de API verificadas en logs
- [ ] MFA configurado y funcional
- [ ] Pagos se crean con step-up exitoso

---

## 📚 Documentación Relacionada

1. `claudedocs/ARCHITECTURE_REDESIGN.md` - Arquitectura completa
2. `claudedocs/REFACTORING_SUMMARY.md` - Resumen de cambios
3. `claudedocs/MFA_QUICK_GUIDE.md` - Guía de MFA
4. `claudedocs/WEBHOOK_TESTING_GUIDE.md` - Testing de webhooks

---

## 🎯 KPIs de Éxito

1. **Webhooks**: 0 errores de AttributeError
2. **Sincronización**: 100% de vendors/customers sincronizados
3. **MFA**: Pagos se crean con step-up automático
4. **Logs**: Sin errores críticos en 24 horas
5. **Performance**: Tiempo de sincronización < 5 min para 100 partners

---

## 📞 Soporte

Si encuentras problemas después del deployment:

1. Revisar logs: `docker-compose logs -f odoo | grep billcom`
2. Verificar configuración en Odoo UI
3. Ejecutar tests desde shell de Odoo
4. Consultar documentación en `claudedocs/`
