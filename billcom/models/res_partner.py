import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "billcom.abstract.model"]

    billcom_sync_state = fields.Selection(
        [
            ("pending", "Pending Sync"),
            ("synced", "Synced"),
            ("error", "Sync Error"),
        ],
        default="pending",
        string="Bill.com Sync State",
    )

    def _prepare_partner_data(self, partner_type="vendor"):
        """Prepare partner data for Bill.com API v3"""
        self.ensure_one()
        if not self.is_sync_to_billcom:
            return False

        # Get billing and shipping addresses
        billing_address = self
        shipping_address = self

        # If this is a contact with a parent company, use parent for some fields
        parent_company = (
            self.parent_id if self.parent_id and self.parent_id.is_company else False
        )

        # Check for specific address types in child contacts
        if self.child_ids:
            for child in self.child_ids:
                if child.type == "invoice":
                    billing_address = child
                elif child.type == "delivery":
                    shipping_address = child

        # Common data for both vendor and customer (only valid API v3 fields)
        common_data = {
            "name": self.name or "Unknown",  # Required field
            "shortName": self.ref
            or (self.name[:40] if self.name else "Unknown")[:40],  # Max 40 chars
        }

        # Add optional fields only if they have values
        if self.email:
            common_data["email"] = self.email
        if self.phone:
            common_data["phone"] = self.phone
        if self.ref:
            common_data["accountNumber"] = self.ref

        # Log the common data for debugging
        _logger.info("Common data prepared: %s", common_data)

        # Address format for Bill.com API v3
        def format_address(addr):
            # Bill.com API v3 required address fields: line1, city, zipOrPostalCode, country
            address_data = {
                "line1": addr.street or "N/A",  # Required: line1 cannot be empty
                "city": addr.city or "N/A",  # Required: city cannot be empty
                "zipOrPostalCode": addr.zip or "00000",  # Required: cannot be empty
                "country": addr.country_id.code
                if addr.country_id
                else "US",  # Required: default to US
            }

            # Optional fields - only add if they have values
            if addr.street2:
                address_data["line2"] = addr.street2
            if addr.state_id and addr.state_id.code:
                address_data["stateOrProvince"] = addr.state_id.code

            # Log the address data for debugging
            _logger.info("Formatted address data: %s", address_data)

            return address_data

        if partner_type == "vendor":
            vendor_data = common_data.copy()

            # Add required fields for vendor
            vendor_data["accountType"] = "BUSINESS" if self.is_company else "PERSON"
            vendor_data["address"] = format_address(self)  # Required field

            # Log final vendor data
            _logger.info("Final vendor data for Bill.com: %s", vendor_data)

            # Note: paymentTermId requires a Bill.com payment term ID (format: pte01XXXXXX)
            # not the Odoo payment term name. Omitting this field for now.
            # TODO: Implement payment term mapping between Odoo and Bill.com if needed

            # Note: Bank account information is now handled separately via dedicated endpoints
            # See: https://developer.bill.com/reference/createvendorbankaccount

            return vendor_data
        else:  # customer
            customer_data = common_data.copy()

            # Add required fields for customer
            customer_data["accountType"] = "BUSINESS" if self.is_company else "PERSON"
            customer_data["billingAddress"] = format_address(billing_address)
            customer_data["shippingAddress"] = format_address(shipping_address)

            # Add optional language field if available
            if self.lang:
                customer_data["language"] = self.lang

            # Log final customer data
            _logger.info("Final customer data for Bill.com: %s", customer_data)

            # Note: paymentTermId requires a Bill.com payment term ID (format: pte01XXXXXX)
            # not the Odoo payment term name. Omitting this field for now.
            # TODO: Implement payment term mapping between Odoo and Bill.com if needed

            return customer_data

    def sync_to_billcom(self, partner_type="vendor"):
        """Sync partner to Bill.com - delegates to service"""
        self.ensure_one()
        if not self.is_sync_to_billcom:
            return False

        try:
            service = self.env["billcom.service"]
            return service.sync_partner(self, partner_type)
        except Exception as e:
            _logger.error("Error syncing partner %s to Bill.com: %s", self.name, str(e))
            raise UserError(_("Error syncing to Bill.com: %s") % str(e))

    def sync_to_billcom_vendor(self):
        """Sync as vendor - delegates to service"""
        return self.sync_to_billcom(partner_type="vendor")

    def sync_to_billcom_customer(self):
        """Sync as customer - delegates to service"""
        return self.sync_to_billcom(partner_type="customer")

    @api.model
    def sync_from_billcom(self, partner_type="vendor"):
        """Sync partners from Bill.com to Odoo - delegates to service"""
        service = self.env["billcom.service"]
        return service.sync_partners_from_billcom(partner_type=partner_type)

    @api.model
    def _sync_partners_cron(self):
        """Cron job to sync partners from Bill.com - delegates to service"""
        service = self.env["billcom.service"]
        return service.sync_partners_cron()

    @api.model
    def sync_from_billcom_by_id(self, billcom_id, partner_type="vendor"):
        """Sync a specific partner from Bill.com by ID - delegates to service"""
        service = self.env["billcom.service"]
        return service.sync_partner_from_billcom_by_id(
            billcom_id, partner_type=partner_type
        )

    # Backwards compatibility
    _sync_vendors_cron = _sync_partners_cron


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    billcom_funding_account_id = fields.Many2one(
        "billcom.funding.account",
        string="Bill.com Funding Account",
        help="Link to the Bill.com funding account (organization bank account). "
        "This is used when creating payments to specify which account to pay from.",
        copy=False,
        domain=[("status", "=", "VERIFIED")],
        ondelete="restrict",
    )
