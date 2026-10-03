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
| PATCH | `/api/personal-dexes/{id}/` | `{name?, is_shiny_dex?}` → 200 com o dex (e contagens); `force_new_box` é ignorado (o esquema já está nas boxes). Nome repetido → `{"name": [...]}`. Sem `PUT` (405) |
| DELETE | `/api/personal-dexes/{id}/` | 204; libera os slots do dex (sem forma, dex nem espécime), deixando as boxes livres para outro dex. Os espécimes depositados **continuam** no inventário, disponíveis |
| GET | `/api/personal-dexes/{id}/boxes/` | boxes com slots do dex, por `position`, **sem paginação** |
| GET | `/api/personal-dexes/{id}/generations/` | progresso por geração, **sem paginação**: `[{generation, total, registered, away, first_box: BoxRef}]` (`registered` e `away` com as regras do `PersonalDex`), na ordem em que as gerações aparecem nas boxes; `generation` é `null` para formas sem pokémon |
| POST | `/api/personal-dexes/{id}/link-specimens/` | depositar automaticamente: `{"strict"?: false, "dry_run"?: false}` → `{"linked": n, "missing": m, "slots": Slot[]}` (ver [Depositar automaticamente](#depositar-automaticamente)) |
| GET | `/api/personal-dexes/{id}/hunts/` | lista de caçadas de um **shiny dex** (paginada, na ordem das boxes): `Hunt[]`; dex que não é shiny dex → 400 `{"detail": ...}`. Filtros em [Caçadas](#caçadas-de-apipersonal-dexesidhunts) |
| GET | `/api/personal-dexes/preview/?force_new_box=` | simula um dex padrão sem criar: `{forms, boxes_needed, largest_free_run, enough_space, boxes_to_create, first_box: BoxRef \| null}`; sem sequência livre que caiba, completa a sequência livre do fim com `boxes_to_create` boxes novas (até 200, o limite do HOME); `first_box` é `null` sem espaço ou quando o dex fica todo em boxes novas |
| POST | `/api/personal-dexes/` | `{name, is_shiny_dex?, force_new_box?}` → 201 com o dex (e contagens); cria com o conjunto padrão de formas, na [ordem canônica](#ordem-canônica-das-formas) (com `force_new_box`, cada geração da espécie começa no 1º slot de uma box), e instala o esquema na 1ª sequência de boxes livres (ou cria no fim as boxes que faltam, como no preview). Nome repetido → `{"name": [...]}`; sem espaço → `{"non_field_errors": [...]}` |
| GET | `/api/slots/?personal_dex=&box=&registered=true\|false&search=` | slots; com `box`, retorna os 30 slots **sem paginação**; `search` = nome da forma (`icontains`, [como slug](#busca-por-nome)) ou número (Pokédex nacional da espécie ou `pokeapi_id` da forma), na ordem das boxes |
| GET | `/api/slots/{id}/` | um slot |
| POST | `/api/slots/{id}/deposit/` | `{specimen_id}` → 200 com o slot, ou 400 |
| POST | `/api/slots/{id}/withdraw/` | 200 com o slot (`specimen: null`); o app não usa mais (libertar = DELETE do specimen) |
| GET/POST | `/api/specimens/?form_id=&available=&is_shiny=&is_alpha=&is_from_go=&search=` + filtros abaixo | lista/cria specimens; `search` = apelido (texto cru) ou nome da forma ([como slug](#busca-por-nome)), `icontains`, ou, se for número, Pokédex nacional da espécie ou `pokeapi_id` da forma |
| GET/PUT/PATCH/DELETE | `/api/specimens/{id}/` | PATCH = editar (`form` imutável); DELETE = libertar, inclusive depositado |
| GET | `/api/specimens/ids/?` + filtros de `/specimens/` | ids de todos os espécimes do filtro, na ordem da lista, **sem paginação**: `[1, 2, ...]` |
| PATCH | `/api/specimens/bulk/` | edição em lote (ver Regras): `{"ids": [...], "changes": {...}}` → `{"updated": n}` |
| POST | `/api/specimens/bulk-release/` | libertar em lote: `{"ids": [...]}` → `{"released": n}`; tudo ou nada (id inexistente ou lista vazia → `{"ids": [...]}`, nada é apagado); depositados deixam o slot vazio, como o `DELETE` |
| GET | `/api/specimens/options/` | choices de language, gender, nature, pokeball, type, generation e origin_mark |
| GET | `/api/forms/?search=` | formas (`FormRef`), busca por nome ([como slug](#busca-por-nome)), na [ordem canônica](#ordem-canônica-das-formas) |
| GET | `/api/forms/{id}/` | `FormDetail` |
| GET/POST | `/api/trainers/?search=` | lista/cria OriginalTrainer |
| GET/POST | `/api/saves/` | saves do usuário, **sem paginação**: `Save[]`; POST `{"trainer": id, "label"?}` → 201 `Save`. Só OT com versão de jogo que recebe do HOME (ver [Saves](#saves-e-localização)); OT que já é save → 400 `{"trainer": [...]}` |
| GET/PATCH/DELETE | `/api/saves/{id}/` | PATCH só `label` (trocar `trainer` → 400); DELETE 204, ou 400 `{"detail": ...}` se ainda há espécimes no save |
| POST | `/api/specimens/transfer/` | `{"ids": [...], "save": id \| null}` → `{"transferred": n}` (quantos mudaram de lugar); `null` traz de volta ao HOME. Tudo ou nada, como o bulk |
| POST | `/api/specimens/{id}/evolve/` | `{"form": id}` → `Specimen`: o espécime evoluiu fora do HOME (ver [Saves](#saves-e-localização)) |
| GET/POST | `/api/shiny-locks/` | shiny locks em ordem alfabética, **sem paginação**: `ShinyLock[]`; POST `{"caption", "description"?, "lock_type"?, "active"?, "forms": [id, ...]}` → 201 `ShinyLock` (ver [Shiny locks](#shiny-locks)) |
| GET/PATCH/DELETE | `/api/shiny-locks/{id}/` | PATCH parcial, mesmos campos (PUT não); DELETE 204 (as formas continuam, só o lock sai) |
| GET | `/api/versions/` | versões de jogo em ordem de lançamento, **sem paginação**: `[{name, version_group, generation}]`; `name` é o valor de `version` no POST de trainers |
| GET | `/api/pokemon/` | (já existia; agora exige autenticação) |

### Busca por nome

Nomes de forma (`name`, `form_name` do espécime) e habilidades são slugs da
PokéAPI (`iron-hands`, `solar-power`). A busca converte o texto digitado com o
`slugify` do Django antes do `icontains`: minúsculas, sem acento, espaços
viram `-` e pontuação some (`Iron Hands` → `iron-hands`, `Mr. Mime` →
`mr-mime`, `Flabébé` → `flabebe`). Se não sobrar nada (só pontuação), usa o
texto cru. Apelido e treinador são texto livre e não passam por isso.

## Shapes

```jsonc
// FormRef (URLs absolutas; sprites HOME). national_number: nº da espécie na
// Pokédex nacional (igual para formas alternativas; null se não houver)
{"id": 1, "name": "bulbasaur", "form_name": "", "pokeapi_id": 1, "national_number": 1,
 "sprite_url": "http://host/media/sprites/pokemon/other/home/1.png",
 "shiny_sprite_url": "http://host/media/sprites/pokemon/other/home/shiny/1.png"}

// FormDetail = FormRef +
{"types": [{"slot": 1, "type": "grass",
            // ícone 60×60 (sword-shield/small); null se não houver arquivo
            "sprite_url": "http://host/media/sprites/types/generation-viii/sword-shield/small/12.png"}],
 "abilities": [{"slot": 1, "ability": "overgrow", "is_hidden": false}],
 "stats": [{"stat": "hp", "base_stat": 45, "effort": 0}, ...],  // ordem dos jogos: hp,
                     // attack, defense, special-attack, special-defense, speed; [] sem pokémon
 "is_shinylocked": false, "is_distro_only": false}

// SpecimenSummary
{"id": 1, "nickname": null, "form_name": "bulbasaur", "ability": "overgrow", "is_shiny": true,
 "is_alpha": false, "is_from_go": false, "gender": "female", "pokeball": "dream-ball",
 "pokeball_sprite_url": "http://host/media/sprites/items/dream-ball.png",
 "location": Save | null,         // null = no HOME
 "location_since": "2026-03-12"}  // data em que saiu (null no HOME)

// Save
{"id": 1, "label": "Switch Lite",  // label pode ser ""
 "trainer": Trainer}

// Specimen: todos os campos do model +
//   form (id, escrita), form_ref (FormRef, leitura),
//   pokeball_sprite_url (leitura), slot (id do slot onde está depositado | null),
//   origin_version (nome da Version | null, leitura; derivado do OT, ver Regras),
//   origin_mark ("paldea" | "galar" | ... | "go" | null, leitura),
//   location (Save | null) e location_since (data | null), leitura: só mudam
//   por /specimens/transfer/

// Slot
{"id": 1, "box": {"id": 1, "name": "HOME 1", "position": 1}, "row": 0, "col": 0,
 "personal_dex": 1, "form": FormRef | null, "specimen": SpecimenSummary | null,
 "is_shiny_display": true}  // specimen shiny, ou slot vazio (com forma) num dex shiny

// Hunt = Slot +
{"reasons": ["no_shiny"],   // todos os motivos em que o slot se encaixa (no_shiny, from_go, pokeball)
 "shiny_lock": null}        // null | "distro-only" | "unobtainable" (só com include_locked)

// ShinyLock (forms: FormRef na ordem da dex nacional; na escrita, ids)
{"id": 25, "caption": "Treasures of Ruin", "description": null,
 "lock_type": "distro-only",   // "unobtainable" (padrão) | "distro-only"
 "active": true, "forms": [FormRef, ...]}

// PersonalDex
{"id": 1, "name": "Shiny Living Dex", "is_shiny_dex": true, "force_new_box": true,
 "total": 1227,       // slots do dex com forma
 "registered": 1158,   // slots do dex com forma e specimen que conta no progresso:
                      // num shiny dex, só shiny (o não shiny pode estar no slot,
                      // mas não conta); num dex normal, qualquer um. Fora do
                      // HOME também conta
 "away": 3}           // desses registered, os que estão num save

// BoxSummary (contagens restritas ao dex; registered e away com as mesmas regras)
{"id": 1, "name": "HOME 1", "position": 1, "total": 30, "registered": 28, "away": 2}

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
 "generation": [{"value": "generation-iv", "label": "Geração IV"}, ...],
 "origin_mark": [{"value": "paldea", "label": "SV"}, ...,
                 {"value": "go", "label": "Pokémon GO"},
                 {"value": "none", "label": "Sem marca de origem"}]}
```

## Filtros de `/api/specimens/`

Listas aceitam vários valores separados por vírgula (**OU** entre os
valores, exceto `type`); filtros diferentes combinam com **E**. Valores
inválidos são ignorados.

| Parâmetro | Exemplo | Regra |
| --- | --- | --- |
| `id` | `3,7,12` | ids dos espécimes (ex.: "só selecionados" do lote); não numéricos são ignorados |
| `location` | `home`, `away`, `4` | no HOME, fora (em qualquer save) ou no save de id 4 |
| `pokeball` | `dive-ball,none` | `none` = sem pokébola |
| `type` | `water,flying` | a forma precisa ter **todos** os tipos |
| `ot` | `1,none` | ids de OriginalTrainer; `none` = sem OT |
| `generation` | `generation-i,generation-iv` | geração da espécie |
| `category` | `legendary,ultra-beast` | categoria da espécie, como nas [caçadas](#caçadas-de-apipersonal-dexesidhunts): qualquer uma de `legendary`, `mythical`, `ultra-beast`, `baby`, `regular` |
| `origin_mark` | `paldea,go` | marca de origem (ver Regras); `none` = sem marca |
| `gender` / `nature` / `language` | `female,genderless` | |
| `ability` | `levitate`, `solar power` | contém (sem diferenciar maiúsculas, [como slug](#busca-por-nome)) |
| `captured_after` / `captured_before` | `2026-01-01` | intervalo inclusivo de `captured_at` |
| `ordering` | `-captured_at` | `box` (padrão: posição nas boxes — o próprio slot se depositado, senão o 1º slot com a forma, em qualquer dex; fora das boxes por último), `national` (nº da Pokédex nacional; formas da mesma espécie juntas, por `form_order`), `captured_at`, `-captured_at` (sem data por último), `-created_at`. Valor desconhecido → `box` |

## Caçadas de `/api/personal-dexes/{id}/hunts/`

Slots (com forma) de um shiny dex que ainda precisam ser caçados. Dois
grupos de filtros:

- **Motivos** (`reasons`, **OU** entre si): por que o slot entra na lista.
  Sem o parâmetro, vale `no_shiny`; motivos desconhecidos são ignorados
  (`reasons=` vazio → lista vazia). A resposta traz em `reasons` **todos**
  os motivos do slot, não só os pedidos.
- **Escopo** (**E** entre os parâmetros): restringe quais slots contam.

| Parâmetro | Exemplo | Regra |
| --- | --- | --- |
| `reasons` | `no_shiny,from_go` | `no_shiny`: sem espécime ou espécime não shiny; `from_go`: shiny com `is_from_go`; `pokeball`: shiny com pokébola **informada** fora de `accepted_balls` |
| `accepted_balls` | `poke-ball,premier-ball` | usado só pelo motivo `pokeball`; sem ele, o motivo é ignorado. Espécime sem pokébola não entra por esse motivo |
| `generation` | `generation-vii` | geração da espécie |
| `type` | `water,flying` | **qualquer um** dos tipos (diferente de `/specimens/`) |
| `category` | `legendary,mythical,ultra-beast` | qualquer uma de `legendary`, `mythical`, `ultra-beast`, `baby`, `regular` (nenhuma das outras). Ultra Beast = pokémon com a habilidade Beast Boost (a PokéAPI não marca UBs) |
| `search` | `pika`, `25` | igual ao de `/slots/` |
| `include_locked` | `true` | inclui formas com shiny lock `unobtainable` (fora por padrão); `distro-only` aparece sempre, com `shiny_lock` |

Exemplos:

```text
# Gen VII, lendário/mítico/UB, sem shiny ou shiny do GO
?generation=generation-vii&category=legendary,mythical,ultra-beast&reasons=no_shiny,from_go
# Sem shiny, ou shiny numa bola fora de Poké/Premier Ball
?reasons=no_shiny,pokeball&accepted_balls=poke-ball,premier-ball
```

## Saves e localização

- **Save** = um save do usuário, com OneToOne para o `OriginalTrainer` (nome,
  TID e versão vêm dele). O OT continua sendo um dado do Pokémon (de onde
  veio); o save é um lugar (onde está). Só vira save um OT com versão de jogo
  que **recebe** do HOME: `sword`, `shield`, `brilliant-diamond`,
  `shining-pearl`, `legends-arceus`, `scarlet`, `violet`, `legends-za`
  (Let's Go, GO e Bank só enviam). No admin, a ação "Marcar como meus saves"
  nos treinadores cria os saves dos elegíveis.
- `Specimen.location` (save ou `null` = HOME) e `location_since` (data da
  saída). Fora do HOME, o espécime **continua no slot**, que fica
  **reservado**: depositar outro espécime ali → 400 `{"non_field_errors":
  [...]}`; retirar (`withdraw`) libera o slot.
- Fora do HOME **conta** no progresso (`registered`); `away` diz quantos
  desses estão fora.
- **Evoluiu fora do HOME** (`POST /specimens/{id}/evolve/`): `form` precisa
  ser evolução (direta ou não) da espécie atual (`evolves_from_species`),
  senão 400 `{"form": [...]}`. O espécime passa a ser a forma nova
  (`form_name` junto), a habilidade vai para a do mesmo slot de habilidade da
  forma nova (ou `null`), e ele sai do slot da forma antiga, que volta a
  faltar. A localização não muda: trazer de volta é outra chamada.

## Depositar automaticamente

`POST /api/personal-dexes/{id}/link-specimens/` faz o mesmo que o comando
`link_specimens` para um dex: põe espécimes **livres** (fora de qualquer slot)
nos slots **vazios com forma**, na ordem das boxes.

- Prefere o brilho do dex (shiny num shiny dex, não shiny num normal); sem
  `strict`, usa o outro quando não há. `strict: true` só aceita o brilho do dex.
- Um espécime vai para um slot só; os já depositados não entram.
- `slots` são os que recebem um espécime, já com ele em `specimen`, como
  ficariam; `missing` é quantos slots vazios ficaram sem.
- `dry_run: true` só simula (nada é salvo): é a prévia que o app mostra antes
  de confirmar.

## Shiny locks

Cadastro manual (não vem da PokéAPI) das formas sem shiny (`unobtainable`) ou
com shiny só por distribuição (`distro-only`). Só os **ativos** valem: são eles
que dão o `is_shinylocked`/`is_distro_only` das formas e o `shiny_lock` das
caçadas, lidos da mesma tabela, então qualquer mudança vale na hora.

- `caption` é único (400 `{"caption": [...]}`); espaços nas pontas são
  removidos. `description` em branco vira `null`.
- `forms` precisa de pelo menos uma forma existente (400 `{"forms": [...]}`).
- `lock_type` fora dos dois valores → 400 `{"lock_type": [...]}`.

## Regras

- <a id="ordem-canônica-das-formas"></a>**Ordem canônica das formas**
  (`FORM_NATIONAL_ORDERING`, em `pokedex/models.py`): nº da Pokédex nacional
  (o pk da espécie), depois `form_order` dentro da espécie e o `pk` para
  desempatar. Vale para `/forms/`, para o conjunto padrão do dex e para os
  desempates de `ordering` em `/specimens/`. O `order` da PokéAPI fica no banco
  mas não é usado: agrupa famílias até a 6ª geração e é quase arbitrário na 9ª
  (Annihilape no fim).
- **Depósito** (`transaction.atomic` + `select_for_update` no slot e no specimen):
  - slot sem forma → `{"non_field_errors": [...]}`
  - forma do specimen ≠ forma do slot (regra de `Slot.clean`) → `{"specimen_id": [...]}`
  - specimen depositado em outro slot → `{"specimen_id": [...]}`
  - specimen inexistente → `{"specimen_id": [...]}`
  - redepositar no mesmo slot é permitido; depositar num slot ocupado substitui
    o specimen anterior (que volta a ficar disponível).
- **Ability** do specimen deve pertencer às abilities do pokémon da forma
  → `{"ability": [...]}`.
- **Editar** (PUT/PATCH): `form` não pode mudar depois de criado → `{"form": [...]}`.
  Enviar a mesma forma é aceito.
- **Libertar** (DELETE → 204): apaga o specimen, mesmo depositado; o slot
  mantém a forma e fica faltante (`Slot.specimen` é `on_delete=SET_NULL`).
- **Edição em lote** (`PATCH /specimens/bulk/`, `transaction.atomic` +
  `select_for_update`), tudo ou nada:
  - `changes` aceita só `pokeball`, `ot`, `language`, `gender`, `nature`,
    `captured_at`, `is_shiny`, `is_alpha`, `is_from_go`; outro campo →
    `{"changes": {"<campo>": [...]}}`; vazio → `{"changes": {"non_field_errors": [...]}}`.
  - `null` em `pokeball`/`ot`/`captured_at` remove o valor (`pokeball: ""`
    também). Campos fora de `changes` ficam como estão.
  - ids repetidos contam uma vez; id inexistente → `{"ids": [...]}`.
  - Gênero validado por espécime: forma `-male`/`-female` define o gênero;
    senão, o `gender_rate` da espécie (-1 sem gênero, 0 só macho, 8 só
    fêmea, 1–7 macho ou fêmea). Conflito →
    `{"gender": ["..."], "conflicts": [{"id": 1, "form_name": "latias"}]}`.
  - `updated_at` é atualizado.
- **Jogo e marca de origem** (`home/origin_marks.py`): a marca de origem do
  HOME é a do jogo em que o Pokémon foi obtido pela primeira vez
  ([Bulbapedia](https://bulbapedia.bulbagarden.net/wiki/Origin_mark)).
  - `origin_version` é **derivado do OT**, sem campo no app: ao criar o
    espécime ou trocar o OT dele (inclusive na edição em lote), recebe a
    `version` do OT, ou `null` se o OT não tiver versão. A API ignora
    `origin_version`/`origin_mark` enviados.
  - Quando a `version` de um OT muda (inclusive de/para `null`), os espécimes
    desse OT com `origin_version` `null` ou igual à versão antiga passam para
    a nova. Correções feitas no admin (outra versão) são preservadas.
  - `origin_mark`: `is_from_go` → `go` (tem prioridade); senão, o
    `version_group` do `origin_version`:

    | marca | version_groups |
    | --- | --- |
    | `game-boy` | red-green-japan, blue-japan, red-blue, yellow, gold-silver, crystal |
    | `kalos` | x-y, omega-ruby-alpha-sapphire |
    | `alola` | sun-moon, ultra-sun-ultra-moon |
    | `lets-go` | lets-go-pikachu-lets-go-eevee |
    | `galar` | sword-shield, the-isle-of-armor, the-crown-tundra |
    | `bdsp` | brilliant-diamond-shining-pearl |
    | `hisui` | legends-arceus |
    | `paldea` | scarlet-violet, the-teal-mask, the-indigo-disk |
    | `lumiose` | legends-za, mega-dimension |

    Os demais (Gen 3–5, Colosseum/XD, Champions) e `null` → sem marca.
- Labels de nature ainda sem tradução pt-BR (caem no inglês) até definirmos os
  nomes; ver `api/choices.py` e `locale/pt_BR/LC_MESSAGES/django.po`.
