from openerp import models, fields, api, _
from openerp.exceptions import except_orm
from openerp.osv import osv
import urllib2, httplib, urlparse, gzip, requests, json
from StringIO import StringIO
import openerp.addons.decimal_precision as dp
from datetime import date
import logging
import ast
from openerp import exceptions
from openerp.exceptions import ValidationError

#Get the logger
_logger = logging.getLogger(__name__)

class purchase_order_select_request(models.TransientModel):
        _name = 'purchase.order.select.request'

        request_id = fields.Many2one('purchase.request',string='Requerimiento')
	request_lines = fields.One2many(comodel_name='purchase.order.select.request.line',inverse_name='header_id',string='Lineas')

        @api.multi
        def confirm_line(self):
		for line in self.request_lines:
			vals = {
				'estado_linea': line.action,
				'comments_po': line.comments,
				}
			request_line = line.line_id
			request_line.write(vals)
		return None


class purchase_order_select_request_line(models.TransientModel):
        _name = 'purchase.order.select.request.line'

        header_id = fields.Many2one('purchase.order.select.request')
	line_id = fields.Many2one('purchase.request.line',string='Linea')
	qty = fields.Integer(string='Cantidad')
	action = fields.Selection(selection=[('progress','En Progreso'),('done','Finalizada')],string='Finalizada')
	comments = fields.Text(string='Comentarios')
