from social_django.middleware import SocialAuthExceptionMiddleware
from users.pipeline import frontend_error_url


class FrontendRedirectExceptionMiddleware(SocialAuthExceptionMiddleware):
    def get_redirect_uri(self, request, exception):
        strategy = getattr(request, "social_strategy", None)
        return frontend_error_url(strategy) if strategy else None
