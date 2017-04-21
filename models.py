# -*- coding: utf-8 -*-

from openerp import models, fields, api, _, tools
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

"""
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
"""

class purchase_order_line_summary(models.Model):
	_name = 'purchase.order.line.summary'
	_description = 'Purchase Order Line Summary'
	_auto = False

	@api.one
	def _compute_price_unit(self):
		if self.product_qty > 0:
			self.price_unit = self.price_subtotal / self.product_qty

	order_id = fields.Many2one('purchase.order',string='Orden')
	product_id = fields.Many2one('product.product',string='Producto')
	name = fields.Char('Nombre')
	product_uom = fields.Many2one('product.uom',string='Unidad de medida')
	product_qty = fields.Float('Cantidad')
	price_subtotal = fields.Float('Total Linea')
	price_unit = fields.Float('Precio Unitario',compute=_compute_price_unit)
	discount = fields.Float('Descuento')

	
	def init(self, cr):
        	"""Initialize the sql view for the event registration """
		tools.drop_view_if_exists(cr, 'purchase_order_line_summary')

	        cr.execute(""" CREATE VIEW purchase_order_line_summary AS (
	            SELECT max(id) as id,order_id,product_id,name,product_uom,sum(product_qty) as product_qty, 
			sum(price_subtotal) as price_subtotal,avg(discount) as discount 
			from purchase_order_line
			group by order_id,product_id,name,product_uom)
			""")

	


class purchase_order_line(models.Model):
	_inherit = 'purchase.order.line'

	@api.one
	def _compute_stock_valle_soleado(self):
		self.stock_valle_soleado = 0
		if self.order_id.state in ['draft','sent']:
			product = self.product_id
			order =  self.order_id
			picking_type = order.picking_type_id
			parent_location_id = self.env['stock.location'].search([('name','=','VS'),('usage','=','view')])
			if parent_location_id:
				location_id = self.env['stock.location'].search([('name','=','Stock'),('location_id','=',parent_location_id.id)])
				if picking_type:
					if picking_type.default_location_dest_id:
						quants = self.env['stock.quant'].search([('product_id','=',product.id),\
							('location_id','=',location_id.id)])
						qty_location = 0
						for quant in quants:
							qty_location += quant.qty
						self.stock_valle_soleado = qty_location
		

	@api.one
	def _compute_stock(self):
		if self.order_id.state in ['draft','sent']:
			product = self.product_id
			order =  self.order_id
			picking_type = order.picking_type_id
			if picking_type:
				if picking_type.default_location_dest_id:
					quants = self.env['stock.quant'].search([('product_id','=',product.id),\
						('location_id','=',picking_type.default_location_dest_id.id)])
					qty_location = 0
					for quant in quants:
						qty_location += quant.qty
					self.stock_location = qty_location
			locations = self.env['stock.location'].search([('company_id','=',order.company_id.id),('usage','=','internal')]).ids
			quants = self.env['stock.quant'].search([('product_id','=',product.id),('location_id','in',locations)])
			qty_company = 0
			for quant in quants:
				qty_company += quant.qty
			self.stock_company = qty_company

	@api.one
	def _compute_item_in_pr(self):
		order = self.order_id
		return_value = False
		if order.request_id:
			for line in order.request_id.line_ids:
				if line.product_id.id == self.product_id.id:
					return_value = True
					break
		self.item_in_pr = return_value

	stock_location = fields.Integer('Stock Deposito',compute=_compute_stock)
	stock_company = fields.Integer('Stock Empresa',compute=_compute_stock)
	stock_valle_soleado = fields.Integer('Stock Valle Soleado',compute=_compute_stock_valle_soleado)
	item_in_pr = fields.Boolean('En PR',compute=_compute_item_in_pr)
	stock_location = fields.Integer('Stock Deposito',compute=_compute_stock)
	stock_company = fields.Integer('Stock Empresa',compute=_compute_stock)
	stock_valle_soleado = fields.Integer('Stock Valle Soleado',compute=_compute_stock_valle_soleado)
	item_in_pr = fields.Boolean('En PR',compute=_compute_item_in_pr)

