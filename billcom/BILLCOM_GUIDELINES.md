# Bill.com Integration Module - Guidelines

## Visión General del Módulo

El **Bill.com Integration Module** es una solución completa para sincronizar datos
financieros entre Odoo 16 y la plataforma Bill.com utilizando la API v3. Este módulo
proporciona sincronización bidireccional de proveedores, facturas, pagos y documentos,
con un sistema robusto de colas y logging.

### Características Principales

- ✅ **Sincronización bidireccional** de datos entre Odoo y Bill.com
- ✅ **API v3 de Bill.com** - Última versión disponible
- ✅ **Sistema de colas** para procesamiento asíncrono y confiable
- ✅ **Sistema de logging** completo para auditoría y debugging
- ✅ **Dashboard interactivo** para monitoreo del estado de sincronización
- ✅ **Manejo de errores** con reintentos automáticos
- ✅ **Soporte multi-empresa** con configuraciones independientes

---

## Arquitectura del Módulo

### 🏗️ **Estructura Principal**

```
billcom/
├── models/                              # Modelos de datos
│   ├── billcom_config.py               # Configuración principal
│   ├── billcom_service_abstract.py     # Servicio base abstracto
│   ├── billcom_service.py              # Implementación del servicio
│   ├── billcom_sync_queue.py           # Sistema de colas
│   ├── billcom_logger.py               # Sistema de logging
│   ├── res_partner.py                  # Extensión de contactos
│   ├── account_move.py                 # Extensión de facturas
│   ├── account_payment.py              # Extensión de pagos
│   └── account_payment_register.py     # Registro de pagos
├── wizards/                             # Asistentes
│   └── billcom_sync_wizard.py          # Wizard de sincronización
├── views/                               # Interfaces de usuario
│   ├── billcom_config_views.xml        # Vistas de configuración
│   ├── billcom_config_kanban_dashboard.xml # Dashboard principal
│   ├── billcom_sync_queue_views.xml    # Vistas de cola de sync
│   ├── billcom_logger_views.xml        # Vistas de logs
│   └── [otros archivos de vistas]
├── data/                                # Datos y configuraciones
│   └── ir_cron_data.xml                # Tareas programadas
└── security/                           # Seguridad y accesos
    ├── ir.model.access.csv             # Permisos de acceso
    └── billcom_security.xml            # Grupos de seguridad
```

### 🔄 **Flujo de Arquitectura**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Odoo Models   │◄──►│  Billcom Service │◄──►│   Bill.com API  │
│                 │    │                  │    │       v3        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Sync Queue    │    │    Logger        │    │   Dashboard     │
│   (Async Ops)   │    │   (Audit Trail)  │    │  (Monitoring)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

---

## Sistema de Colas (billcom.sync.queue)

### 🎯 **Propósito del Sistema de Colas**

El sistema de colas de Bill.com está diseñado para:

1. **Procesamiento Asíncrono**: Evita bloqueos en la UI durante operaciones largas
2. **Confiabilidad**: Garantiza que las operaciones se completen incluso si fallan
   temporalmente
3. **Gestión de Errores**: Maneja reintentos automáticos con backoff exponencial
4. **Monitoreo**: Proporciona visibilidad completa del estado de sincronización
5. **Priorización**: Permite procesar operaciones críticas primero

### 📋 **Campos Principales del Modelo**

```python
# Información Básica
sync_type = fields.Selection([
    ('vendor', 'Vendor Sync'),
    ('customer', 'Customer Sync'),
    ('bill', 'Bill Sync'),
    ('invoice', 'Invoice Sync'),
    ('payment', 'Payment Sync'),
    ('attachment', 'Attachment Sync'),
])

direction = fields.Selection([
    ('odoo_to_billcom', 'Odoo → Bill.com'),
    ('billcom_to_odoo', 'Bill.com → Odoo'),
    ('bidirectional', 'Bidirectional'),
])

operation = fields.Selection([
    ('create', 'Create'),
    ('update', 'Update'),
    ('delete', 'Delete'),
    ('sync', 'Synchronize'),
])

# Estado y Prioridad
state = fields.Selection([
    ('draft', 'Draft'),
    ('queued', 'Queued'),
    ('processing', 'Processing'),
    ('success', 'Success'),
    ('error', 'Error'),
    ('cancelled', 'Cancelled'),
])

priority = fields.Selection([
    ('0', 'Low'),
    ('1', 'Normal'),
    ('2', 'High'),
    ('3', 'Critical'),
])
```

