from odoo import models, fields


class BillcomAbstractModel(models.AbstractModel):
    _name = "billcom.abstract.model"
    _description = "Bill.com Abstract Model"

    billcom = fields.Char(string="Bill.com Reference", copy=False)
    billcom_id = fields.Char(string="Bill.com ID", readonly=True, copy=False)
    is_sync_to_billcom = fields.Boolean(string="Sync to Bill.com", default=True, copy=False)
    last_sync_date = fields.Datetime(copy=False)