class purchase_order(models.Model):
	_inherit = 'purchase.order'


	#@api.multi
	#def action_rfq_send(self):
	#	body_msg = self.name + ' fue enviado a proveedor.'
	#	self.message_post(body=body_msg, subject='Mail enviado', subtype='mt_comment')
	#	return super(purchase_order,self).action_rfq_send()

	#@api.constrains('account_analytic_id','order_line')
	#def _check_account_analytic_id(self):
	#	for order in self:
	#		for record in order.order_line:
	#			if record.account_analytic_id and not order.account_analytic_id:
	#				raise exceptions.except_orm('Es necesario ingresar la cuenta analítica de la orden')	
	#		for record in order.order_line:
	#			if record.account_analytic_id and not order.account_analytic_id.parent_id:
	#				if record.account_analytic_id.id != order.account_analytic_id.id:
	#					raise exceptions.Warning('Cta analitica para el producto ' + record.product_id.name + '\nno se corresponde con cta analítica de la orden')	
	#			if record.account_analytic_id and order.account_analytic_id:
	#				account_analytic = record.account_analytic_id
	#				while account_analytic.parent_id:
	#					account_analytic = account_analytic.parent_id
	#				if account_analytic.id != order_id.account_analytic_id.id:
	#					raise exceptions.except_orm('Cta analitica para el producto ' + record.product_id.name + '\nno se corresponde con cta analítica de la orden')	


	@api.multi
	def complete_request(self):
		if len(self) > 1:
                         raise exceptions.ValidationError('Debe seleccionar solo una PO')
		vals_header = {
			'request_id': self.request_id.id,
			}
		header_id = self.env['purchase.order.select.request'].create(vals_header)
		request = self.request_id
		for line in request.line_ids:
			vals_line = {
				'header_id': header_id.id,
				'line_id': line.id,
				'qty': line.product_qty,
				'action': 'progress'
				}
			rq_line_id = self.env['purchase.order.select.request.line'].create(vals_line)
		return {'type': 'ir.actions.act_window',
                        'name': 'Completar requisicion',
                        'res_model': 'purchase.order.select.request',
                        'res_id': header_id.id,
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'nodestroy': True,
                        }

			
			

        @api.model
        def create(self, vals):
		company_id = vals.get('company_id',None)
		if company_id:
			company = self.env['res.company'].browse(company_id)
			if company.purchase_notes:
				vals['notes'] = company.purchase_notes
			if company.user_deliver_to:
				vals['user_deliver_to'] = company.user_deliver_to.id
			else:
				vals['user_deliver_to'] = self.env.context['uid']
                return super(purchase_order, self).create(vals)


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
				for request_line in line.purchase_request_lines:
					if request_line.request_id.name not in request_names:
						request_names.append(request_line.request_id.name)
		if request_names:
			return_value = ','.join(request_names)
		self.request_name = return_value

	@api.one
	def _compute_request_id(self):
		return_value = None
		for line in self.order_line:
			if line.purchase_request_lines:
				for request_line in line.purchase_request_lines:
					if request_line.request_id:
						return_value = request_line.request_id.id
		self.request_id = return_value

	@api.multi
	def button_approve(self):
		vals = {
			'approver_id': self.env.context['uid']
			}
		self.write(vals)
		return super(purchase_order, self).button_approve()
		 

	@api.multi
	def button_confirm(self):
		emails = []
		if self.order_line:
			emails = []
			users = []


	@api.multi
	def complete_request(self):
		if len(self) > 1:
                         raise exceptions.ValidationError('Debe seleccionar solo una PO')
		vals_header = {
			'request_id': self.request_id.id,
			}
		header_id = self.env['purchase.order.select.request'].create(vals_header)
		request = self.request_id
		for line in request.line_ids:
			vals_line = {
				'header_id': header_id.id,
				'line_id': line.id,
				'qty': line.product_qty,
				'action': 'progress'
				}
			rq_line_id = self.env['purchase.order.select.request.line'].create(vals_line)
		return {'type': 'ir.actions.act_window',
                        'name': 'Completar requisicion',
                        'res_model': 'purchase.order.select.request',
                        'res_id': header_id.id,
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'nodestroy': True,
                        }

			
			

        @api.model
        def create(self, vals):
		company_id = vals.get('company_id',None)
		if company_id:
			company = self.env['res.company'].browse(company_id)
			if company.purchase_notes:
				vals['notes'] = company.purchase_notes
			if company.user_deliver_to:
				vals['user_deliver_to'] = company.user_deliver_to.id
			else:
				vals['user_deliver_to'] = self.env.context['uid']
		if 'order_line' in vals.keys():
			order_line = vals['order_line']
			for line in order_line:
				line = line[2]
				if 'account_analytic_id' in line.keys() and 'product_id' in line.keys() and 'account_analytic_id' in vals.keys():
					account_analytic_id = self.env['account.analytic.account'].browse(line['account_analytic_id'])
					product_id = self.env['product.product'].browse(line['product_id'])
					if account_analytic_id and not ('account_analytic_id' in vals.keys()):
						raise ValidationError('Es necesario ingresar la cuenta analitica de la orden')	
					order_account_analytic_id = self.env['account.analytic.account'].browse(vals['account_analytic_id'])
					if not account_analytic_id.parent_id:
						if account_analytic_id.id != order_account_analytic_id.id:
							raise ValidationError('Cta analitica para el producto ' + product_id.name + '\nno se corresponde con cta analitica de la orden')	
					if order_account_analytic_id:
						account_analytic = account_analytic_id
						while account_analytic.parent_id:
							account_analytic = account_analytic.parent_id
						if account_analytic.id != order_account_analytic_id.id:
							raise ValidationError('Cta analitica para el producto ' + product_id.name + '\nno se corresponde con cta analitica de la orden')	
		

                return super(purchase_order, self).create(vals)

	@api.multi
	def write(self,vals):
		if 'order_line' in vals.keys():
			order_line = vals['order_line']
			for line in order_line:
				line_id = line[1]
				line_obj = self.env['purchase.order.line'].browse(line_id)
				line = line[2]
				if 'account_analytic_id' in line.keys():
					account_analytic_id = self.env['account.analytic.account'].browse(line['account_analytic_id'])
					product_id = self.env['product.product'].browse(line['product_id'])
					if account_analytic_id and not (self.account_analytic_id):
						raise ValidationError('Es necesario ingresar la cuenta analitica de la orden')	
					order_account_analytic_id = self.account_analytic_id
					if not account_analytic_id.parent_id:
						if account_analytic_id.id != order_account_analytic_id.id:
							raise ValidationError('Cta analitica para el producto ' + product_id.name + '\nno se corresponde con cta analitica de la orden')	
					if order_account_analytic_id:
						account_analytic = account_analytic_id
						while account_analytic.parent_id:
							account_analytic = account_analytic.parent_id
						if account_analytic.id != order_account_analytic_id.id:
							raise ValidationError('Cta analitica para el producto ' + product_id.name + '\nno se corresponde con cta analitica de la orden')	
                return super(purchase_order, self).create(vals)
		


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
				for request_line in line.purchase_request_lines:
					if request_line.request_id.name not in request_names:
						request_names.append(request_line.request_id.name)
		if request_names:
			return_value = ','.join(request_names)
		self.request_name = return_value

	@api.one
	def _compute_request_id(self):
		return_value = None
		for line in self.order_line:
			if line.purchase_request_lines:
				for request_line in line.purchase_request_lines:
					if request_line.request_id:
						return_value = request_line.request_id.id
		self.request_id = return_value

	@api.multi
	def button_approve(self):
		vals = {
			'approver_id': self.env.context['uid']
			}
		self.write(vals)
		return super(purchase_order, self).button_approve()
		 

	@api.multi
	def button_confirm(self):
		emails = []
		if self.order_line:
			emails = []
			users = []
			for line in self.order_line:
				if line.purchase_request_lines:
					rq_lines = line.purchase_request_lines
					for rq_line in rq_lines:
						user = self.env['res.users'].browse(rq_line.create_uid.id)
						if user.notify_email != 'none':
							emails.append([user.email,rq_line.request_id.name,user.name])
							users.append(user)
			if emails:
				index = 0
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
					users[index].notify_info(message=body,title=subject)
                emails = []
                users = self.env['res.users'].search([])
                for user in users:
			if user.has_group('purchase.group_purchase_manager') and user.notify_email != 'none':
	                        emails.append([user.email,self.name,user.name])
				user.notify_info(message='La orden '+self.name+' fue confirmada',title='Orden '+self.name+' confirmada')
			
                if emails:
                        for email in emails:
                                subject = 'La orden de compra ' + email[1] + ' fue confirmada'
                                body = 'Estimado/a ' + email[2] + '\n'
                                body += 'La orden de compra ' + email[1] + 'fue confirmada'
                                body_html = '<p>La orden de compra ' + email[1] + ' fue confirmada''</p>'
                                email_to = email[0]
                                vals = {
                                        'body': body,
                                        'body_html': body_html,
                                        'subject': subject,
                                        'email_to': email_to
                                        }
                                msg = self.env['mail.mail'].create(vals)
		return super(purchase_order, self).button_confirm()

	@api.one
	def _compute_nro_remito(self):
		if self.picking_ids:
			remitos = []
			for picking_id in self.picking_ids:
				if picking_id.nro_remito:
					remitos.append(picking_id.nro_remito)
			if remitos:
				self.nro_remito = ','.join(remitos)

	@api.one
	def _compute_fecha_recepcion(self):
		if self.picking_ids:
			dates = []
			for picking_id in self.picking_ids:
				if picking_id.fecha_entrega and picking_id.state == 'done':
					dates.append(str(picking_id.fecha_entrega))
			if dates:
				self.fecha_recepcion = ','.join(dates)

	@api.one
	def _compute_tender_id(self):
		if self.origin:
			tender_ids = self.env['purchase.requisition'].search([('name','=',self.origin)])
			if tender_ids:
				self.tender_id = tender_ids[0].id	


	request_id = fields.Many2one('purchase.request',string='Requisicion',compute=_compute_request_id)
	request_name = fields.Char(string='Requisicion',compute=_compute_request_name)
	approver_id = fields.Many2one('res.users',string='Approver')
	nro_remito = fields.Char('Nro.Remito',compute=_compute_nro_remito)
	fecha_recepcion = fields.Char('Fecha Recepcion',compute=_compute_fecha_recepcion)
	tipo_entrega = fields.Selection(selection=[('propio','Entrega en depósito de obra'),('proveedor','Retiramos de Depósito del Proveedor'),('valle_soleado','Entrega en Valle Soleado')],\
			string='Tipo de Entrega')
	purchase_notes = fields.Text('Notas de compra')
	user_deliver_to = fields.Many2one('res.users',string='Entregar a')
	tender_id = fields.Many2one('purchase.requisition',string='Licitacion',compute=_compute_tender_id)
	summary_ids = fields.One2many(comodel_name='purchase.order.line.summary',inverse_name='order_id')
	account_analytic_id = fields.Many2one('account.analytic.account',string='Cuenta analítica',domain=[('parent_id','=',False)])	

