#!/bin/bash
# Script para verificar logs de MFA después de intentar crear pago

echo "=== LOGS DE AUTENTICACIÓN ==="
docker-compose logs odoo 2>&1 | grep -E "Successfully authenticated|Authenticating with" | tail -5

echo ""
echo "=== LOGS DE MFA STEP-UP ==="
docker-compose logs odoo 2>&1 | grep -E "Performing MFA|Step-up|step-up|trusted" | tail -10

echo ""
echo "=== LOGS DE ERRORES MFA ==="
docker-compose logs odoo 2>&1 | grep -E "BDC_1361|Untrusted|MFA-trusted session" | tail -10

echo ""
echo "=== ÚLTIMOS 20 LOGS RELEVANTES ==="
docker-compose logs odoo 2>&1 | tail -50 | grep -E "INFO|ERROR|WARNING" | grep -E "billcom|mfa|auth|step" -i | tail -20