### 🔄 **Flujo de Procesamiento de Cola**

```
1. Creación → [draft]
    ↓
2. Encolado → [queued]
    ↓
3. Procesamiento → [processing]
    ↓
4. Resultado → [success] | [error] | [cancelled]
    ↓
5. Si error y retry_count < max_retries → [queued] (con delay)
```

### ⚙️ **Métodos Principales**

#### **create_sync_item()**

Crea un nuevo elemento en la cola de sincronización:

```python
sync_item = self.env['billcom.sync.queue'].create_sync_item(
    sync_type='vendor',
    record_model='res.partner',
    record_id=partner.id,
    direction='odoo_to_billcom',
    operation='sync',
    priority='1'
)
```

#### **process_queue()**

Procesa elementos en cola (ejecutado por cron):

```python
# Cron job ejecuta cada 5 minutos
model.process_queue(limit=50)
```

#### **action_retry()**

Reintenta operaciones fallidas:

```python
# Manual o automático con backoff exponencial
failed_item.action_retry()
```

### 🕒 **Sistema de Reintentos**

- **Máximo de reintentos**: 3 por defecto
- **Backoff exponencial**: 2^retry_count minutos
- **Programación automática**: Reintenta automáticamente en caso de fallo
- **Cancelación manual**: Los elementos pueden cancelarse si no se pueden procesar

---

## Sistema de Logging (billcom.logger)

### 📊 **Propósito del Sistema de Logs**

El sistema de logging proporciona:

1. **Auditoría Completa**: Rastrea todas las operaciones de sincronización
2. **Debugging**: Información detallada para resolver problemas
3. **Monitoreo**: Métricas en tiempo real del estado del sistema
4. **Compliance**: Registro de cambios para auditorías
5. **Performance**: Análisis de tiempos de ejecución

### 🏷️ **Estructura de Logs**

```python
# Campos Principales
operation_type = fields.Char()          # Tipo de operación
level = fields.Selection([              # Nivel del log
    ('debug', 'Debug'),
    ('info', 'Info'),
    ('warning', 'Warning'),
    ('error', 'Error'),
    ('critical', 'Critical'),
])

status = fields.Selection([             # Estado de la operación
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('success', 'Success'),
    ('error', 'Error'),
    ('retry', 'Retry'),
])

# Contexto y Referencias
record_model = fields.Char()            # Modelo Odoo relacionado
record_id = fields.Integer()            # ID del registro
billcom_id = fields.Char()              # ID en Bill.com
sync_queue_id = fields.Many2one()       # Referencia a cola

# Información de Ejecución
message = fields.Text()                 # Mensaje descriptivo
start_time = fields.Datetime()          # Tiempo de inicio
end_time = fields.Datetime()            # Tiempo de finalización
duration = fields.Float()               # Duración en segundos
```

### 📈 **Tipos de Logs Generados**

1. **Logs de Autenticación**: `auth_login`, `auth_refresh`
2. **Logs de Sincronización**: `sync_vendor`, `sync_bill`, `sync_payment`
3. **Logs de API**: `api_request`, `api_response`
4. **Logs de Error**: `api_error`, `sync_error`, `validation_error`
5. **Logs de Sistema**: `queue_process`, `cron_execution`

### 🔍 **Métodos de Logging**

```python
# Log de operación completa
self.env['billcom.logger'].log_operation(
    operation_type='sync_vendor',
    status='processing',
    record_model='res.partner',
    record_id=partner.id,
    message='Synchronizing vendor to Bill.com'
)

# Log de éxito
log_entry.mark_success('Vendor synchronized successfully')

# Log de error
log_entry.mark_error('API connection failed')

# Log de reintento
log_entry.mark_retry(retry_count=2, error_message='Temporary failure')
```

---

## API de Bill.com v3

### 🌐 **Endpoints Principales Utilizados**

#### **Autenticación**

```
POST /v3/login
```

**Propósito**: Obtener token de sesión para API calls **Datos**: `organizationId`,
`devKey`, `username`, `password` **Respuesta**: `sessionId`, `expires`

#### **Gestión de Proveedores**

```
POST /v3/vendors/create     # Crear proveedor
POST /v3/vendors/update     # Actualizar proveedor
GET  /v3/vendors/list       # Listar proveedores
GET  /v3/vendors/{id}       # Obtener proveedor específico
```

#### **Gestión de Facturas**