class res_company(models.Model):
	_inherit = 'res.company'

	purchase_notes = fields.Text(string='Purchase Notes')
	user_deliver_to = fields.Many2one('res.users',string='Entregar a')

class purchase_request_line(models.Model):
	_inherit = 'purchase.request.line'



	@api.one
	def _compute_po_status(self):
		names = []
		for line in self.purchase_lines:
			if line.order_id:
				estados = {
					'draft':'borrador',
					'sent': 'enviado',
					'purchase': 'en proceso',
					'to approve': 'para aprobar',
					'done': 'finalizada',
					'cancel': 'cancelada'
					}
				names.append(line.order_id.name + ' (' + estados[line.order_id.state] + ')')
		if names:
			self.po_status = ','.join(names)

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
	
	@api.model
	def create(self, vals):
		if 'product_id' in vals.keys():
			product = self.env['product.product'].browse(vals['product_id'])
			request =  self.env['purchase.request'].browse(vals['request_id'])
			picking_type = request.picking_type_id
			if picking_type:
				if picking_type.default_location_dest_id:
					quants = self.env['stock.quant'].search([('product_id','=',product.id),\
						('location_id','=',picking_type.default_location_dest_id.id)])
					qty_location = 0
					for quant in quants:
						qty_location += quant.qty
					vals['stock_location'] = qty_location
			locations = self.env['stock.location'].search([('company_id','=',request.company_id.id),('usage','=','internal')]).ids
			quants = self.env['stock.quant'].search([('product_id','=',product.id),('location_id','in',locations)])
			qty_company = 0
			for quant in quants:
				qty_company += quant.qty
			vals['stock_company'] = qty_company
                        parent_location_id = self.env['stock.location'].search([('name','=','VS'),('usage','=','view')])
                        location_id = self.env['stock.location'].search([('name','=','Stock'),('location_id','=',parent_location_id.id)])
                        if picking_type:
                                if picking_type.default_location_dest_id:
                                        quants = self.env['stock.quant'].search([('product_id','=',product.id),\
                                                ('location_id','=',location_id.id)])
                                        qty_location = 0
                                        for quant in quants:
                                                qty_location += quant.qty
                                        vals['stock_valle_soleado'] = qty_location

        	return super(purchase_request_line, self).create(vals)
	
	@api.multi
	def write(self, vals):
		if 'product_id' in vals.keys():
			product = self.env['product.product'].browse(vals['product_id'])
			request =  self.request_id
			picking_type = request.picking_type_id
			if picking_type:
				if picking_type.default_location_dest_id:
					quants = self.env['stock.quant'].search([('product_id','=',product.id),\
						('location_id','=',picking_type.default_location_dest_id.id)])
					qty_location = 0
					for quant in quants:
						qty_location += quant.qty
					vals['stock_location'] = qty_location
			locations = self.env['stock.location'].search([('company_id','=',request.company_id.id),('usage','=','internal')]).ids
			quants = self.env['stock.quant'].search([('product_id','=',product.id),('location_id','in',locations)])
			qty_company = 0
			for quant in quants:
				qty_company += quant.qty
			vals['stock_company'] = qty_company
                        parent_location_id = self.env['stock.location'].search([('name','=','VS'),('usage','=','view')])
                        location_id = self.env['stock.location'].search([('name','=','Stock'),('location_id','=',parent_location_id.id)])
                        if picking_type:
                                if picking_type.default_location_dest_id:
                                        quants = self.env['stock.quant'].search([('product_id','=',product.id),\
                                                ('location_id','=',location_id.id)])
                                        qty_location = 0
                                        for quant in quants:
                                                qty_location += quant.qty
                                        vals['stock_valle_soleado'] = qty_location
                return super(purchase_request_line, self).write(vals)

			#(0, 'N/A'),
			#(1,'PO Cancelada'),
			#(2,'PO Borrador'),
			#(3,'PO Enviada'),
			#(4,'PO esperando aprobación'),
			#(5,'PO Esperando materiales del proveedor'),
			#(6,'PO Finalizada'),
			#(7,'Licitación cancelada'),
			#(8,'Licitación en borrador'),
			#(9,'Licitación en proceso. No se generaron POs'),
			#(10,'Licitación en proceso. Se pidio presupuestos a proveedores'),
			#(11,'Licitación en proceso. Se espera aprobacion de las POs'),
			#(12,'Licitación en proceso. Se esperan los materiales del proveedor'),
			#(13,'Licitación finalizada')

	@api.multi
	def _purchase_status_search(self, operator, operand):
		list_ids  = []
		if operand == '0':
			rq_ids = self.env['purchase.request'].search([('state','=','approved')])
			for rq in rq_ids:
				rql_ids = rq.line_ids
				for rql in rql_ids:
					if not rql.requisition_lines and not rql.purchase_lines:
						list_ids.append(rql.id)
		if operand != '0':
			if operand in ['1','2','3','4','5','6']:
				rql_ids = self.search([('purchase_lines','!=',None)])
				for rql in rql_ids:
					if rql.requisition_lines:
						continue
					value = 0
					for purchase_line in rql.purchase_lines:
						if purchase_line.state == 'cancel':
							if value < 1:
								value = 1
						if purchase_line.state == 'draft':
							if value < 2:
								value = 2
						if purchase_line.state == 'sent':
							if value < 3:
								value = 3
						if purchase_line.state == 'to approve':
							if value < 4:
								value = 4
						if purchase_line.state == 'purchase':
							if value < 5:
								value = 5
						if purchase_line.state == 'done':
							if value < 6:
								value = 6
						
					if str(value) == operand:
						list_ids.append(rql.id)
						"""
						if operand == '1':
							if purchase_line.state == 'cancel':
								list_ids.append(rql.id)	
						if operand == '2':
							if purchase_line.state == 'draft':
								list_ids.append(rql.id)	
						if operand == '3':
							if purchase_line.state == 'sent':
								list_ids.append(rql.id)	
						if operand == '4':
							if purchase_line.state == 'to approve':
								list_ids.append(rql.id)	
						if operand == '5':
							if purchase_line.state == 'purchase':
								list_ids.append(rql.id)	
						if operand == '6':
							if purchase_line.state == 'done':
								list_ids.append(rql.id)	
						"""
			else:
				rql_ids = self.search([('requisition_lines','!=',None)])
				for line in rql_ids:
					for requisition in line.requisition_lines:
						if operand == '7' and requisition.requisition_id.state == 'cancel':
							list_ids.append(line.id)	
						if operand == '8' and requisition.requisition_id.state == 'draft':
							list_ids.append(line.id)	
						if operand in ['9','10','11','12','13'] and requisition.requisition_id.state in ['in_progress','open','done']:
							if not requisition.requisition_id.purchase_ids and operand == '9':
								list_ids.append(line.id)	
							else:
								for purchase in requisition.requisition_id.purchase_ids:
									if purchase.state == 'cancel' and operand == '9':
										list_ids.append(line.id)	
									if purchase.state == 'draft' and operand == '9':
										list_ids.append(line.id)	
									if purchase.state == 'sent' and operand == '10':
										list_ids.append(line.id)	
									if purchase.state == 'to approve' and operand == '11':
										list_ids.append(line.id)	
									if purchase.state == 'purchase' and operand == '12':
										list_ids.append(line.id)	
									if purchase.state == 'done' and operand == '13':
										list_ids.append(line.id)	
							

        	return [('id', 'in', list_ids)]

	@api.model
	def _po_status_search(self, operator, operand):
		return self._purchase_status_search( operator, operand)

	
	@api.depends('purchase_lines','requisition_lines')
	def _compute_compras_status(self):
		for rec in self:
			return_value = ''
			#if self.id == 169:
			#	import pdb;pdb.set_trace()
			index_value = 0 
			if rec.purchase_lines:
				value = 0
				for line in rec.purchase_lines:
					if line.order_id.state == 'cancel':
						if value < 1:
							value = 1 
					if line.order_id.state == 'draft':
						if value < 2:
							value = 2
					if line.order_id.state == 'sent':
						if value < 3:
							value = 3
					if line.order_id.state == 'to approve':
						if value < 4:
							value = 4 
					if line.order_id.state == 'purchase':
						if value < 5:
							value = 5
					if line.order_id.state == 'done':
						if value < 6:
							value = 6
				mapping_state = {
					0: 'N/A',
					1: 'cancelada',
					2: 'borrador',
					3: 'enviada a proveedor',
					4: 'esperando aprobación',
					5: 'esperando materiales del proveedor',
					6: 'finalizada',
					}	
				index_value = value			
				return_value = 'Se generaron POs. Su estado es ' + mapping_state[value]
			else:
				if rec.requisition_lines:
					value = 0
					for line in rec.requisition_lines:
						if line.requisition_id.state == 'cancel':
							if value < 1:
								value = 1
						if line.requisition_id.state == 'draft':
							if value < 2:
								value = 2
						if line.requisition_id.state in ['in_progress','open','done']:
							if not line.requisition_id.purchase_ids:
								if value < 3:
									value = 3
							else:
								for purchase in line.requisition_id.purchase_ids:
									if purchase.state == 'cancel':
										if value < 4:
											value = 4 
									if purchase.state == 'draft':
										if value < 5:
											value = 5
									if purchase.state == 'sent':
										if value < 6:
											value = 6
									if purchase.state == 'to approve':
										if value < 7:
											value = 7 
									if purchase.state == 'purchase':
										if value < 8:
											value = 8
									if purchase.state == 'done':
										if value < 9:
											value = 9
							
					
					mapping_state = {
						0: 'N/A',
						1: 'cancelada',
						2: 'borrador',
						3: 'en proceso por Compras. Aun no se generaron POs',
						4: 'en proceso por Compras. Se generaron POs y se cancelaron',
						5: 'en proceso por Compras. Se generaron POs en estado borrador',
						6: 'en proceso por Compras. Se generaron POs y se enviaron a los proveedores',
						7: 'en proceso por Compras. Se generaron POs y se espera su aprobación',
						8: 'en proceso por Compras. Se generaron POs y se esperan los materiales del proveedor',
						9: 'en proceso por Compras. Se generaron POs y se completaron',
						}		
					index_value = 6 + value		
					return_value = 'Se generó licitación(es) y su estado es ' + mapping_state[value]
				else:	
					return_value = 'Please check with admin'	
			rec.compras_status_index = index_value 
			rec.compras_status = return_value 


	status_index = [
			(0, 'N/A'),
			(1,'PO Cancelada'),
			(2,'PO Borrador'),
			(3,'PO Enviada'),
			(4,'PO esperando aprobación'),
			(5,'PO Esperando materiales del proveedor'),
			(6,'PO Finalizada'),
			(7,'Licitación cancelada'),
			(8,'Licitación en borrador'),
			(9,'Licitación en proceso. No se generaron POs'),
			(10,'Licitación en proceso. Se pidio presupuestos a proveedores'),
			(11,'Licitación en proceso. Se espera aprobacion de las POs'),
			(12,'Licitación en proceso. Se esperan los materiales del proveedor'),
			(13,'Licitación finalizada'),
			(14,'Check admin')
			]

	compras_status_index = fields.Selection(selection=status_index,compute=_compute_compras_status,search=_po_status_search)
	compras_status = fields.Char('Estado Gestion Compras',compute=_compute_compras_status)
	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")
	categ_id = fields.Many2one('product.category',string='Categoria',related="product_id.product_tmpl_id.categ_id")
	line_status = fields.Selection(selection=[('not_match_delivery','Entregas no coinciden'),('match_delivery','Entregas coinciden'),\
						('match_po','Coinciden cantidades con PO'),('not_match_po','No coinciden cantidades con PO')],\
					compute=_compute_line_status,string='Estado del requerimiento')
	stock_location = fields.Integer('Stock Deposito')
	stock_company = fields.Integer('Stock Empresa')
	stock_valle_soleado = fields.Integer('Stock Valle Soleado')
	po_status = fields.Char('Estado PO',compute=_compute_po_status)
	estado_linea = fields.Selection(selection=[('progress','En progreso'),('done','Finalizado')],\
					string='Status del requerimiento')
	comments_po = fields.Text(string='Comentarios PO')

