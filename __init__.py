# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import company, production, stock


def register():
    Pool.register(
        company.Company,
        stock.Configuration,
        stock.ConfigurationSequence,
        stock.PalletSerial,
        stock.Move,
        module='stock_sscc_number', type_='model')
    Pool.register(
        production.PalletSerial,
        production.Production,
        production.GeneratePalletOutputStart,
        module='stock_sscc_number', type_='model',
        depends=['production'])
    Pool.register(
        production.GeneratePalletOutput,
        module='stock_sscc_number', type_='wizard',
        depends=['production'])
