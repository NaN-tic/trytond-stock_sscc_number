# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'generate_pallet_output': {
                    'invisible': ~Eval('state').in_([
                            'draft', 'waiting', 'assigned', 'running']),
                    'depends': ['state'],
                    },
                })

    @classmethod
    @ModelView.button_action(
        'stock_sscc_number.wizard_generate_pallet_output')
    def generate_pallet_output(cls, productions):
        pass

    @classmethod
    def generate_pallet_output_move(cls, productions, lot=None):
        pool = Pool()
        Move = pool.get('stock.move')
        Pallet = pool.get('stock.pallet.serial')
        Configuration = pool.get('stock.configuration')

        to_delete = []
        to_create_pallet = []
        to_save = []
        for production in productions:
            move = production._get_pallet_pending_output()
            if not move:
                raise UserError(gettext(
                        'stock_sscc_number.msg_no_pallet_pending_output',
                        production=production.rec_name))

            pending_quantity = production._get_output_package_quantity(move)
            pallet_quantity = production._get_output_pallet_quantity(
                move, pending_quantity)
            remaining_quantity = pending_quantity - pallet_quantity

            pallet_move, = Move.copy([move],
                default=production._pallet_output_copy_default(
                    move, pallet_quantity))
            production._set_output_package_quantity(
                pallet_move, pallet_quantity)
            if lot:
                pallet_move.lot = lot
            if not pallet_move.lot:
                raise UserError(gettext(
                        'stock_sscc_number.msg_no_pallet_lot',
                        move=pallet_move.rec_name))
            to_save.append(pallet_move)
            to_create_pallet.append((production, pallet_move))

            if remaining_quantity > 0:
                production._set_output_package_quantity(
                    move, remaining_quantity)
                to_save.append(move)
            else:
                to_delete.append(move)

        if to_save:
            Move.save(to_save)
        if to_create_pallet:
            Pallet.create([
                    {
                        'number': Configuration.get_next_sscc(
                            production.company),
                        'product': move.product.id,
                        'lot': move.lot.id,
                        'origin': str(production),
                        'move': move.id,
                        }
                    for production, move in to_create_pallet])
        if to_delete:
            Move.delete(to_delete)

    def _get_pallet_pending_output(self):
        outputs = sorted(self.outputs, key=lambda m: m.id or 0)
        for move in outputs:
            if move.state in {'done', 'cancelled'}:
                continue
            if self._get_output_package_quantity(move, raise_error=False) > 0:
                return move

    def _get_output_package_quantity(self, move, raise_error=True):
        package_quantity = getattr(move, 'package_quantity', None)
        if package_quantity:
            return int(package_quantity)

        package = self._get_output_package(move)
        if package and move.quantity:
            return int(move.quantity / package.quantity)

        if raise_error:
            raise UserError(gettext(
                    'stock_sscc_number.msg_no_pallet_package',
                    move=move.rec_name))
        return 0

    def _get_output_pallet_quantity(self, move, pending_quantity):
        package = self._get_output_package(move)
        boxes_per_pallet = getattr(package, 'box_per_pallet', None)
        if not boxes_per_pallet:
            raise UserError(gettext(
                    'stock_sscc_number.msg_no_boxes_per_pallet',
                    move=move.rec_name))
        return min(int(boxes_per_pallet), pending_quantity)

    def _pallet_output_copy_default(self, move, package_quantity):
        default = {
            'state': 'draft',
            }
        if hasattr(move, 'package_quantity'):
            default['package_quantity'] = package_quantity
        if hasattr(move, 'scanned_package_quantity'):
            default['scanned_package_quantity'] = 0
        package = self._get_output_package(move)
        if package and not hasattr(move, 'package_quantity'):
            default['quantity'] = package_quantity * package.quantity
        return default

    def _get_output_package(self, move):
        package = getattr(move, 'product_package', None)
        if package:
            return package

        product = move.product
        if not product:
            return None
        if hasattr(product, '_get_default_package'):
            return product._get_default_package()
        package = getattr(product, 'default_package', None)
        if package:
            return package
        template = getattr(product, 'template', None)
        if template:
            return getattr(template, 'default_package', None)

    def _set_output_package_quantity(self, move, package_quantity):
        package = self._get_output_package(move)
        if hasattr(move, 'product_package') and package:
            move.product_package = package
        if hasattr(move, 'package_quantity'):
            move.package_quantity = package_quantity
        elif package:
            move.quantity = package_quantity * package.quantity
        if hasattr(move, 'scanned_package_quantity'):
            move.scanned_package_quantity = 0
        if hasattr(move, 'on_change_package_quantity'):
            move.on_change_package_quantity()
        if hasattr(move, 'on_change_scanned_package_quantity'):
            move.on_change_scanned_package_quantity()


class PalletSerial(metaclass=PoolMeta):
    __name__ = 'stock.pallet.serial'

    @classmethod
    def get_origin(cls):
        origins = super().get_origin()
        production_origin = ('production', 'Production')
        if production_origin not in origins:
            origins.append(production_origin)
        return origins


class GeneratePalletOutput(Wizard):
    __name__ = 'stock_sscc_number.production.generate_pallet_output'

    start = StateView(
        'stock_sscc_number.production.generate_pallet_output.start',
        'stock_sscc_number.generate_pallet_output_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generate', 'generate_', 'tryton-ok', default=True),
            ])
    generate_ = StateTransition()

    def default_start(self, fields):
        pool = Pool()
        Production = pool.get('production')
        productions = Production.browse(
            Transaction().context.get('active_ids', []))
        if len(productions) != 1:
            return {}
        production, = productions
        move = production._get_pallet_pending_output()
        if not move:
            return {}
        return {
            'product': move.product.id if move.product else None,
            'lot': move.lot.id if move.lot else None,
            }

    def transition_generate_(self):
        pool = Pool()
        Production = pool.get('production')
        productions = Production.browse(
            Transaction().context.get('active_ids', []))
        Production.generate_pallet_output_move(productions, lot=self.start.lot)
        return 'end'


class GeneratePalletOutputStart(ModelView):
    'Generate Pallet Output'
    __name__ = 'stock_sscc_number.production.generate_pallet_output.start'

    product = fields.Many2One('product.product', 'Product', readonly=True)
    lot = fields.Many2One('stock.lot', 'Lot', required=True,
        domain=[
            ('product', '=', Eval('product')),
            ],
        depends=['product'])
