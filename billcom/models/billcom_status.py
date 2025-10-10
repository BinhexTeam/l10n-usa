# Copyright 2024 Binhex
# License AGPL-3.

from odoo import fields, models


class BillcomBillStatus(models.Model):
    _name = "billcom.bill.status"
    _description = "Bill.com Bill Status"
    _order = "sequence, name"

    name = fields.Char(string="Status Name", required=True)
    code = fields.Char(string="API Code", required=True)
    sequence = fields.Integer(string="Sequence", default=10)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Status code must be unique!"),
    ]


class BillcomInvoiceStatus(models.Model):
    _name = "billcom.invoice.status"
    _description = "Bill.com Invoice Status"
    _order = "sequence, name"

    name = fields.Char(string="Status Name", required=True)
    code = fields.Char(string="API Code", required=True)
    sequence = fields.Integer(string="Sequence", default=10)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Status code must be unique!"),
    ]


class BillcomPaymentStatus(models.Model):
    _name = "billcom.payment.status"
    _description = "Bill.com Payment Status"
    _order = "sequence, name"

    name = fields.Char(string="Status Name", required=True)
    code = fields.Char(string="API Code", required=True)
    sequence = fields.Integer(string="Sequence", default=10)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Status code must be unique!"),
    ]


class BillcomBillApprovalStatus(models.Model):
    _name = "billcom.bill.approval.status"
    _description = "Bill.com Bill Approval Status"
    _order = "sequence, name"

    name = fields.Char(string="Status Name", required=True)
    code = fields.Char(string="API Code", required=True)
    sequence = fields.Integer(string="Sequence", default=10)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Status code must be unique!"),
    ]
