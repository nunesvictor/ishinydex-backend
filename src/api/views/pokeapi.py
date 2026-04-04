import pokebase as pb
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers.pokeapi import PokemonSerializer


class PokemonView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            pokemon = pb.pokemon(kwargs.get("pokemon"))
            serializer = PokemonSerializer(pokemon)

            return Response(serializer.data, status=status.HTTP_200_OK)
        except BaseException as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
