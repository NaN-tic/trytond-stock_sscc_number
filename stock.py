# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id

from .exceptions import SSCCError, SSCCValidationError


def _only_digits(value):
    return value.isdigit() if value else False


def _check_digit(base_number):
    total = 0
    for index, digit in enumerate(reversed(base_number), start=1):
        total += int(digit) * (3 if index % 2 else 1)
    return str((10 - (total % 10)) % 10)


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    sscc_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "SSCC Sequence", required=True,
            domain=[
                ('company', 'in', [
                        Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('stock_sscc_number', 'sequence_type_sscc')),
                ],
            help="Sequence used to generate the serial reference of SSCC "
            "numbers."))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'sscc_sequence':
            return pool.get('stock.configuration.sequence')
        return super().multivalue_model(field)

    @classmethod
    def default_sscc_sequence(cls, **pattern):
        return cls.multivalue_model('sscc_sequence').default_sscc_sequence()

    @classmethod
    def validate_sscc_number(cls, number):
        if len(number) != 18 or not number.isdigit():
            raise SSCCValidationError(
                gettext('stock_sscc_number.msg_invalid_sscc_format',
                    sscc=number))
        expected = _check_digit(number[:-1])
        if number[-1] != expected:
            raise SSCCValidationError(
                gettext('stock_sscc_number.msg_invalid_sscc_check_digit',
                    sscc=number,
                    expected=expected))

    @classmethod
    def build_sscc(cls, company, serial_reference):
        if not company:
            raise SSCCError(gettext('stock_sscc_number.msg_missing_company'))
        if not company.sscc_company_prefix:
            raise SSCCError(
                gettext('stock_sscc_number.msg_missing_company_prefix',
                    company=company.rec_name))
        if not _only_digits(company.sscc_company_prefix):
            raise SSCCValidationError(
                gettext('stock_sscc_number.msg_invalid_company_prefix',
                    company=company.rec_name,
                    prefix=company.sscc_company_prefix))

        extension_digit = company.sscc_extension_digit or '0'
        if len(extension_digit) != 1 or not extension_digit.isdigit():
            raise SSCCValidationError(
                gettext('stock_sscc_number.msg_invalid_extension_digit',
                    company=company.rec_name,
                    digit=extension_digit))

        serial_length = 16 - len(company.sscc_company_prefix)
        if serial_length <= 0:
            raise SSCCValidationError(
                gettext('stock_sscc_number.msg_invalid_company_prefix_length',
                    company=company.rec_name,
                    prefix=company.sscc_company_prefix))
        if not _only_digits(serial_reference):
            raise SSCCValidationError(
                gettext('stock_sscc_number.msg_invalid_serial_reference',
                    serial=serial_reference))
        if len(serial_reference) > serial_length:
            raise SSCCValidationError(
                gettext('stock_sscc_number.msg_serial_reference_too_long',
                    serial=serial_reference,
                    length=serial_length))

        base_number = ''.join([
                extension_digit,
                company.sscc_company_prefix,
                serial_reference.zfill(serial_length),
                ])
        return base_number + _check_digit(base_number)

    @classmethod
    def get_next_sscc(cls, company):
        config = cls(1)
        sequence = config.get_multivalue('sscc_sequence', company=company.id)
        if not sequence:
            raise SSCCError(
                gettext('stock_sscc_number.msg_missing_sscc_sequence',
                    company=company.rec_name))
        return cls.build_sscc(company, sequence.get())


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'stock.configuration.sequence'

    sscc_sequence = fields.Many2One(
        'ir.sequence', "SSCC Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=', Id('stock_sscc_number', 'sequence_type_sscc')),
            ],
        help="Sequence used to generate the serial reference of SSCC "
        "numbers.")

    @classmethod
    def default_sscc_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock_sscc_number', 'sequence_sscc')
        except KeyError:
            return None
