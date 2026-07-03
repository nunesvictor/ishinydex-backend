from rest_framework import routers

from .views.pokedex import PokemonViewSet

app_name = "api"

router = routers.DefaultRouter()

router.register(r"pokemon", PokemonViewSet)

urlpatterns = router.urls
