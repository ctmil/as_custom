# -*- coding: utf-8 -*-
##############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    "name": "AS Customizations",
    "category": "Generic Modules/Projects & Services",
    "depends": ["base","project","analytic","account","purchase","product_brand","purchase_discount","purchase_request_to_rfq","base_vat","purchase_request","product_brand","mail","web_notify","multicompany_product_taxes","purchase_requisition","mail_tracking"],
    "init_xml": [],
    "data": [
	'purchase_report.xml',
	'security/security.xml',
	'security/ir.model.access.csv',
	'report_purchasequotation.xml',
	'as_custom_views.xml',
	#'obra_view.xml',
	'wizard/wizard_view.xml'
    ],
    'demo_xml': [
    ],
    'test':[
    ],
    'installable': True,
    'active': False,
    'certificate': '',
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
