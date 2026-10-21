import re

from django.core.exceptions import ValidationError


def normalize_document(value):
    return re.sub(r'\D', '', value or '')


def normalize_cpf(value):
    return normalize_document(value)


def validate_cpf(value):
    document = normalize_document(value)

    if len(document) == 14:
        validate_cnpj(document)
        return

    if len(document) != 11 or document == document[0] * 11:
        raise ValidationError('Informe um CPF válido.')

    for check_digit in (9, 10):
        total = sum(int(digit) * weight for digit, weight in zip(document, range(check_digit + 1, 1, -1)))
        expected_digit = (total * 10 % 11) % 10
        if int(document[check_digit]) != expected_digit:
            raise ValidationError('Informe um CPF válido.')


def validate_cnpj(value):
    cnpj = normalize_document(value)

    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        raise ValidationError('Informe um CNPJ válido.')

    for weights, check_digit in (
        ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), 12),
        ((6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), 13),
    ):
        total = sum(int(digit) * weight for digit, weight in zip(cnpj[:check_digit], weights))
        expected_digit = 0 if total % 11 < 2 else 11 - total % 11
        if int(cnpj[check_digit]) != expected_digit:
            raise ValidationError('Informe um CNPJ válido.')
