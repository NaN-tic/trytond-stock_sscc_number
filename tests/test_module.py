# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from trytond.model.exceptions import ValidationError
from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class StockSSCCNumberTestCase(ModuleTestCase):
    'Test Stock SSCC Number module'
    module = 'stock_sscc_number'
    extras = ['production']

    @with_transaction()
    def test_build_sscc(self):
        pool = Pool()
        Company = pool.get('company.company')
        Configuration = pool.get('stock.configuration')

        company = create_company()
        Company.write([company], {
                'sscc_company_prefix': '84212345',
                'sscc_extension_digit': '3',
                })
        sscc = Configuration.build_sscc(company, '1234567')
        self.assertEqual(sscc, '384212345012345676')

    @with_transaction()
    def test_validate_check_digit(self):
        pool = Pool()
        Configuration = pool.get('stock.configuration')

        with self.assertRaises(ValidationError):
            Configuration.validate_sscc_number('384212345001234568')

    @with_transaction()
    def test_get_next_sscc(self):
        pool = Pool()
        Company = pool.get('company.company')
        Configuration = pool.get('stock.configuration')

        company = create_company()
        with set_company(company):
            Company.write([company], {
                    'sscc_company_prefix': '84212345',
                    'sscc_extension_digit': '0',
                    })
            sscc = Configuration.get_next_sscc(company)
            self.assertEqual(len(sscc), 18)
            self.assertTrue(sscc.startswith('084212345'))
            Configuration.validate_sscc_number(sscc)

    @with_transaction()
    def test_get_next_sscc_uses_default_sequence_and_trims_padding(self):
        pool = Pool()
        Company = pool.get('company.company')
        Configuration = pool.get('stock.configuration')

        company = create_company()
        with set_company(company):
            Company.write([company], {
                    'sscc_company_prefix': '184370081725',
                    'sscc_extension_digit': '0',
                    })
            preview = Configuration.get_next_sscc_preview(company)
            sscc = Configuration.get_next_sscc(company)

            self.assertEqual(len(preview), 18)
            self.assertEqual(len(sscc), 18)
            self.assertTrue(preview.startswith('0184370081725'))
            self.assertTrue(sscc.startswith('0184370081725'))
            Configuration.validate_sscc_number(preview)
            Configuration.validate_sscc_number(sscc)

    @with_transaction()
    def test_create_pallet_serial(self):
        pool = Pool()
        Company = pool.get('company.company')
        Configuration = pool.get('stock.configuration')
        Location = pool.get('stock.location')
        Lot = pool.get('stock.lot')
        Move = pool.get('stock.move')
        Pallet = pool.get('stock.pallet.serial')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        unit, = Uom.search([('name', '=', 'Unit')])
        template, = Template.create([{
                    'name': 'Pallet Serial Product',
                    'type': 'goods',
                    'default_uom': unit.id,
                    }])
        product, = Product.create([{
                    'template': template.id,
                    }])
        lot, = Lot.create([{
                    'number': 'LOT-1',
                    'product': product.id,
                    }])
        supplier, = Location.search([('code', '=', 'SUP')])
        storage, = Location.search([('code', '=', 'STO')])

        company = create_company()
        currency = company.currency
        with set_company(company):
            Company.write([company], {
                    'sscc_company_prefix': '84212345',
                    'sscc_extension_digit': '0',
                    })
            move, = Move.create([{
                        'product': product.id,
                        'lot': lot.id,
                        'unit': unit.id,
                        'quantity': 1,
                        'from_location': supplier.id,
                        'to_location': storage.id,
                        'company': company.id,
                        'unit_price': Decimal('1'),
                        'currency': currency.id,
                        }])
            number = Configuration.get_next_sscc(company)
            pallet, = Pallet.create([{
                        'number': number,
                        'product': product.id,
                        'lot': lot.id,
                        'origin': str(move),
                        'move': move.id,
                        }])

            self.assertEqual(pallet.number, number)
            self.assertEqual(pallet.product, product)
            self.assertEqual(pallet.lot, lot)
            self.assertEqual(move.pallet_serials_move, (pallet,))
            self.assertEqual(move.pallet_numbers, number)
            Configuration.validate_sscc_number(pallet.number)


del ModuleTestCase