class stock_move(models.Model):
	_inherit = 'stock.move'

	@api.one
	def _compute_request_name(self):
		return_value = ''
		if self.origin:
			purchase_id = self.env['purchase.order'].search([('name','=',self.origin)])
			if purchase_id.request_name:
				return_value = purchase_id.request_name
		self.request_name = return_value

	@api.one
	def _compute_product_uom_qty_int(self):
		self.product_uom_qty_int = int(self.product_uom_qty)
	
	@api.one
	def _compute_po_id(self):
		po_id = self.env['purchase.order'].search([('name','=',self.origin)])
		if po_id:
			self.po_id = po_id.id
	
	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")
	categ_id = fields.Many2one('product.category',string='Categoria',related="product_id.product_tmpl_id.categ_id")
	tipo_entrega = fields.Selection(selection=[('propio','Deposito Propio'),('proveedor','Deposito Proveedor')],\
			string='Tipo de Entrega',related='picking_id.purchase_id.tipo_entrega')
	request_name = fields.Char('Requerimientos',compute=_compute_request_name)
	product_uom_qty_int = fields.Integer('Cantidad',compute=_compute_product_uom_qty_int)
	po_id = fields.Many2one('purchase.order',string='Orden de Compra',compute='_compute_po_id')

class purchase_order_line(models.Model):
	_inherit = 'purchase.order.line'

	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")
	categ_id = fields.Many2one('product.category',string='Categoria',related="product_id.product_tmpl_id.categ_id")
	
