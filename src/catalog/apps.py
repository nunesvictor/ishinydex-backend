from django.apps import AppConfig


class CatalogConfig(AppConfig):
    """O gerador do catálogo do app (``exportcatalog``): os dados de
    referência que o iShinyDex usa sem servidor (ishinydex#48)."""

    name = "catalog"
