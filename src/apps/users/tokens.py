from datetime import timedelta

from rest_framework_simplejwt.tokens import Token


class OneTimeToken(Token):
    token_type = "ott"
    lifetime = timedelta(seconds=60)
