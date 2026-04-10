# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model.exceptions import ValidationError
from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class StockSSCCNumberTestCase(ModuleTestCase):
    'Test Stock SSCC Number module'
    module = 'stock_sscc_number'

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


del ModuleTestCase
