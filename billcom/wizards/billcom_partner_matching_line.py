# Copyright 2024 Sodexis
# License OPL-1 (Odoo Proprietary License v1.0).

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BillcomPartnerMatchingLine(models.TransientModel):
    _name = "billcom.partner.matching.line"
    _description = "Bill.com Partner Matching Line"
    _order = "confidence_level desc, match_score desc, id"

    wizard_id = fields.Many2one(
        "billcom.partner.matching.wizard", string="Wizard", required=True, ondelete="cascade"
    )
    odoo_partner_id = fields.Many2one(
        "res.partner", string="Odoo Partner", required=True, readonly=True
    )
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
            if not line.billcom_partner_id:
                line.write(
                    {
                        "state": "error",
                        "error_message": "No Bill.com partner to link",
                    }
                )
                continue

            try:
                # Update Odoo partner with Bill.com ID
                line.odoo_partner_id.with_context(skip_billcom_sync=True).write(
                    {
                        "billcom_id": line.billcom_partner_id,
                        "billcom": line.billcom_partner_id,
                        "last_sync_date": fields.Datetime.now(),
                    }
                )

                line.write({"state": "linked"})

                # Log success
                _logger.info(
                    f"Linked partner {line.odoo_partner_id.name} (ID: {line.odoo_partner_id.id}) "
                    f"with Bill.com {line.billcom_partner_name} (ID: {line.billcom_partner_id})"
                )

                # Post message on partner for audit trail
                line.odoo_partner_id.message_post(
                    body=_(
                        "<p><strong>Bill.com Partner Linked</strong></p>"
                        "<ul>"
                        "<li>Bill.com Name: %s</li>"
                        "<li>Bill.com ID: %s</li>"
                        "<li>Confidence: %s</li>"
                        "<li>Match Details: %s</li>"
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
