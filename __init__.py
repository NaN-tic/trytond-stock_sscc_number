# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import company, stock


def register():
    Pool.register(
        company.Company,
        stock.Configuration,
        stock.ConfigurationSequence,
        module='stock_sscc_number', type_='model')
