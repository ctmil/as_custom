# -*- coding: utf-8 -*-

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


class purchase_order_line(models.Model):
	_inherit = 'purchase.order.line'

	@api.one
	def _compute_stock_valle_soleado(self):
		if self.order_id.state in ['draft','sent']:
			product = self.product_id
			order =  self.order_id
			picking_type = order.picking_type_id
			parent_location_id = self.env['stock.location'].search([('name','=','VS'),('usage','=','view')])
			location_id = self.env['stock.location'].search([('name','=','Stock')],('location_id','=',parent_location_id.id))
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

	stock_location = fields.Integer('Stock Deposito',compute=_compute_stock)
	stock_company = fields.Integer('Stock Empresa',compute=_compute_stock)
	stock_valle_soleado = fields.Integer('Stock Valle Soleado',compute=_compute_stock_valle_soleado)


class purchase_order(models.Model):
	_inherit = 'purchase.order'


	#@api.multi
	#def action_rfq_send(self):
	#	body_msg = self.name + ' fue enviado a proveedor.'
	#	self.message_post(body=body_msg, subject='Mail enviado', subtype='mt_comment')
	#	return super(purchase_order,self).action_rfq_send()


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


	request_id = fields.Many2one('purchase.request',string='Requisicion',compute=_compute_request_id)
	request_name = fields.Char(string='Requisicion',compute=_compute_request_name)
	approver_id = fields.Many2one('res.users',string='Approver')
	nro_remito = fields.Char('Nro.Remito',compute=_compute_nro_remito)
	fecha_recepcion = fields.Char('Fecha Recepcion',compute=_compute_fecha_recepcion)
	tipo_entrega = fields.Selection(selection=[('propio','Entrega en depósito de obra'),('proveedor','Retiramos de Depósito del Proveedor'),('valle_soleado','Entrega en Valle Soleado')],\
			string='Tipo de Entrega')
	purchase_notes = fields.Text('Notas de compra')
	user_deliver_to = fields.Many2one('res.users',string='Entregar a')
	

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
				names.append(line.order_id.name + ' (' + line.order_id.state + ')')
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
                return super(purchase_request_line, self).write(vals)
	

	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")
	categ_id = fields.Many2one('product.category',string='Categoria',related="product_id.product_tmpl_id.categ_id")
	line_status = fields.Selection(selection=[('not_match_delivery','Entregas no coinciden'),('match_delivery','Entregas coinciden'),\
						('match_po','Coinciden cantidades con PO'),('not_match_po','No coinciden cantidades con PO')],\
					compute=_compute_line_status,string='Estado del requerimiento')
	stock_location = fields.Integer('Stock Deposito')
	stock_company = fields.Integer('Stock Empresa')
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
	
	brand_id = fields.Many2one('product.brand',string='Marca',related="product_id.product_tmpl_id.product_brand_id")
	categ_id = fields.Many2one('product.category',string='Categoria',related="product_id.product_tmpl_id.categ_id")
	tipo_entrega = fields.Selection(selection=[('propio','Deposito Propio'),('proveedor','Deposito Proveedor')],\
			string='Tipo de Entrega',related='picking_id.purchase_id.tipo_entrega')
	request_name = fields.Char('Requerimientos',compute=_compute_request_name)
	product_uom_qty_int = fields.Integer('Cantidad',compute=_compute_product_uom_qty_int)

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
