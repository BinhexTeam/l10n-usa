# Guía de Integración BILL API v3 con Odoo

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Análisis: BILL API v3 vs Módulo Actual](#análisis-bill-api-v3-vs-módulo-actual)
3. [Arquitectura de Integración](#arquitectura-de-integración)
4. [Fase 1: Foundation Setup](#fase-1-foundation-setup)
5. [Fase 2: AP (Accounts Payable)](#fase-2-ap-accounts-payable)
6. [Fase 3: AR (Accounts Receivable)](#fase-3-ar-accounts-receivable)
7. [Fase 4: Webhooks](#fase-4-webhooks)
8. [Fase 5: Enhanced Features](#fase-5-enhanced-features)
9. [Mejores Prácticas](#mejores-prácticas)
10. [Troubleshooting](#troubleshooting)

---

## Introducción

### Objetivos de la Integración

Esta guía proporciona un plan ordenado para desarrollar un módulo Odoo que integre los
flujos clave de CxP (Cuentas por Pagar) y CxC (Cuentas por Cobrar) con la plataforma
BILL (Bill.com), permitiendo:

✅ **Sincronizar** proveedores, facturas de proveedor (bills), pagos y documentos ✅
**Enviar** pagos desde Odoo a BILL y consultar su estado ✅ **Recibir** eventos mediante
webhooks para mantener Odoo actualizado ✅ **Soportar** autenticación con POST
/v3/login, MFA y ambiente Sandbox/Producción

### Scope de la Plataforma BILL

La plataforma BILL ofrece cuatro áreas principales:

1. **AP (Accounts Payable)**: Vendors, Bills, Payments, Vendor credits
2. **AR (Accounts Receivable)**: Customers, Invoices, Credit memos, AR payments
3. **BILL Network**: Conexión con millones de customers y vendors
4. **Spend & Expense**: Budgets, Cards, Transactions, Reimbursements

Esta guía se enfocará principalmente en **AP y AR** con soporte base para **BILL
Network** y referencias para **Spend & Expense** como fase opcional.

---

## Análisis: BILL API v3 vs Módulo Actual

### Capacidades del Módulo Actual

El módulo `billcom` actual (versión 16.0.1.0.0) proporciona:

| Característica           | Estado             | Observaciones                                      |
| ------------------------ | ------------------ | -------------------------------------------------- |
| **Autenticación API v3** | ✅ Implementado    | POST /v3/login con tokens                          |
| **Sync de Vendors**      | ✅ Implementado    | Bidireccional Odoo ↔ BILL                          |
| **Sync de Bills**        | ✅ Implementado    | Bidireccional Odoo ↔ BILL                          |
| **Sync de Payments**     | ✅ Implementado    | Bidireccional Odoo ↔ BILL                          |
| **Sistema de Colas**     | ✅ Implementado    | billcom.sync.queue con reintentos                  |
| **Sistema de Logging**   | ✅ Implementado    | billcom.logger con auditoría                       |
| **Dashboard Monitoring** | ✅ Implementado    | Kanban view con métricas                           |
| **MFA Support**          | ❌ No implementado | Se requiere desarrollo                             |
| **Webhooks**             | ⚠️ Parcial         | Controller existe pero sin implementación completa |
| **AR (Customers)**       | ❌ No implementado | Solo CxP está implementado                         |
| **AR (Invoices)**        | ❌ No implementado | Solo vendor bills                                  |
| **BILL Network**         | ❌ No implementado | No hay integración                                 |
| **Spend & Expense**      | ❌ No implementado | No hay integración                                 |

### Gaps de Funcionalidad

#### **Gap 1: Multi-Factor Authentication (MFA)**

**Estado Actual**: Autenticación básica con username/password **Requerido**: Soporte
para MFA según BILL API v3 **Impacto**: Alto - Requerido para cuentas enterprise

#### **Gap 2: Accounts Receivable (AR)**

**Estado Actual**: No implementado **Requerido**: Sincronización de customers, invoices,
AR payments, credit memos **Impacto**: Alto - Funcionalidad principal faltante

#### **Gap 3: Webhooks Robustos**

**Estado Actual**: Controller básico sin handlers completos **Requerido**: Event
handlers para bill status, payment status, customer updates **Impacto**: Medio - Mejora
tiempo real vs polling

#### **Gap 4: BILL Network**

**Estado Actual**: No implementado **Requerido**: Conexión para envío de bills/invoices
a través de la red **Impacto**: Medio - Feature adicional de valor

#### **Gap 5: Spend & Expense**

**Estado Actual**: No implementado **Requerido**: Budgets, cards, transactions,
reimbursements **Impacto**: Bajo - Feature enterprise opcional

### Capacidades de BILL API v3 Disponibles

| Endpoint Category   | Endpoints Principales                         | Prioridad   |
| ------------------- | --------------------------------------------- | ----------- |
| **Authentication**  | POST /v3/login, POST /v3/mfa/verify           | 🔴 Critical |
| **AP - Vendors**    | POST /v3/vendors/_, GET /v3/vendors/_         | 🔴 Critical |
| **AP - Bills**      | POST /v3/bills/_, GET /v3/bills/_             | 🔴 Critical |
| **AP - Payments**   | POST /v3/payments/_, GET /v3/payments/_       | 🔴 Critical |
| **AR - Customers**  | POST /v3/customers/_, GET /v3/customers/_     | 🟡 High     |
| **AR - Invoices**   | POST /v3/invoices/_, GET /v3/invoices/_       | 🟡 High     |
| **AR - Payments**   | POST /v3/ar-payments/_, GET /v3/ar-payments/_ | 🟡 High     |
| **Webhooks**        | POST /v3/webhooks/_, GET /v3/webhooks/_       | 🟡 High     |
| **BILL Network**    | POST /v3/network/_, GET /v3/network/_         | 🟢 Medium   |
| **Spend & Expense** | POST /v3/budgets/_, GET /v3/transactions/_    | 🟢 Low      |

---

## Arquitectura de Integración

### Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────┐
│                        Odoo 16.0                                │
├─────────────────────────────────────────────────────────────────┤
│  Accounting                         CRM                          │
│  ┌─────────────────┐              ┌──────────────────┐          │
│  │ res.partner     │              │ res.partner      │          │
│  │ (Vendors)       │              │ (Customers)      │          │
│  └────────┬────────┘              └────────┬─────────┘          │
│           │                                │                    │
│  ┌────────▼────────┐              ┌───────▼──────────┐          │
│  │ account.move    │              │ account.move     │          │
│  │ (Vendor Bills)  │              │ (Invoices)       │          │
│  └────────┬────────┘              └────────┬─────────┘          │
│           │                                │                    │
│  ┌────────▼─────────────────────────┬──────▼────────┐          │
│  │      account.payment             │               │          │
│  │      (AP + AR Payments)          │               │          │
│  └──────────────────────────────────┴───────────────┘          │
│                        ▲                    ▲                   │
├────────────────────────┼────────────────────┼───────────────────┤
│    Integration Layer   │                    │                   │
│  ┌─────────────────────▼────────────────────▼─────────────┐    │
│  │           billcom_service_abstract.py                   │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │ Token Management | Request Handler | Retry Logic│   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │           billcom_service.py                            │    │
│  │  ┌──────────────┬────────────────┬──────────────────┐   │    │
│  │  │ AP Service   │ AR Service     │ Network Service  │   │    │
│  │  └──────────────┴────────────────┴──────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                        ▲                    ▲                   │
│  ┌─────────────────────┼────────────────────┼─────────────┐    │
│  │     billcom.sync.queue (Async Processing)            │    │
│  │  ┌────────────────┬────────────────┬─────────────┐    │    │
│  │  │ AP Queue       │ AR Queue       │ NW Queue    │    │    │
│  │  └────────────────┴────────────────┴─────────────┘    │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │     billcom.logger (Audit Trail & Debug)                │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │     billcom_controller (Webhook Handler)                 │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                            │ HTTPS (API v3)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BILL API Platform v3                         │
├─────────────────────────────────────────────────────────────────┤
│  AP Module          AR Module          Network        S&E       │
│  ┌──────────┐      ┌──────────┐      ┌────────┐    ┌────────┐  │
│  │ Vendors  │      │Customers │      │Connect │    │Budgets │  │
│  │ Bills    │      │Invoices  │      │Send    │    │Cards   │  │
│  │ Payments │      │AR Pay    │      │Receive │    │Expenses│  │
│  └──────────┘      └──────────┘      └────────┘    └────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │               Webhook Event System                       │    │
│  │  bill.created, bill.approved, payment.completed, etc.   │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Componentes Clave

#### **1. Service Layer (billcom_service_abstract.py)**

- **Autenticación**: Login, token management, MFA
- **Request Handler**: HTTP requests con retry logic
- **Error Handling**: Manejo de rate limits, timeouts, API errors

#### **2. Business Logic (billcom_service.py)**

- **AP Service**: Vendors, bills, payments
- **AR Service**: Customers, invoices, AR payments
- **Network Service**: BILL Network operations
- **Sync Orchestration**: Coordinación de sincronizaciones

#### **3. Queue System (billcom_sync_queue.py)**

- **Async Processing**: Procesamiento en background
- **Retry Logic**: Reintentos con backoff exponencial
- **Priority Management**: Procesamiento prioritario

#### **4. Webhook Handler (billcom_controller.py)**

- **Event Reception**: Recibe eventos de BILL
- **Validation**: Valida signatures y authenticity
- **Event Dispatch**: Procesa eventos según tipo

#### **5. Logging System (billcom_logger.py)**

- **Audit Trail**: Registro completo de operaciones
- **Debug Info**: Información para troubleshooting
- **Metrics**: Datos para monitoring

### Patrón de Sincronización

```
┌──────────────────────────────────────────────────────────────┐
│                   Synchronization Pattern                     │
└──────────────────────────────────────────────────────────────┘

Odoo Record Change → Queue Item Creation → Processing → API Call
                                              ↓
                                        Success/Error
                                              ↓
                                      Update Record + Log

BILL Event (Webhook) → Controller → Validation → Queue Item
                                                      ↓
                                                  Processing
                                                      ↓
                                              Update Odoo Record
```

---

## Fase 1: Foundation Setup

### Objetivo

Establecer la base de autenticación, configuración y manejo de conexiones para soportar
todos los flujos de integración.

### 1.1 Autenticación Robusta

#### **Implementar MFA Support**

**Archivo**: `models/billcom_service_abstract.py`

**Método 1: Login básico (ya existe)**

```python
def _get_token(self):
    """Get authentication token from Bill.com API v3"""
    auth_url = f"{self.config.api_url}/v3/login"
    payload = {
        "organizationId": self.config.organization_id,
        "devKey": self.config.dev_key,
        "username": self.config.username,
        "password": self.config.password,
    }
    response = self._make_request('POST', auth_url, data=payload)

    if response.get('status') == 'success':
        token = response.get('data', {}).get('sessionId')
        expires = response.get('data', {}).get('expires')
        return token, expires
    elif response.get('requiresMfa'):
        # Nuevo: Manejar MFA
        return self._handle_mfa(response)
    else:
        raise Exception(f"Authentication failed: {response.get('errorMessage')}")
```

**Método 2: MFA Handler (nuevo)**

```python
def _handle_mfa(self, login_response):
    """Handle Multi-Factor Authentication flow

    Args:
        login_response: Response from /v3/login indicating MFA required

    Returns:
        tuple: (token, expires)
    """
    mfa_session_id = login_response.get('data', {}).get('mfaSessionId')

    # Strategy 1: Use stored MFA token if available
    if self.config.mfa_token:
        return self._verify_mfa_token(mfa_session_id, self.config.mfa_token)

    # Strategy 2: Trigger user notification for MFA code
    self._notify_mfa_required(mfa_session_id)

    # Strategy 3: Wait for user to provide MFA code through UI
    # This will be handled by a wizard in billcom_mfa_wizard.py
    raise UserError(
        "Multi-Factor Authentication required. "
        "Please check your email/SMS and enter the verification code."
    )

def _verify_mfa_token(self, mfa_session_id, mfa_code):
    """Verify MFA code and get session token

    Args:
        mfa_session_id: Session ID from initial login
        mfa_code: MFA verification code

    Returns:
        tuple: (token, expires)
    """
    mfa_url = f"{self.config.api_url}/v3/mfa/verify"
    payload = {
        "organizationId": self.config.organization_id,
        "mfaSessionId": mfa_session_id,
        "verificationCode": mfa_code,
    }

    response = self._make_request('POST', mfa_url, data=payload)

    if response.get('status') == 'success':
        token = response.get('data', {}).get('sessionId')
        expires = response.get('data', {}).get('expires')

        # Store token and expiration
        self.config.write({
            'token': token,
            'token_expires': expires,
        })

        return token, expires
    else:
        raise Exception(f"MFA verification failed: {response.get('errorMessage')}")

def _notify_mfa_required(self, mfa_session_id):
    """Create notification for MFA requirement

    Args:
        mfa_session_id: Session ID requiring MFA
    """
    self.env['billcom.mfa.pending'].create({
        'config_id': self.config.id,
        'mfa_session_id': mfa_session_id,
        'state': 'pending',
        'created_at': fields.Datetime.now(),
    })

    # Send notification to user
    self.env['bus.bus']._sendone(
        self.env.user.partner_id,
        'billcom_mfa_required',
        {
            'title': 'BILL.com MFA Required',
            'message': 'Please check your email/SMS for verification code',
            'config_id': self.config.id,
        }
    )
```

**Nuevo Modelo**: `models/billcom_mfa_pending.py`

```python
from odoo import models, fields, api

class BillcomMfaPending(models.Model):
    _name = 'billcom.mfa.pending'
    _description = 'Pending MFA Verifications'
    _order = 'create_date desc'

    config_id = fields.Many2one('billcom.config', required=True, ondelete='cascade')
    mfa_session_id = fields.Char(required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('expired', 'Expired'),
        ('failed', 'Failed'),
    ], default='pending', required=True)
    verification_code = fields.Char(string="Verification Code")
    created_at = fields.Datetime(required=True, default=fields.Datetime.now)
    expires_at = fields.Datetime(compute='_compute_expires_at', store=True)

    @api.depends('created_at')
    def _compute_expires_at(self):
        """MFA codes typically expire in 10 minutes"""
        for record in self:
            if record.created_at:
                record.expires_at = record.created_at + timedelta(minutes=10)

    def action_verify_mfa(self):
        """Verify MFA code and complete authentication"""
        self.ensure_one()

        if self.state != 'pending':
            raise UserError("This MFA request is no longer pending")

        if not self.verification_code:
            raise UserError("Please enter the verification code")

        # Get service and verify
        service = self.env['billcom.service'].with_config(self.config_id)

        try:
            token, expires = service._verify_mfa_token(
                self.mfa_session_id,
                self.verification_code
            )
            self.state = 'verified'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'MFA verification successful',
                    'type': 'success',
                }
            }
        except Exception as e:
            self.state = 'failed'
            raise UserError(f"MFA verification failed: {str(e)}")
```

**Nuevo Wizard**: `wizards/billcom_mfa_wizard.py`

```python
from odoo import models, fields, api
from odoo.exceptions import UserError

class BillcomMfaWizard(models.TransientModel):
    _name = 'billcom.mfa.wizard'
    _description = 'Bill.com MFA Verification Wizard'

    mfa_pending_id = fields.Many2one('billcom.mfa.pending', required=True)
    verification_code = fields.Char(string="Verification Code", required=True)

    def action_verify(self):
        """Verify the MFA code"""
        self.ensure_one()

        self.mfa_pending_id.verification_code = self.verification_code
        return self.mfa_pending_id.action_verify_mfa()
```

#### **Configuración de Ambientes**

**Archivo**: `models/billcom_config.py` (extensión)

```python
# Agregar campos para ambientes
environment = fields.Selection([
    ('sandbox', 'Sandbox'),
    ('production', 'Production'),
], string="Environment", default='sandbox', required=True)

mfa_enabled = fields.Boolean(string="MFA Enabled", default=False)
mfa_token = fields.Char(string="MFA Backup Token", groups="base.group_system")

@api.depends('environment')
def _compute_api_url(self):
    """Compute API URL based on environment"""
    for record in self:
        if record.environment == 'sandbox':
            record.api_url = 'https://api-stage.bill.com'
        else:
            record.api_url = 'https://api.bill.com'

def action_test_connection(self):
    """Test API connection with current credentials"""
    self.ensure_one()

    try:
        service = self.env['billcom.service'].with_config(self)
        token, expires = service._get_token()

        self.write({
            'connection_status': 'connected',
            'last_connection_test': fields.Datetime.now(),
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Connection Successful',
                'message': f'Connected to BILL {self.environment} environment',
                'type': 'success',
            }
        }
    except Exception as e:
        self.write({
            'connection_status': 'error',
            'last_sync_error': str(e),
        })
        raise UserError(f"Connection test failed: {str(e)}")
```

### 1.2 Enhanced Request Handling

**Archivo**: `models/billcom_service_abstract.py`

```python
def _make_request(self, method, endpoint, data=None, files=None, retry_count=0):
    """Enhanced request handler with comprehensive error handling

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: Full URL or path
        data: Request payload
        files: File attachments
        retry_count: Current retry attempt

    Returns:
        dict: Response data
    """
    max_retries = 3
    timeout = 40

    # Prepare headers
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    # Add authentication if token exists
    if self.config.token:
        headers['Authorization'] = f'Bearer {self.config.token}'

    # Log request
    log_entry = self.env['billcom.logger'].log_operation(
        operation_type=f'api_{method.lower()}',
        status='processing',
        record_model=self._name,
        record_id=self.id if hasattr(self, 'id') else None,
        message=f'{method} request to {endpoint}'
    )

    try:
        # Make request
        if method == 'GET':
            response = requests.get(endpoint, headers=headers, timeout=timeout)
        elif method == 'POST':
            response = requests.post(endpoint, json=data, headers=headers,
                                   files=files, timeout=timeout)
        elif method == 'PUT':
            response = requests.put(endpoint, json=data, headers=headers, timeout=timeout)
        elif method == 'DELETE':
            response = requests.delete(endpoint, headers=headers, timeout=timeout)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Parse response
        response_data = response.json()

        # Handle different response statuses
        if response.status_code == 200:
            log_entry.mark_success(f'Request successful: {response.status_code}')
            return response_data

        elif response.status_code == 401:
            # Token expired, refresh and retry
            if retry_count < max_retries:
                log_entry.mark_retry(retry_count + 1, 'Token expired, refreshing')
                self._refresh_token()
                return self._make_request(method, endpoint, data, files, retry_count + 1)
            else:
                raise Exception('Authentication failed after retries')

        elif response.status_code == 429:
            # Rate limit exceeded
            retry_after = int(response.headers.get('Retry-After', 60))
            if retry_count < max_retries:
                log_entry.mark_retry(retry_count + 1,
                                   f'Rate limit exceeded, waiting {retry_after}s')
                time.sleep(retry_after)
                return self._make_request(method, endpoint, data, files, retry_count + 1)
            else:
                raise Exception('Rate limit exceeded')

        elif response.status_code >= 500:
            # Server error, retry with backoff
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                log_entry.mark_retry(retry_count + 1,
                                   f'Server error, waiting {wait_time}s')
                time.sleep(wait_time)
                return self._make_request(method, endpoint, data, files, retry_count + 1)
            else:
                raise Exception(f'Server error: {response.status_code}')

        else:
            # Other errors
            error_msg = response_data.get('errorMessage', 'Unknown error')
            raise Exception(f'API error: {error_msg}')

    except requests.exceptions.Timeout:
        log_entry.mark_error('Request timeout')
        if retry_count < max_retries:
            return self._make_request(method, endpoint, data, files, retry_count + 1)
        raise Exception('Request timeout after retries')

    except requests.exceptions.ConnectionError:
        log_entry.mark_error('Connection error')
        raise Exception('Cannot connect to BILL API')

    except Exception as e:
        log_entry.mark_error(str(e))
        raise
```

### 1.3 Testing Suite

**Nuevo archivo**: `tests/test_billcom_authentication.py`

```python
from odoo.tests import TransactionCase
from odoo.exceptions import UserError
from unittest.mock import patch, MagicMock

class TestBillcomAuthentication(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config = self.env['billcom.config'].create({
            'name': 'Test Config',
            'environment': 'sandbox',
            'organization_id': 'test_org_123',
            'dev_key': 'test_dev_key',
            'username': 'test@example.com',
            'password': 'test_password',
        })

    @patch('requests.post')
    def test_basic_login_success(self, mock_post):
        """Test basic login without MFA"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'success',
            'data': {
                'sessionId': 'test_token_123',
                'expires': '2025-10-01T00:00:00Z'
            }
        }
        mock_post.return_value = mock_response

        service = self.env['billcom.service'].with_config(self.config)
        token, expires = service._get_token()

        self.assertEqual(token, 'test_token_123')
        self.assertTrue(expires)

    @patch('requests.post')
    def test_mfa_required(self, mock_post):
        """Test MFA flow when required"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'requiresMfa': True,
            'data': {
                'mfaSessionId': 'mfa_session_123'
            }
        }
        mock_post.return_value = mock_response

        service = self.env['billcom.service'].with_config(self.config)

        with self.assertRaises(UserError) as context:
            service._get_token()

        self.assertIn('Multi-Factor Authentication required', str(context.exception))

        # Verify MFA pending record was created
        pending_mfa = self.env['billcom.mfa.pending'].search([
            ('config_id', '=', self.config.id),
            ('state', '=', 'pending')
        ])
        self.assertEqual(len(pending_mfa), 1)
        self.assertEqual(pending_mfa.mfa_session_id, 'mfa_session_123')

    @patch('requests.post')
    def test_environment_urls(self, mock_post):
        """Test correct URLs for different environments"""
        # Test Sandbox
        self.config.environment = 'sandbox'
        self.assertEqual(self.config.api_url, 'https://api-stage.bill.com')

        # Test Production
        self.config.environment = 'production'
        self.assertEqual(self.config.api_url, 'https://api.bill.com')
```

### Deliverables Fase 1

✅ **Autenticación MFA completa** ✅ **Configuración de ambientes (Sandbox/Production)**
✅ **Request handler robusto con retry logic** ✅ **Testing suite para autenticación**
✅ **UI para MFA verification**

---

## Fase 2: AP (Accounts Payable)

### Objetivo

Mejorar y completar la integración de CxP (Cuentas por Pagar) con sincronización robusta
de vendors, bills y payments.

### 2.1 Enhanced Vendor Synchronization

El módulo actual ya tiene sincronización de vendors, pero se puede mejorar con:

**Archivo**: `models/billcom_service.py`

```python
def sync_vendor_to_billcom(self, partner):
    """Enhanced vendor synchronization to BILL

    Args:
        partner: res.partner record (supplier)

    Returns:
        dict: Response from BILL API
    """
    # Validate partner is a supplier
    if not partner.supplier_rank:
        raise UserError("Partner must be a supplier to sync to BILL")

    # Prepare vendor data with enhanced fields
    vendor_data = {
        'organizationId': self.config.organization_id,
        'data': {
            'name': partner.name,
            'companyName': partner.commercial_company_name or partner.name,
            'email': partner.email,
            'phone': partner.phone,
            'accountNumber': partner.ref,
            'taxId': partner.vat,  # Tax ID / EIN
            'isActive': partner.active,
            'paymentMethod': self._get_payment_method(partner),
            'address': {
                'addressLine1': partner.street,
                'addressLine2': partner.street2,
                'city': partner.city,
                'state': partner.state_id.code if partner.state_id else None,
                'zip': partner.zip,
                'country': partner.country_id.code if partner.country_id else 'US',
            },
            # Banking information for ACH payments
            'bankAccount': self._get_bank_account_data(partner) if partner.bank_ids else None,
            # Custom fields mapping
            'customFields': self._map_custom_fields(partner),
        }
    }

    # Determine operation: create or update
    if partner.billcom_id:
        endpoint = f"{self.config.api_url}/v3/vendors/update"
        vendor_data['data']['id'] = partner.billcom_id
        operation = 'update'
    else:
        endpoint = f"{self.config.api_url}/v3/vendors/create"
        operation = 'create'

    # Log operation
    log_entry = self.env['billcom.logger'].log_operation(
        operation_type=f'sync_vendor_{operation}',
        status='processing',
        record_model='res.partner',
        record_id=partner.id,
        message=f'Syncing vendor {partner.name} to BILL'
    )

    try:
        # Make API request
        response = self._make_request('POST', endpoint, data=vendor_data)

        if response.get('status') == 'success':
            billcom_vendor_id = response.get('data', {}).get('id')

            # Update partner with BILL ID
            partner.write({
                'billcom_id': billcom_vendor_id,
                'billcom_last_sync': fields.Datetime.now(),
            })

            log_entry.mark_success(f'Vendor synced successfully: {billcom_vendor_id}')
            return response
        else:
            error_msg = response.get('errorMessage', 'Unknown error')
            log_entry.mark_error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        log_entry.mark_error(str(e))
        raise

def _get_payment_method(self, partner):
    """Determine preferred payment method for vendor

    Args:
        partner: res.partner record

    Returns:
        str: Payment method code
    """
    # Check if vendor has ACH banking info
    if partner.bank_ids:
        return 'ACH'
    # Check for check payments
    elif hasattr(partner, 'payment_method_id') and partner.payment_method_id:
        if 'check' in partner.payment_method_id.name.lower():
            return 'CHECK'

    # Default to check
    return 'CHECK'

def _get_bank_account_data(self, partner):
    """Extract bank account information for ACH

    Args:
        partner: res.partner record

    Returns:
        dict: Bank account data
    """
    if not partner.bank_ids:
        return None

    # Use primary bank account
    bank_account = partner.bank_ids[0]

    return {
        'routingNumber': bank_account.bank_id.routing if bank_account.bank_id else None,
        'accountNumber': bank_account.acc_number,
        'accountType': bank_account.acc_type if hasattr(bank_account, 'acc_type') else 'checking',
        'bankName': bank_account.bank_id.name if bank_account.bank_id else None,
    }

def _map_custom_fields(self, partner):
    """Map Odoo custom fields to BILL custom fields

    Args:
        partner: res.partner record

    Returns:
        dict: Custom fields mapping
    """
    custom_fields = {}

    # Example: Map category to custom field
    if partner.category_id:
        custom_fields['vendor_category'] = ','.join(partner.category_id.mapped('name'))

    # Example: Map user to custom field
    if partner.user_id:
        custom_fields['account_manager'] = partner.user_id.name

    return custom_fields
```

### 2.2 Enhanced Bill Synchronization

**Archivo**: `models/billcom_service.py`

```python
def sync_bill_to_billcom(self, move):
    """Enhanced bill synchronization to BILL

    Args:
        move: account.move record (vendor bill)

    Returns:
        dict: Response from BILL API
    """
    # Validate move is a vendor bill
    if move.move_type != 'in_invoice':
        raise UserError("Only vendor bills can be synced to BILL")

    # Validate vendor has BILL ID
    if not move.partner_id.billcom_id:
        raise UserError(
            f"Vendor {move.partner_id.name} must be synced to BILL first"
        )

    # Prepare bill data
    bill_data = {
        'organizationId': self.config.organization_id,
        'data': {
            'vendorId': move.partner_id.billcom_id,
            'invoiceNumber': move.ref or move.name,
            'invoiceDate': move.invoice_date.isoformat() if move.invoice_date else None,
            'dueDate': move.invoice_date_due.isoformat() if move.invoice_date_due else None,
            'description': move.narration or f'Bill from {move.partner_id.name}',
            'poNumber': move.ref,  # Purchase Order reference
            'amount': move.amount_total,
            'lineItems': self._prepare_bill_lines(move),
            # Approval workflow
            'approvalStatus': self._determine_approval_status(move),
            # Custom fields
            'customFields': self._map_bill_custom_fields(move),
        }
    }

    # Add attachments if configured
    if self.config.sync_attachments:
        bill_data['attachments'] = self._prepare_bill_attachments(move)

    # Determine operation
    if move.billcom_id:
        endpoint = f"{self.config.api_url}/v3/bills/update"
        bill_data['data']['id'] = move.billcom_id
        operation = 'update'
    else:
        endpoint = f"{self.config.api_url}/v3/bills/create"
        operation = 'create'

    # Log operation
    log_entry = self.env['billcom.logger'].log_operation(
        operation_type=f'sync_bill_{operation}',
        status='processing',
        record_model='account.move',
        record_id=move.id,
        message=f'Syncing bill {move.name} to BILL'
    )

    try:
        # Make API request
        response = self._make_request('POST', endpoint, data=bill_data)

        if response.get('status') == 'success':
            billcom_bill_id = response.get('data', {}).get('id')

            # Update move with BILL ID
            move.write({
                'billcom_id': billcom_bill_id,
                'billcom_last_sync': fields.Datetime.now(),
                'billcom_status': response.get('data', {}).get('status', 'draft'),
            })

            log_entry.mark_success(f'Bill synced successfully: {billcom_bill_id}')

            # Trigger approval workflow if configured
            if self.config.auto_approve_bills and move.state == 'posted':
                self.approve_bill_in_billcom(move)

            return response
        else:
            error_msg = response.get('errorMessage', 'Unknown error')
            log_entry.mark_error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        log_entry.mark_error(str(e))
        raise

def _prepare_bill_lines(self, move):
    """Prepare bill line items for BILL API

    Args:
        move: account.move record

    Returns:
        list: Line items data
    """
    line_items = []

    for line in move.invoice_line_ids:
        # Skip lines with zero quantity or amount
        if not line.quantity or not line.price_subtotal:
            continue

        line_item = {
            'description': line.name or line.product_id.name,
            'quantity': line.quantity,
            'unitPrice': line.price_unit,
            'amount': line.price_subtotal,
            'accountId': self._map_account_to_billcom(line.account_id),
            # Tax handling
            'taxAmount': line.price_total - line.price_subtotal,
            # Product/Service reference
            'itemId': line.product_id.default_code if line.product_id else None,
        }

        line_items.append(line_item)

    return line_items

def _determine_approval_status(self, move):
    """Determine approval status based on Odoo state

    Args:
        move: account.move record

    Returns:
        str: Approval status for BILL
    """
    if move.state == 'draft':
        return 'DRAFT'
    elif move.state == 'posted':
        # Check if needs approval in Odoo
        if hasattr(move, 'approval_state'):
            if move.approval_state == 'approved':
                return 'APPROVED'
            elif move.approval_state == 'pending':
                return 'PENDING_APPROVAL'
        return 'APPROVED'  # Default for posted bills
    elif move.state == 'cancel':
        return 'VOID'

    return 'DRAFT'

def approve_bill_in_billcom(self, move):
    """Approve bill in BILL platform

    Args:
        move: account.move record
    """
    if not move.billcom_id:
        raise UserError("Bill must be synced to BILL before approval")

    endpoint = f"{self.config.api_url}/v3/bills/approve"
    data = {
        'organizationId': self.config.organization_id,
        'data': {
            'billId': move.billcom_id,
            'approvalComment': f'Auto-approved from Odoo by {self.env.user.name}'
        }
    }

    response = self._make_request('POST', endpoint, data=data)

    if response.get('status') == 'success':
        move.write({
            'billcom_status': 'approved',
            'billcom_approved_date': fields.Datetime.now(),
        })

        return response
    else:
        raise Exception(f"Bill approval failed: {response.get('errorMessage')}")
```

### 2.3 Enhanced Payment Synchronization

**Archivo**: `models/billcom_service.py`

```python
def sync_payment_to_billcom(self, payment):
    """Enhanced payment synchronization to BILL

    Args:
        payment: account.payment record

    Returns:
        dict: Response from BILL API
    """
    # Validate payment type
    if payment.payment_type != 'outbound':
        raise UserError("Only outbound payments can be synced to BILL")

    # Validate related bills
    if not payment.reconciled_bill_ids:
        raise UserError("Payment must be linked to vendor bills")

    # Check all bills have BILL IDs
    bills_without_billcom_id = payment.reconciled_bill_ids.filtered(
        lambda b: not b.billcom_id
    )
    if bills_without_billcom_id:
        raise UserError(
            f"The following bills must be synced to BILL first: "
            f"{', '.join(bills_without_billcom_id.mapped('name'))}"
        )

    # Prepare payment data
    payment_data = {
        'organizationId': self.config.organization_id,
        'data': {
            'vendorId': payment.partner_id.billcom_id,
            'amount': payment.amount,
            'paymentDate': payment.date.isoformat() if payment.date else None,
            'paymentMethod': self._map_payment_method(payment),
            'description': payment.ref or f'Payment to {payment.partner_id.name}',
            # Bills being paid
            'billPayments': self._prepare_bill_payments(payment),
            # Payment method details
            'paymentAccount': self._get_payment_account_data(payment),
            # Check details if applicable
            'checkNumber': payment.check_number if hasattr(payment, 'check_number') else None,
        }
    }

    # Determine operation
    if payment.billcom_id:
        endpoint = f"{self.config.api_url}/v3/payments/update"
        payment_data['data']['id'] = payment.billcom_id
        operation = 'update'
    else:
        endpoint = f"{self.config.api_url}/v3/payments/create"
        operation = 'create'

    # Log operation
    log_entry = self.env['billcom.logger'].log_operation(
        operation_type=f'sync_payment_{operation}',
        status='processing',
        record_model='account.payment',
        record_id=payment.id,
        message=f'Syncing payment {payment.name} to BILL'
    )

    try:
        # Make API request
        response = self._make_request('POST', endpoint, data=payment_data)

        if response.get('status') == 'success':
            billcom_payment_id = response.get('data', {}).get('id')
            billcom_status = response.get('data', {}).get('status', 'pending')

            # Update payment with BILL ID and status
            payment.write({
                'billcom_id': billcom_payment_id,
                'billcom_status': billcom_status,
                'billcom_last_sync': fields.Datetime.now(),
            })

            log_entry.mark_success(
                f'Payment synced successfully: {billcom_payment_id}, status: {billcom_status}'
            )

            # If payment method is ACH/Wire, send payment
            if payment_data['data']['paymentMethod'] in ['ACH', 'WIRE']:
                self.send_payment_in_billcom(payment)

            return response
        else:
            error_msg = response.get('errorMessage', 'Unknown error')
            log_entry.mark_error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        log_entry.mark_error(str(e))
        raise

def _prepare_bill_payments(self, payment):
    """Prepare bill payment allocations

    Args:
        payment: account.payment record

    Returns:
        list: Bill payment data
    """
    bill_payments = []

    for bill in payment.reconciled_bill_ids:
        # Calculate amount allocated to this bill
        amount_allocated = 0.0
        for line in payment.move_id.line_ids:
            if line.reconciled:
                for aml in line.matched_debit_ids + line.matched_credit_ids:
                    if aml.debit_move_id.move_id == bill or aml.credit_move_id.move_id == bill:
                        amount_allocated += aml.amount

        bill_payment = {
            'billId': bill.billcom_id,
            'amount': amount_allocated or payment.amount,
        }

        bill_payments.append(bill_payment)

    return bill_payments

def _map_payment_method(self, payment):
    """Map Odoo payment method to BILL payment method

    Args:
        payment: account.payment record

    Returns:
        str: BILL payment method code
    """
    # Check payment method
    if hasattr(payment, 'payment_method_id') and payment.payment_method_id:
        method_name = payment.payment_method_id.name.lower()

        if 'ach' in method_name or 'electronic' in method_name:
            return 'ACH'
        elif 'wire' in method_name:
            return 'WIRE'
        elif 'check' in method_name or 'cheque' in method_name:
            return 'CHECK'
        elif 'card' in method_name or 'credit' in method_name:
            return 'CREDIT_CARD'

    # Default based on journal
    if payment.journal_id:
        journal_name = payment.journal_id.name.lower()
        if 'ach' in journal_name or 'electronic' in journal_name:
            return 'ACH'
        elif 'check' in journal_name:
            return 'CHECK'

    # Default to CHECK
    return 'CHECK'

def send_payment_in_billcom(self, payment):
    """Send payment for processing in BILL

    Args:
        payment: account.payment record with billcom_id

    Returns:
        dict: Response from BILL API
    """
    if not payment.billcom_id:
        raise UserError("Payment must be synced to BILL before sending")

    endpoint = f"{self.config.api_url}/v3/payments/send"
    data = {
        'organizationId': self.config.organization_id,
        'data': {
            'paymentId': payment.billcom_id,
            'sendDate': fields.Date.today().isoformat(),
        }
    }

    response = self._make_request('POST', endpoint, data=data)

    if response.get('status') == 'success':
        payment.write({
            'billcom_status': 'sent',
            'billcom_sent_date': fields.Datetime.now(),
        })

        # Log success
        self.env['billcom.logger'].log_operation(
            operation_type='send_payment',
            status='success',
            record_model='account.payment',
            record_id=payment.id,
            billcom_id=payment.billcom_id,
            message=f'Payment sent successfully in BILL'
        )

        return response
    else:
        raise Exception(f"Payment send failed: {response.get('errorMessage')}")

def check_payment_status(self, payment):
    """Check payment status in BILL

    Args:
        payment: account.payment record with billcom_id

    Returns:
        dict: Payment status from BILL
    """
    if not payment.billcom_id:
        raise UserError("Payment must be synced to BILL before checking status")

    endpoint = f"{self.config.api_url}/v3/payments/{payment.billcom_id}"
    params = {
        'organizationId': self.config.organization_id,
    }

    response = self._make_request('GET', endpoint, data=params)

    if response.get('status') == 'success':
        payment_status = response.get('data', {}).get('status')

        # Update payment status in Odoo
        payment.write({
            'billcom_status': payment_status,
            'billcom_last_status_check': fields.Datetime.now(),
        })

        # Handle status changes
        if payment_status == 'completed':
            # Payment completed, mark as reconciled if not already
            if payment.state != 'reconciled':
                payment.action_post()
        elif payment_status == 'failed':
            # Payment failed, notify user
            self._notify_payment_failed(payment, response.get('data', {}).get('failureReason'))

        return response.get('data')
    else:
        raise Exception(f"Payment status check failed: {response.get('errorMessage')}")

def _notify_payment_failed(self, payment, reason):
    """Send notification when payment fails in BILL

    Args:
        payment: account.payment record
        reason: Failure reason from BILL
    """
    self.env['bus.bus']._sendone(
        self.env.user.partner_id,
        'billcom_payment_failed',
        {
            'title': 'BILL Payment Failed',
            'message': f'Payment {payment.name} failed in BILL: {reason}',
            'payment_id': payment.id,
            'type': 'warning',
        }
    )

    # Create activity for follow-up
    payment.activity_schedule(
        'mail.mail_activity_data_warning',
        summary=f'BILL Payment Failed: {payment.name}',
        note=f'Payment failed in BILL with reason: {reason}',
        user_id=payment.create_uid.id,
    )
```

### Deliverables Fase 2

✅ **Enhanced vendor sync con banking info** ✅ **Complete bill sync con line items y
attachments** ✅ **Robust payment sync con status tracking** ✅ **Payment sending y
status monitoring** ✅ **Approval workflows**

---

## Fase 3: AR (Accounts Receivable)

### Objetivo

Implementar sincronización completa de CxC (Cuentas por Cobrar) incluyendo customers,
invoices, AR payments y credit memos.

### 3.1 Customer Synchronization

**Nuevo archivo**: `models/billcom_service_ar.py`

```python
from odoo import models, fields, api
from odoo.exceptions import UserError

class BillcomServiceAR(models.AbstractModel):
    _name = 'billcom.service.ar'
    _description = 'Bill.com AR Service'
    _inherit = 'billcom.service.abstract'

    def sync_customer_to_billcom(self, partner):
        """Synchronize customer to BILL

        Args:
            partner: res.partner record (customer)

        Returns:
            dict: Response from BILL API
        """
        # Validate partner is a customer
        if not partner.customer_rank:
            raise UserError("Partner must be a customer to sync to BILL")

        # Prepare customer data
        customer_data = {
            'organizationId': self.config.organization_id,
            'data': {
                'name': partner.name,
                'companyName': partner.commercial_company_name or partner.name,
                'email': partner.email,
                'phone': partner.phone,
                'accountNumber': partner.ref,
                'taxId': partner.vat,
                'isActive': partner.active,
                # Customer specific fields
                'paymentTerms': self._get_payment_terms(partner),
                'creditLimit': partner.credit_limit if hasattr(partner, 'credit_limit') else 0.0,
                'address': {
                    'addressLine1': partner.street,
                    'addressLine2': partner.street2,
                    'city': partner.city,
                    'state': partner.state_id.code if partner.state_id else None,
                    'zip': partner.zip,
                    'country': partner.country_id.code if partner.country_id else 'US',
                },
                # Billing address if different
                'billingAddress': self._get_billing_address(partner),
                # Custom fields
                'customFields': self._map_customer_custom_fields(partner),
            }
        }

        # Determine operation
        if partner.billcom_customer_id:
            endpoint = f"{self.config.api_url}/v3/customers/update"
            customer_data['data']['id'] = partner.billcom_customer_id
            operation = 'update'
        else:
            endpoint = f"{self.config.api_url}/v3/customers/create"
            operation = 'create'

        # Log operation
        log_entry = self.env['billcom.logger'].log_operation(
            operation_type=f'sync_customer_{operation}',
            status='processing',
            record_model='res.partner',
            record_id=partner.id,
            message=f'Syncing customer {partner.name} to BILL'
        )

        try:
            # Make API request
            response = self._make_request('POST', endpoint, data=customer_data)

            if response.get('status') == 'success':
                billcom_customer_id = response.get('data', {}).get('id')

                # Update partner with BILL customer ID
                partner.write({
                    'billcom_customer_id': billcom_customer_id,
                    'billcom_ar_last_sync': fields.Datetime.now(),
                })

                log_entry.mark_success(f'Customer synced successfully: {billcom_customer_id}')
                return response
            else:
                error_msg = response.get('errorMessage', 'Unknown error')
                log_entry.mark_error(error_msg)
                raise Exception(error_msg)

        except Exception as e:
            log_entry.mark_error(str(e))
            raise

    def _get_payment_terms(self, partner):
        """Get payment terms for customer

        Args:
            partner: res.partner record

        Returns:
            str: Payment terms description
        """
        if partner.property_payment_term_id:
            return partner.property_payment_term_id.name
        return 'Net 30'  # Default

    def _get_billing_address(self, partner):
        """Get billing address if different from main address

        Args:
            partner: res.partner record

        Returns:
            dict: Billing address or None
        """
        # Check for invoice address type
        invoice_address = partner.child_ids.filtered(
            lambda c: c.type == 'invoice'
        )

        if invoice_address and invoice_address != partner:
            addr = invoice_address[0]
            return {
                'addressLine1': addr.street,
                'addressLine2': addr.street2,
                'city': addr.city,
                'state': addr.state_id.code if addr.state_id else None,
                'zip': addr.zip,
                'country': addr.country_id.code if addr.country_id else 'US',
            }

        return None

    def _map_customer_custom_fields(self, partner):
        """Map Odoo customer custom fields to BILL

        Args:
            partner: res.partner record

        Returns:
            dict: Custom fields
        """
        custom_fields = {}

        # Sales team
        if partner.team_id:
            custom_fields['sales_team'] = partner.team_id.name

        # Salesperson
        if partner.user_id:
            custom_fields['salesperson'] = partner.user_id.name

        # Industry/Tags
        if partner.category_id:
            custom_fields['customer_tags'] = ','.join(partner.category_id.mapped('name'))

        return custom_fields
```

### 3.2 Invoice Synchronization

**Extensión en**: `models/billcom_service_ar.py`

```python
def sync_invoice_to_billcom(self, move):
    """Synchronize customer invoice to BILL

    Args:
        move: account.move record (customer invoice)

    Returns:
        dict: Response from BILL API
    """
    # Validate move is a customer invoice
    if move.move_type not in ['out_invoice', 'out_refund']:
        raise UserError("Only customer invoices can be synced to BILL AR")

    # Validate customer has BILL ID
    if not move.partner_id.billcom_customer_id:
        raise UserError(
            f"Customer {move.partner_id.name} must be synced to BILL first"
        )

    # Prepare invoice data
    invoice_data = {
        'organizationId': self.config.organization_id,
        'data': {
            'customerId': move.partner_id.billcom_customer_id,
            'invoiceNumber': move.name,
            'invoiceDate': move.invoice_date.isoformat() if move.invoice_date else None,
            'dueDate': move.invoice_date_due.isoformat() if move.invoice_date_due else None,
            'description': move.narration or f'Invoice for {move.partner_id.name}',
            'poNumber': move.ref,  # Customer PO reference
            'amount': move.amount_total,
            'subtotal': move.amount_untaxed,
            'taxAmount': move.amount_tax,
            # Line items
            'lineItems': self._prepare_invoice_lines(move),
            # Payment terms
            'paymentTerms': move.invoice_payment_term_id.name if move.invoice_payment_term_id else 'Net 30',
            # Send options
            'sendOptions': {
                'sendViaEmail': self.config.auto_send_invoices,
                'emailAddress': move.partner_id.email,
                'emailSubject': f'Invoice {move.name} from {self.env.company.name}',
            } if self.config.auto_send_invoices else None,
            # Custom fields
            'customFields': self._map_invoice_custom_fields(move),
        }
    }

    # Handle credit notes (refunds)
    if move.move_type == 'out_refund':
        invoice_data['data']['isCredit Memo'] = True
        if move.reversed_entry_id and move.reversed_entry_id.billcom_invoice_id:
            invoice_data['data']['originalInvoiceId'] = move.reversed_entry_id.billcom_invoice_id

    # Determine operation
    if move.billcom_invoice_id:
        endpoint = f"{self.config.api_url}/v3/invoices/update"
        invoice_data['data']['id'] = move.billcom_invoice_id
        operation = 'update'
    else:
        endpoint = f"{self.config.api_url}/v3/invoices/create"
        operation = 'create'

    # Log operation
    log_entry = self.env['billcom.logger'].log_operation(
        operation_type=f'sync_invoice_{operation}',
        status='processing',
        record_model='account.move',
        record_id=move.id,
        message=f'Syncing invoice {move.name} to BILL'
    )

    try:
        # Make API request
        response = self._make_request('POST', endpoint, data=invoice_data)

        if response.get('status') == 'success':
            billcom_invoice_id = response.get('data', {}).get('id')

            # Update move with BILL ID
            move.write({
                'billcom_invoice_id': billcom_invoice_id,
                'billcom_ar_last_sync': fields.Datetime.now(),
                'billcom_invoice_status': response.get('data', {}).get('status', 'draft'),
            })

            log_entry.mark_success(f'Invoice synced successfully: {billcom_invoice_id}')

            # Send invoice if configured
            if self.config.auto_send_invoices and move.state == 'posted':
                self.send_invoice_in_billcom(move)

            return response
        else:
            error_msg = response.get('errorMessage', 'Unknown error')
            log_entry.mark_error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        log_entry.mark_error(str(e))
        raise

def _prepare_invoice_lines(self, move):
    """Prepare invoice line items for BILL API

    Args:
        move: account.move record

    Returns:
        list: Line items data
    """
    line_items = []

    for line in move.invoice_line_ids:
        if not line.quantity or not line.price_subtotal:
            continue

        line_item = {
            'description': line.name or line.product_id.name,
            'quantity': line.quantity,
            'unitPrice': line.price_unit,
            'amount': line.price_subtotal,
            'itemId': line.product_id.default_code if line.product_id else None,
            # Tax
            'taxable': bool(line.tax_ids),
            'taxAmount': line.price_total - line.price_subtotal,
        }

        line_items.append(line_item)

    return line_items

def send_invoice_in_billcom(self, move):
    """Send invoice to customer via BILL

    Args:
        move: account.move record with billcom_invoice_id

    Returns:
        dict: Response from BILL API
    """
    if not move.billcom_invoice_id:
        raise UserError("Invoice must be synced to BILL before sending")

    endpoint = f"{self.config.api_url}/v3/invoices/send"
    data = {
        'organizationId': self.config.organization_id,
        'data': {
            'invoiceId': move.billcom_invoice_id,
            'emailAddress': move.partner_id.email,
            'emailSubject': f'Invoice {move.name} from {self.env.company.name}',
            'emailBody': self._get_invoice_email_body(move),
            'sendMethod': 'EMAIL',  # or 'POSTAL', 'BILLNETWORK'
        }
    }

    response = self._make_request('POST', endpoint, data=data)

    if response.get('status') == 'success':
        move.write({
            'billcom_invoice_status': 'sent',
            'billcom_invoice_sent_date': fields.Datetime.now(),
        })

        # Log success
        self.env['billcom.logger'].log_operation(
            operation_type='send_invoice',
            status='success',
            record_model='account.move',
            record_id=move.id,
            billcom_id=move.billcom_invoice_id,
            message=f'Invoice sent successfully via BILL'
        )

        return response
    else:
        raise Exception(f"Invoice send failed: {response.get('errorMessage')}")

def _get_invoice_email_body(self, move):
    """Generate email body for invoice

    Args:
        move: account.move record

    Returns:
        str: Email body HTML
    """
    return f"""
    <p>Dear {move.partner_id.name},</p>

    <p>Please find attached invoice {move.name} for your review and payment.</p>

    <ul>
        <li><strong>Invoice Number:</strong> {move.name}</li>
        <li><strong>Invoice Date:</strong> {move.invoice_date}</li>
        <li><strong>Due Date:</strong> {move.invoice_date_due}</li>
        <li><strong>Amount Due:</strong> ${move.amount_total:.2f}</li>
    </ul>

    <p>Please remit payment at your earliest convenience.</p>

    <p>Thank you for your business!</p>

    <p>
        {self.env.company.name}<br>
        {self.env.company.phone}<br>
        {self.env.company.email}
    </p>
    """
```

### 3.3 AR Payment Recording

**Extensión en**: `models/billcom_service_ar.py`

```python
def record_ar_payment_from_billcom(self, billcom_payment_data):
    """Record AR payment received via BILL in Odoo

    Args:
        billcom_payment_data: Payment data from BILL webhook or API

    Returns:
        account.payment: Created payment record
    """
    # Extract payment info
    billcom_payment_id = billcom_payment_data.get('id')
    customer_id = billcom_payment_data.get('customerId')
    amount = billcom_payment_data.get('amount')
    payment_date = billcom_payment_data.get('paymentDate')
    payment_method = billcom_payment_data.get('paymentMethod')
    reference = billcom_payment_data.get('reference')

    # Find customer in Odoo
    partner = self.env['res.partner'].search([
        ('billcom_customer_id', '=', customer_id)
    ], limit=1)

    if not partner:
        raise UserError(f"Customer with BILL ID {customer_id} not found in Odoo")

    # Check if payment already exists
    existing_payment = self.env['account.payment'].search([
        ('billcom_ar_payment_id', '=', billcom_payment_id)
    ], limit=1)

    if existing_payment:
        # Update existing payment
        existing_payment.write({
            'billcom_ar_payment_status': billcom_payment_data.get('status'),
            'billcom_ar_last_sync': fields.Datetime.now(),
        })
        return existing_payment

    # Find invoices being paid
    invoice_payments = billcom_payment_data.get('invoicePayments', [])
    invoice_ids = []

    for inv_payment in invoice_payments:
        invoice = self.env['account.move'].search([
            ('billcom_invoice_id', '=', inv_payment.get('invoiceId'))
        ], limit=1)
        if invoice:
            invoice_ids.append(invoice.id)

    # Determine payment journal
    payment_journal = self._get_ar_payment_journal(payment_method)

    # Create payment
    payment_vals = {
        'payment_type': 'inbound',
        'partner_type': 'customer',
        'partner_id': partner.id,
        'amount': amount,
        'date': payment_date,
        'journal_id': payment_journal.id,
        'ref': reference or f'BILL Payment {billcom_payment_id}',
        'billcom_ar_payment_id': billcom_payment_id,
        'billcom_ar_payment_status': billcom_payment_data.get('status'),
        'billcom_ar_last_sync': fields.Datetime.now(),
    }

    payment = self.env['account.payment'].create(payment_vals)

    # Post payment
    payment.action_post()

    # Reconcile with invoices
    if invoice_ids:
        invoices = self.env['account.move'].browse(invoice_ids)
        self._reconcile_payment_with_invoices(payment, invoices)

    # Log operation
    self.env['billcom.logger'].log_operation(
        operation_type='record_ar_payment',
        status='success',
        record_model='account.payment',
        record_id=payment.id,
        billcom_id=billcom_payment_id,
        message=f'AR payment recorded from BILL: {amount}'
    )

    return payment

def _get_ar_payment_journal(self, payment_method):
    """Get appropriate journal for AR payment method

    Args:
        payment_method: Payment method from BILL

    Returns:
        account.journal: Journal record
    """
    journal_type = 'bank'

    # Try to find journal by payment method
    if payment_method == 'CREDIT_CARD':
        journal = self.env['account.journal'].search([
            ('type', '=', journal_type),
            ('name', 'ilike', 'credit card')
        ], limit=1)
    elif payment_method == 'ACH':
        journal = self.env['account.journal'].search([
            ('type', '=', journal_type),
            ('name', 'ilike', 'ach')
        ], limit=1)
    elif payment_method == 'BILLNETWORK':
        journal = self.env['account.journal'].search([
            ('type', '=', journal_type),
            ('name', 'ilike', 'bill')
        ], limit=1)
    else:
        journal = None

    # Fallback to default bank journal
    if not journal:
        journal = self.env['account.journal'].search([
            ('type', '=', journal_type),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

    if not journal:
        raise UserError("No bank journal found for AR payments")

    return journal

def _reconcile_payment_with_invoices(self, payment, invoices):
    """Reconcile payment with invoices

    Args:
        payment: account.payment record
        invoices: account.move recordset
    """
    # Get payment move lines
    payment_lines = payment.move_id.line_ids.filtered(
        lambda l: l.account_id.user_type_id.type in ['receivable']
    )

    # Get invoice move lines
    invoice_lines = invoices.mapped('line_ids').filtered(
        lambda l: l.account_id.user_type_id.type in ['receivable'] and not l.reconciled
    )

    # Reconcile
    if payment_lines and invoice_lines:
        (payment_lines + invoice_lines).reconcile()
```

### 3.4 Extension to Models

**Archivo**: `models/res_partner.py` (extensión)

```python
# Add AR fields
billcom_customer_id = fields.Char(
    string="BILL Customer ID",
    readonly=True,
    help="Unique identifier for customer in Bill.com"
)
billcom_ar_last_sync = fields.Datetime(
    string="AR Last Sync",
    readonly=True,
    help="Last synchronization date for AR data"
)

def action_sync_customer_to_billcom(self):
    """Sync customer to BILL (manual action)"""
    self.ensure_one()

    if not self.customer_rank:
        raise UserError("This partner is not a customer")

    # Get BILL service
    config = self.env['billcom.config'].get_active_config()
    service = self.env['billcom.service.ar'].with_config(config)

    # Sync customer
    service.sync_customer_to_billcom(self)

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': 'Success',
            'message': f'Customer {self.name} synced to BILL',
            'type': 'success',
        }
    }
```

**Archivo**: `models/account_move.py` (extensión)

```python
# Add AR fields
billcom_invoice_id = fields.Char(
    string="BILL Invoice ID",
    readonly=True,
    help="Unique identifier for invoice in Bill.com"
)
billcom_invoice_status = fields.Selection([
    ('draft', 'Draft'),
    ('sent', 'Sent'),
    ('viewed', 'Viewed'),
    ('paid', 'Paid'),
    ('partial', 'Partially Paid'),
    ('overdue', 'Overdue'),
], string="BILL Invoice Status", readonly=True)
billcom_invoice_sent_date = fields.Datetime(
    string="BILL Invoice Sent Date",
    readonly=True
)
billcom_ar_last_sync = fields.Datetime(
    string="AR Last Sync",
    readonly=True
)

def action_sync_invoice_to_billcom(self):
    """Sync invoice to BILL (manual action)"""
    self.ensure_one()

    if self.move_type not in ['out_invoice', 'out_refund']:
        raise UserError("Only customer invoices can be synced to BILL")

    # Get BILL service
    config = self.env['billcom.config'].get_active_config()
    service = self.env['billcom.service.ar'].with_config(config)

    # Sync invoice
    service.sync_invoice_to_billcom(self)

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': 'Success',
            'message': f'Invoice {self.name} synced to BILL',
            'type': 'success',
        }
    }

def action_send_invoice_via_billcom(self):
    """Send invoice to customer via BILL"""
    self.ensure_one()

    if not self.billcom_invoice_id:
        raise UserError("Invoice must be synced to BILL before sending")

    # Get BILL service
    config = self.env['billcom.config'].get_active_config()
    service = self.env['billcom.service.ar'].with_config(config)

    # Send invoice
    service.send_invoice_in_billcom(self)

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': 'Success',
            'message': f'Invoice {self.name} sent via BILL',
            'type': 'success',
        }
    }
```

**Archivo**: `models/account_payment.py` (extensión)

```python
# Add AR payment fields
billcom_ar_payment_id = fields.Char(
    string="BILL AR Payment ID",
    readonly=True,
    help="Unique identifier for AR payment in Bill.com"
)
billcom_ar_payment_status = fields.Selection([
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
], string="BILL AR Payment Status", readonly=True)
billcom_ar_last_sync = fields.Datetime(
    string="AR Last Sync",
    readonly=True
)
```

### Deliverables Fase 3

✅ **Customer synchronization complete** ✅ **Invoice synchronization con line items**
✅ **Invoice sending via BILL** ✅ **AR payment recording from BILL** ✅ **Credit memo
support** ✅ **Extended models con AR fields**

---

## Fase 4: Webhooks

### Objetivo

Implementar sistema robusto de webhooks para recibir eventos en tiempo real desde BILL y
mantener Odoo actualizado automáticamente.

### 4.1 Webhook Configuration

**Archivo**: `models/billcom_webhook_config.py` (nuevo)

```python
from odoo import models, fields, api
from odoo.exceptions import UserError
import hashlib
import hmac

class BillcomWebhookConfig(models.Model):
    _name = 'billcom.webhook.config'
    _description = 'Bill.com Webhook Configuration'
    _order = 'create_date desc'

    name = fields.Char(required=True, default="BILL Webhook")
    config_id = fields.Many2one('billcom.config', required=True, ondelete='cascade')

    # Webhook settings
    webhook_url = fields.Char(
        string="Webhook URL",
        compute='_compute_webhook_url',
        help="URL where BILL will send webhook events"
    )
    webhook_secret = fields.Char(
        string="Webhook Secret",
        required=True,
        default=lambda self: self._generate_secret(),
        help="Secret key for validating webhook signatures"
    )
    billcom_webhook_id = fields.Char(
        string="BILL Webhook ID",
        readonly=True,
        help="ID of webhook subscription in BILL"
    )

    # Event subscriptions
    event_bill_created = fields.Boolean(string="Bill Created", default=True)
    event_bill_updated = fields.Boolean(string="Bill Updated", default=True)
    event_bill_approved = fields.Boolean(string="Bill Approved", default=True)
    event_bill_paid = fields.Boolean(string="Bill Paid", default=True)

    event_payment_created = fields.Boolean(string="Payment Created", default=True)
    event_payment_sent = fields.Boolean(string="Payment Sent", default=True)
    event_payment_completed = fields.Boolean(string="Payment Completed", default=True)
    event_payment_failed = fields.Boolean(string="Payment Failed", default=True)

    event_invoice_created = fields.Boolean(string="Invoice Created", default=True)
    event_invoice_sent = fields.Boolean(string="Invoice Sent", default=True)
    event_invoice_paid = fields.Boolean(string="Invoice Paid", default=True)

    event_vendor_updated = fields.Boolean(string="Vendor Updated", default=False)
    event_customer_updated = fields.Boolean(string="Customer Updated", default=False)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ], default='draft', required=True)

    last_event_date = fields.Datetime(string="Last Event Received", readonly=True)
    total_events_received = fields.Integer(string="Total Events", readonly=True, default=0)

    @api.depends('config_id')
    def _compute_webhook_url(self):
        """Compute webhook URL based on Odoo base URL"""
        for record in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            record.webhook_url = f"{base_url}/billcom/webhook/{record.id}"

    def _generate_secret(self):
        """Generate a random secret key"""
        import secrets
        return secrets.token_urlsafe(32)

    def action_register_webhook(self):
        """Register webhook with BILL"""
        self.ensure_one()

        # Get events to subscribe
        events = self._get_subscribed_events()

        if not events:
            raise UserError("Please select at least one event to subscribe to")

        # Get service
        service = self.env['billcom.service'].with_config(self.config_id)

        # Register webhook in BILL
        endpoint = f"{self.config_id.api_url}/v3/webhooks/create"
        data = {
            'organizationId': self.config_id.organization_id,
            'data': {
                'url': self.webhook_url,
                'events': events,
                'description': f'Odoo Webhook - {self.name}',
                'isActive': True,
            }
        }

        response = service._make_request('POST', endpoint, data=data)

        if response.get('status') == 'success':
            webhook_id = response.get('data', {}).get('id')
            self.write({
                'billcom_webhook_id': webhook_id,
                'state': 'active',
            })

            # Log success
            self.env['billcom.logger'].log_operation(
                operation_type='webhook_register',
                status='success',
                record_model=self._name,
                record_id=self.id,
                billcom_id=webhook_id,
                message=f'Webhook registered successfully with {len(events)} events'
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Webhook Registered',
                    'message': f'Webhook successfully registered in BILL',
                    'type': 'success',
                }
            }
        else:
            error_msg = response.get('errorMessage', 'Unknown error')
            self.state = 'error'
            raise UserError(f"Webhook registration failed: {error_msg}")

    def _get_subscribed_events(self):
        """Get list of events to subscribe to

        Returns:
            list: Event names
        """
        events = []

        if self.event_bill_created:
            events.append('bill.created')
        if self.event_bill_updated:
            events.append('bill.updated')
        if self.event_bill_approved:
            events.append('bill.approved')
        if self.event_bill_paid:
            events.append('bill.paid')

        if self.event_payment_created:
            events.append('payment.created')
        if self.event_payment_sent:
            events.append('payment.sent')
        if self.event_payment_completed:
            events.append('payment.completed')
        if self.event_payment_failed:
            events.append('payment.failed')

        if self.event_invoice_created:
            events.append('invoice.created')
        if self.event_invoice_sent:
            events.append('invoice.sent')
        if self.event_invoice_paid:
            events.append('invoice.paid')

        if self.event_vendor_updated:
            events.append('vendor.updated')
        if self.event_customer_updated:
            events.append('customer.updated')

        return events

    def action_unregister_webhook(self):
        """Unregister webhook from BILL"""
        self.ensure_one()

        if not self.billcom_webhook_id:
            raise UserError("Webhook is not registered in BILL")

        # Get service
        service = self.env['billcom.service'].with_config(self.config_id)

        # Unregister webhook
        endpoint = f"{self.config_id.api_url}/v3/webhooks/{self.billcom_webhook_id}/delete"
        data = {
            'organizationId': self.config_id.organization_id,
        }

        response = service._make_request('POST', endpoint, data=data)

        if response.get('status') == 'success':
            self.write({
                'state': 'inactive',
                'billcom_webhook_id': False,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Webhook Unregistered',
                    'message': 'Webhook successfully unregistered from BILL',
                    'type': 'success',
                }
            }
        else:
            error_msg = response.get('errorMessage', 'Unknown error')
            raise UserError(f"Webhook unregistration failed: {error_msg}")

    def validate_webhook_signature(self, payload, signature):
        """Validate webhook signature

        Args:
            payload: Raw webhook payload
            signature: Signature from BILL

        Returns:
            bool: True if valid
        """
        self.ensure_one()

        # Compute expected signature
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Compare signatures
        return hmac.compare_digest(signature, expected_signature)
```

### 4.2 Webhook Controller

**Archivo**: `controllers/billcom_controller.py` (extensión)

```python
import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class BillcomController(http.Controller):

    @http.route('/billcom/webhook/<int:webhook_id>', type='json', auth='public',
                methods=['POST'], csrf=False)
    def webhook_handler(self, webhook_id, **kwargs):
        """Handle incoming webhooks from BILL

        Args:
            webhook_id: ID of billcom.webhook.config record

        Returns:
            dict: Response
        """
        try:
            # Get webhook config
            webhook_config = request.env['billcom.webhook.config'].sudo().browse(webhook_id)

            if not webhook_config.exists():
                _logger.error(f"Webhook config {webhook_id} not found")
                return {'status': 'error', 'message': 'Webhook not found'}

            # Get payload and signature
            payload = request.httprequest.data.decode('utf-8')
            signature = request.httprequest.headers.get('X-BILL-Signature', '')

            # Validate signature
            if not webhook_config.validate_webhook_signature(payload, signature):
                _logger.warning(f"Invalid webhook signature for webhook {webhook_id}")
                return {'status': 'error', 'message': 'Invalid signature'}

            # Parse payload
            event_data = json.loads(payload)

            # Log webhook receipt
            _logger.info(f"Received webhook: {event_data.get('event')} for webhook {webhook_id}")

            # Update webhook stats
            webhook_config.write({
                'last_event_date': fields.Datetime.now(),
                'total_events_received': webhook_config.total_events_received + 1,
            })

            # Process event
            self._process_webhook_event(webhook_config, event_data)

            return {'status': 'success', 'message': 'Webhook processed'}

        except Exception as e:
            _logger.exception(f"Error processing webhook {webhook_id}: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _process_webhook_event(self, webhook_config, event_data):
        """Process webhook event

        Args:
            webhook_config: billcom.webhook.config record
            event_data: Event data from BILL
        """
        event_type = event_data.get('event')
        data = event_data.get('data', {})

        # Create event log
        event_log = request.env['billcom.webhook.event'].sudo().create({
            'webhook_config_id': webhook_config.id,
            'event_type': event_type,
            'event_data': json.dumps(data),
            'state': 'received',
        })

        try:
            # Route to appropriate handler
            if event_type.startswith('bill.'):
                self._handle_bill_event(event_type, data, webhook_config)
            elif event_type.startswith('payment.'):
                self._handle_payment_event(event_type, data, webhook_config)
            elif event_type.startswith('invoice.'):
                self._handle_invoice_event(event_type, data, webhook_config)
            elif event_type.startswith('vendor.'):
                self._handle_vendor_event(event_type, data, webhook_config)
            elif event_type.startswith('customer.'):
                self._handle_customer_event(event_type, data, webhook_config)
            else:
                _logger.warning(f"Unhandled webhook event type: {event_type}")

            # Mark event as processed
            event_log.state = 'processed'

        except Exception as e:
            _logger.exception(f"Error handling webhook event {event_type}: {str(e)}")
            event_log.write({
                'state': 'error',
                'error_message': str(e),
            })
            raise

    def _handle_bill_event(self, event_type, data, webhook_config):
        """Handle bill-related events

        Args:
            event_type: Event type (bill.created, bill.approved, etc.)
            data: Event data
            webhook_config: Webhook configuration
        """
        billcom_bill_id = data.get('id')

        # Find bill in Odoo
        bill = request.env['account.move'].sudo().search([
            ('billcom_id', '=', billcom_bill_id)
        ], limit=1)

        if event_type == 'bill.created':
            if not bill:
                # Bill created in BILL, sync to Odoo
                self._sync_bill_from_billcom(data, webhook_config.config_id)

        elif event_type == 'bill.updated':
            if bill:
                # Update bill in Odoo
                self._update_bill_from_billcom(bill, data)

        elif event_type == 'bill.approved':
            if bill:
                # Update approval status
                bill.write({
                    'billcom_status': 'approved',
                    'billcom_approved_date': fields.Datetime.now(),
                })

                # Send notification
                self._notify_bill_approved(bill)

        elif event_type == 'bill.paid':
            if bill:
                # Update payment status
                bill.write({
                    'billcom_status': 'paid',
                    'billcom_paid_date': fields.Datetime.now(),
                })

                # Check if payment exists in Odoo, if not create it
                self._check_and_create_payment(bill, data)

    def _handle_payment_event(self, event_type, data, webhook_config):
        """Handle payment-related events

        Args:
            event_type: Event type (payment.sent, payment.completed, etc.)
            data: Event data
            webhook_config: Webhook configuration
        """
        billcom_payment_id = data.get('id')

        # Find payment in Odoo (check both AP and AR)
        payment = request.env['account.payment'].sudo().search([
            '|',
            ('billcom_id', '=', billcom_payment_id),
            ('billcom_ar_payment_id', '=', billcom_payment_id)
        ], limit=1)

        if event_type == 'payment.sent':
            if payment:
                payment.write({
                    'billcom_status': 'sent',
                    'billcom_sent_date': fields.Datetime.now(),
                })
                self._notify_payment_sent(payment)

        elif event_type == 'payment.completed':
            if payment:
                payment.write({
                    'billcom_status': 'completed',
                    'billcom_completed_date': fields.Datetime.now(),
                })

                # Post payment if draft
                if payment.state == 'draft':
                    payment.action_post()

                self._notify_payment_completed(payment)
            else:
                # Payment completed in BILL but not in Odoo, create it
                self._create_payment_from_billcom(data, webhook_config.config_id)

        elif event_type == 'payment.failed':
            if payment:
                payment.write({
                    'billcom_status': 'failed',
                    'billcom_failure_reason': data.get('failureReason'),
                })
                self._notify_payment_failed(payment, data.get('failureReason'))

    def _handle_invoice_event(self, event_type, data, webhook_config):
        """Handle invoice-related events (AR)

        Args:
            event_type: Event type (invoice.sent, invoice.paid, etc.)
            data: Event data
            webhook_config: Webhook configuration
        """
        billcom_invoice_id = data.get('id')

        # Find invoice in Odoo
        invoice = request.env['account.move'].sudo().search([
            ('billcom_invoice_id', '=', billcom_invoice_id)
        ], limit=1)

        if event_type == 'invoice.sent':
            if invoice:
                invoice.write({
                    'billcom_invoice_status': 'sent',
                    'billcom_invoice_sent_date': fields.Datetime.now(),
                })

        elif event_type == 'invoice.paid':
            if invoice:
                invoice.write({
                    'billcom_invoice_status': 'paid',
                })

                # Check if payment exists, if not create it
                payment_data = data.get('payment', {})
                if payment_data:
                    service = request.env['billcom.service.ar'].sudo().with_config(
                        webhook_config.config_id
                    )
                    service.record_ar_payment_from_billcom(payment_data)

    def _notify_bill_approved(self, bill):
        """Send notification when bill is approved in BILL"""
        request.env['bus.bus']._sendone(
            bill.create_uid.partner_id,
            'billcom_bill_approved',
            {
                'title': 'Bill Approved in BILL',
                'message': f'Bill {bill.name} has been approved in BILL.com',
                'bill_id': bill.id,
            }
        )

    def _notify_payment_sent(self, payment):
        """Send notification when payment is sent"""
        request.env['bus.bus']._sendone(
            payment.create_uid.partner_id,
            'billcom_payment_sent',
            {
                'title': 'Payment Sent',
                'message': f'Payment {payment.name} has been sent via BILL.com',
                'payment_id': payment.id,
            }
        )

    def _notify_payment_completed(self, payment):
        """Send notification when payment is completed"""
        request.env['bus.bus']._sendone(
            payment.create_uid.partner_id,
            'billcom_payment_completed',
            {
                'title': 'Payment Completed',
                'message': f'Payment {payment.name} has been completed',
                'payment_id': payment.id,
                'type': 'success',
            }
        )

    def _notify_payment_failed(self, payment, reason):
        """Send notification when payment fails"""
        request.env['bus.bus']._sendone(
            payment.create_uid.partner_id,
            'billcom_payment_failed',
            {
                'title': 'Payment Failed',
                'message': f'Payment {payment.name} failed: {reason}',
                'payment_id': payment.id,
                'type': 'danger',
            }
        )
```

### 4.3 Webhook Event Model

**Nuevo archivo**: `models/billcom_webhook_event.py`

```python
from odoo import models, fields

class BillcomWebhookEvent(models.Model):
    _name = 'billcom.webhook.event'
    _description = 'Bill.com Webhook Event Log'
    _order = 'create_date desc'

    webhook_config_id = fields.Many2one(
        'billcom.webhook.config',
        required=True,
        ondelete='cascade'
    )
    event_type = fields.Char(required=True, index=True)
    event_data = fields.Text(required=True)
    state = fields.Selection([
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('error', 'Error'),
    ], default='received', required=True, index=True)
    error_message = fields.Text()
    processed_date = fields.Datetime()

    def action_retry_processing(self):
        """Retry processing failed events"""
        for event in self:
            if event.state != 'error':
                continue

            try:
                event.state = 'processing'
                controller = request.env['billcom_controller']
                controller._process_webhook_event(
                    event.webhook_config_id,
                    json.loads(event.event_data)
                )
                event.write({
                    'state': 'processed',
                    'processed_date': fields.Datetime.now(),
                    'error_message': False,
                })
            except Exception as e:
                event.write({
                    'state': 'error',
                    'error_message': str(e),
                })
```

### Deliverables Fase 4

✅ **Webhook configuration model** ✅ **Webhook registration with BILL** ✅ **Signature
validation** ✅ **Event handlers para bill, payment, invoice** ✅ **Real-time
notifications** ✅ **Event logging y retry mechanism**

---

## Fase 5: Enhanced Features

### Objetivo

Implementar características avanzadas como BILL Network, mejores prácticas y
optimizaciones.

### 5.1 BILL Network Integration

**Nuevo archivo**: `models/billcom_service_network.py`

```python
from odoo import models, fields, api
from odoo.exceptions import UserError

class BillcomServiceNetwork(models.AbstractModel):
    _name = 'billcom.service.network'
    _description = 'Bill.com Network Service'
    _inherit = 'billcom.service.abstract'

    def send_bill_via_network(self, move):
        """Send bill to vendor via BILL Network

        Args:
            move: account.move record (vendor bill)

        Returns:
            dict: Response from BILL API
        """
        if not move.billcom_id:
            raise UserError("Bill must be synced to BILL before sending via network")

        endpoint = f"{self.config.api_url}/v3/network/bills/send"
        data = {
            'organizationId': self.config.organization_id,
            'data': {
                'billId': move.billcom_id,
                'sendMethod': 'NETWORK',
                'recipientEmail': move.partner_id.email,
            }
        }

        response = self._make_request('POST', endpoint, data=data)

        if response.get('status') == 'success':
            move.write({
                'billcom_network_sent': True,
                'billcom_network_sent_date': fields.Datetime.now(),
            })

            return response
        else:
            raise Exception(f"Network send failed: {response.get('errorMessage')}")

    def send_invoice_via_network(self, move):
        """Send invoice to customer via BILL Network

        Args:
            move: account.move record (customer invoice)

        Returns:
            dict: Response from BILL API
        """
        if not move.billcom_invoice_id:
            raise UserError("Invoice must be synced to BILL before sending via network")

        endpoint = f"{self.config.api_url}/v3/network/invoices/send"
        data = {
            'organizationId': self.config.organization_id,
            'data': {
                'invoiceId': move.billcom_invoice_id,
                'sendMethod': 'NETWORK',
                'recipientEmail': move.partner_id.email,
                # Network-specific options
                'enableFastPay': True,  # Allow instant payment
                'allowPartialPayment': False,
            }
        }

        response = self._make_request('POST', endpoint, data=data)

        if response.get('status') == 'success':
            move.write({
                'billcom_network_sent': True,
                'billcom_network_sent_date': fields.Datetime.now(),
            })

            return response
        else:
            raise Exception(f"Network send failed: {response.get('errorMessage')}")
```

### 5.2 Mejores Prácticas

#### **Configuración Recomendada**

```python
# En billcom.config, agregar configuración de mejores prácticas
auto_sync_vendors = fields.Boolean(
    string="Auto-sync Vendors",
    default=True,
    help="Automatically sync vendors when created/updated"
)
auto_sync_bills = fields.Boolean(
    string="Auto-sync Bills",
    default=True,
    help="Automatically sync bills when validated"
)
auto_approve_bills = fields.Boolean(
    string="Auto-approve Bills",
    default=False,
    help="Automatically approve bills in BILL when posted in Odoo"
)
auto_send_invoices = fields.Boolean(
    string="Auto-send Invoices",
    default=False,
    help="Automatically send invoices via BILL when posted"
)
sync_attachments = fields.Boolean(
    string="Sync Attachments",
    default=True,
    help="Sync bill/invoice attachments to BILL"
)
use_network = fields.Boolean(
    string="Use BILL Network",
    default=False,
    help="Use BILL Network for sending bills and invoices"
)
queue_batch_size = fields.Integer(
    string="Queue Batch Size",
    default=50,
    help="Number of queue items to process per cron run"
)
retry_max_attempts = fields.Integer(
    string="Max Retry Attempts",
    default=3,
    help="Maximum number of retry attempts for failed operations"
)
```

### Deliverables Fase 5

✅ **BILL Network integration** ✅ **Configuración de mejores prácticas** ✅
**Optimizaciones de performance** ✅ **Documentación completa**

---

## Mejores Prácticas

### Seguridad

1. **Nunca** hardcodear credenciales en código
2. **Siempre** validar webhooks con signatures
3. **Usar** HTTPS exclusivamente
4. **Aplicar** principio de menor privilegio
5. **Rotar** tokens y secrets regularmente

### Performance

1. **Usar** sistema de colas para operaciones asíncronas
2. **Batch** múltiples operaciones cuando sea posible
3. **Cache** tokens de autenticación
4. **Configurar** timeouts apropiados
5. **Limpiar** logs y colas regularmente

### Debugging

1. **Habilitar** logging detallado en desarrollo
2. **Monitorear** estados de cola y logs
3. **Probar** endpoints manualmente cuando sea necesario
4. **Usar** ambiente Sandbox para desarrollo
5. **Mantener** capacidad de rollback

### Deployment

1. **Separar** configuración por ambiente
2. **Planear** migración de datos existentes
3. **Probar** en staging antes de producción
4. **Configurar** alertas para fallos críticos
5. **Mantener** backups antes de cambios

---

## Troubleshooting

### Errores Comunes

#### Error: "Authentication failed"

**Causa**: Credenciales incorrectas o token expirado **Solución**: Verificar
credenciales en configuración, refresh token

#### Error: "MFA required"

**Causa**: Cuenta requiere MFA pero no está configurado **Solución**: Completar wizard
de MFA verification

#### Error: "Webhook signature invalid"

**Causa**: Webhook secret incorrecto o payload alterado **Solución**: Regenerar webhook
secret, re-register webhook

#### Error: "Rate limit exceeded"

**Causa**: Demasiadas requests en corto tiempo **Solución**: Implementar backoff,
reducir frecuencia de sync

#### Error: "Bill not found in BILL"

**Causa**: Bill fue eliminado en BILL pero existe en Odoo **Solución**: Re-sync bill
desde Odoo o unlink billcom_id

---

## Conclusión

Esta guía proporciona un roadmap completo para integrar BILL API v3 con Odoo, cubriendo:

✅ **Foundation Setup** con MFA y ambientes ✅ **AP Integration** completa con vendors,
bills, payments ✅ **AR Integration** completa con customers, invoices, AR payments ✅
**Webhooks** para sincronización en tiempo real ✅ **Enhanced Features** con BILL
Network

El módulo actual ya tiene una base sólida para AP, y esta guía extiende la funcionalidad
para cubrir todos los objetivos solicitados.

### Próximos Pasos Recomendados

1. **Implementar MFA Support** (Fase 1) - Crítico para cuentas enterprise
2. **Desarrollar AR Module** (Fase 3) - Funcionalidad principal faltante
3. **Completar Webhooks** (Fase 4) - Mejora sincronización tiempo real
4. **Agregar BILL Network** (Fase 5) - Feature de valor agregado
5. **Testing Completo** - Unit tests, integration tests, E2E tests

### Recursos Adicionales

- **BILL API Documentation**: https://developer.bill.com/hc/en-us
- **Odoo Development**: https://www.odoo.com/documentation/16.0/developer.html
- **Repositorio OCA**: https://github.com/OCA/l10n-usa
