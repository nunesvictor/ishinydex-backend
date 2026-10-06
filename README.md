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
> Até a `v1.0.0`, este repositório era também a API REST e o admin do app.
> Desde a `v2.0.0`, os dados do usuário ficam nos aparelhos, e a API não é
> mais usada; a limpeza desse código está em
> [#88](https://github.com/nunesvictor/ishinydex-backend/issues/88). O comando
> `exportuserdata` leva os dados de um servidor antigo para o formato do app
> (Ajustes → Importar dados).

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

- **Contrato da API usada pelo app:** [`docs/plans/frontend-api.md`](docs/plans/frontend-api.md).
  Com o servidor rodando, o Swagger fica em `/api/docs/`.
- **Fluxo de trabalho** (issues, PRs e CI): [CONTRIBUTING.md](CONTRIBUTING.md).
- **Shiny locks padrão** do catálogo: [`src/pokedex/data/shiny_locks.json`](src/pokedex/data/shiny_locks.json) (formas pelo nome).
