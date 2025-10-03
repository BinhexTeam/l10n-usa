from odoo import fields, models


class BillcomAbstractModel(models.AbstractModel):
    _name = "billcom.abstract.model"
    _description = "Bill.com Abstract Model"

    billcom = fields.Char(string="Bill.com Reference", copy=False)
    billcom_id = fields.Char(string="Bill.com ID", readonly=True, copy=False)
    is_sync_to_billcom = fields.Boolean(
        string="Sync to Bill.com", default=True, copy=False
    )
    last_sync_date = fields.Datetime(copy=False)
    billcom_sync_status = fields.Selection(
        [
            ("not_synced", "Not Synced"),
            ("synced", "Synced to Bill.com"),
            ("sync_failed", "Sync Failed"),
        ],
        string="Bill.com Sync Status",
        readonly=True,
        copy=False,
        default="not_synced",
        help="Indicates whether this record was successfully synced to Bill.com",
    )
    billcom_sync_error = fields.Text(
        string="Bill.com Sync Error",
        readonly=True,
        copy=False,
        help="Error message if sync to Bill.com failed",
    )
