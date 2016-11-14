from openerp import models, fields, api, _
from openerp.osv import osv
from openerp.exceptions import except_orm, ValidationError
from StringIO import StringIO
import urllib2, httplib, urlparse, gzip, requests, json
import openerp.addons.decimal_precision as dp
import logging
import datetime
from openerp.fields import Date as newdate

#Get the logger
_logger = logging.getLogger(__name__)

class product_product(models.Model):
	_inherit = 'product.product'

        @api.multi
        def name_get(self):
                res = super(product_product,self).name_get()
                data = []
                for product in self:
                        if product.product_tmpl_id.product_brand_id:
                                display_value = '[' + product.product_tmpl_id.product_brand_id.name.strip() + '] ' + product.name
                        else:
                                display_value = product.name
                        data.append((product.id,display_value))
                return data


class purchase_order(models.Model):
	_inherit = 'purchase.order'

	@api.multi
	def print_quotation(self):
		self.write({'state': "sent"})
		return self.env['report'].get_action(self, 'as_custom.report_purchasequotation')


	@api.one
	def _compute_request_name(self):
		return_value = ''
		request_names = []
		for line in self.order_line:
			if line.purchase_request_lines:
				if line.purchase_request_lines.request_id.name not in request_names:
					request_names.append(line.purchase_request_lines.request_id.name)
		if request_names:
			return_value = ','.join(request_names)
		self.request_name = return_value

	@api.multi
	def button_approve(self):
		vals = {
			'approver_id': self.env.context['uid']
			}
		self.write(vals)
		return super(purchase_order, self).button_approve()

	@api.multi
	def button_confirm(self):
		res = super(purchase_order, self).button_confirm()
		emails = []
		if self.order_line:
			emails = []
			for line in self.order_line:
				if line.purchase_request_lines:
					rq_lines = line.purchase_request_lines
					for rq_line in rq_lines:
						user = self.env['res.users'].browse(rq_line.create_uid.id)
						emails.append([user.email,rq_line.request_id.name,user.name])
			if emails:
				for email in emails:
	                                subject = 'Requerimiento ' + email[1] + ' fue aprobado'
	                                body = 'Estimado/a ' + email[2] + '\n'
        	                        body += 'El requerimiento ' + email[1] + 'fue aprobado'
					body_html = '<p>Requerimiento ' + email[1] + ' fue aprobado''</p>'
	                                email_to = email[0]
        	                        vals = {
                	                        'body': body,
                        	                'body_html': body_html,
                                	        'subject': subject,
                                        	'email_to': email_to
	                                        }
        	                        msg = self.env['mail.mail'].create(vals)

		return res

	@api.one
	def _compute_nro_remito(self):
		if self.picking_ids:
			remitos = []
			for picking_id in self.picking_ids:
				if picking_id.nro_remito:
					remitos.append(picking_id.nro_remito)
			if remitos:
				self.nro_remito = ','.join(remitos)



	request_name = fields.Char(string='Requisicion',compute=_compute_request_name)
	approver_id = fields.Many2one('res.users',string='Approver')
	nro_remito = fields.Char('Nro.Remito',compute=_compute_nro_remito)

class res_company(models.Model):
	_inherit = 'res.company'

	purchase_notes = fields.Text(string='Purchase Notes')
	user_deliver_to = fields.Many2one('res.users',string='Entregar a')

class purchase_request_line(models.Model):
	_inherit = 'purchase.request.line'

	@api.one
	def _compute_line_status(self):
		for line in self.purchase_lines:
			if (line.qty_received > 0) and line.qty_received != self.product_qty:
				self.line_status = 'not_match_delivery'
			else:
				if (line.qty_received > 0) and line.qty_received == self.product_qty:
					self.line_status = 'match_delivery'
				else:
					if line.product_qty == self.product_qty:
						self.line_status = 'match_po'
					else:
						self.line_status = 'not_match_po'

	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")
	line_status = fields.Selection(selection=[('not_match_delivery','Entregas no coinciden'),('match_delivery','Entregas coinciden'),\
						('match_po','Coinciden cantidades con PO'),('not_match_po','No coinciden cantidades con PO')],\
					compute=_compute_line_status,string='Estado del requerimiento')

class stock_move(models.Model):
	_inherit = 'stock.move'

	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")

class purchase_order_line(models.Model):
	_inherit = 'purchase.order.line'

	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")
	
class stock_pack_operation(models.Model):
	_inherit = 'stock.pack.operation'

	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")

	@api.one
	def complete_qty_done(self):
		if self.product_qty:
			self.qty_done = self.product_qty

class stock_quant(models.Model):
	_inherit = 'stock.quant'

	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")

class purchase_request(models.Model):
	_inherit = 'purchase.request'


	@api.multi
	def button_approved(self):
		res = super(purchase_request, self).button_approved()
		emails = []
		users = self.env['res.users'].search([])
		for user in users:
			if user.has_group('purchase.group_purchase_user'):
				emails.append([user.email,self.name,user.name])
		if emails:
			for email in emails:
                                subject = 'Requerimiento ' + email[1] + ' fue aprobado'
                                body = 'Estimado/a ' + email[2] + '\n'
       	                        body += 'El requerimiento ' + email[1] + 'fue aprobado'
				body_html = '<p>Requerimiento ' + email[1] + ' fue aprobado''</p>'
                                email_to = email[0]
       	                        vals = {
               	                        'body': body,
                       	                'body_html': body_html,
                               	        'subject': subject,
                                       	'email_to': email_to
                                        }
       	                        msg = self.env['mail.mail'].create(vals)
		return res

class stock_picking(models.Model):
	_inherit = 'stock.picking'

	nro_remito = fields.Char('Nro.Remito')
