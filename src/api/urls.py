from django.urls import path

from rest_framework import routers
from rest_framework.authtoken.views import ObtainAuthToken

from .views.home import (
    FormViewSet,
    PersonalDexViewSet,
    SaveViewSet,
    SlotViewSet,
    SpecimenViewSet,
    TrainerViewSet,
    VersionViewSet,
)
from .views.pokedex import PokemonViewSet

app_name = "api"

router = routers.DefaultRouter()

router.register(r"pokemon", PokemonViewSet)
router.register(r"personal-dexes", PersonalDexViewSet, basename="personal-dex")
router.register(r"slots", SlotViewSet, basename="slot")
router.register(r"specimens", SpecimenViewSet, basename="specimen")
router.register(r"forms", FormViewSet, basename="form")
router.register(r"trainers", TrainerViewSet, basename="trainer")
router.register(r"saves", SaveViewSet, basename="save")
router.register(r"versions", VersionViewSet, basename="version")

urlpatterns = [
    # Sem autenticação: um cookie de sessão (ex.: do admin, na mesma origem)
    # faria o SessionAuthentication exigir CSRF no login.
    path(
        "auth/token/",
        ObtainAuthToken.as_view(authentication_classes=[]),
        name="auth-token",
    ),
    *router.urls,
]
