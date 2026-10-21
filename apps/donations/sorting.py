def resolve_ordering(request, allowed_ordering, default_ordering):
    requested = request.GET.get('sort', '')
    if requested in allowed_ordering:
        return requested
    return default_ordering


def apply_ordering(queryset, ordering, allowed_ordering):
    fields = allowed_ordering.get(ordering)
    if not fields:
        return queryset
    return queryset.order_by(*fields)
