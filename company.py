# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    sscc_company_prefix = fields.Char(
        "SSCC Company Prefix",
        size=12,
        help="GS1 company prefix used to generate SSCC logistic identifiers.")
    sscc_extension_digit = fields.Char(
        "SSCC Extension Digit",
        size=1,
        help="Extension digit used as the first SSCC digit.")

    @staticmethod
    def default_sscc_extension_digit():
        return '0'

