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
    duplicate_group_line_ids = fields.One2many(
        "billcom.partner.matching.line",
        "wizard_id",
        string="Duplicate Group Lines",
        domain=[("is_duplicate_group", "=", True)],
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
    selected_count = fields.Integer(
        string="Selected Lines", compute="_compute_stats", store=True
    )
    duplicate_group_count = fields.Integer(
        string="Duplicate Groups", compute="_compute_stats", store=True
    )

    @api.depends(
        "line_ids",
        "line_ids.confidence_level",
        "line_ids.selected",
        "line_ids.is_duplicate_group",
    )
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
            wizard.selected_count = len(wizard.line_ids.filtered(lambda l: l.selected))
            wizard.duplicate_group_count = len(
                wizard.line_ids.filtered(lambda l: l.is_duplicate_group)
            )

    def _normalize_partner_name(self, name):
        """Normalize partner name for duplicate detection

        Args:
            name (str): Partner name to normalize

        Returns:
            str: Normalized name (lowercase, no special chars, trimmed)
        """
        if not name:
            return ""

        import re

        # Convert to lowercase
        normalized = name.lower()

        # Remove common company suffixes
        suffixes = [
            "inc",
            "incorporated",
            "corp",
            "corporation",
            "llc",
            "ltd",
            "limited",
            "co",
            "company",
            "gmbh",
            "s.a.",
            "sa",
            "srl",
            "usd",
            "eur",
            "gbp",
            "cad",
            "aud",  # Currency codes
        ]
        for suffix in suffixes:
            # Remove suffix with optional punctuation and spaces
            normalized = re.sub(rf"\b{re.escape(suffix)}\b[.,\s]*", "", normalized)

        # Remove all special characters and extra spaces
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip()

        return normalized

    def _group_billcom_duplicates(self, billcom_partners):
        """Group Bill.com partners by normalized name to detect duplicates

        Args:
            billcom_partners (list): List of Bill.com partner dictionaries

        Returns:
            tuple: (grouped_partners, duplicates)
                - grouped_partners: dict {normalized_name: [partner_dicts]}
                - duplicates: dict {normalized_name: [partner_dicts]} (only groups with >1 partner)
        """
        from collections import defaultdict

        grouped = defaultdict(list)

        for partner in billcom_partners:
            name = partner.get("name", "")
            normalized = self._normalize_partner_name(name)

            # Store partner with normalized key
            grouped[normalized].append(partner)

        # Identify duplicates (groups with multiple partners)
        duplicates = {
            name: partners for name, partners in grouped.items() if len(partners) > 1
        }

        _logger.info(
            f"Duplicate detection: {len(billcom_partners)} total partners, "
            f"{len(grouped)} unique names, {len(duplicates)} duplicate groups"
        )

        if duplicates:
            for normalized_name, partners in duplicates.items():
                currencies = [p.get("billCurrency", "USD") for p in partners]
                _logger.info(
                    f"  Duplicate group '{normalized_name}': {len(partners)} partners "
                    f"with currencies {currencies}"
                )

        return grouped, duplicates

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
        # if self.partner_type == "vendor":
        #     domain.append(("supplier_rank", ">", 0))
        # else:
        #     domain.append(("customer_rank", ">", 0))

        odoo_partners = self.env["res.partner"].search(domain)

        _logger.info(
            f"📋 Found {len(odoo_partners)} Odoo {self.partner_type}s without billcom_id to match against"
        )

        if not odoo_partners:
            raise UserError(
                _("No %ss found without Bill.com ID. All partners are already linked.")
                % self.partner_type
            )

        # Get vendors/customers from Bill.com with pagination support
        endpoint = "vendors" if self.partner_type == "vendor" else "customers"
        billcom_partners = []
        try:
            # Fetch all pages of results
            next_page = None
            page_num = 1

            while True:
                _logger.info(
                    f"Fetching {self.partner_type}s from Bill.com - Page {page_num}"
                )

                # Build params with pagination
                # Note: Bill.com API does not allow filters when using page token
                params = {"max": 100}
                if next_page:
                    # When using page token, DO NOT send filters
                    params["page"] = next_page
                else:
                    # Only send filters on first request
                    params["filters"] = "archived:eq:false"

                result = service._make_request(endpoint, method="GET", params=params)

                if not result:
                    break

                # Add results from this page
                page_results = result.get("results", [])
                billcom_partners.extend(page_results)
                _logger.info(
                    f"Page {page_num}: Fetched {len(page_results)} {self.partner_type}s (Total: {len(billcom_partners)})"
                )

                # Check if there are more pages
                next_page = result.get("nextPage")
                if not next_page:
                    break

                page_num += 1

            _logger.info(
                f"✓ Completed fetching all {len(billcom_partners)} {self.partner_type}s from Bill.com"
            )

            # Filter out archived partners (in case pagination brought some)
            original_count = len(billcom_partners)
            billcom_partners = [
                partner
                for partner in billcom_partners
                if not partner.get("archived", False)
            ]
            filtered_archived = original_count - len(billcom_partners)
            if filtered_archived > 0:
                _logger.info(
                    f"Filtered out {filtered_archived} archived partners. "
                    f"Remaining: {len(billcom_partners)} active partners"
                )

        except Exception as e:
            raise UserError(_("Error fetching data from Bill.com: %s") % str(e))

        if not billcom_partners:
            raise UserError(
                _("No %ss found in Bill.com") % self.partner_type.capitalize()
            )

        # Filter out Bill.com partners that are already linked to Odoo partners
        _logger.info(
            f"Filtering Bill.com partners that are already linked to Odoo partners..."
        )

        # Get all Bill.com IDs that already exist in Odoo
        billcom_ids_in_odoo = set()
        all_odoo_partners = self.env["res.partner"].search(
            [
                "|",
                ("billcom_id", "!=", False),
                ("billcom", "!=", False),
            ]
        )

        for partner in all_odoo_partners:
            if partner.billcom_id:
                billcom_ids_in_odoo.add(partner.billcom_id)
            if partner.billcom:
                billcom_ids_in_odoo.add(partner.billcom)

        _logger.info(
            f"Found {len(billcom_ids_in_odoo)} Bill.com IDs already linked in Odoo"
        )

        # Filter Bill.com partners to exclude already linked ones
        original_count = len(billcom_partners)
        billcom_partners = [
            bc_partner
            for bc_partner in billcom_partners
            if bc_partner["id"] not in billcom_ids_in_odoo
        ]

        filtered_count = original_count - len(billcom_partners)
        _logger.info(
            f"Filtered out {filtered_count} already linked partners. "
            f"Remaining: {len(billcom_partners)} to process"
        )

        if not billcom_partners:
            raise UserError(
                _(
                    "All %ss from Bill.com are already linked to Odoo partners. "
                    "No new partners to match."
                )
                % self.partner_type
            )

        # Group Bill.com partners to detect duplicates
        grouped_partners, duplicate_groups = self._group_billcom_duplicates(
            billcom_partners
        )

        _logger.info(
            f"Starting matching: {len(billcom_partners)} Bill.com partners vs {len(odoo_partners)} Odoo partners"
        )

        # Track processed Bill.com IDs to avoid duplicates in matching lines
        processed_billcom_ids = set()

        # Reverse logic: Find matches for each Bill.com partner against ALL Odoo partners
        matching_lines = []

        # Process duplicate groups first (multiple Bill.com records → one Odoo partner)
        for normalized_name, partners in duplicate_groups.items():
            # Get all Bill.com IDs and currencies in this group
            billcom_ids_data = []
            for partner in partners:
                billcom_ids_data.append(
                    {
                        "id": partner["id"],
                        "name": partner.get("name", ""),
                        "currency": partner.get("billCurrency", "USD"),
                        "email": partner.get("email", ""),
                        "phone": partner.get("phone", ""),
                    }
                )
                processed_billcom_ids.add(partner["id"])

            # Use first partner as representative for matching
            representative = partners[0]

            # Find Odoo matches for this group
            potential_matches = self._find_odoo_matches(representative, odoo_partners)

            # Build display name showing all currencies
            currencies = [p.get("billCurrency", "USD") for p in partners]
            display_name = f"{representative.get('name', '')} ({', '.join(currencies)})"

            import json

            if not potential_matches:
                # No matches - suggest creating ONE Odoo partner for ALL Bill.com records
                matching_lines.append(
                    {
                        "wizard_id": self.id,
                        "odoo_partner_id": False,
                        "billcom_partner_id": representative["id"],  # Primary ID
                        "billcom_partner_name": display_name,
                        "billcom_partner_email": representative.get("email", ""),
                        "billcom_partner_phone": representative.get("phone", ""),
                        "billcom_ids_json": json.dumps(billcom_ids_data),
                        "is_duplicate_group": True,
                        "confidence_level": "none",
                        "match_score": 0,
                        "match_details": f"Duplicate group: {len(partners)} Bill.com records with different currencies → Create ONE Odoo partner",
                        "action": "create",
                    }
                )
            else:
                # Found matches - Select BEST match and create ONE line to link entire group
                best_match = max(potential_matches, key=lambda m: m["score"])

                # Determine action - all IDs in this group are not yet linked (filtered earlier)
                action = (
                    "link" if best_match["confidence_level"] == "high" else "review"
                )
                confidence = best_match["confidence_level"]
                odoo_partner_id = best_match["odoo_id"]
                match_details = (
                    f"Duplicate group: {len(partners)} Bill.com IDs → "
                    f"Link all to '{self.env['res.partner'].browse(best_match['odoo_id']).name}'"
                )

                matching_lines.append(
                    {
                        "wizard_id": self.id,
                        "odoo_partner_id": odoo_partner_id,
                        "billcom_partner_id": representative["id"],
                        "billcom_partner_name": display_name,
                        "billcom_partner_email": representative.get("email", ""),
                        "billcom_partner_phone": representative.get("phone", ""),
                        "billcom_ids_json": json.dumps(billcom_ids_data),
                        "is_duplicate_group": True,
                        "confidence_level": confidence,
                        "match_score": best_match["score"],
                        "match_details": match_details,
                        "action": action,
                    }
                )

        # Process remaining single Bill.com partners (not in duplicate groups)
        for billcom_partner in billcom_partners:
            if billcom_partner["id"] in processed_billcom_ids:
                continue  # Skip already processed duplicates

            # Find ALL potential Odoo matches for this Bill.com partner
            # Note: Already linked partners were filtered out earlier
            potential_matches = self._find_odoo_matches(billcom_partner, odoo_partners)

            if not potential_matches:
                # No matches found - suggest creating new partner in Odoo
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
                        "match_details": "No matches found - Create new partner suggested",
                        "action": "create",  # Suggest create action for no matches
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
        billcom_short_name = self._normalize_text(billcom_partner.get("shortName", ""))

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
            name_match = bool(
                (billcom_short_name or billcom_name and odoo_name)
                and (billcom_name == odoo_name or billcom_short_name == odoo_name)
            )

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
        """Apply actions to selected lines based on their action field

        Processes only lines with selected=True according to their action:
        - 'create': Creates new partner (parent-child for duplicate groups)
        - 'link': Links to existing partner (parent-child for duplicate groups)
        - 'ignore': Marks as ignored
        """
        self.ensure_one()

        # Filter ONLY selected lines
        selected_lines = self.line_ids.filtered(lambda l: l.selected)

        if not selected_lines:
            raise UserError(_("No lines selected. Please select lines to process."))

        # Group by action
        lines_to_create = selected_lines.filtered(lambda l: l.action == "create")
        lines_to_link = selected_lines.filtered(lambda l: l.action == "link")
        lines_to_ignore = selected_lines.filtered(lambda l: l.action == "ignore")

        _logger.info(
            f"Processing selected lines: {len(lines_to_create)} create, "
            f"{len(lines_to_link)} link, {len(lines_to_ignore)} ignore"
        )

        # Process CREATE actions
        for line in lines_to_create:
            try:
                if line.is_duplicate_group and line.billcom_ids_json:
                    _logger.info(
                        f"Creating parent-child structure for duplicate group: {line.billcom_partner_name}"
                    )
                    line._create_partner_from_duplicate_group()
                else:
                    _logger.info(
                        f"Creating single partner: {line.billcom_partner_name}"
                    )
                    line.action_apply_create()
            except Exception as e:
                _logger.error(
                    f"Error creating partner {line.billcom_partner_name}: {e}"
                )
                line.write({"state": "error", "error_message": str(e)})

        # Process LINK actions
        for line in lines_to_link:
            try:
                if line.is_duplicate_group and line.billcom_ids_json:
                    _logger.info(
                        f"Linking duplicate group to parent: {line.billcom_partner_name}"
                    )
                    line._link_duplicate_group_to_existing_partner()
                else:
                    _logger.info(f"Linking single partner: {line.billcom_partner_name}")
                    line.action_apply_link()
            except Exception as e:
                _logger.error(f"Error linking partner {line.billcom_partner_name}: {e}")
                line.write({"state": "error", "error_message": str(e)})

        # Process IGNORE actions
        for line in lines_to_ignore:
            line.write({"state": "ignored"})
            _logger.info(f"Ignored: {line.billcom_partner_name}")

        # Build summary message
        messages = []
        if lines_to_create:
            created_success = lines_to_create.filtered(lambda l: l.state == "created")
            messages.append(
                _("%d partners created (%d succeeded)")
                % (len(lines_to_create), len(created_success))
            )
        if lines_to_link:
            linked_success = lines_to_link.filtered(lambda l: l.state == "linked")
            messages.append(
                _("%d partners linked (%d succeeded)")
                % (len(lines_to_link), len(linked_success))
            )
        if lines_to_ignore:
            messages.append(_("%d partners ignored") % len(lines_to_ignore))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": " and ".join(messages),
                "type": "success",
                "sticky": False,
            },
        }

    def action_select_all(self):
        """Select all lines for bulk operations"""
        self.ensure_one()
        self.line_ids.write({"selected": True})
        return {"type": "ir.actions.act_window_close"}

    def action_deselect_all(self):
        """Deselect all lines"""
        self.ensure_one()
        self.line_ids.write({"selected": False})
        return {"type": "ir.actions.act_window_close"}

    def action_select_no_match(self):
        """Select only lines with no matches (to create in Odoo)"""
        self.ensure_one()
        # First deselect all
        self.line_ids.write({"selected": False})
        # Then select only no match lines
        no_match_lines = self.line_ids.filtered(lambda l: l.confidence_level == "none")
        no_match_lines.write({"selected": True})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Selection Updated"),
                "message": _("%d lines selected (No Match only)") % len(no_match_lines),
                "type": "info",
                "sticky": False,
            },
        }

    def action_select_high_confidence(self):
        """Select only high confidence matches (to link)"""
        self.ensure_one()
        # First deselect all
        self.line_ids.write({"selected": False})
        # Then select only high confidence lines
        high_conf_lines = self.line_ids.filtered(lambda l: l.confidence_level == "high")
        high_conf_lines.write({"selected": True})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Selection Updated"),
                "message": _("%d lines selected (High Confidence only)")
                % len(high_conf_lines),
                "type": "info",
                "sticky": False,
            },
        }

    def action_bulk_set_link(self):
        """Set selected lines to 'Link' action"""
        self.ensure_one()
        selected_lines = self.line_ids.filtered(lambda l: l.selected)

        if not selected_lines:
            raise UserError(_("No lines selected. Please select lines first."))

        # Only set to link if they have an Odoo partner
        linkable_lines = selected_lines.filtered(lambda l: l.odoo_partner_id)
        non_linkable = selected_lines - linkable_lines

        linkable_lines.write({"action": "link"})

        message_parts = []
        if linkable_lines:
            message_parts.append(_("%d lines set to 'Link'") % len(linkable_lines))
        if non_linkable:
            message_parts.append(
                _("%d lines skipped (no Odoo partner selected)") % len(non_linkable)
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Action Applied"),
                "message": ", ".join(message_parts),
                "type": "success" if not non_linkable else "warning",
                "sticky": False,
            },
        }

    def action_bulk_set_create(self):
        """Set selected lines to 'Create in Odoo' action"""
        self.ensure_one()
        selected_lines = self.line_ids.filtered(lambda l: l.selected)

        if not selected_lines:
            raise UserError(_("No lines selected. Please select lines first."))

        selected_lines.write({"action": "create"})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Action Applied"),
                "message": _("%d lines set to 'Create in Odoo'") % len(selected_lines),
                "type": "success",
                "sticky": False,
            },
        }

    def action_bulk_set_ignore(self):
        """Set selected lines to 'Ignore' action"""
        self.ensure_one()
        selected_lines = self.line_ids.filtered(lambda l: l.selected)

        if not selected_lines:
            raise UserError(_("No lines selected. Please select lines first."))

        selected_lines.write({"action": "ignore"})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk Action Applied"),
                "message": _("%d lines set to 'Ignore'") % len(selected_lines),
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
