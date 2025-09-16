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
            "shortName": self.ref or (self.name[:40] if self.name else "Unknown")[:40],  # Max 40 chars
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
                "country": addr.country_id.code if addr.country_id else "US",  # Required: default to US
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
        """Sync partner to Bill.com"""
        self.ensure_one()
        if not self.is_sync_to_billcom:
            return False

        try:
            # Use the service model to sync the partner
            service = self.env["billcom.service"]
            return service.sync_partner(self, partner_type)
        except Exception as e:
            _logger.error("Error syncing partner %s to Bill.com: %s", self.name, str(e))
            raise UserError(_("Error syncing to Bill.com: %s") % str(e))

    def sync_to_billcom_vendor(self):
        return self.sync_to_billcom(partner_type="vendor")

    def sync_to_billcom_customer(self):
        return self.sync_to_billcom(partner_type="customer")

    @api.model
    def sync_from_billcom(self, partner_type="vendor"):
        """Sync partners from Bill.com to Odoo"""
        try:
            config = self.env["billcom.config"].get_config()
        except UserError as e:
            _logger.warning(str(e))
            return False

        if partner_type == "vendor" and not config.sync_vendors:
            _logger.info("Vendor synchronization is disabled")
            return False
        elif partner_type == "customer" and not config.sync_customers:
            _logger.info("Customer synchronization is disabled")
            return False

        endpoint = "vendors" if partner_type == "vendor" else "customers"
        try:
            result = self.env["billcom.service"]._make_request(endpoint, method="GET")
            partners = result.get("data", [])
            synced_count = 0

            for partner_data in partners:
                existing_partner = self.search(
                    [("billcom", "=", partner_data["id"])], limit=1
                )

                address = partner_data.get("address", {})
                partner_vals = {
                    "name": partner_data["name"],
                    "email": partner_data.get("email", ""),
                    "phone": partner_data.get("phone", ""),
                    "street": address.get("line1", ""),  # Updated field name for v16
                    "street2": address.get("line2", ""),  # Updated field name for v16
                    "city": address.get("city", ""),
                    "zip": address.get(
                        "zipOrPostalCode", ""
                    ),  # Updated field name for v16
                    "billcom": partner_data["id"],
                    "last_sync_date": fields.Datetime.now(),
                    "ref": partner_data.get("shortName", ""),
                    "lang": partner_data.get("language", "en_US"),
                    "is_sync_to_billcom": True,
                }

                if partner_type == "vendor":
                    partner_vals["supplier_rank"] = 1
                    partner_vals["customer_rank"] = 0
                else:
                    partner_vals["supplier_rank"] = 0
                    partner_vals["customer_rank"] = 1

                if address.get("stateOrProvince"):  # Updated field name for v16
                    state = self.env["res.country.state"].search(
                        [("code", "=", address["stateOrProvince"])], limit=1
                    )
                    if state:
                        partner_vals["state_id"] = state.id

                if address.get("country"):
                    country = self.env["res.country"].search(
                        [("code", "=", address["country"])], limit=1
                    )
                    if country:
                        partner_vals["country_id"] = country.id

                if existing_partner:
                    existing_partner.write(partner_vals)
                    _logger.info(
                        "Updated %s: %s from Bill.com",
                        partner_type,
                        partner_data["name"],
                    )
                    partner_to_use = existing_partner
                else:
                    partner_to_use = self.create(partner_vals)
                    _logger.info(
                        "Created %s: %s from Bill.com",
                        partner_type,
                        partner_data["name"],
                    )
                synced_count += 1

                # If this is a vendor, try to sync bank account information
                if partner_type == "vendor" and partner_to_use.billcom:
                    try:
                        # Get bank account information from Bill.com
                        bank_result = self.env["billcom.service"]._make_request(
                            f"vendors/{partner_to_use.billcom}/bank-account",
                            method="GET",
                        )

                        if bank_result and bank_result.get("bankAccount"):
                            bank_info = bank_result.get("bankAccount", {})

                            # Check if we already have this bank account
                            existing_bank = False
                            if partner_to_use.bank_ids:
                                for bank in partner_to_use.bank_ids:
                                    if bank.acc_number == bank_info.get(
                                        "accountNumber"
                                    ):
                                        existing_bank = True
                                        break

                            # Create bank account if it doesn't exist
                            if not existing_bank:
                                bank_vals = {
                                    "acc_number": bank_info.get("accountNumber", ""),
                                    "aba_routing": bank_info.get("routingNumber", ""),
                                    "acc_holder_name": bank_info.get(
                                        "nameOnAccount", partner_to_use.name
                                    ),
                                    "partner_id": partner_to_use.id,
                                }

                                # Try to find the bank based on routing number
                                if bank_info.get("routingNumber"):
                                    bank_id = self.env["res.bank"].search(
                                        [
                                            (
                                                "aba_routing",
                                                "=",
                                                bank_info.get("routingNumber"),
                                            )
                                        ],
                                        limit=1,
                                    )
                                    if bank_id:
                                        bank_vals["bank_id"] = bank_id.id

                                # Create the bank account
                                self.env["res.partner.bank"].create(bank_vals)
                                _logger.info(
                                    "Created bank account for vendor %s from Bill.com",
                                    partner_to_use.name,
                                )
                    except Exception as e:
                        # If error is 404, it means bank account doesn't exist, which is fine
                        if "404" not in str(e):
                            _logger.warning(
                                "Error syncing bank account for vendor %s: %s",
                                partner_to_use.name,
                                str(e),
                            )

            _logger.info("Synced %d %ss from Bill.com", synced_count, partner_type)
            return synced_count
        except Exception as e:
            _logger.error("Error syncing %ss from Bill.com: %s", partner_type, str(e))
            raise UserError(f"Error syncing {partner_type}s from Bill.com: {str(e)}")

    @api.model
    def _sync_partners_cron(self):
        """Cron job to sync partners from Bill.com"""
        try:
            # Get config and check if auto sync is enabled
            try:
                config = self.env["billcom.config"].get_config()
                if not config.auto_sync_enabled:
                    _logger.info("Automatic sync is disabled in configuration")
                    return False
            except UserError as e:
                _logger.warning(str(e))
                return False

            # Sync vendors if enabled
            if config.sync_vendors:
                try:
                    vendor_count = self.sync_from_billcom(partner_type="vendor")
                    _logger.info(
                        "Cron job synced %s vendors from Bill.com", vendor_count or 0
                    )
                except Exception as e:
                    _logger.error("Error in vendor sync cron: %s", str(e))

            # Sync customers if enabled
            if config.sync_customers:
                try:
                    customer_count = self.sync_from_billcom(partner_type="customer")
                    _logger.info(
                        "Cron job synced %s customers from Bill.com",
                        customer_count or 0,
                    )
                except Exception as e:
                    _logger.error("Error in customer sync cron: %s", str(e))

            return True
        except Exception as e:
            _logger.error("Error in partner sync cron: %s", str(e))
            return False

    @api.model
    def sync_from_billcom_by_id(self, billcom_id, partner_type="vendor"):
        """Sync a specific partner from Bill.com by ID"""
        try:
            config = self.env["billcom.config"].get_config()
        except UserError as e:
            _logger.warning(str(e))
            return False

        if partner_type == "vendor" and not config.sync_vendors:
            _logger.info("Vendor synchronization is disabled")
            return False
        elif partner_type == "customer" and not config.sync_customers:
            _logger.info("Customer synchronization is disabled")
            return False

        endpoint = (
            f"{'vendors' if partner_type == 'vendor' else 'customers'}/{billcom_id}"
        )

        try:
            partner_data = self.env["billcom.service"]._make_request(
                endpoint, method="GET"
            )

            if not partner_data or partner_data.get("status") == "error":
                _logger.warning("Partner not found in Bill.com with ID: %s", billcom_id)
                return False

            # Find existing partner or create new one
            existing_partner = self.search([("billcom_id", "=", billcom_id)], limit=1)
            if not existing_partner:
                existing_partner = self.search([("billcom", "=", billcom_id)], limit=1)

            address = partner_data.get("address", {})
            partner_vals = {
                "name": partner_data.get("name", "Unknown"),
                "email": partner_data.get("email", ""),
                "phone": partner_data.get("phone", ""),
                "street": address.get("line1", ""),
                "street2": address.get("line2", ""),
                "city": address.get("city", ""),
                "zip": address.get("zipOrPostalCode", ""),
                "billcom_id": billcom_id,
                "billcom": billcom_id,  # Backwards compatibility
                "last_sync_date": fields.Datetime.now(),
                "ref": partner_data.get("shortName", ""),
                "is_sync_to_billcom": True,
                "billcom_sync_state": "synced",
            }

            # Set partner type
            if partner_type == "vendor":
                partner_vals["supplier_rank"] = 1
                partner_vals["customer_rank"] = 0
            else:
                partner_vals["supplier_rank"] = 0
                partner_vals["customer_rank"] = 1

            # Set state/country
            if address.get("stateOrProvince"):
                state = self.env["res.country.state"].search(
                    [("code", "=", address["stateOrProvince"])], limit=1
                )
                if state:
                    partner_vals["state_id"] = state.id

            if address.get("country"):
                country = self.env["res.country"].search(
                    [("code", "=", address["country"])], limit=1
                )
                if country:
                    partner_vals["country_id"] = country.id

            if existing_partner:
                existing_partner.write(partner_vals)
                _logger.info(
                    "Updated %s: %s from Bill.com",
                    partner_type,
                    partner_data.get("name"),
                )
                return existing_partner
            else:
                new_partner = self.create(partner_vals)
                _logger.info(
                    "Created %s: %s from Bill.com",
                    partner_type,
                    partner_data.get("name"),
                )
                return new_partner

        except Exception as e:
            _logger.error(
                "Error syncing %s %s from Bill.com: %s",
                partner_type,
                billcom_id,
                str(e),
            )
            if existing_partner:
                existing_partner.billcom_sync_state = "error"
            return False

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
