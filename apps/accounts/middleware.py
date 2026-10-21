from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class StaffAdminOnlyMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return None

        static_url = f'/{settings.STATIC_URL.lstrip("/")}'
        media_url = getattr(settings, 'MEDIA_URL', '')
        media_url = f'/{media_url.lstrip("/")}' if media_url and media_url != '/' else ''
        if request.path_info.startswith(static_url) or (media_url and request.path_info.startswith(media_url)):
            return None

        namespace = getattr(request.resolver_match, 'namespace', '')
        if namespace in {'admin', 'accounts'}:
            return None

        return redirect('admin:index')
