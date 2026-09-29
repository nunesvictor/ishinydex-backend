Closes #

## O que muda

## Como testar

## Checklist
- [ ] `python manage.py test` passa (no container: `docker compose exec web python manage.py test`)
- [ ] `pre-commit` passa (black, isort, flake8)
- [ ] Mudou a API? `docs/plans/frontend-api.md` atualizado e issue/PR irmão no frontend vinculado
- [ ] Migrações criadas e revisadas, se o modelo mudou
