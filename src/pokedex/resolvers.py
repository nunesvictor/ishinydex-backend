from pathlib import Path

from pokedex.models import Pokemon, PokemonForm


class PokemonSpriteResolver:
    def _resolve_female_path(self) -> Path:
        if self.pokemon is None or self.form is None:
            return Path()

        if self.pokemon.species.has_gender_differences and not self.form.is_default:
            return Path("female")

        return Path()

    def _resolve_shiny_path(self) -> Path:
        return Path("shiny" if self.shiny else "")

    def resolve(self, sprite_path: Path) -> Path:
        sprite_path /= self._resolve_shiny_path()
        sprite_path /= self._resolve_female_path()

        if self.form.is_default:
            return sprite_path / f"{self.pokemon.pokeapi_id}.png"

        if not sprite_path.name == "female" and self.pokemon.name != self.form.name:
            suffix = self.form.name.removeprefix(self.pokemon.name)
            return sprite_path / f"{self.pokemon.pokeapi_id}{suffix}.png"

        return sprite_path / f"{self.pokemon.pokeapi_id}.png"

    def __init__(self, pokemon: Pokemon | None, form: PokemonForm | None, shiny: bool):
        self.pokemon = pokemon
        self.form = form
        self.shiny = shiny


class SingleSpriteResolver(PokemonSpriteResolver):
    def resolve(self, sprite_path: Path) -> Path:
        sprite_path /= self._resolve_shiny_path()
        sprite_path /= self._resolve_female_path()

        return sprite_path / f"{self.pokemon.pokeapi_id}.png"
