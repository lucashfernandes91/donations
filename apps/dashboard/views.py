from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from .services import dashboard_context


@login_required
@permission_required('donations.view_donation', raise_exception=True)
def index(request):
    return render(request, 'dashboard/index.html', dashboard_context(request.GET))
