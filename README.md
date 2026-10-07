# iShinyDex — Backend

O **gerador do catálogo** do [iShinyDex](https://github.com/nunesvictor/ishinydex):
importa os dados da [PokéAPI](https://pokeapi.co/) (espécies, formas, versões,
habilidades) e os exporta como o pacote `catalog.json`, que o app usa como
dados de referência. No GitHub, o workflow **Catálogo** gera o pacote e o
publica como release `catalog-AAAA.MM.DD`.

Django + PostgreSQL 17.

> **Quer usar o app?** Ele roda no navegador, sem servidor: veja o
> repositório principal, [**ishinydex**](https://github.com/nunesvictor/ishinydex).
>
> Até a `v1.0.0`, este repositório era também a API REST do app (servida por
> uWSGI). Desde a `v2.0.0`, os dados do usuário ficam nos aparelhos, e a API
> saiu ([#88](https://github.com/nunesvictor/ishinydex-backend/issues/88)).
> O comando `exportuserdata` leva os dados de um servidor antigo para o
> formato do app (Ajustes → Importar dados), e o admin do Django segue
> disponível no ambiente de desenvolvimento.

## Desenvolvimento e testes

```sh
cp .env.example src/.env && ln -s src/.env .env   # troque os change-me
docker compose up -d --build        # db, sprites e web (runserver em :8008)
# uma vez por cópia: o código montado esconde as traduções compiladas da imagem
docker compose exec web python manage.py compilemessages -l pt_BR
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

O banco não é publicado no host, e cada cópia do repositório (clone ou
worktree) tem os próprios volumes: o ambiente de dev nunca toca no banco do
app instalado.

| O que | Comando |
| --- | --- |
| Testes | `docker compose run --rm web python manage.py test --parallel 4` |
| Lint/format | `pre-commit run --all-files` |
| Backup / restauração | `python manage.py backupdb` / `restoredb` (em `backups/`) |
| Dados da PokeAPI | `python manage.py sync_pokeapi` (com `POKEAPI_URL=file:///…/api-data/data`, lê um clone do [api-data](https://github.com/PokeAPI/api-data), offline) |
| Pacote do catálogo (app local-first) | `python manage.py exportcatalog` → `catalog/catalog.json`; no GitHub, o workflow **Catálogo** gera e publica a release `catalog-AAAA.MM.DD` |
| Boxes do HOME e dex padrão | `python manage.py create_home_boxes` / `create_personal_dex -i` |

- **Gerador e formato do catálogo:** [`src/catalog/build.py`](src/catalog/build.py).
- **Fluxo de trabalho** (issues, PRs e CI): [CONTRIBUTING.md](CONTRIBUTING.md).
- **Dados versionados** do catálogo, que a PokéAPI não tem (formas e espécies pelo nome, com as fontes no próprio arquivo):
  - shiny locks padrão: [`src/pokedex/data/shiny_locks.json`](src/pokedex/data/shiny_locks.json);
  - exclusivos de versão: [`src/pokedex/data/version_exclusives.json`](src/pokedex/data/version_exclusives.json);
  - lendários fora das pokédex (Aventura Dinamax, Snacksworth): [`src/pokedex/data/special_encounters.json`](src/pokedex/data/special_encounters.json).
