from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse


class PanelLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.is_staff:
            return reverse('admin:index')
        return super().get_success_url()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect('admin:index')
        return super().dispatch(request, *args, **kwargs)
