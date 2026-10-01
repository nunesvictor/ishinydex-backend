# iShinyDex — Backend

API REST e admin do **iShinyDex**, gerenciador pessoal de PersonalDex no estilo
das boxes do Pokémon HOME: formas (dados da PokeAPI), boxes espelhadas do HOME,
PersonalDexes, espécimes (shiny, alfa, pokébola, OT…) e o depósito nos slots.

Django + Django REST Framework, PostgreSQL 17, uWSGI em produção.

> **Este repositório não é para deploy.** Para instalar e rodar o iShinyDex
> (backend + frontend), clone o repositório principal
> [**ishinydex**](https://github.com/nunesvictor/ishinydex), que traz este
> código como submodule e sobe tudo com um comando:
>
> ```sh
> git clone --recurse-submodules https://github.com/nunesvictor/ishinydex.git
> cd ishinydex && cp .env.example .env   # troque os change-me
> docker compose up -d --build           # app em http://<host>:8090
> ```
>
> O `Dockerfile` daqui é usado por esse compose. Já o `docker-compose.yml`
> e o `.env.example` deste repositório são só para **desenvolvimento e
> testes**.

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
| Testes | `docker compose run --rm web python manage.py test` |
| Lint/format | `pre-commit run --all-files` |
| Backup / restauração | `python manage.py backupdb` / `restoredb` (em `backups/`) |
| Dados da PokeAPI | `python manage.py sync_pokeapi` |
| Boxes do HOME e dex padrão | `python manage.py create_home_boxes` / `create_personal_dex -i` |

- **Contrato da API usada pelo app:** [`docs/plans/frontend-api.md`](docs/plans/frontend-api.md).
  Com o servidor rodando, o Swagger fica em `/api/docs/`.
- **Fluxo de trabalho** (issues, PRs e CI): [CONTRIBUTING.md](CONTRIBUTING.md).
