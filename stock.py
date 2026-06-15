# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id
from trytond.transaction import Transaction

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
    def get_sscc_sequence(cls, company):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Sequence = pool.get('ir.sequence')

        config = cls(1)
        sequence = config.get_multivalue(
            'sscc_sequence', company=company.id)
        if sequence:
            return sequence
        try:
            sequence_id = ModelData.get_id(
                'stock_sscc_number', 'sequence_sscc')
        except KeyError:
            return None
        return Sequence(sequence_id)

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
        serial_reference = cls.normalize_sscc_serial_reference(
            company, serial_reference)
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
    def normalize_sscc_serial_reference(cls, company, serial_reference):
        serial_reference = str(serial_reference or '')
        prefix = getattr(company, 'sscc_company_prefix', '') or ''
        serial_length = 16 - len(prefix)
        if (serial_length > 0
                and len(serial_reference) > serial_length
                and serial_reference.isdigit()):
            stripped = serial_reference.lstrip('0') or '0'
            if len(stripped) <= serial_length:
                return stripped
        return serial_reference

    @classmethod
    def get_next_sscc(cls, company):
        sequence = cls.get_sscc_sequence(company)
        if not sequence:
            raise SSCCError(
                gettext('stock_sscc_number.msg_missing_sscc_sequence',
                    company=company.rec_name))
        serial_reference = cls.normalize_sscc_serial_reference(
            company, sequence.get())
        return cls.build_sscc(company, serial_reference)

    @classmethod
    def get_next_sscc_preview(cls, company):
        sequence = cls.get_sscc_sequence(company)
        if not sequence:
            return ''
        serial_reference = sequence.on_change_with_preview(None)
        if not serial_reference:
            return ''
        serial_reference = cls.normalize_sscc_serial_reference(
            company, serial_reference)
        return cls.build_sscc(company, serial_reference)


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


class PalletSerial(ModelSQL, ModelView):
    'Pallet Serial'
    __name__ = 'stock.pallet.serial'

    number = fields.Char('Number', required=True)
    product = fields.Many2One('product.product', 'Product', required=True)
    lot = fields.Many2One('stock.lot', 'Lot', required=True)
    origin = fields.Reference('Origin', selection='get_origin', required=True)
    move = fields.Many2One('stock.move', 'Move')

    @classmethod
    def get_origin(cls):
        return [(None, ''),
            ('stock.inventory.line', 'Inventory Line'),
            ('stock.inventory', 'Inventory'), ('stock.move', 'Move'),
            ('stock.shipment.in', 'Shipment In'),
            ('stock.shipment.internal', 'Shipment Internal'),
            ('stock.shipment.out.return', 'Shipment Out Return'),
            ('stock.shipment.out', 'Shipment Out')]


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    pallet_serials_move = fields.One2Many('stock.pallet.serial', 'move',
        'Matriculas')
    pallet_numbers = fields.Function(fields.Char('Matriculas'),
        'get_pallet_numbers', searcher='search_pallet_numbers')
    next_pallet_number = fields.Function(fields.Char('Next Pallet Number'),
        'get_next_pallet_number')


    @classmethod
    def get_pallet_numbers(cls, moves, name):
        pool = Pool()
        Pallet = pool.get('stock.pallet.serial')

        result = {m.id: '' for m in moves}
        if not moves:
            return result

        move_ids = [m.id for m in moves if m.id is not None]
        if not move_ids:
            return result

        pallets = Pallet.search([
            ('move', 'in', move_ids),
            ], order=[('number', 'ASC')])
        grouped = {}
        for pallet in pallets:
            grouped.setdefault(pallet.move.id, []).append(pallet.number)

        for move in moves:
            result[move.id] = ', '.join(grouped.get(move.id, []))
        return result

    @classmethod
    def get_next_pallet_number(cls, moves, name):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        Company = pool.get('company.company')
        result = {m.id: '' for m in moves}
        if not moves:
            return result

        for move in moves:
            if move.pallet_numbers:
                result[move.id] = move.pallet_numbers.split(', ', 1)[0]
                continue
            company = getattr(move, 'company', None)
            if isinstance(company, int):
                company = Company(company)
            if not company:
                company_id = Transaction().context.get('company')
                if company_id:
                    company = Company(company_id)
            if company:
                result[move.id] = Configuration.get_next_sscc_preview(company)
        return result

    @classmethod
    def search_pallet_numbers(cls, name, clause):
        _, operator, value = clause
        Pallet = Pool().get('stock.pallet.serial')
        pallet = Pallet.__table__()

        Operator = fields.SQL_OPERATORS[operator]
        where = Operator(pallet.number, value)
        query = pallet.select(pallet.move, where=where & (pallet.move != None))

        negative = {'!=', 'not like', 'not ilike', 'not in'}
        if operator in negative:
            return [('id', 'not in', query)]
        return [('id', 'in', query)]
