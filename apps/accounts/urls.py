from django.contrib.auth import views as auth_views
from django.urls import path

from .views import PanelLoginView

app_name = 'accounts'

urlpatterns = [
    path(
        'entrar/',
        PanelLoginView.as_view(),
        name='login',
    ),
    path('sair/', auth_views.LogoutView.as_view(), name='logout'),
]
