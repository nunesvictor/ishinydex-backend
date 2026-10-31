import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from core.tests import factories as f
from pokedex import showdown_moves
from pokedex.models import (
    Move,
    PokemonFormType,
    PokemonMoveLearn,
    PokemonType,
)
from pokedex.showdown_moves import (
    ShowdownMovesError,
    ShowdownMovesImporter,
    learn_method,
    showdown_id,
)
from pokedex.tests.showdown_fixtures import LEARNSETS, showdown_tree


class HelpersTests(SimpleTestCase):
    def test_showdown_id(self):
        self.assertEqual(showdown_id("floette-eternal"), "floetteeternal")
        self.assertEqual(showdown_id("mr-mime-galar"), "mrmimegalar")

    def test_learn_method(self):
        self.assertEqual(learn_method("9L12"), ("level-up", 12))
        self.assertEqual(learn_method("9M"), ("machine", 0))
        self.assertEqual(learn_method("8R"), ("form-change", 0))
        self.assertIsNone(learn_method("9S0"))

    def test_unknown_code_fails(self):
        with self.assertRaisesMessage(ShowdownMovesError, "desconhecido: 9E"):
            learn_method("9E")


class ShowdownMovesImporterTests(TestCase):
    def setUp(self):
        self.tmp = showdown_tree(**{"mods/gen9legends/learnsets.ts": LEARNSETS})
        self.addCleanup(self.tmp.cleanup)
        self.za = f.make_version_group(name="legends-za", order=30)
        self.sv = f.make_version_group(name="scarlet-violet", order=25)
        self.data = {
            "versionGroups": {
                "legends-za": "gen9legends",
                # Grupo que o banco não tem (import parcial): fica de fora.
                "legends-zz": "gen9zz",
            },
            "aliases": {"meowsticf": "meowstic-female"},
        }
        self.moves = {
            name: Move.objects.create(
                name=name,
                pp=10,
                priority=0,
                damage_class="special",
                generation="generation-i",
                target="selected-pokemon",
                type="ghost",
            )
            for name in (
                "astonish",
                "shadow-ball",
                "light-of-ruin",
                "tackle",
                "hydro-pump",
            )
        }
        species, self.pumpkaboo, _ = f.make_full_pokemon(
            "pumpkaboo-average", 710, types=("ghost", "grass")
        )
        species.name = "pumpkaboo"
        species.save()
        self.large = self.variety(species, "pumpkaboo-large", ("ghost", "grass"))
        self.variety(species, "pumpkaboo-mega", ("ghost", "grass"), is_mega=True)
        self.variety(species, "pumpkaboo-odd", ("ghost", "fire"))
        species, self.floette, _ = f.make_full_pokemon("floette", 670, types=("fairy",))
        self.eternal = self.variety(species, "floette-eternal", ("fairy",))
        species, _, _ = f.make_full_pokemon("meowstic-male", 678, types=("psychic",))
        species.name = "meowstic"
        species.save()
        self.female = self.variety(species, "meowstic-female", ("psychic",))
        species, _, _ = f.make_full_pokemon("rotom", 479, types=("electric", "ghost"))
        self.wash = self.variety(species, "rotom-wash", ("electric", "water"))
        # Golpe de outro jogo: fica.
        PokemonMoveLearn.objects.create(
            pokemon=self.floette,
            move=self.moves["tackle"],
            version_group=self.sv,
            method="level-up",
            level=5,
        )

    def variety(self, species, name, types, **form):
        pokemon = f.make_pokemon(species, name=name, is_default=False)
        made = f.make_form(pokemon, name=name, **form)
        for slot, type_ in enumerate(types, start=1):
            pokemon.types.add(PokemonType.objects.create(slot=slot, type=type_))
            made.types.add(PokemonFormType.objects.create(slot=slot, type=type_))
        return pokemon

    def run_import(self):
        file = Path(self.tmp.name) / "showdown_learnsets.json"
        file.write_text(json.dumps(self.data), encoding="utf-8")
        with mock.patch.object(showdown_moves, "SHOWDOWN_LEARNSETS_FILE", file):
            return ShowdownMovesImporter(self.tmp.name, log=lambda _: None).run()

    def learns(self, pokemon):
        return sorted(
            PokemonMoveLearn.objects.filter(
                pokemon=pokemon, version_group=self.za
            ).values_list("move__name", "method", "level")
        )

    def test_imports_moves_by_form(self):
        self.assertEqual(self.run_import(), 11)

        # A espécie dá a forma padrão; o "9M" e o "9L30" são duas linhas.
        self.assertEqual(
            self.learns(self.pumpkaboo),
            [
                ("astonish", "level-up", 1),
                ("shadow-ball", "level-up", 30),
                ("shadow-ball", "machine", 0),
            ],
        )
        # O nome sem pontuação, sem o golpe de evento.
        self.assertEqual(self.learns(self.eternal), [("light-of-ruin", "level-up", 50)])
        self.assertEqual(self.learns(self.floette), [("tackle", "level-up", 1)])
        # O alias e a troca de forma do Rotom.
        self.assertEqual(self.learns(self.female), [("shadow-ball", "machine", 0)])
        self.assertEqual(
            self.learns(self.wash),
            [("hydro-pump", "form-change", 0), ("shadow-ball", "machine", 0)],
        )

    def test_forms_not_in_showdown_take_the_default_moves(self):
        self.run_import()

        self.assertEqual(self.learns(self.large), self.learns(self.pumpkaboo))
        # Sem a mega, a forma de outros tipos e o pokémon padrão que o
        # Showdown não lista (o Rotom e o Meowstic macho).
        self.assertEqual(
            set(
                PokemonMoveLearn.objects.filter(version_group=self.za).values_list(
                    "pokemon__name", flat=True
                )
            ),
            {
                "pumpkaboo-average",
                "pumpkaboo-large",
                "floette",
                "floette-eternal",
                "meowstic-female",
                "rotom-wash",
            },
        )

    def test_runs_again_without_duplicates_and_keeps_other_games(self):
        self.run_import()

        self.assertEqual(self.run_import(), 11)
        self.assertEqual(
            PokemonMoveLearn.objects.filter(version_group=self.sv).count(), 1
        )

    def test_form_without_pair_fails(self):
        del self.data["aliases"]["meowsticf"]

        with self.assertRaisesMessage(
            ShowdownMovesError, "sem par na PokéAPI: meowsticf"
        ):
            self.run_import()

    def test_move_without_pair_fails(self):
        self.moves["hydro-pump"].delete()

        with self.assertRaisesMessage(
            ShowdownMovesError, "sem par na PokéAPI: hydropump"
        ):
            self.run_import()

    def test_missing_mod_fails(self):
        self.data["versionGroups"]["legends-za"] = "gen9zz"

        with self.assertRaisesMessage(
            ShowdownMovesError, "gen9zz/learnsets.ts não existe"
        ):
            self.run_import()


