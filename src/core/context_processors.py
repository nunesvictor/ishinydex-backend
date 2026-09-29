from django.conf import settings


def environment(request) -> dict:
    """``is_dev_environment``: o admin se identifica como DEV quando
    ``DEBUG=True``. Lido a cada requisição (respeita ``override_settings``)."""
    return {"is_dev_environment": settings.DEBUG}
