from django.urls import include, path

from .views.pokeapi import PokemonView

urlpatterns = [
    path("pokemon/<str:pokemon>/", PokemonView.as_view(), name="pokemon-view"),
    path("auth/", include("rest_framework.urls", namespace="rest_framework")),
]
