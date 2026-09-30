from django.core.management import base


class BaseCommand(base.BaseCommand):
    """`BaseCommand` que aceita `help` lazy (`gettext_lazy`) na classe.

    O Django passa `self.help` como `description` do `ArgumentParser`, e o
    argparse do Python 3.14 formata esse texto com `re.sub`, que não aceita o
    proxy do `gettext_lazy` (`TypeError: expected string or bytes-like
    object, got '__proxy__'`). Aqui o texto é resolvido no idioma ativo na hora
    de montar o parser. Nos `help` de `add_arguments`, use `gettext` direto:
    eles já rodam nessa hora.
    """

    def create_parser(self, prog_name, subcommand, **kwargs):
        self.help = str(self.help)
        return super().create_parser(prog_name, subcommand, **kwargs)