```
POST /v3/bills/create       # Crear factura
POST /v3/bills/update       # Actualizar factura
GET  /v3/bills/list         # Listar facturas
GET  /v3/bills/{id}         # Obtener factura específica
```

#### **Gestión de Pagos**

```
POST /v3/payments/create    # Crear pago
POST /v3/payments/update    # Actualizar pago
GET  /v3/payments/list      # Listar pagos
GET  /v3/payments/{id}      # Obtener estado de pago
```

### 🔐 **Sistema de Autenticación**

#### **Flujo de Autenticación**

1. **Login**: Envía credenciales a `/v3/login`
2. **Token**: Recibe `sessionId` con tiempo de expiración
3. **Cache**: Almacena token en `billcom.config.token`
4. **Renovación**: Renueva automáticamente antes de expiración
5. **Headers**: Incluye token en `Authorization: Bearer {sessionId}`

#### **Configuración de Credenciales**

```python
# Configuración en billcom.config
api_url = "https://api.bill.com"        # Production
# api_url = "https://api-stage.bill.com"  # Sandbox

organization_id = "ABC123"              # ID de organización
dev_key = "dev_key_12345"              # Clave de desarrollador
username = "user@company.com"          # Usuario Bill.com
password = "secure_password"           # Contraseña
```

### 📡 **Manejo de Requests**

#### **Estructura de Request**

```python
headers = {
    'Authorization': f'Bearer {session_token}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

payload = {
    'organizationId': config.organization_id,
    'data': request_data
}

response = requests.post(url, json=payload, headers=headers, timeout=40)
```

#### **Manejo de Respuestas**

```python
# Respuesta exitosa
{
    "status": "success",
    "data": {...},
    "meta": {...}
}

# Respuesta de error
{
    "status": "error",
    "errorMessage": "Invalid data",
    "errorCode": "400"
}
```

### 🔄 **Sincronización de Datos**

#### **Mapeo Odoo ↔ Bill.com**

| **Odoo Model**             | **Bill.com Entity** | **Sincronización** |
| -------------------------- | ------------------- | ------------------ |
| res.partner (supplier)     | Vendor              | Bidireccional      |
| res.partner (customer)     | Customer            | Bidireccional      |
| account.move (vendor bill) | Bill                | Bidireccional      |
| account.payment            | Payment             | Bidireccional      |
| ir.attachment              | Attachment          | Odoo → Bill.com    |

#### **Campos Sincronizados**

**Proveedores (res.partner → Vendor)**:

```python
{
    'name': partner.name,
    'companyName': partner.commercial_company_name,
    'email': partner.email,
    'phone': partner.phone,
    'accountNumber': partner.ref,
    'address': {
        'addressLine1': partner.street,
        'city': partner.city,
        'state': partner.state_id.code,
        'zip': partner.zip,
        'country': partner.country_id.code
    }
}
```

**Facturas (account.move → Bill)**:

```python
{
    'vendorId': move.partner_id.billcom_id,
    'invoiceNumber': move.ref,
    'invoiceDate': move.invoice_date,
    'dueDate': move.invoice_date_due,
    'description': move.narration,
    'amount': move.amount_total,
    'lineItems': [...]
}
```

---

## Flujo de Trabajo Completo

### 🚀 **Proceso de Sincronización**

#### **1. Configuración Inicial**

```
1. Crear configuración Bill.com (billcom.config)
2. Configurar credenciales API
3. Probar conexión
4. Activar sincronización automática
```

#### **2. Sincronización de Proveedor**

```
Evento: Crear/Editar proveedor en Odoo
    ↓
Verificar: is_sync_to_billcom = True
    ↓
Crear: Elemento en cola (billcom.sync.queue)
    ↓
Procesar: Cron job procesa cola cada 5 minutos
    ↓
Autenticar: Obtener token de Bill.com
    ↓
Sincronizar: Enviar datos a Bill.com API
    ↓
Actualizar: billcom_id en res.partner
    ↓
Log: Registrar resultado en billcom.logger
```

#### **3. Sincronización de Factura**

```
Evento: Validar factura de proveedor
    ↓
Verificar: Proveedor tiene billcom_id
    ↓
Crear: Elemento en cola para sincronización
    ↓
Procesar: Preparar datos de factura
    ↓
Enviar: Factura a Bill.com con líneas de detalle
    ↓
Actualizar: billcom_id en account.move
    ↓
Sincronizar: Estado de aprobación si es necesario
```

