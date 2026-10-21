from django.urls import path

from . import views

app_name = 'donors'

urlpatterns = [
    path('', views.DonorListView.as_view(), name='list'),
    path('buscar/', views.DonorSearchView.as_view(), name='search'),
    path('novo/', views.DonorCreateView.as_view(), name='create'),
    path('responsaveis/', views.ResponsibleListView.as_view(), name='responsible-list'),
    path('responsaveis/buscar/', views.ResponsibleSearchView.as_view(), name='responsible-search'),
    path('responsaveis/novo/', views.ResponsibleCreateView.as_view(), name='responsible-create'),
    path('responsaveis/<int:pk>/', views.ResponsibleDetailView.as_view(), name='responsible-detail'),
    path('responsaveis/<int:pk>/editar/', views.ResponsibleUpdateView.as_view(), name='responsible-update'),
    path('responsaveis/<int:pk>/excluir/', views.ResponsibleDeleteView.as_view(), name='responsible-delete'),
    path('<int:pk>/', views.DonorDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', views.DonorUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.DonorDeleteView.as_view(), name='delete'),
]
