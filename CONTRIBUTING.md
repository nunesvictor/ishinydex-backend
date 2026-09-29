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
   fechar sozinha no merge. Quando o frontend depende do backend, o PR do
   backend é mergeado primeiro.
4. **Revisão e merge.** O dono do repositório revisa e faz **squash merge**,
   o único modo habilitado: vira um commit na `main` com o número do PR. A
   branch é apagada automaticamente.
5. **Deploy local.** Só depois do merge:
   `docker compose --profile prod up -d --build prod`.

## Antes de abrir o PR

```sh
docker compose exec web python manage.py test
pre-commit run --all-files
```
