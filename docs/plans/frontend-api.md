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
| GET | `/api/personal-dexes/{id}/generations/` | progresso por geração, **sem paginação**: `[{generation, total, registered, first_box: BoxRef}]`, na ordem em que as gerações aparecem nas boxes; `generation` é `null` para formas sem pokémon |
| GET | `/api/personal-dexes/preview/?force_new_box=` | simula um dex padrão sem criar: `{forms, boxes_needed, largest_free_run, enough_space, first_box: BoxRef \| null}` |
| POST | `/api/personal-dexes/` | `{name, is_shiny_dex?, force_new_box?}` → 201 com o dex (e contagens); cria com o conjunto padrão de formas e instala o esquema na 1ª sequência de boxes livres. Nome repetido → `{"name": [...]}`; sem espaço → `{"non_field_errors": [...]}` |
| GET | `/api/slots/?personal_dex=&box=&registered=true\|false&search=` | slots; com `box`, retorna os 30 slots **sem paginação**; `search` = nome da forma (`icontains`) ou número (Pokédex nacional da espécie ou `pokeapi_id` da forma), na ordem das boxes |
| GET | `/api/slots/{id}/` | um slot |
| POST | `/api/slots/{id}/deposit/` | `{specimen_id}` → 200 com o slot, ou 400 |
| POST | `/api/slots/{id}/withdraw/` | 200 com o slot (`specimen: null`); o app não usa mais (libertar = DELETE do specimen) |
| GET/POST | `/api/specimens/?form_id=&available=&is_shiny=&is_alpha=&is_from_go=&search=` + filtros abaixo | lista/cria specimens |
| GET/PUT/PATCH/DELETE | `/api/specimens/{id}/` | PATCH = editar (`form` imutável); DELETE = libertar, inclusive depositado |
| GET | `/api/specimens/options/` | choices de language, gender, nature, pokeball, type e generation |
| GET | `/api/forms/?search=` | formas (`FormRef`), busca por nome |
| GET | `/api/forms/{id}/` | `FormDetail` |
| GET/POST | `/api/trainers/?search=` | lista/cria OriginalTrainer |
| GET | `/api/versions/` | versões de jogo em ordem de lançamento, **sem paginação**: `[{name, version_group, generation}]`; `name` é o valor de `version` no POST de trainers |
| GET | `/api/pokemon/` | (já existia; agora exige autenticação) |

## Shapes

```jsonc
// FormRef (URLs absolutas; sprites HOME)
{"id": 1, "name": "bulbasaur", "form_name": "", "pokeapi_id": 1,
 "sprite_url": "http://host/media/sprites/pokemon/other/home/1.png",
 "shiny_sprite_url": "http://host/media/sprites/pokemon/other/home/shiny/1.png"}

// FormDetail = FormRef +
{"types": [{"slot": 1, "type": "grass",
            // ícone 60×60 (sword-shield/small); null se não houver arquivo
            "sprite_url": "http://host/media/sprites/types/generation-viii/sword-shield/small/12.png"}],
 "abilities": [{"slot": 1, "ability": "overgrow", "is_hidden": false}],
 "is_shinylocked": false, "is_distro_only": false}

// SpecimenSummary
{"id": 1, "nickname": null, "form_name": "bulbasaur", "ability": "overgrow", "is_shiny": true,
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
               "sprite_url": "http://host/media/sprites/items/poke-ball.png"}, ...],
 "type": [{"value": "water", "label": "Água",
           "sprite_url": "http://host/media/sprites/types/.../11.png"}, ...],  // sprite_url pode ser null
 "generation": [{"value": "generation-iv", "label": "Geração IV"}, ...]}
```

## Filtros de `/api/specimens/`

Listas aceitam vários valores separados por vírgula (**OU** entre os
valores, exceto `type`); filtros diferentes combinam com **E**. Valores
inválidos são ignorados.

| Parâmetro | Exemplo | Regra |
| --- | --- | --- |
| `pokeball` | `dive-ball,none` | `none` = sem pokébola |
| `type` | `water,flying` | a forma precisa ter **todos** os tipos |
| `ot` | `1,none` | ids de OriginalTrainer; `none` = sem OT |
| `generation` | `generation-i,generation-iv` | geração da espécie |
| `gender` / `nature` / `language` | `female,genderless` | |
| `ability` | `levitate` | contém (sem diferenciar maiúsculas) |
| `captured_after` / `captured_before` | `2026-01-01` | intervalo inclusivo de `captured_at` |
| `ordering` | `-captured_at` | `dex` (padrão), `captured_at`, `-captured_at` (sem data por último), `-created_at` |

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
- **Editar** (PUT/PATCH): `form` não pode mudar depois de criado → `{"form": [...]}`.
  Enviar a mesma forma é aceito.
- **Libertar** (DELETE → 204): apaga o specimen, mesmo depositado; o slot
  mantém a forma e fica faltante (`Slot.specimen` é `on_delete=SET_NULL`).
- Labels de nature ainda sem tradução pt-BR (caem no inglês) até definirmos os
  nomes; ver `api/choices.py` e `locale/pt_BR/LC_MESSAGES/django.po`.
