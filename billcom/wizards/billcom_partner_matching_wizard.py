# Copyright 2024 Sodexis
# License OPL-1 (Odoo Proprietary License v1.0).

import logging
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BillcomPartnerMatchingWizard(models.TransientModel):
    _name = "billcom.partner.matching.wizard"
    _description = "Bill.com Partner Matching Wizard"

    partner_type = fields.Selection(
        [("vendor", "Vendors"), ("customer", "Customers")],
        string="Partner Type",
        default="vendor",
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("analyzing", "Analyzing"),
            ("review", "Review Matches"),
            ("done", "Done"),
        ],
        default="draft",
        string="State",
    )
    line_ids = fields.One2many(
        "billcom.partner.matching.line",
        "wizard_id",
        string="Matching Lines",
    )
    # Filtered line_ids for each confidence level
    high_confidence_line_ids = fields.One2many(
        "billcom.partner.matching.line",
        "wizard_id",
        string="High Confidence Lines",
        domain=[("confidence_level", "=", "high")],
    )
    medium_confidence_line_ids = fields.One2many(
        "billcom.partner.matching.line",
        "wizard_id",
        string="Medium Confidence Lines",
        domain=[("confidence_level", "=", "medium")],
    )
    low_confidence_line_ids = fields.One2many(
        "billcom.partner.matching.line",
        "wizard_id",
        string="Low Confidence Lines",
        domain=[("confidence_level", "=", "low")],
    )
    no_match_line_ids = fields.One2many(
        "billcom.partner.matching.line",
        "wizard_id",
        string="No Match Lines",
        domain=[("confidence_level", "=", "none")],
    )
    auto_link_high_confidence = fields.Boolean(
        string="Auto-link matches with 100% confidence (3/3 criteria)",
        default=False,
        help="Automatically link partners with exact match on email, phone, and name",
    )
    total_partners = fields.Integer(
        string="Total Partners to Match", compute="_compute_stats", store=True
    )
    high_confidence_count = fields.Integer(
        string="High Confidence (3/3)", compute="_compute_stats", store=True
    )
    medium_confidence_count = fields.Integer(
        string="Medium Confidence (2/3)", compute="_compute_stats", store=True
    )
    low_confidence_count = fields.Integer(
        string="Low Confidence (1/3)", compute="_compute_stats", store=True
    )
    no_match_count = fields.Integer(
        string="No Matches", compute="_compute_stats", store=True
    )

    @api.depends("line_ids", "line_ids.confidence_level")
    def _compute_stats(self):
        for wizard in self:
            wizard.total_partners = len(wizard.line_ids)
            wizard.high_confidence_count = len(
                wizard.line_ids.filtered(lambda l: l.confidence_level == "high")
            )
            wizard.medium_confidence_count = len(
                wizard.line_ids.filtered(lambda l: l.confidence_level == "medium")
            )
            wizard.low_confidence_count = len(
                wizard.line_ids.filtered(lambda l: l.confidence_level == "low")
            )
            wizard.no_match_count = len(
                wizard.line_ids.filtered(lambda l: l.confidence_level == "none")
            )

    def action_find_matches(self):
        """Find matches between Odoo partners and Bill.com vendors/customers"""
        self.ensure_one()

        # Clear existing lines
        self.line_ids.unlink()

        # Get Bill.com service
        try:
            service = self.env["billcom.service"].sudo()
            config = service._get_config()
        except UserError as e:
            raise UserError(_("Bill.com configuration error: %s") % str(e))

        # Check if sync is enabled for this partner type
        if self.partner_type == "vendor" and not config.sync_vendors:
            raise UserError(_("Vendor synchronization is disabled in configuration"))
        elif self.partner_type == "customer" and not config.sync_customers:
            raise UserError(_("Customer synchronization is disabled in configuration"))

        # Get partners from Odoo without billcom_id
        domain = [("billcom_id", "=", False)]
        if self.partner_type == "vendor":
            domain.append(("supplier_rank", ">", 0))
        else:
            domain.append(("customer_rank", ">", 0))

        odoo_partners = self.env["res.partner"].search(domain)

        _logger.info(
            f"📋 Found {len(odoo_partners)} Odoo {self.partner_type}s without billcom_id to match against"
        )

        if not odoo_partners:
            raise UserError(
                _("No %ss found without Bill.com ID. All partners are already linked.")
                % self.partner_type
            )

        # Get vendors/customers from Bill.com
        endpoint = "vendors" if self.partner_type == "vendor" else "customers"
        try:
            result = service._make_request(endpoint, method="GET")
            billcom_partners = result.get("results", [])
        except Exception as e:
            raise UserError(_("Error fetching data from Bill.com: %s") % str(e))

        if not billcom_partners:
            raise UserError(
                _("No %ss found in Bill.com") % self.partner_type.capitalize()
            )

        _logger.info(
            f"Starting matching: {len(billcom_partners)} Bill.com partners vs {len(odoo_partners)} Odoo partners"
        )

        # Reverse logic: Find matches for each Bill.com partner against ALL Odoo partners
        matching_lines = []
        for billcom_partner in billcom_partners:
            # Find ALL potential Odoo matches for this Bill.com partner
            potential_matches = self._find_odoo_matches(billcom_partner, odoo_partners)

            if not potential_matches:
                # No matches found - create empty line for review
                matching_lines.append(
                    {
                        "wizard_id": self.id,
                        "odoo_partner_id": False,
                        "billcom_partner_id": billcom_partner["id"],
                        "billcom_partner_name": billcom_partner.get("name", ""),
                        "billcom_partner_email": billcom_partner.get("email", ""),
                        "billcom_partner_phone": billcom_partner.get("phone", ""),
                        "confidence_level": "none",
                        "match_score": 0,
                        "match_details": "No matches found",
                        "action": "review",
                    }
                )
            else:
                # Create a line for each potential Odoo match
                for match in potential_matches:
                    matching_lines.append(
                        {
                            "wizard_id": self.id,
                            "odoo_partner_id": match["odoo_id"],
                            "billcom_partner_id": billcom_partner["id"],
                            "billcom_partner_name": billcom_partner.get("name", ""),
                            "billcom_partner_email": billcom_partner.get("email", ""),
                            "billcom_partner_phone": billcom_partner.get("phone", ""),
                            "confidence_level": match["confidence_level"],
                            "match_score": match["score"],
                            "match_details": match["details"],
                            "action": "link"
                            if match["confidence_level"] == "high"
                            else "review",
                        }
                    )

        self.line_ids = [(0, 0, line) for line in matching_lines]

        # Auto-link high confidence matches if enabled
        if self.auto_link_high_confidence:
            high_confidence_lines = self.line_ids.filtered(
                lambda l: l.confidence_level == "high" and l.action == "link"
            )
            if high_confidence_lines:
                high_confidence_lines.action_apply_link()
                _logger.info(
                    f"Auto-linked {len(high_confidence_lines)} high confidence matches"
                )

        self.state = "review"

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def _normalize_text(self, text):
        """Normalize text for comparison: lowercase, no accents, no special chars"""
        if not text:
            return ""
        # Lowercase
        text = text.lower().strip()
        # Remove accents
        text = (
            unicodedata.normalize("NFKD", text)
            .encode("ASCII", "ignore")
            .decode("utf-8")
        )
        # Remove special characters except spaces
        text = "".join(c for c in text if c.isalnum() or c.isspace())
        # Remove multiple spaces
        text = " ".join(text.split())
        return text

    def _normalize_phone(self, phone):
        """Normalize phone number: keep only digits"""
        if not phone:
            return ""
        return "".join(c for c in phone if c.isdigit())

    def _find_odoo_matches(self, billcom_partner, odoo_partners):
        """Find ALL potential Odoo partners that match a Bill.com partner

        Uses OR logic: finds Odoo partners that match on ANY of these criteria:
        1. Email exact match
        2. Phone exact match (digits only)
        3. Name normalized match (full name comparison)

        Confidence levels:
        - High (3/3): All three criteria match
        - Medium (2/3): Two criteria match
        - Low (1/3): One criterion matches

        Args:
            billcom_partner: Dict with Bill.com partner data
            odoo_partners: Recordset of res.partner to search

        Returns:
            List of match dictionaries, sorted by score (highest first)
        """
        matches = []

        # Normalize Bill.com partner data
        billcom_email = self._normalize_text(billcom_partner.get("email", ""))
        billcom_phone = self._normalize_phone(billcom_partner.get("phone", ""))
        billcom_name = self._normalize_text(billcom_partner.get("name", ""))

        _logger.info(
            f"🔍 Matching Bill.com partner: {billcom_partner.get('name')} | "
            f"Normalized: name='{billcom_name}', email='{billcom_email}', phone='{billcom_phone}'"
        )

        # Search through ALL Odoo partners
        checked_count = 0
        for odoo_partner in odoo_partners:
            checked_count += 1
            odoo_email = self._normalize_text(odoo_partner.email or "")
            odoo_phone = self._normalize_phone(odoo_partner.phone or "")
            odoo_name = self._normalize_text(odoo_partner.name or "")

            # Calculate matches using OR logic
            email_match = bool(
                billcom_email and odoo_email and billcom_email == odoo_email
            )
            phone_match = bool(
                billcom_phone and odoo_phone and billcom_phone == odoo_phone
            )
            name_match = bool(billcom_name and odoo_name and billcom_name == odoo_name)

            # Debug logging for potential name matches
            if billcom_name and odoo_name and billcom_name in odoo_name:
                _logger.info(
                    f"  🔎 Checking Odoo partner: {odoo_partner.name} (ID: {odoo_partner.id}) | "
                    f"Normalized: name='{odoo_name}', email='{odoo_email}', phone='{odoo_phone}' | "
                    f"Matches: name={name_match}, email={email_match}, phone={phone_match}"
                )

            # Only include if at least one criterion matches
            if not (email_match or phone_match or name_match):
                continue

            # Count matches for confidence level
            match_count = sum([email_match, phone_match, name_match])

            # Build match details
            match_details = []
            if name_match:
                match_details.append("✓ Name")
            if email_match:
                match_details.append("✓ Email")
            if phone_match:
                match_details.append("✓ Phone")

            # Determine confidence level
            if match_count == 3:
                confidence = "high"
            elif match_count == 2:
                confidence = "medium"
            else:  # match_count == 1
                confidence = "low"

            matches.append(
                {
                    "odoo_id": odoo_partner.id,
                    "odoo_name": odoo_partner.name,
                    "odoo_email": odoo_partner.email or "",
                    "odoo_phone": odoo_partner.phone or "",
                    "score": match_count,
                    "confidence_level": confidence,
                    "details": ", ".join(match_details),
                }
            )

        # Sort by score (highest first), then by name
        matches.sort(key=lambda x: (-x["score"], x["odoo_name"]))

        _logger.info(
            f"  ✅ Result: Checked {checked_count} Odoo partners, found {len(matches)} matches"
        )

        return matches

    def action_apply_selected(self):
        """Apply selected links"""
        self.ensure_one()

        lines_to_link = self.line_ids.filtered(lambda l: l.action == "link")

        if not lines_to_link:
            raise UserError(_("No partners selected to link"))

        lines_to_link.action_apply_link()

        self.state = "done"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("%d partners successfully linked with Bill.com")
                % len(lines_to_link),
                "type": "success",
                "sticky": False,
            },
        }

    def action_reset(self):
        """Reset wizard to start over"""
        self.ensure_one()
        self.line_ids.unlink()
        self.state = "draft"

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
