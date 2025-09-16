# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **Bill.com Integration** module for Odoo 16.0, providing comprehensive integration with Bill.com API v3. The module enables:

- Two-way synchronization of vendors and bills between Odoo and Bill.com
- Real-time payment processing and status tracking with webhook support
- Advanced retry logic for robust API communication
- Configurable synchronization settings and scheduled actions

## Architecture

The module follows Odoo's standard addon structure with a layered service architecture:

### Core Components

- **billcom_service_abstract.py**: Abstract base service providing common API functionality including authentication, token management, and request handling with retry logic
- **billcom_service.py**: Main service implementation inheriting from abstract base, handles synchronization workflows
- **billcom_config.py**: Configuration model for API credentials, connection settings, and sync preferences

### Extended Models

- **res_partner.py**: Extends partners with Bill.com synchronization fields and methods
- **account_move.py**: Extends vendor bills with Bill.com integration
- **account_payment.py**: Extends payments with Bill.com status tracking
- **account_payment_register.py**: Custom payment registration with Bill.com integration

### Controllers

- **billcom_controller.py**: HTTP endpoints for webhook handling and API callbacks

## Development Environment

This module is part of a **Doodba-based Odoo environment**. Doodba is a Docker-based Odoo development framework.

### Key Environment Files

- `devel.yaml`: Development Docker Compose configuration
- `docker-compose.yml` → `devel.yaml`: Symlinked for development
- `tasks.py`: Invoke-based task runner for common operations
- `.pre-commit-config.yaml`: Code quality and formatting hooks

### Dependencies

External Python dependencies (defined in `__manifest__.py`):
- `requests`: HTTP client for API communication
- `PyJWT`: JSON Web Token handling

## Common Development Commands

Since this is a Doodba environment, use these commands from the project root:

### Development Server
```bash
# Start development environment
docker-compose up -d

# View logs
docker-compose logs -f odoo

# Access Odoo shell
docker-compose exec odoo odoo shell -d [database_name]
```

### Code Quality
```bash
# Run pre-commit hooks (linting, formatting)
pre-commit run --all-files

# Run specific hooks
pre-commit run black --all-files
pre-commit run flake8 --all-files
pre-commit run pylint_odoo --all-files
```

### Module Management
```bash
# Install/upgrade the module in development
docker-compose exec odoo odoo -i billcom -d [database_name]
docker-compose exec odoo odoo -u billcom -d [database_name]
```

## API Integration Architecture

The Bill.com integration uses a robust service pattern:

1. **Authentication Layer**: Token-based authentication with automatic refresh
2. **Request Layer**: Centralized HTTP request handling with comprehensive retry logic
3. **Sync Layer**: Business logic for data synchronization between systems
4. **Configuration Layer**: Multi-company configuration management with connection state tracking

### Sync Mechanisms

- **Scheduled Actions**: Automated synchronization via Odoo cron jobs (defined in `data/ir_cron_data.xml`)
- **Real-time Sync**: Triggered on record creation/modification
- **Manual Sync**: User-initiated synchronization from UI
- **Webhook Support**: Real-time updates from Bill.com via controller endpoints

## Code Quality Standards

The project uses OCA (Odoo Community Association) standards with:

- **Black**: Python code formatting
- **isort**: Import sorting
- **flake8**: Linting with bugbear plugin
- **pylint-odoo**: Odoo-specific linting
- **pre-commit hooks**: Automated quality checks

## Testing

No dedicated test files are present. Testing should follow Odoo's testing framework patterns if implemented.

## Configuration Notes

The module supports both sandbox and production Bill.com environments. Configuration is managed through the `billcom.config` model with fields for:

- API credentials (key, secret, organization ID, dev key)
- Environment selection (sandbox/production)
- Sync preferences (vendors, customers, payments, bills)
- Connection state tracking and error reporting