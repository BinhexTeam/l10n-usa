import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "billcom.abstract.model"]

    # Bill.com specific fields for bills/invoices
    billcom_status = fields.Char(
        string="Bill.com Status",
        help="Payment status from Bill.com (PAID, UNPAID, PARTIALLY_PAID, etc.)",
        readonly=True,
    )

    def _prepare_bill_data(self):
        """Prepare bill data for Bill.com API"""
        self.ensure_one()
        if not self.is_sync_to_billcom or not self.partner_id.is_sync_to_billcom:
            return False

        if self.move_type != "in_invoice":
            return False

        # Prepare line items
        lines = []
        for line in self.invoice_line_ids:
            line_data = {
                "description": line.name or "",
                "amount": line.price_subtotal,
            }
            lines.append(line_data)

        # Build bill data according to Bill.com API v3 format
        # Only include required fields - API calculates amount and assigns paymentStatus
        bill_data = {
            "vendorId": self.partner_id.billcom_id or self.partner_id.billcom,
            "billLineItems": lines,
            "invoice": {
                "invoiceNumber": self.name or "",
                "invoiceDate": self.invoice_date.isoformat()
                if self.invoice_date
                else "",
            },
        }

        # Add dueDate if available
        if self.invoice_date_due:
            bill_data["dueDate"] = self.invoice_date_due.isoformat()

        return bill_data

    def _prepare_invoice_data(self):
        """Prepare invoice data for Bill.com API"""
        self.ensure_one()
        if not self.is_sync_to_billcom or not self.partner_id.is_sync_to_billcom:
            return False

        if self.move_type != "out_invoice":
            return False

        # Prepare line items
        lines = []
        for line in self.invoice_line_ids:
            line_data = {
                "description": line.name or "",
                "quantity": line.quantity,
                "price": line.price_unit,
            }
            # Optional: include itemId if product has Bill.com reference
            if (
                line.product_id
                and hasattr(line.product_id, "billcom_id")
                and line.product_id.billcom_id
            ):
                line_data["itemId"] = line.product_id.billcom_id

            lines.append(line_data)

        # Build invoice data according to Bill.com API v3 format
        # Only include required fields - API calculates totalAmount and assigns status
        invoice_data = {
            "customer": {
                "id": self.partner_id.billcom_id or self.partner_id.billcom
            },
            "invoiceLineItems": lines,
            "invoiceNumber": self.name or "",
            "processingOptions": {
                "sendEmail": False  # Don't send email by default
            },
        }

        # Add dueDate if available
        if self.invoice_date_due:
            invoice_data["dueDate"] = self.invoice_date_due.isoformat()

        return invoice_data

    def _find_existing_billcom_document(self, endpoint, document_number):
        """Search Bill.com for existing document by number

        Args:
            endpoint: 'invoices' or 'bills'
            document_number: The invoice/bill number to search for

        Returns:
            Bill.com ID if found, None otherwise
        """
        try:
            # Build search parameters based on endpoint type
            if endpoint == "invoices":
                params = {"invoiceNumber": document_number}
            elif endpoint == "bills":
                params = {"invoiceNumber": document_number}
            else:
                return None

            # Search for existing document
            result = self.env["billcom.service"]._make_request(
                endpoint, method="GET", params=params
            )

            # Check if we found any results
            if result and isinstance(result, list) and len(result) > 0:
                return result[0].get("id")
            elif result and isinstance(result, dict) and result.get("id"):
                return result.get("id")

            return None

        except Exception as e:
            _logger.warning(
                "Error searching for existing %s with number %s: %s",
                endpoint,
                document_number,
                str(e)
            )
            return None

    def button_sync_to_billcom(self):
        """Sync document to Bill.com"""
        self.ensure_one()
        if not self.is_sync_to_billcom or not self.partner_id.is_sync_to_billcom:
            return False

        if self.move_type not in ["in_invoice", "out_invoice"]:
            return False

        try:
            endpoint = ""
            data = {}

            if self.move_type == "in_invoice":
                endpoint = "bills"
                data = self._prepare_bill_data()
            else:
                endpoint = "invoices"
                data = self._prepare_invoice_data()

            if not data:
                return False

            # Determine if we should update or create
            existing_id = self.billcom_id or self.billcom

            # If no ID in Odoo, check if document exists in Bill.com by number
            if not existing_id:
                existing_id = self._find_existing_billcom_document(endpoint, self.name)
                if existing_id:
                    _logger.info(
                        "Found existing %s in Bill.com with number %s (ID: %s)",
                        endpoint,
                        self.name,
                        existing_id
                    )

            if existing_id:
                # Update existing document
                _logger.info("Updating existing %s with ID %s in Bill.com", endpoint, existing_id)
                result = self.env["billcom.service"]._make_request(
                    f"{endpoint}/{existing_id}", method="PUT", data=data
                )
            else:
                # Create new document
                _logger.info("Creating new %s in Bill.com", endpoint)
                result = self.env["billcom.service"]._make_request(
                    endpoint, method="POST", data=data
                )

            if result and result.get("id"):
                self.with_context(skip_billcom_sync=True).write(
                    {
                        "billcom": result.get("id"),
                        "billcom_id": result.get("id"),
                        "last_sync_date": fields.Datetime.now(),
                    }
                )
                _logger.info("Successfully synced %s with Bill.com", self.name)
                return result
            return False
        except Exception as e:
            _logger.error("Error syncing %s to Bill.com: %s", self.name, str(e))
            return False

    @api.model
    def _sync_documents_cron(self):
        """Cron job to sync documents from Bill.com"""
        try:
            config = (
                self.env["billcom.config"]
                .sudo()
                .search(
                    [("active", "=", True), ("company_id", "=", self.env.company.id)],
                    limit=1,
                )
            )
            if not config or not config.auto_sync_enabled:
                _logger.info(
                    "Automatic sync is disabled or no active configuration found"
                )
                return

            service = self.env["billcom.service"].sudo()
            # Sync both invoices and bills
            service.sync_invoices()
            service.sync_bills()
        except Exception as e:
            _logger.error("Error in document sync cron: %s", str(e))

    def write(self, vals):
        """Override write to sync changes to Bill.com"""
        res = super().write(vals)
        if self.env.context.get("skip_billcom_sync"):
            return res

        for record in self:
            # Only sync if record was created in Odoo (not from Bill.com)
            # Records from Bill.com have billcom_id set
            if (
                record.is_sync_to_billcom
                and record.partner_id.is_sync_to_billcom
                and record.move_type in ["in_invoice", "out_invoice"]
                and not record.billcom_id  # Skip if already synced from Bill.com
            ):
                try:
                    record.with_context(skip_billcom_sync=True).button_sync_to_billcom()
                except Exception as e:
                    _logger.error("Error syncing document to Bill.com: %s", str(e))

    @api.model
    def sync_from_billcom(self, billcom_id):
        """Sync a bill/invoice from Bill.com by ID (called by webhook)

        Args:
            billcom_id (str): Bill.com ID of the document to sync

        Returns:
            bool: True if successful, False otherwise
        """
        if not billcom_id:
            _logger.error("No Bill.com ID provided for sync")
            return False

        try:
            # Search for existing document with this Bill.com ID
            move = self.search([
                '|',
                ('billcom_id', '=', billcom_id),
                ('billcom', '=', billcom_id)
            ], limit=1)

            # Determine if it's a bill or invoice by trying both endpoints
            service = self.env["billcom.service"].sudo()
            document_data = None
            endpoint = None

            # Try bills endpoint first
            try:
                document_data = service._make_request(f"bills/{billcom_id}", method="GET")
                if document_data and document_data.get('id'):
                    endpoint = "bills"
                    move_type = "in_invoice"
            except Exception:
                pass

            # If not a bill, try invoices endpoint
            if not document_data:
                try:
                    document_data = service._make_request(f"invoices/{billcom_id}", method="GET")
                    if document_data and document_data.get('id'):
                        endpoint = "invoices"
                        move_type = "out_invoice"
                except Exception:
                    pass

            if not document_data:
                _logger.error("Could not fetch document %s from Bill.com", billcom_id)
                return False

            _logger.info("Syncing %s %s from Bill.com", endpoint, billcom_id)

            # Extract partner information
            partner_id = None
            if endpoint == "bills":
                vendor_id = document_data.get('vendorId')
                if vendor_id:
                    partner = self.env['res.partner'].sudo().search([
                        '|',
                        ('billcom_id', '=', vendor_id),
                        ('billcom', '=', vendor_id)
                    ], limit=1)
                    if partner:
                        partner_id = partner.id
            elif endpoint == "invoices":
                customer_id = document_data.get('customerId')
                if customer_id:
                    partner = self.env['res.partner'].sudo().search([
                        '|',
                        ('billcom_id', '=', customer_id),
                        ('billcom', '=', customer_id)
                    ], limit=1)
                    if partner:
                        partner_id = partner.id

            if not partner_id:
                _logger.warning("Partner not found for %s %s", endpoint, billcom_id)
                return False

            # Prepare values for create/update
            invoice_info = document_data.get('invoice', {})
            vals = {
                'move_type': move_type,
                'partner_id': partner_id,
                'billcom_id': billcom_id,
                'billcom': billcom_id,
                'billcom_status': document_data.get('paymentStatus'),
                'ref': invoice_info.get('invoiceNumber', ''),
                'invoice_date': invoice_info.get('invoiceDate'),
                'invoice_date_due': document_data.get('dueDate'),
                'last_sync_date': fields.Datetime.now(),
            }

            # Create or update the move
            if move:
                # Update existing move
                move.with_context(skip_billcom_sync=True).write(vals)
                _logger.info("Updated existing %s in Odoo: %s", endpoint, move.name)
            else:
                # Create new move
                vals['is_sync_to_billcom'] = False  # Prevent sync back to Bill.com
                move = self.with_context(skip_billcom_sync=True).create(vals)
                _logger.info("Created new %s in Odoo: %s", endpoint, move.name)

            return True

        except Exception as e:
            _logger.error("Error syncing %s from Bill.com: %s", billcom_id, str(e))
            return False
