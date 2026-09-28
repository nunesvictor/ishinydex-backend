from rest_framework import viewsets

from pokedex.models import Pokemon

from ..filters import PokemonFromFormFilterBackend
from ..serializers.pokedex import PokemonSerializer


class PokemonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Pokemon.objects.prefetch_related("abilities", "stats", "types")
    serializer_class = PokemonSerializer
    filter_backends = (PokemonFromFormFilterBackend,)
