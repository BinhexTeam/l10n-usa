# Copyright 2024 Sodexis
# License OPL-1 (Odoo Proprietary License v1.0).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BillcomPartnerMatchingLine(models.TransientModel):
    _name = "billcom.partner.matching.line"
    _description = "Bill.com Partner Matching Line"
    _order = "confidence_level desc, match_score desc, id"

    wizard_id = fields.Many2one(
        "billcom.partner.matching.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    odoo_partner_id = fields.Many2one("res.partner", string="Odoo Partner")
    odoo_partner_name = fields.Char(
        related="odoo_partner_id.name", string="Odoo Name", readonly=True
    )
    odoo_partner_email = fields.Char(
        related="odoo_partner_id.email", string="Odoo Email", readonly=True
    )
    odoo_partner_phone = fields.Char(
        related="odoo_partner_id.phone", string="Odoo Phone", readonly=True
    )
    billcom_partner_id = fields.Char(
        string="Bill.com ID", readonly=True, help="Bill.com partner ID"
    )
    billcom_partner_name = fields.Char(string="Bill.com Name", readonly=True)
    billcom_partner_email = fields.Char(string="Bill.com Email", readonly=True)
    billcom_partner_phone = fields.Char(string="Bill.com Phone", readonly=True)
    confidence_level = fields.Selection(
        [
            ("high", "High (3/3)"),
            ("medium", "Medium (2/3)"),
            ("low", "Low (1/3)"),
            ("none", "No Match"),
        ],
        string="Confidence",
        readonly=True,
        help="Matching confidence based on email, phone, and name criteria",
    )
    match_score = fields.Integer(
        string="Score",
        readonly=True,
        help="Number of criteria matched (0-3)",
    )
    match_details = fields.Char(
        string="Match Details",
        readonly=True,
        help="Details of what criteria matched",
    )
    action = fields.Selection(
        [
            ("link", "Link"),
            ("ignore", "Ignore"),
            ("review", "Review"),
        ],
        string="Action",
        default="review",
        help="Action to take for this match",
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("linked", "Linked"),
            ("ignored", "Ignored"),
            ("error", "Error"),
        ],
        string="State",
        default="pending",
        readonly=True,
    )
    error_message = fields.Text(string="Error Message", readonly=True)

    # Computed fields for color coding
    confidence_color = fields.Integer(compute="_compute_confidence_color")

    @api.depends("confidence_level")
    def _compute_confidence_color(self):
        """Compute color for tree view based on confidence level"""
        color_map = {
            "high": 10,  # Green
            "medium": 4,  # Blue
            "low": 2,  # Orange
            "none": 1,  # Red
        }
        for line in self:
            line.confidence_color = color_map.get(line.confidence_level, 0)

    def action_apply_link(self):
        """Apply the link between Odoo partner and Bill.com partner"""
        for line in self:
            # Validate both partners are present
            if not line.billcom_partner_id:
                line.write(
                    {
                        "state": "error",
                        "error_message": "No Bill.com partner to link",
                    }
                )
                continue

            if not line.odoo_partner_id:
                line.write(
                    {
                        "state": "error",
                        "error_message": "No Odoo partner selected. Please select a partner to link.",
                    }
                )
                continue

            # Check if the selected Odoo partner already has a Bill.com ID
            if line.odoo_partner_id.billcom_id:
                line.write(
                    {
                        "state": "error",
                        "error_message": _(
                            "This Odoo partner is already linked to Bill.com ID: %s. "
                            "Please unlink it first or choose a different partner."
                        )
                        % line.odoo_partner_id.billcom_id,
                    }
                )
                continue

            # Check if another Odoo partner is already linked to this Bill.com ID
            existing_link = self.env["res.partner"].search(
                [
                    ("billcom_id", "=", line.billcom_partner_id),
                    ("id", "!=", line.odoo_partner_id.id),
                ],
                limit=1,
            )
            if existing_link:
                line.write(
                    {
                        "state": "error",
                        "error_message": _(
                            "Bill.com partner %s is already linked to Odoo partner: %s (ID: %d). "
                            "Please unlink it first or choose a different Bill.com partner."
                        )
                        % (
                            line.billcom_partner_name,
                            existing_link.name,
                            existing_link.id,
                        ),
                    }
                )
                continue

            try:
                # Determine partner type
                service = self.env["billcom.service"].sudo()
                partner_type = (
                    "vendor" if line.odoo_partner_id.supplier_rank > 0 else "customer"
                )

                # Fetch complete partner data from Bill.com
                endpoint = (
                    f"vendors/{line.billcom_partner_id}"
                    if partner_type == "vendor"
                    else f"customers/{line.billcom_partner_id}"
                )

                billcom_data = service._make_request(endpoint, method="GET")
                _logger.info(
                    f"Fetched complete {partner_type} data from Bill.com for {line.odoo_partner_id.name}"
                )

                # Update ALL partner fields with Bill.com data
                vals = {
                    "name": billcom_data.get("name")
                    or billcom_data.get("companyName", line.odoo_partner_id.name),
                    "is_sync_to_billcom": True,
                    "billcom": line.billcom_partner_id,
                    "billcom_id": line.billcom_partner_id,
                    "email": billcom_data.get("email") or line.odoo_partner_id.email,
                    "phone": billcom_data.get("phone") or line.odoo_partner_id.phone,
                    "ref": billcom_data.get("accountNumber")
                    or line.odoo_partner_id.ref,
                    "vat": billcom_data.get("taxId") or line.odoo_partner_id.vat,
                    "active": not billcom_data.get("archived", False),
                    "last_sync_date": fields.Datetime.now(),
                    "company_type": "company"
                    if billcom_data.get("accountType") == "BUSINESS"
                    else "person",
                }

                # Set supplier or customer rank
                if partner_type == "vendor":
                    vals["supplier_rank"] = 1
                else:
                    vals["customer_rank"] = 1

                # Add short name as comment if exists
                if billcom_data.get("shortName"):
                    vals["comment"] = f"Short name: {billcom_data.get('shortName')}"

                # Map address - Bill.com API v3 uses different field names
                address_data = billcom_data.get("address") or billcom_data.get(
                    "billingAddress"
                )
                if address_data:
                    vals.update(
                        {
                            "street": address_data.get("line1")
                            or address_data.get("addressLine1"),
                            "street2": address_data.get("line2")
                            or address_data.get("addressLine2"),
                            "city": address_data.get("city"),
                            "zip": address_data.get("zipOrPostalCode")
                            or address_data.get("zip"),
                        }
                    )

                    # Map state
                    state_code = address_data.get(
                        "stateOrProvince"
                    ) or address_data.get("state")
                    if state_code:
                        state = self.env["res.country.state"].search(
                            [("code", "=", state_code)], limit=1
                        )
                        if state:
                            vals["state_id"] = state.id

                    # Map country
                    country_code = address_data.get("country")
                    if country_code:
                        country = self.env["res.country"].search(
                            [("code", "=", country_code)], limit=1
                        )
                        if country:
                            vals["country_id"] = country.id

                # Update Odoo partner with all Bill.com data
                line.odoo_partner_id.with_context(skip_billcom_sync=True).write(vals)
                _logger.info(
                    f"Updated Odoo partner {line.odoo_partner_id.name} with all Bill.com data"
                )

                # Sync bank account if paymentInformation exists
                payment_info = billcom_data.get("paymentInformation", {})
                if payment_info and payment_info.get("bankAccount"):
                    try:
                        service._sync_partner_bank_account(
                            line.odoo_partner_id, payment_info
                        )
                        _logger.info(
                            f"Synced bank account from Bill.com for {line.odoo_partner_id.name}"
                        )
                    except Exception as e:
                        _logger.warning(
                            f"Could not sync bank account from Bill.com: {e}"
                        )
                        # Don't fail the linking process if bank sync fails

                line.write({"state": "linked"})

                # Log success
                _logger.info(
                    f"Linked and synced partner {line.odoo_partner_id.name} (ID: {line.odoo_partner_id.id}) "
                    f"with Bill.com {line.billcom_partner_name} (ID: {line.billcom_partner_id})"
                )

                # Build sync details for message
                sync_details = []
                if vals.get("email"):
                    sync_details.append(f"Email: {vals['email']}")
                if vals.get("phone"):
                    sync_details.append(f"Phone: {vals['phone']}")
                if vals.get("street"):
                    sync_details.append(
                        f"Address: {vals['street']}, {vals.get('city', '')}"
                    )
                if payment_info and payment_info.get("bankAccount"):
                    sync_details.append("Bank Account: Synced")

                # Post message on partner for audit trail
                line.odoo_partner_id.message_post(
                    body=_(
                        "<p><strong>Bill.com Partner Linked & Synced</strong></p>"
                        "<ul>"
                        "<li>Bill.com Name: %s</li>"
                        "<li>Bill.com ID: %s</li>"
                        "<li>Confidence: %s</li>"
                        "<li>Match Details: %s</li>"
                        "<li>Synced Fields: %s</li>"
                        "<li>Linked via: Partner Matching Wizard</li>"
                        "</ul>"
                    )
                    % (
                        line.billcom_partner_name,
                        line.billcom_partner_id,
                        dict(line._fields["confidence_level"].selection).get(
                            line.confidence_level
                        ),
                        line.match_details,
                        ", ".join(sync_details)
                        if sync_details
                        else "All available fields",
                    ),
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                )

            except Exception as e:
                error_msg = str(e)
                line.write({"state": "error", "error_message": error_msg})
                _logger.error(
                    f"Error linking partner {line.odoo_partner_id.name}: {error_msg}"
                )

    def action_ignore(self):
        """Mark this match as ignored"""
        self.ensure_one()
        self.write({"action": "ignore", "state": "ignored"})

    def action_select_for_link(self):
        """Select this match for linking"""
        self.ensure_one()
        self.write({"action": "link"})

    def action_search_billcom(self):
        """Open search dialog to manually find Bill.com partner"""
        self.ensure_one()

        # This would open a new wizard for manual search
        # For now, we'll just show a message
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Manual Search"),
                "message": _(
                    "Manual search feature coming soon. "
                    "For now, please use the Bill.com sync wizard to create a new partner."
                ),
                "type": "info",
                "sticky": False,
            },
        }

    def action_unlink_partner(self):
        """Unlink Bill.com ID from Odoo partner (in case of error)"""
        self.ensure_one()

        if not self.odoo_partner_id.billcom_id:
            raise UserError(_("This partner is not linked to Bill.com"))

        old_billcom_id = self.odoo_partner_id.billcom_id

        self.odoo_partner_id.with_context(skip_billcom_sync=True).write(
            {
                "billcom_id": False,
                "billcom": False,
            }
        )

        self.write({"state": "pending", "error_message": False})

        # Post message on partner
        self.odoo_partner_id.message_post(
            body=_(
                "<p><strong>Bill.com Partner Unlinked</strong></p>"
                "<ul>"
                "<li>Previous Bill.com ID: %s</li>"
                "<li>Unlinked via: Partner Matching Wizard</li>"
                "</ul>"
            )
            % old_billcom_id,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Partner unlinked successfully"),
                "type": "success",
                "sticky": False,
            },
        }
