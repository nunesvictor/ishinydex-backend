import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from django.test import SimpleTestCase, override_settings

from home.choices import Pokeball

# Para o pyright, o mixin "é" um TestCase (setUp, addCleanup...); em runtime
# continua um object, combinado com o TestCase de cada classe de teste.
_TestCaseBase = SimpleTestCase if TYPE_CHECKING else object


class TempSpritesMixin(_TestCaseBase):
    """Aponta BASE_DIR para um diretório temporário (por teste) com sprites.

    Os renderers resolvem caminhos como ``BASE_DIR / "media/sprites/..."`` e
    verificam se o arquivo existe; assim os testes não dependem do volume de
    sprites real. Use ``self.add_sprite("pokemon/1.png")`` para criar arquivos.

    Por padrão já cria os sprites de todas as pokébolas, exigidos pelos forms
    de Specimen.
    """

    create_pokeball_sprites = True

    def setUp(self):
        super().setUp()

        self.sprites_tmp = Path(tempfile.mkdtemp(prefix="sprites-test-"))
        self.addCleanup(shutil.rmtree, self.sprites_tmp, ignore_errors=True)

        sprites_override = override_settings(BASE_DIR=self.sprites_tmp)
        sprites_override.enable()
        self.addCleanup(sprites_override.disable)

        if self.create_pokeball_sprites:
            for ball in Pokeball:
                self.add_sprite(f"items/{ball.value}.png")

    def add_sprite(self, relative_path: str) -> Path:
        path = self.sprites_tmp / "media" / "sprites" / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path
