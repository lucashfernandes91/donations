from django.urls import path

from . import views

app_name = 'donations'

urlpatterns = [
    path('', views.DonationListView.as_view(), name='list'),
    path('nova/', views.DonationCreateView.as_view(), name='create'),
    path('doadores/buscar/', views.DonorSearchView.as_view(), name='donor-search'),
    path('exportar/xlsx/', views.DonationExportXlsxView.as_view(), name='export-xlsx'),
    path('<int:pk>/', views.DonationDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', views.DonationUpdateView.as_view(), name='update'),
    path('<int:pk>/cancelar/', views.DonationCancelView.as_view(), name='cancel'),
    path('<int:pk>/comprovante/<str:receipt_type>/', views.DonationReceiptView.as_view(), name='receipt'),
    path(
        '<int:pk>/comprovante/<str:receipt_type>/baixar/',
        views.DonationReceiptDownloadView.as_view(),
        name='receipt-download',
    ),
]
