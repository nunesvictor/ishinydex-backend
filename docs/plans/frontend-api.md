# API REST para o frontend Flutter (PersonalDex)

Contrato da API usada pelo `ishinydex-frontend` (web responsiva + iOS via PWA),
focado no PersonalDex: visualizar o dex e depositar specimens.

Schema OpenAPI: `GET /api/schema/` · Swagger UI: `GET /api/docs/` (públicos).

## Configuração

- Dependências: `django-cors-headers`, `drf-spectacular`.
- Autenticação: `Authorization: Token <key>` (também aceita sessão do admin).
  Toda a API exige autenticação (`IsAuthenticated`); sem credenciais → **401**
  com `WWW-Authenticate: Token`.
- CORS: `FRONTEND_ORIGINS` (env, separado por vírgula) → `CORS_ALLOWED_ORIGINS`.
  Com `DEBUG=True`, `http://localhost:<porta>` e `http://127.0.0.1:<porta>`
  também são aceitos.
- Paginação (`api.pagination.PageNumberPagination`): `?page=`, `?page_size=`
  (padrão 10, máximo 100). Resposta `{count, next, previous, results}`.
- Erros de validação no formato DRF `{campo: [msg]}` (ou
  `{non_field_errors: [msg]}`), com mensagens em pt-BR.

## Endpoints

| Método | Rota | Descrição |
| --- | --- | --- |
| POST | `/api/auth/token/` | `{username, password}` → `{token}` |
| GET | `/api/personal-dexes/` | lista paginada de dexes |
| GET | `/api/personal-dexes/{id}/` | um dex |
| GET | `/api/personal-dexes/{id}/boxes/` | boxes com slots do dex, por `position`, **sem paginação** |
| GET | `/api/slots/?personal_dex=&box=&registered=true\|false` | slots; com `box`, retorna os 30 slots **sem paginação** |
| GET | `/api/slots/{id}/` | um slot |
| POST | `/api/slots/{id}/deposit/` | `{specimen_id}` → 200 com o slot, ou 400 |
| POST | `/api/slots/{id}/withdraw/` | 200 com o slot (`specimen: null`) |
| GET/POST | `/api/specimens/?form_id=&available=&is_shiny=&search=` | lista/cria specimens |
| GET/PUT/PATCH/DELETE | `/api/specimens/{id}/` | DELETE de specimen depositado → 400 |
| GET | `/api/specimens/options/` | choices de language, gender, nature e pokeball |
| GET | `/api/forms/?search=` | formas (`FormRef`), busca por nome |
| GET | `/api/forms/{id}/` | `FormDetail` |
| GET/POST | `/api/trainers/?search=` | lista/cria OriginalTrainer |
| GET | `/api/pokemon/` | (já existia; agora exige autenticação) |

## Shapes

```jsonc
// FormRef (URLs absolutas; sprites HOME)
{"id": 1, "name": "bulbasaur", "form_name": "", "pokeapi_id": 1,
 "sprite_url": "http://host/media/sprites/pokemon/other/home/1.png",
 "shiny_sprite_url": "http://host/media/sprites/pokemon/other/home/shiny/1.png"}

// FormDetail = FormRef +
{"types": [{"slot": 1, "type": "grass"}],
 "abilities": [{"slot": 1, "ability": "overgrow", "is_hidden": false}],
 "is_shinylocked": false, "is_distro_only": false}

// SpecimenSummary
{"id": 1, "nickname": null, "form_name": "bulbasaur", "is_shiny": true,
 "is_alpha": false, "pokeball": "dream-ball",
 "pokeball_sprite_url": "http://host/media/sprites/items/dream-ball.png"}

// Specimen: todos os campos do model +
//   form (id, escrita), form_ref (FormRef, leitura),
//   pokeball_sprite_url (leitura), slot (id do slot onde está depositado | null)

// Slot
{"id": 1, "box": {"id": 1, "name": "HOME 1", "position": 1}, "row": 0, "col": 0,
 "personal_dex": 1, "form": FormRef | null, "specimen": SpecimenSummary | null,
 "is_shiny_display": true}  // specimen shiny, ou slot vazio (com forma) num dex shiny

// PersonalDex
{"id": 1, "name": "Shiny Living Dex", "is_shiny_dex": true, "force_new_box": true,
 "total": 1227,       // slots do dex com forma
 "registered": 1158}  // slots do dex com forma e specimen

// BoxSummary (contagens restritas ao dex)
{"id": 1, "name": "HOME 1", "position": 1, "total": 30, "registered": 28}

// Trainer (version pelo nome da Version, opcional)
{"id": 1, "name": "Ash", "trainer_id": "123456", "version": "scarlet"}

// /specimens/options/
{"language": [{"value": "pt-br", "label": "Português brasileiro"}, ...],
 "gender": [{"value": "male", "label": "Macho"}, ...],
 "nature": [{"value": "adamant", "label": "Adamant"}, ...],
 "pokeball": [{"value": "poke-ball", "label": "Poké Ball",
               "sprite_url": "http://host/media/sprites/items/poke-ball.png"}, ...]}
```

## Regras

- **Depósito** (`transaction.atomic` + `select_for_update` no slot e no specimen):
  - slot sem forma → `{"non_field_errors": [...]}`
  - forma do specimen ≠ forma do slot (regra de `Slot.clean`) → `{"specimen_id": [...]}`
  - specimen depositado em outro slot → `{"specimen_id": [...]}`
  - specimen inexistente → `{"specimen_id": [...]}`
  - redepositar no mesmo slot é permitido; depositar num slot ocupado substitui
    o specimen anterior (que volta a ficar disponível).
- **Ability** do specimen deve pertencer às abilities do pokémon da forma
  (mesma regra do `SpecimenAdminForm`) → `{"ability": [...]}`.
- **DELETE** de specimen depositado → 400 `{"detail": "..."}`.
- Labels de nature ainda sem tradução pt-BR (caem no inglês) até definirmos os
  nomes; ver `api/choices.py` e `locale/pt_BR/LC_MESSAGES/django.po`.
