Closes #

## O que muda

## Como testar

## Checklist
- [ ] CI verde (pre-commit e testes); localmente: `docker compose run --rm web python manage.py test` e `pre-commit run --all-files`
- [ ] Mudou o catálogo? `catalog/build.py` (e o `SCHEMA_VERSION`, se incompatível) e issue/PR irmão no frontend vinculado
- [ ] Migrações criadas e revisadas, se o modelo mudou