class ShippedShowdownLearnsetsTests(SimpleTestCase):
    def test_file_is_well_formed(self):
        data = json.loads(
            showdown_moves.SHOWDOWN_LEARNSETS_FILE.read_text(encoding="utf-8")
        )
        self.assertEqual(set(data), {"sources", "notes", "versionGroups", "aliases"})
        self.assertEqual(data["versionGroups"], {"legends-za": "gen9legends"})
        self.assertEqual(list(data["aliases"]), sorted(data["aliases"]))


class SyncShowdownMovesCommandTests(TestCase):
    def setUp(self):
        self.tmp = showdown_tree(**{"mods/gen9legends/learnsets.ts": LEARNSETS})
        self.addCleanup(self.tmp.cleanup)
        f.make_version_group(name="legends-za")
        _, self.floette, _ = f.make_full_pokemon("floette", 670, types=("fairy",))
        Move.objects.create(
            name="tackle",
            pp=35,
            priority=0,
            damage_class="physical",
            generation="generation-i",
            target="selected-pokemon",
            type="normal",
        )
        file = Path(self.tmp.name) / "showdown_learnsets.json"
        file.write_text(
            json.dumps({"versionGroups": {"legends-za": "gen9legends"}, "aliases": {}}),
            encoding="utf-8",
        )
        patcher = mock.patch.object(showdown_moves, "SHOWDOWN_LEARNSETS_FILE", file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_imports_and_fails_on_forms_without_pair(self):
        # Só a Floette existe no banco: as outras formas falham.
        with self.assertRaisesMessage(CommandError, "sem par na PokéAPI"):
            call_command("sync_showdown_moves", self.tmp.name, stdout=StringIO())

    def test_imports(self):
        text = (
            LEARNSETS.split("\tpumpkaboo")[0]
            + "\tfloette"
            + LEARNSETS.split("\tfloette")[1].split("\tfloetteeternal")[0]
            + "};\n"
        )
        (Path(self.tmp.name) / "data/mods/gen9legends/learnsets.ts").write_text(
            text, encoding="utf-8"
        )
        out = StringIO()
        call_command("sync_showdown_moves", self.tmp.name, stdout=out)

        self.assertIn("move_learns=1", out.getvalue())
        self.assertEqual(PokemonMoveLearn.objects.get().pokemon, self.floette)

    def test_clone_without_the_mod_fails(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaisesMessage(CommandError, "learnsets.ts não existe"):
                call_command("sync_showdown_moves", empty, stdout=StringIO())
