# iShinyDex — Backend

API REST e admin do **iShinyDex**, gerenciador pessoal de PersonalDex no estilo
das boxes do Pokémon HOME: formas (dados da PokeAPI), boxes espelhadas do HOME,
PersonalDexes, espécimes (shiny, alfa, pokébola, OT…) e o depósito nos slots.

Django + Django REST Framework, PostgreSQL 17, uWSGI em produção.

> **Rodar o app completo (backend + frontend):** use o repositório
> [**ishinydex**](https://github.com/nunesvictor/ishinydex), que junta os dois
> como submodules e sobe tudo com um `docker compose up -d --build`. Este
> repositório é o código do backend e o ambiente de desenvolvimento dele.

## Desenvolvimento

```sh
cp .env.prod.example src/.env && ln -s src/.env .env   # troque os change-me
docker compose up -d --build        # db, sprites, web (runserver :8008) e jupyter
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

| O que | Comando |
| --- | --- |
| Testes | `docker compose exec web python manage.py test` |
| Lint/format | `pre-commit run --all-files` |
| Imagem de produção local (uWSGI, `:8080`) | `docker compose --profile prod up -d --build prod` |
| Backup / restauração | `python manage.py backupdb` / `restoredb` (em `backups/`) |
| Dados da PokeAPI | `python manage.py sync_pokeapi` |
| Boxes do HOME e dex padrão | `python manage.py create_home_boxes` / `create_personal_dex -i` |

- **Contrato da API usada pelo app:** [`docs/plans/frontend-api.md`](docs/plans/frontend-api.md).
  Com o servidor rodando, o Swagger fica em `/api/docs/`.
- **Fluxo de trabalho** (issues, PRs e CI): [CONTRIBUTING.md](CONTRIBUTING.md).
