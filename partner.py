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
from datetime import datetime, timedelta


class res_partner(osv.osv):
    """añadimos los nuevos campos"""

    def _crm_information(self, cr, uid, ids, field_names, arg, context=None):

        # Función para rellenar los campos calculados en el módulo
        if context is None:
            context = {}       
                
        vals = {}

        # pdb.set_trace()

        # Cogemos el partner        
        partners = self.browse(cr,uid,ids)
        
        # Cogemos las sales order del partner       
        for partner in partners:
            vals[partner.id] = {}
            partner_orders = self._get_sale_orders(cr, uid, partner.name)       
            # Asignamos el nombre de la última compra (se accede con [-1]): campo "latest_sale_order"           
            if partner_orders:  

                # Obtenemos los tres ultimos pedidos y sus fechas
                latest_orders = self.pool.get('crm.last.orders')
                vals[partner.id]['crm_last_orders_ids'] = latest_orders.calculate_last_orders(cr, uid, partner_orders)

                # Calculamos el número de ventas en los 6 últimos meses y la cantidad en € asociada a las mismas
                sale_orders = self._get_orders_in_window(cr, uid, partner.name)
                vals[partner.id]['sales_six_months'] = len(sale_orders) 

                sold_amount = 0
                for sale_order in sale_orders:
                    sold_amount = sold_amount + sale_order.amount_total
                vals[partner.id]['sales_amount_six_months'] = sold_amount       

                # Calculamos los productos más vendidos y su cantidad
                most_sold_model = self.pool.get('crm.product.sold')
                vals[partner.id]['crm_sold_prod_ids'] = most_sold_model.calculate_sold_products(cr, uid, partner_orders, limit=3)   

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

    def _get_orders_in_window(self, cr, uid, partner_name):
        """
        Obtiene todos los pedidos que esten dentro de 6 últimos meses
        """
        calculation_date = datetime.today() - timedelta(days=180)
        str_calculation_date = datetime.strftime(calculation_date, "%Y-%m-%d") + " 00:00:00"

        args = [('create_date', '>=', str_calculation_date)]
        sale_orders = self._get_objects(cr, uid, 'sale.order', args)       

        return [so for so in sale_orders if so.partner_id.name==partner_name]

    def _search_products(self, cr, uid, obj, field_name, criterion, context=None):
        
        ids = []
        comparision = criterion[0][1]
        product = criterion[0][2]
        args = [("name", comparision, product)]
        prod_ids = self.pool.get('product.product').search(cr,uid,args)

        if prod_ids:
            partner_ids = self.search(cr,uid,[])
            partners = self.browse(cr,uid,partner_ids)
            
            # Cogemos las sales order del partner               
            for partner in partners:

                partner_orders = self._get_sale_orders(cr, uid, partner.name)

                most_sold_model = self.pool.get('crm.product.sold')
                most_sold_ids = most_sold_model.calculate_sold_products(cr, uid, partner_orders)
                most_sold_objs = most_sold_model.browse(cr, uid, most_sold_ids)
                for obj in most_sold_objs:
                    if obj.product_id.id == prod_ids[0]:
                        ids.append(partner.id)
                        break

        return [("id", "in", ids)]

    _name = "res.partner"
    _inherit = "res.partner"
    _columns = {        
        'crm_partner_tracking_ids' : fields.one2many('crm.partner.tracking', 'partner_id', string="Partner tracking"),        
        'crm_sold_prod_ids' : fields.function(_crm_information, type='one2many', fnct_search=_search_products, string='Sold products', multi='crm_information', relation='crm.product.sold'),
        'crm_last_orders_ids' : fields.function(_crm_information, type='one2many', string='Last orders', multi='crm_information', relation='crm.last.orders'),      
        'sales_six_months' : fields.function(_crm_information, type='integer', string='Sales in the last six months', multi='crm_information'),
        'sales_amount_six_months' : fields.function(_crm_information, type='float', string='Sales in the last six months', multi='crm_information'),
    }

class crm_product_sold (osv.osv):

    def calculate_sold_products(self, cr, uid, partner_orders, limit=0):
        '''Calcula los tres productos más vendidos y la cantidad vendida'''

        products = {}
        self._clear_objects(cr,uid)
        
        for partner_order in partner_orders:
            order_lines = partner_order.order_line
            # products.setdefault(order_lines[0].product_id, {})                
            for order_line in order_lines:
                id = order_line.product_id.id                   
                products[id] = products.get(id, 0) + order_line.product_uom_qty                     

        for prod_id, amount_sold in products.iteritems():
            record = {
                "product_id" : prod_id,
                "amount_sold" : amount_sold
            }
            self.create(cr, uid, record)
            
        return self.search(cr, uid, [], limit=limit)

    def _clear_objects(self, cr, uid, args=[], ids=None):
        """
        Elimina los objetos de forma permanente
        """
        if not ids:
            ids = self.search(cr, uid, args)
        self.unlink(cr, uid, ids)

    _name = "crm.product.sold"
    _order = "amount_sold desc"
    _columns = {        
        'product_id': fields.many2one('product.product', 'Product'),        
        'amount_sold' : fields.float('Amount sold'),
    }    

class crm_last_orders (osv.osv):

    def calculate_last_orders(self, cr, uid, partner_orders):
        '''Calcula los tres últimos pedidos y su fecha'''

        self._clear_objects(cr,uid)

        record = {
            "order_id" : partner_orders[-1].id,
            "order_date" : partner_orders[-1].date_order,
            "amount_untaxed" : partner_orders[-1].amount_untaxed,
            "amount_total" : partner_orders[-1].amount_total
        }
        self.create(cr, uid, record)
        
        if len(partner_orders) > 1:
            record = {
            "order_id" : partner_orders[-2].id,
            "order_date" : partner_orders[-2].date_order,
            "amount_untaxed" : partner_orders[-2].amount_untaxed,
            "amount_total" : partner_orders[-2].amount_total
            }
            self.create(cr, uid, record)
        
        if len(partner_orders) > 2:
            record = {
            "order_id" : partner_orders[-3].id,
            "order_date" : partner_orders[-3].date_order,
            "amount_untaxed" : partner_orders[-3].amount_untaxed,
            "amount_total" : partner_orders[-3].amount_total
            }
            self.create(cr, uid, record)

        return self.search(cr, uid, [])

    def _clear_objects(self, cr, uid, args=[], ids=None):
        """
        Elimina los objetos de forma permanente
        """
        if not ids:
            ids = self.search(cr, uid, args)
        self.unlink(cr, uid, ids)

    def view_order_info(self, cr, uid, ids, context=None):

        select_order = self.browse(cr, uid, ids, context=context)[0]
        id = select_order.order_id.id

        return {
            'domain': str([('id', '=', id)]),
            'name': 'Product Cost Analysis',
            'type': 'ir.actions.act_window',
            'res_model':'sale.order',
            'view_mode': 'tree,form',
            'view_type': 'form'
        }

    _name = "crm.last.orders"   
    _columns = {        
        'order_id': fields.many2one('sale.order', 'Sale Order'),        
        'order_date' : fields.date('Order date'),
        'amount_untaxed' : fields.float('Untaxed Amount'),
        'amount_total' : fields.float('Total'),
    }

class crm_partner_tracking (osv.osv):
    
    _name = "crm.partner.tracking"  
    _columns = {        
        'partner_id': fields.many2one("res.partner", string="Partner", ondelete="CASCADE"), 
        'note': fields.char('Note', required=True),        
        'note_date' : fields.date('Note date', required=True),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: