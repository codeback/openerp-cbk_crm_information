# -*- encoding: utf-8 -*-
##############################################################################
#
#    cbk_crm_information: CRM Information Tab
#    Copyright (c) 2013 Codeback Software S.L. (http://codeback.es)    
#    @author: Miguel García <miguel@codeback.es>
#    @author: Javier Fuentes <javier@codeback.es>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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

from osv import fields, osv
from datetime import datetime, timedelta
from openerp.tools.translate import _
import pdb

class res_partner(osv.osv):
    """añadimos los nuevos campos"""
    name = "res.partner"
    _inherit = "res.partner"
    
    def _get_crm_info(self, cr, uid, ids, field_names, arg, context=None):
        """
        Gets information from related models for updating purposes       
        """    
        vals={}
        for partner in self.browse(cr,uid,ids):
            vals = self._recalculate_crm_info(cr,uid,ids,partner.shown_products)        

        return vals
    
    def _recalculate_crm_info(self,cr,uid,ids,limit):
        """
        Recalculates the info for the requested number of elements
        """
        most_sold_model = self.pool.get('crm.product.sold')
        last_orders = self.pool.get('crm.last.orders')
        vals={}
        for id in ids:
            vals[id] = {}
            args = [('partner_id', '=', id)]
            if limit == "all" or limit == False:
                vals[id]['crm_sold_prod_ids'] = most_sold_model.search(cr, uid, args)
            else:
                vals[id]['crm_sold_prod_ids'] = most_sold_model.search(cr, uid, args, limit=int(limit))
                
            vals[id]['crm_last_orders_ids'] = last_orders.search(cr, uid, args)
        return vals


    def shown_products_change(self, cr, uid, ids, shown_products, context=None):        
        vals={}
        vals = self._recalculate_crm_info(cr,uid,ids,shown_products) 
        if vals and ids:
            return { 'value': vals[ids[0]] }
        else:
            return vals

        #self.write(cr, uid, ids, {'shown_products': shown_products}, context=context)
        #self._get_crm_info(cr, uid, ids, [], [], context=context)


    def _search_products(self, cr, uid, obj, field_name, criterion, context=None):
        """
        Implements search function       
        """        
        comparision = criterion[0][1]

        modificador = ""

        if comparision == "not ilike":
            comparision = "ilike"
            modificador = "not "

        if comparision == "!=":
            comparision = "="
            modificador = "not "

        product = criterion[0][2]
        args = [("name", comparision, product)]
        prod_ids = self.pool.get('product.product').search(cr,uid,args)

        partner_ids = []
        if prod_ids:
            sold_prod_model = self.pool.get('crm.product.sold')
            args = [('product_id', 'in', prod_ids)]
            ids = sold_prod_model.search(cr, uid, args)
        
            objetos = sold_prod_model.browse(cr, uid, ids)

            partner_ids = [objeto.partner_id.id for objeto in objetos]

        return [("id", modificador + "in", partner_ids)]

    _columns = {        
        'crm_partner_tracking_ids' : fields.one2many('crm.partner.tracking', 'partner_id', string="Partner tracking"),
        'crm_sold_prod_ids' : fields.function(_get_crm_info, type='one2many', fnct_search=_search_products, string='Sold products', multi='get_crm_info', relation='crm.product.sold'),
        'crm_sold_prod_search_type': fields.char('Product search type'),
        'crm_last_orders_ids' : fields.function(_get_crm_info, type='one2many', string='Last orders', multi='get_crm_info', relation='crm.last.orders'),               
        'sales_in_window' : fields.integer(string='Sales in the specified window'),
        'sales_amount_in_window' : fields.float(string='Sales in the specified window'),
        'shown_products' : fields.selection ([('2', '2 products'),('10', '10 products'),('15', '15 products'),('all', 'All products')],'Shown elements'),
    }

    _defaults = {    
        'shown_products' : '2',
    }

    def run_scheduler(self, cr, uid, context=None):
        """ Update CRM Information from scheduler"""   
        self.update_crm(cr, uid, context)
        return True
    
    def update_crm(self, cr, uid, context=None):
        """
        Main function to retrieve all the required information for the Tab       
        """
        # Configuration data is read
        config = self._get_config_data(cr,uid)         

        if context is None:
            context = {}       
                        
        # Selection of allpartners
        args = []
        partners_ids = self.search(cr, uid, args)
        partners = self.browse(cr,uid,partners_ids)
        
        latest_orders = self.pool.get('crm.last.orders')
        latest_orders.clear_objects(cr, uid)
        most_sold_model = self.pool.get('crm.product.sold')
        most_sold_model.clear_objects(cr, uid)

        # Analysis of the parter_orders of each partner       
        for partner in partners:
            partner_orders = self.get_sale_orders(cr, uid, partner.id)       
            
            if partner_orders:  

                # Calculation of latest orders from the partner
                latest_orders.calculate_last_orders(cr, uid, partner.id)                

                # Calculation of the number of sales in the specified window
                sale_orders = self._get_orders_in_window(cr, uid, partner.id, config['window_days'] )

                sold_amount = 0
                for sale_order in sale_orders:
                    sold_amount = sold_amount + sale_order.amount_total

                # Calculation of the most sold products and the amount sold in the current currency
                most_sold_model.calculate_sold_products(cr, uid, partner_orders, config['search_type'])

                if config['search_type'] == 'm':
                    prod_search_type= "By model"
                else:
                    prod_search_type= "By product"

                record = {
                    'sales_in_window'           : len(sale_orders),
                    'sales_amount_in_window'    : sold_amount,
                    'crm_sold_prod_search_type' : prod_search_type   
                }
                
                self.write(cr, uid, partner.id, record)

        return True

    def _get_objects(self, cr, uid, name, args=[], ids=None, order=None, limit=None):   
        """
        Gets objects from a model
        """                  
        obj = self.pool.get(name)
        if not ids:
            ids = obj.search(cr, uid, args, order=order, limit=limit)
        return obj.browse(cr, uid, ids)

    def get_sale_orders(self, cr, uid, partner_id, limit=None):
        """
        Gets the orders from a partner
        """
        args=[('partner_id', '=', partner_id)]
        return self._get_objects(cr, uid, 'sale.order', args=args, limit=limit)    

    def _get_orders_in_window(self, cr, uid, partner_id, window):
        """
        Gets all the sales order in the specified window
        """
        calculation_date = datetime.today() - timedelta(days=window)
        str_calculation_date = datetime.strftime(calculation_date, "%Y-%m-%d") + " 00:00:00"

        args = [('create_date', '>=', str_calculation_date),('partner_id', '=', partner_id)]
        return self._get_objects(cr, uid, 'sale.order', args)       

    def _get_config_data(self, cr, uid):
        """
        Reads active config data
        """
        model_conf = self.pool.get('crm.information.settings')
        args = [('selected', '=', True)]    
        ids = model_conf.search(cr, uid, args)
        config = model_conf.browse(cr, uid, ids[0])

        return {
            'window_days': config.window_days,
            'search_type': config.search_type
        }    

    def _get_crm_info(self, cr, uid, ids, field_names, arg, context=None):
        """
        Updates model fields
        """
        most_sold_model = self.pool.get('crm.product.sold')

        vals={}

        for id in ids:
            vals[id] = {}
            args = [('partner_id', '=', id)]
            vals[id]['crm_sold_prod_ids'] = most_sold_model.search(cr, uid, args)

        return vals

