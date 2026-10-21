from django import template
import re

register = template.Library()


@register.filter
def format_document(value):
    digits = re.sub(r'\D', '', value or '')
    if len(digits) == 11:
        return f'{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}'
    if len(digits) == 14:
        return f'{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}'
    return value


@register.filter
def format_phone(value):
    digits = re.sub(r'\D', '', value or '')
    if len(digits) == 10:
        return f'({digits[:2]}) {digits[2:6]}-{digits[6:]}'
    if len(digits) == 11:
        return f'({digits[:2]}) {digits[2:7]}-{digits[7:]}'
    if len(digits) == 12 and digits.startswith('55'):
        return f'+55 ({digits[2:4]}) {digits[4:8]}-{digits[8:]}'
    if len(digits) == 13 and digits.startswith('55'):
        return f'+55 ({digits[2:4]}) {digits[4:9]}-{digits[9:]}'
    return value


@register.inclusion_tag('includes/sortable_th.html', takes_context=True)
def sortable_th(context, field, label):
    request = context['request']
    current_sort = context.get('ordering') or request.GET.get('sort', '')
    active = current_sort.lstrip('-') == field
    descending = current_sort == f'-{field}'
    next_sort = field if not active or descending else f'-{field}'
    params = request.GET.copy()
    params['sort'] = next_sort
    params.pop('page', None)
    return {
        'label': label,
        'url': f'{request.path}?{params.urlencode()}',
        'active': active,
        'descending': descending,
        'aria_sort': 'descending' if descending else 'ascending' if active else 'none',
    }
