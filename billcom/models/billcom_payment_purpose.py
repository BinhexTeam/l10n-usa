# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class BillcomPaymentPurpose(models.Model):
    _name = 'billcom.payment.purpose'
    _description = 'BillcomPaymentPurpose'

    name = fields.Char(compute="_compute_get_name")
    code = fields.Char('Code', required=True)
    description = fields.Char('Description')
    active = fields.Boolean('Active', default=True)
    country_id = fields.Many2one(
        'res.country', string='Country', required=True,
        default=lambda self: self.env.ref('base.us', raise_if_not_found=False)
    )

    def _compute_get_name(self):
        for record in self:
            record.name = f"{record.code} - {record.description[:50] if record.description else ''}"
