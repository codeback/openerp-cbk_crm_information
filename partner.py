# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2013 Codeback Software S.L. (www.codeback.es). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

"""añadimos información comercial relevante"""

import pdb
from osv import fields, osv

class res_partner(osv.osv):
	"""añadimos los nuevos campos"""

	def _crm_information(self, cr, uid, ids, field_names, arg, context=None):

		# Función para rellenar los campos calculados en el módulo
		if context is None:
			context = {}	   
				
		vals = {}
		products = {}

		# pdb.set_trace()

		# Cogemos el partner		
		partners = self.pool.get('res.partner').browse(cr,uid,ids)
		
		# Cogemos las sales order del partner		
		for partner in partners:
			vals[partner.id] = {}
			partner_orders = self._get_sale_orders(cr,uid,partner.name)		
			# Asignamos el nombre de la última compra (se accede con [-1]): campo "latest_sale_order"					
			vals[partner.id]['latest_sale_order'] = partner_orders[-1].name
			vals[partner.id]['latest_sale_date'] = partner_orders[-1].date_order

			# # Calculamos cual es el producto más vendido al cliente
			# pdb.set_trace()
			# for partner_order in partner_orders:
			# 	order_lines = partner_order.order_line
			# 	products.setdefault(order_lines[0].product_id, {})
			# 	for order_line in order_lines:
			# 		# products[order_line.product_id] = {}
			# 		products[order_line.product_id] = products.get(order_line.product_id, 0) + 1
			# 		# Sale este error: TypeError: unsupported operand type(s) for +: 'dict' and 'int'

			# # v=list(products.values())
            # # k=list(products.keys())
            # # product = k[v.index(max(v))]
		
		return vals

	def _get_objects(self, cr, uid, name, args=[], ids=None):   
		"""
		Obtiene los objetos del modelo 
		"""                  
		obj = self.pool.get(name)
		if not ids:
		    ids = obj.search(cr, uid, args)
		return obj.browse(cr, uid, ids)

	def _get_sale_orders(self, cr, uid, partner_name):
		"""
		Obtiene los pedido de un cliente determinado
		"""
		sale_orders = self._get_objects(cr, uid, 'sale.order')     
		return [so for so in sale_orders if so.partner_id.name==partner_name]

	_name = "res.partner"
	_inherit = "res.partner"
	_columns = {
		'latest_sale_order' : fields.function(_crm_information, type='char', string='Latest sale', multi='crm_information'),
		'latest_sale_date' : fields.function(_crm_information, type='date', string='Latest sale date', multi='crm_information'),
	}

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

