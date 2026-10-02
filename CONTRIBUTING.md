# Fluxo de trabalho

Toda mudança entra na `main` por pull request, a partir de uma issue.

1. **Issue.** Descreva o problema ou a funcionalidade (em pt-BR), com o
   contexto e o que fica fora do escopo. Se a mudança também afeta o app,
   abra a issue irmã em
   [ishinydex-frontend](https://github.com/nunesvictor/ishinydex-frontend)
   e vincule as duas.
2. **Branch.** Uma por issue, nomeada `<número>-<resumo>` (ex.:
   `2-libertar-especime`), a partir da `main` atualizada.
3. **Pull request.** Preencha o template com `Closes #<número>`, para a issue
   fechar sozinha no merge. O CI ([ci.yml](.github/workflows/ci.yml)) roda
   o pre-commit e os testes (contra um Postgres 17) em todo PR, e precisa
   ficar verde. Quando o frontend depende do backend, o PR do backend é
   mergeado primeiro.
4. **Revisão e merge.** O dono do repositório revisa e faz **squash merge**,
   o único modo habilitado: vira um commit na `main` com o número do PR. A
   branch é apagada automaticamente.
5. **Deploy.** Só depois do merge, pelo repositório principal
   [ishinydex](https://github.com/nunesvictor/ishinydex): PR que atualiza
   o submodule para o commit da `main`, e depois
   `docker compose up -d --build` lá. O compose deste repositório é só
   para desenvolvimento e testes.

## Antes de abrir o PR

```sh
# 1ª vez nesta cópia: docker compose run --rm web python manage.py compilemessages -l pt_BR
docker compose run --rm web python manage.py test
pre-commit run --all-files
```

O pre-commit inclui o **pyright** (o motor do Pylance), com a config em
`[tool.pyright]` do `pyproject.toml`: o VS Code e o hook mostram os mesmos
erros, independente das configurações de usuário. O pyright não enxerga o que
o Django cria em runtime; anote no model o que o código usa (relações
reversas como `slots: "RelatedManager[Slot]"` e colunas `<fk>_id`). Ao subir
a versão de uma dependência, atualize também o `additional_dependencies` do
hook.