#### **4. Sincronización de Pagos**

```
Evento: Crear pago en Odoo
    ↓
Verificar: Factura tiene billcom_id
    ↓
Crear: Pago en Bill.com
    ↓
Monitorear: Estado del pago via webhook/polling
    ↓
Actualizar: Estado en Odoo según Bill.com
    ↓
Conciliar: Movimientos contables automáticamente
```

### 📊 **Dashboard y Monitoreo**

#### **Métricas Principales**

- **Conexión**: Estado de conectividad con Bill.com
- **Partners**: Total, sincronizados, pendientes
- **Bills**: Total, sincronizadas, pendientes
- **Payments**: Total, sincronizados, pendientes
- **Queue**: Elementos completados, pendientes, fallidos
- **Logs**: Entradas diarias, warnings, errores

#### **Acciones Disponibles**

- **Sync Now**: Forzar sincronización inmediata
- **Test API**: Verificar conectividad
- **Refresh**: Actualizar métricas del dashboard
- **View Queue**: Acceder a cola de sincronización
- **View Logs**: Revisar logs detallados

### 🛠️ **Tareas de Mantenimiento**

#### **Cron Jobs Configurados**

```xml
<!-- Procesar cola de sincronización -->
<record id="ir_cron_process_sync_queue" model="ir.cron">
    <field name="name">Bill.com: Process Sync Queue</field>
    <field name="interval_number">5</field>
    <field name="interval_type">minutes</field>
    <field name="code">model.process_queue()</field>
</record>

<!-- Limpiar elementos completados -->
<record id="ir_cron_cleanup_completed_items" model="ir.cron">
    <field name="name">Bill.com: Cleanup Completed Queue Items</field>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
    <field name="code">model.cleanup_completed_items(days=7)</field>
</record>
```

#### **Limpieza Automática**

- **Items de cola**: Se eliminan después de 7 días de completados
- **Logs antiguos**: Se archivan después de 30 días
- **Tokens expirados**: Se renuevan automáticamente

---

## Mejores Prácticas

### 🔒 **Seguridad**

1. **Credenciales**: Nunca hardcodear credenciales en código
2. **Tokens**: Almacenar tokens de forma segura con expiración
3. **HTTPS**: Siempre usar conexiones seguras
4. **Permisos**: Aplicar principio de menor privilegio
5. **Logs**: No registrar información sensible

### ⚡ **Performance**

1. **Colas**: Usar procesamiento asíncrono para operaciones largas
2. **Lotes**: Procesar múltiples elementos cuando sea posible
3. **Cache**: Reutilizar tokens de autenticación
4. **Timeouts**: Configurar timeouts apropiados para requests
5. **Limpieza**: Mantener tablas de logs y colas limpias

### 🐛 **Debugging**

1. **Logs**: Habilitar logging detallado durante desarrollo
2. **Estados**: Verificar estados de cola y logs
3. **API**: Probar endpoints manualmente cuando sea necesario
4. **Sandbox**: Usar ambiente de prueba para desarrollo
5. **Rollback**: Mantener capacidad de reversión

### 🚀 **Deployment**

1. **Configuración**: Separar configuración por ambiente
2. **Migración**: Planear migración de datos existentes
3. **Testing**: Probar en ambiente de staging primero
4. **Monitoring**: Configurar alertas para fallos críticos
5. **Backup**: Mantener respaldos antes de cambios importantes

---

## Troubleshooting Común

### ❌ **Errores de Autenticación**

```
Error: "Invalid credentials"
Solución: Verificar username, password, organization_id, dev_key
```

### ❌ **Errores de Sincronización**

```
Error: "Invalid field 'status' on model"
Solución: Usar campo 'state' en lugar de 'status'
```

### ❌ **Errores de API**

```
Error: "API rate limit exceeded"
Solución: Implementar backoff y reducir frecuencia de requests
```

### ❌ **Errores de Cola**

```
Error: Items se quedan en estado 'processing'
Solución: Verificar logs, reiniciar elementos manualmente
```

---

## Contacto y Soporte

**Desarrolladores**: Binhex, Simple Solutions, Odoo Community Association (OCA)
**Repositorio**: https://github.com/OCA/l10n-usa **Licencia**: AGPL-3 **Versión**:
16.0.1.0.0

Para reportar bugs o solicitar nuevas características, utilizar el sistema de issues del
repositorio oficial en GitHub.