class stock_pack_operation(models.Model):
	_inherit = 'stock.pack.operation'

	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")
	categ_id = fields.Many2one('product.category',string='Categoria',related="product_id.product_tmpl_id.categ_id")

	@api.one
	def complete_qty_done(self):
		if self.product_qty:
			self.qty_done = self.product_qty

class stock_quant(models.Model):
	_inherit = 'stock.quant'

	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")
	categ_id = fields.Many2one('product.category',string='Categoria',related="product_id.product_tmpl_id.categ_id")

class purchase_request(models.Model):
	_inherit = 'purchase.request'


	@api.multi
	def button_approved(self):
		res = super(purchase_request, self).button_approved()
		emails = []
		users = self.env['res.users'].search([])
		for user in users:
			if user.has_group('purchase.group_purchase_user') and user.notify_email != 'none':
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

	@api.one
	def _compute_product_uom_qty_int(self):
		self.product_uom_qty_int = int(self.product_uom_qty)

	nro_remito = fields.Char('Nro.Remito')
	fecha_entrega = fields.Date('Fecha de Entrega')	
	product_uom_qty_int = fields.Integer('Cantidad',compute=_compute_product_uom_qty_int)

class res_partner(models.Model):
	_inherit = 'res.partner'

	@api.one
	def _compute_cuit(self):
		if self.vat and len(self.vat) > 2:
			self.cuit = self.vat[2:]
	
	cuit = fields.Char('CUIT',compute=_compute_cuit)