class crm_product_sold (osv.osv):

    def calculate_sold_products(self, cr, uid, partner_orders, search_type):
        '''
        Calculates the most sold products and the sold amount
        '''
        products = {}        

        if partner_orders:
            for partner_order in partner_orders:
                order_lines = partner_order.order_line
                for order_line in order_lines:
                    id = order_line.product_id.id          

                    if search_type == 'm' and order_line.product_id.parent_prod_id: #by model
                        id = order_line.product_id.parent_prod_id.id
                        
                    products[id] = products.get(id, 0) + order_line.product_uom_qty

            for prod_id, amount_sold in products.iteritems():
                record = {
                    "partner_id" : partner_orders[0].partner_id.id,
                    "product_id" : prod_id,
                    "amount_sold" : amount_sold
                }
                self.create(cr, uid, record)
            
    def clear_objects(self, cr, uid, args=[], ids=None):
        """
        Permanently remove objects
        """
        if not ids:
            ids = self.search(cr, uid, args)
        self.unlink(cr, uid, ids)

    _name = "crm.product.sold"
    _order = "amount_sold desc"
    _columns = {        
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'product_id': fields.many2one('product.product', 'Product'),        
        'amount_sold' : fields.float('Amount sold'),
    }    

class crm_last_orders (osv.osv):

    def calculate_last_orders(self, cr, uid, partner_id):
        '''
        Calculate three las orders
        '''

        model = self.pool.get('res.partner')
        partner_orders = model.get_sale_orders(cr, uid, partner_id, limit=3)

        for partner_order in partner_orders:
            record = {
                "partner_id" : partner_id,
                "order_id" : partner_order.id,
                "order_date" : partner_order.date_order,
                "amount_untaxed" : partner_order.amount_untaxed,
                "amount_total" : partner_order.amount_total
            }
            self.create(cr, uid, record)

    def clear_objects(self, cr, uid, args=[], ids=None):
        """
        Permanently remove objects
        """

        _order = "amount_sold desc"
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
    _order = "order_date desc"
    _columns = {        
        'partner_id': fields.many2one('res.partner', 'Partner'),
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

class crm_information_settings(osv.osv):  
    _name = "crm.information.settings"
    
    _columns = {        
        'window_days': fields.integer('Window days', required=True),     
        'name': fields.char('Name', size=64, required=True),
        'search_type': fields.selection((('p','By product'), ('m','By model')),'Product search type', 
            help='Indicates if sold products are grouped by model'),      
        'selected': fields.boolean('Selected'), 
    } 
    
    _defaults = {        
        'name' : "Default",
        'window_days': 45,
        'selected': False, 
        'search_type': "p",        
    } 

    def write (self, cr, uid, ids, values, context=None):        
        if 'selected' in values:
            self._validate_selected(cr, uid, ids, values['selected'])

        return super(crm_information_settings, self).write(cr, uid, ids, values, context=context)

    def unlink (self, cr, uid, ids, context=None):        
        args = []
        ids_all = self.search(cr, uid, args)        
        
        if len(ids) == len(ids_all):
            raise osv.except_osv(_('Error removing objects!'), _('You cannot remove all records'))
        else:
            for id in ids:
                if self.browse(cr, uid, id).selected == True:
                    raise osv.except_osv(_('Error removing objects!'), _('You cannot remove a record with value "selected" = True'))

    def _validate_selected(self, cr, uid, ids, selected):      
        args = [('selected', '=', True)]
        ids_selected = self.search(cr, uid, args)        
        if not selected:
            if ids_selected and ids_selected[0] == ids[0]:
                raise osv.except_osv(_('Invalid Selected!'), _('You cannot deselect all configurations. Please, select another configuration first.'))
        else:                        
            values = {
                'selected': False,
            }
            super(crm_information_settings, self).write(cr, uid, ids_selected, values)

        return {'value': selected}

class crm_update(osv.osv_memory):
    _name = "crm.update"
    _columns = {}

    def run_crm_update(self, cr, uid, ids, context=None):
        """ Estimate stock from wizard"""    

        obj = self.pool.get('res.partner')
        obj.update_crm(cr, uid, ids)        
        
        #Comprobar funcionalidad de las líneas siguientes
        '''
        menu_mod = self.pool.get('ir.ui.menu')        
        args = [('name', '=', 'Stock estimation manager')]
        menu_ids = menu_mod.search(cr, uid, args)
        
        return {
            'name': 'Stock Estimation',
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {'menu_id': menu_ids[0]},
        }      
        '''

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: