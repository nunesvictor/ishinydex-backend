from django.test import TestCase

from core.tests import factories as f
from pokedex.models import (
    PokemonForm,
    PokemonSpeciesDexEntry,
    PokemonSpeciesVariety,
    PokemonStat,
    ShinyLock,
    VersionGameIndex,
)


class PokemonFormTests(TestCase):
    def setUp(self):
        _, _, self.form = f.make_full_pokemon("zarude", 893)

    def test_str_without_shinylock(self):
        self.assertEqual(str(self.form), "zarude")
        self.assertFalse(self.form.is_shinylocked)
        self.assertFalse(self.form.is_distro_only)

    def test_unobtainable_lock(self):
        f.make_shinylock(self.form, lock_type=ShinyLock.LockTypeChoices.UNOBTAINABLE)

        self.assertEqual(str(self.form), "zarude🔒")
        self.assertTrue(self.form.is_shinylocked)
        self.assertFalse(self.form.is_distro_only)

    def test_distro_only_lock(self):
        f.make_shinylock(self.form, lock_type=ShinyLock.LockTypeChoices.DISTRO_ONLY)

        self.assertEqual(str(self.form), "zarude🎁")
        self.assertTrue(self.form.is_distro_only)
        self.assertFalse(self.form.is_shinylocked)

    def test_inactive_lock_has_no_suffix(self):
        f.make_shinylock(self.form, active=False)

        self.assertEqual(str(self.form), "zarude")

    def test_str_of_unsaved_form(self):
        """Regressão: str() de forma não salva gerava RecursionError."""
        self.assertEqual(str(PokemonForm(name="bulbasaur")), "bulbasaur")
        self.assertEqual(
            repr(PokemonForm(name="bulbasaur")), "<PokemonForm: bulbasaur>"
        )

    def test_default_lock_type_is_unobtainable(self):
        lock = f.make_shinylock(self.form)

        self.assertEqual(lock.lock_type, ShinyLock.LockTypeChoices.UNOBTAINABLE)
        self.assertEqual(str(lock), lock.caption)


class StrRepresentationTests(TestCase):
    def test_species_pokemon_and_variety(self):
        species, pokemon, _ = f.make_full_pokemon("bulbasaur", 1)
        variety = PokemonSpeciesVariety.objects.create(
            is_default=False, pokemon=pokemon
        )

        self.assertEqual(str(species), "bulbasaur")
        self.assertEqual(str(pokemon), "bulbasaur")
        self.assertEqual(str(species.varieties.get()), "bulbasaur (default)")
        self.assertEqual(str(variety), "bulbasaur")

    def test_dex_entry_and_stat(self):
        entry = PokemonSpeciesDexEntry(entry_number=25, pokedex="national")
        stat = PokemonStat(stat="speed", effort=2, base_stat=90)

        self.assertEqual(str(entry), "national#25")
        self.assertEqual(str(stat), "speed: 90")

    def test_version_and_game_index(self):
        version = f.make_version(name="red")
        index = VersionGameIndex.objects.create(game_index=153, version=version)

        self.assertEqual(str(version), "red")
        self.assertEqual(str(index), "red#153")
        self.assertEqual(str(version.version_group), version.version_group.name)
