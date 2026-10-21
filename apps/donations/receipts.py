from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


MONTH_NAMES = (
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
)
ONES = ('zero', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove')
TEENS = {
    10: 'dez', 11: 'onze', 12: 'doze', 13: 'treze', 14: 'quatorze',
    15: 'quinze', 16: 'dezesseis', 17: 'dezessete', 18: 'dezoito', 19: 'dezenove',
}
TENS = {
    20: 'vinte', 30: 'trinta', 40: 'quarenta', 50: 'cinquenta',
    60: 'sessenta', 70: 'setenta', 80: 'oitenta', 90: 'noventa',
}
HUNDREDS = {
    100: 'cento', 200: 'duzentos', 300: 'trezentos', 400: 'quatrocentos',
    500: 'quinhentos', 600: 'seiscentos', 700: 'setecentos',
    800: 'oitocentos', 900: 'novecentos',
}
SCALES = (
    (1_000_000_000, 'bilhão', 'bilhões'),
    (1_000_000, 'milhão', 'milhões'),
    (1_000, 'mil', 'mil'),
)
PAGE_W, PAGE_H = A4
TEXT_FONT = 'Times-Roman'
TEXT_SIZE = 12
FIELD_GAP = 4.32
TEMPLATE_PATH = Path(settings.BASE_DIR) / 'static' / 'pdf' / 'comprovante-modelo.png'


DONATION_RECEIPT = 'donation'
CONTRIBUTION_RECEIPT = 'contribution'


def receipt_filename(donation, receipt_type):
    suffix = 'doacao' if receipt_type == DONATION_RECEIPT else 'contribuicao'
    return f'comprovante-{suffix}-{receipt_identifier(donation, receipt_type).lower()}.pdf'


def receipt_identifier(donation, receipt_type):
    if receipt_type == DONATION_RECEIPT:
        return (
            str(donation.donation_receipt_number)
            if donation.donation_receipt_number is not None
            else f'{donation.receipt_number}-D'
        )
    if receipt_type == CONTRIBUTION_RECEIPT:
        return (
            str(donation.contribution_receipt_number)
            if donation.contribution_receipt_number is not None
            else f'{donation.receipt_number}-C'
        )
    raise ValueError('Tipo de comprovante inválido.')


def format_currency(amount):
    return f'{amount:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def number_to_words(number):
    number = int(number)
    if number < 10:
        return ONES[number]
    if number < 20:
        return TEENS[number]
    if number < 100:
        tens, remainder = divmod(number, 10)
        return TENS[tens * 10] if not remainder else f'{TENS[tens * 10]} e {ONES[remainder]}'
    if number < 1000:
        hundreds, remainder = divmod(number, 100)
        if number == 100:
            return 'cem'
        return HUNDREDS[hundreds * 100] if not remainder else f'{HUNDREDS[hundreds * 100]} e {number_to_words(remainder)}'

    parts = []
    remainder = number
    for scale, singular, plural in SCALES:
        quantity, remainder = divmod(remainder, scale)
        if not quantity:
            continue
        if scale == 1000 and quantity == 1:
            parts.append(singular)
        else:
            label = singular if quantity == 1 else plural
            parts.append(f'{number_to_words(quantity)} {label}')
    if remainder:
        parts.append(number_to_words(remainder))
    return ' e '.join(parts)


def amount_to_words(amount):
    value = Decimal(amount).quantize(Decimal('0.01'))
    whole, cents = divmod(int(value * 100), 100)
    unit = 'real' if whole == 1 else 'reais'
    result = f'{number_to_words(whole)} {unit}'
    if cents:
        cents_unit = 'centavo' if cents == 1 else 'centavos'
        result = f'{result} e {number_to_words(cents)} {cents_unit}'
    return result


def receipt_data(donation, receipt_type):
    zero = Decimal('0.00')
    if receipt_type == DONATION_RECEIPT:
        amount = donation.donation_amount or zero
        if amount <= zero:
            raise ValueError('Esta doação não possui valor de doação para emitir comprovante.')
        return {
            'number': receipt_identifier(donation, receipt_type),
            'recipient': donation.donor.name,
            'amount': amount,
            'reference': 'doação',
        }
    if receipt_type == CONTRIBUTION_RECEIPT:
        amount = donation.contribution_amount or zero
        if amount <= zero:
            raise ValueError('Esta doação não possui valor de contribuição para emitir comprovante.')
        return {
            'number': receipt_identifier(donation, receipt_type),
            'recipient': (donation.responsible or donation.donor).name,
            'amount': amount,
            'reference': 'contribuição',
        }
    raise ValueError('Tipo de comprovante inválido.')


def fitted_font(text, max_width, size=TEXT_SIZE, minimum=8):
    current = size
    while current > minimum and stringWidth(text, TEXT_FONT, current) > max_width:
        current -= 0.25
    return current


def draw_fitted(canvas, text, x, y, max_width, size=TEXT_SIZE):
    canvas.setFont(TEXT_FONT, fitted_font(text, max_width, size=size))
    canvas.drawString(x, y, text)


def draw_centered_fitted(canvas, text, center_x, y, max_width, size=TEXT_SIZE):
    canvas.setFont(TEXT_FONT, fitted_font(text, max_width, size=size))
    canvas.drawCentredString(center_x, y, text)


def draw_copy(canvas, donation, data, positions):
    draw_fitted(canvas, data['number'], *positions['number'], 105)
    draw_fitted(canvas, format_currency(data['amount']), *positions['numeric'], 105)
    draw_fitted(canvas, data['recipient'], *positions['donor'], 445)
    draw_fitted(canvas, amount_to_words(data['amount']), *positions['amount'], 430)
    draw_fitted(canvas, data['reference'], *positions['reference'], 470)

    date = donation.donation_date
    date_y = positions['date_y']
    day_x, month_x, year_x = positions['date_centers']
    draw_centered_fitted(canvas, str(date.day), day_x, date_y, 24)
    draw_centered_fitted(canvas, MONTH_NAMES[date.month - 1], month_x, date_y, 175)
    draw_centered_fitted(canvas, f'{date.year % 100:02d}', year_x, date_y, 32)


def generate_receipt_pdf(donation, receipt_type):
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f'Modelo de comprovante não encontrado: {TEMPLATE_PATH}')

    data = receipt_data(donation, receipt_type)
    output = BytesIO()
    canvas = Canvas(output, pagesize=A4)
    canvas.drawImage(ImageReader(str(TEMPLATE_PATH)), 0, 0, width=PAGE_W, height=PAGE_H)
    draw_copy(
        canvas,
        donation,
        data,
        {
            'number': (460, 719),
            'numeric': (460, 667 + FIELD_GAP),
            'donor': (118, 603 + FIELD_GAP),
            'amount': (132, 583 + FIELD_GAP),
            'reference': (89, 564 + FIELD_GAP),
            'date_y': 531 + FIELD_GAP,
            'date_centers': (377, 455, 560),
        },
    )
    draw_copy(
        canvas,
        donation,
        data,
        {
            'number': (460, 325),
            'numeric': (464, 274 + FIELD_GAP),
            'donor': (118, 210 + FIELD_GAP),
            'amount': (132, 189 + FIELD_GAP),
            'reference': (89, 169 + FIELD_GAP),
            'date_y': 136 + FIELD_GAP,
            'date_centers': (377, 455, 560),
        },
    )
    canvas.save()
    output.seek(0)
    return output.getvalue()
