# UMT-pythonweb-hw-13 — Contacts REST API (final)

Фінальне домашнє завдання курсу. Це розвиток
[Homework 11](https://github.com/saniksin/UMT-pythonweb-hw-11): до готового REST API
додано **документацію Sphinx**, **модульні та інтеграційні тести (pytest, покриття (75 %)**, **кешування користувача в Redis**, **скидання пароля поштою**, **ролі користувачів (`user` / `admin`)** та (додатково) **пару JWT-токенів `access` + `refresh`**.

Стек: **FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Redis · Alembic ·
Pydantic v2 · FastAPI-Mail · slowapi · Cloudinary · pytest · Sphinx ·
Docker Compose · uv**.

---

## Зміст

- [Що нового порівняно з Homework 11](#що-нового-порівняно-з-homework-11)
- [Структура проєкту](#структура-проєкту)
- [Конфігурація (.env)](#конфігурація-env)
- [Запуск у Docker Compose](#запуск-у-docker-compose)
- [Запуск локально](#запуск-локально)
- [Кешування в Redis](#кешування-в-redis)
- [Скидання пароля](#скидання-пароля)
- [Ролі користувачів](#ролі-користувачів)
- [Пара токенів access / refresh](#пара-токенів-access--refresh)
- [Тестування та покриття](#тестування-та-покриття)
- [Документація Sphinx](#документація-sphinx)
- [Опис ендпоінтів](#опис-ендпоінтів)
- [Перевірка вимог завдання](#перевірка-вимог-завдання)

---

## Що нового порівняно з Homework 11

| Можливість | Деталі |
|------------|--------|
| **Sphinx-документація** | `docs/` — `automodule` для `main` і всіх модулів `src`. Збірка: `cd docs && make html`. До функцій/методів додано docstrings у reST-стилі. |
| **Модульні тести** | `tests/test_users_repository_unit.py`, `tests/test_contacts_repository_unit.py` — `AsyncMock(spec=AsyncSession)`, перевірка кожного методу репозиторіїв. |
| **Інтеграційні тести** | `tests/test_integration_*.py` — `TestClient` + тестова БД SQLite, маршрути auth / users / contacts / utils. |
| **Покриття > 75 %** | `pytest-cov`, фактичне покриття `src` — **89 %**. |
| **Кеш Redis** | `get_current_user` спершу читає користувача з Redis і лише на промах звертається до БД (`src/services/cache.py`). |
| **Скидання пароля** | `POST /auth/reset_password` + `POST /auth/reset_password/confirm` — безпечний токен на 1 годину, лист через FastAPI-Mail. |
| **Ролі** | Колонка `users.role` (`user` / `admin`). Зміна аватара (`PATCH /users/avatar`) доступна **лише адміністраторам** — інші отримують `403`. |
| **Пара JWT-токенів** | `login` повертає `access_token` + `refresh_token`; `POST /auth/refresh_token` оновлює пару. |
| **Redis у Compose** | `docker-compose.yml` піднімає `redis:7-alpine` поряд з Postgres і застосунком. |

---

## Структура проєкту

```
UMT-pythonweb-hw-13/
├── docker-compose.yml          # postgres + redis + app (healthchecks, автоміграції)
├── Dockerfile
├── alembic.ini
├── main.py                     # FastAPI app, CORS, rate-limit, роутери
├── pyproject.toml              # залежності + [tool.pytest.ini_options] + dev-група
├── .env.example                # шаблон конфігурації
│
├── docs/                       # Sphinx
│   ├── Makefile / make.bat
│   └── source/
│       ├── conf.py             # autodoc + dummy ENV для імпорту Settings()
│       └── index.rst           # automodule для всіх модулів
│
├── migrations/versions/        # Alembic
│   ├── f60ca8e17744_init_contacts.py
│   ├── a1b2c3d4e5f6_add_users_and_link_contacts.py
│   └── b2c3d4e5f6a7_add_role_to_user.py
│
├── tests/                      # pytest
│   ├── conftest.py             # SQLite-БД, TestClient, get_token, seed admin
│   ├── test_users_repository_unit.py
│   ├── test_contacts_repository_unit.py
│   ├── test_integration_auth.py
│   ├── test_integration_contacts.py
│   ├── test_integration_users.py
│   └── test_integration_utils.py
│
└── src/
    ├── api/                    # auth, users, contacts, utils
    ├── conf/config.py          # Pydantic Settings (+ Redis, refresh token)
    ├── database/               # db.py, models.py (User+UserRole, Contact)
    ├── repository/             # users.py, contacts.py
    ├── services/               # auth, users, contacts, email, cache, upload_file
    └── schemas.py              # Pydantic-схеми (+ reset / refresh)
```

---

## Конфігурація (.env)

Скопіюйте шаблон і відредагуйте секрети:

```bash
cp .env.example .env
```

Нові порівняно з hw-11 змінні:

| Змінна | Призначення |
|--------|-------------|
| `JWT_REFRESH_EXPIRATION_SECONDS` | Час життя refresh-токена (за замовч. 7 днів) |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB` | Підключення до Redis |
| `REDIS_USER_TTL` | TTL кешованого користувача (секунди) |

Усі секрети читаються лише з ENV / `.env` — у коді немає літералів.

---

## Запуск у Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Compose піднімає `postgres:16`, `redis:7-alpine` та застосунок, чекає healthcheck-ів,
виконує `alembic upgrade head` і стартує uvicorn на `:8000`.
Swagger — <http://127.0.0.1:8000/docs>.

---

## Запуск локально

```bash
uv sync                                   # встановити залежності (+ dev-група)
docker run -d -p 6379:6379 redis:7-alpine # Redis
docker run -d --name some-postgres -p 5432:5432 -e POSTGRES_PASSWORD=567234 postgres:16
```

**Якщо БД `contacts_app` ще не існує — спершу створіть її** (Alembic не створює БД,
а лише накатує схему на наявну):

```bash
# варіант 1 — через psql у контейнері postgres
docker exec -it some-postgres psql -U postgres -c "CREATE DATABASE contacts_app;"

# варіант 2 — однією командою через createdb
docker exec -it some-postgres createdb -U postgres contacts_app
```

**Якщо БД вже існує — одразу застосовуйте міграції і запускайте сервер:**

```bash
uv run alembic upgrade head
uv run uvicorn main:app --reload
```

> У `docker compose up` цей крок не потрібен: Postgres сам створює БД зі змінної
> `POSTGRES_DB`, після чого контейнер застосунку автоматично виконує
> `alembic upgrade head`.

---

## Кешування в Redis

`src/services/cache.py` тримає лінивий async-клієнт Redis і три функції:
`get_cached_user`, `cache_user`, `invalidate_user`. У `get_current_user`
(`src/services/auth.py`) користувач спершу шукається в кеші за ключем
`user:<username>`; на промах виконується запит до БД і результат кешується на
`REDIS_USER_TTL` секунд. Кеш скидається після зміни аватара та скидання пароля,
тож дані лишаються актуальними. Усі звернення до Redis обгорнуті в `try/except` —
якщо Redis недоступний, застосунок продовжує працювати напряму з БД.

---

## Скидання пароля

1. `POST /api/auth/reset_password` `{ "email": ... }` — на пошту надсилається лист
   із токеном (scope `reset_password`, дійсний 1 годину). Відповідь однакова
   незалежно від існування email, тож адреси не можна перебрати.
2. `POST /api/auth/reset_password/confirm` `{ "token": ..., "new_password": ... }` —
   токен перевіряється, пароль хешується bcrypt і зберігається, кеш користувача
   скидається.

---

## Ролі користувачів

`UserRole` = `user` (за замовчуванням) або `admin`. Залежність
`get_current_admin_user` пропускає лише адміністраторів. Маршрут
`PATCH /api/users/avatar` захищений нею — звичайний користувач отримує
`403 Insufficient access rights`. Підвищення до `admin` робиться вручну (через БД).

---

## Пара токенів access / refresh

`POST /api/auth/login` повертає `access_token` (короткоживучий) і `refresh_token`
(довгоживучий). Коли access-токен спливає, клієнт викликає
`POST /api/auth/refresh_token` `{ "refresh_token": ... }` і отримує нову пару.
Токени розрізняються за claim `scope`, тож refresh-токен не приймається там, де
очікується access-токен, і навпаки.

---

## Тестування та покриття

```bash
uv run pytest                              # усі тести
uv run pytest --cov=src --cov-report=term-missing
uv run pytest --cov=src --cov-report=html  # звіт у htmlcov/index.html
```

- **51 тест**, усі проходять.
- Покриття `src` — **89 %** (вимога — понад 75 %).
- Модульні тести репозиторіїв ізольовані через `AsyncMock`.
- Інтеграційні тести використовують окрему SQLite-БД (`app.dependency_overrides`),
  пошту мокають через `monkeypatch`, а Cloudinary — через `@patch`.

---

## Документація Sphinx

```bash
cd docs
make html         # Linux/macOS
# .\make.bat html # Windows
```

Готова документація — `docs/build/index.html`. `docs/source/conf.py` додає корінь
проєкту в `sys.path` і задає фіктивні ENV-змінні, щоб `autodoc` міг імпортувати
модулі, які створюють `Settings()` під час імпорту.

---

## Опис ендпоінтів

Базовий префікс — `/api`.

### Auth

| Метод | Шлях | Опис |
|-------|------|------|
| `POST` | `/auth/register` | Реєстрація (201 / 409) + лист підтвердження |
| `POST` | `/auth/login` | OAuth2-форма → `access_token` + `refresh_token` |
| `POST` | `/auth/refresh_token` | Оновлення пари токенів за refresh-токеном |
| `GET`  | `/auth/confirmed_email/{token}` | Підтвердження email |
| `POST` | `/auth/request_email` | Повторний лист підтвердження |
| `POST` | `/auth/reset_password` | Запит на скидання пароля (лист) |
| `POST` | `/auth/reset_password/confirm` | Встановлення нового пароля за токеном |

### Users

| Метод | Шлях | Захист | Опис |
|-------|------|--------|------|
| `GET`   | `/users/me` | JWT | Поточний користувач (кеш Redis), rate limit 10/min |
| `PATCH` | `/users/avatar` | **admin** | Завантаження аватара у Cloudinary |

### Contacts (усі під JWT)

| Метод | Шлях | Опис |
|-------|------|------|
| `GET` | `/contacts/` | список (пагінація + пошук) |
| `GET` | `/contacts/{id}` | один контакт |
| `POST` | `/contacts/` | створити (201) |
| `PUT` | `/contacts/{id}` | оновити |
| `DELETE` | `/contacts/{id}` | видалити |
| `GET` | `/contacts/birthdays` | дні народження на найближчі `?days=` днів |

### Utils

| Метод | Шлях | Опис |
|-------|------|------|
| `GET` | `/healthchecker` | Перевірка з'єднання з БД |

---

## Перевірка вимог завдання

| # | Вимога task.txt | Бали | Де реалізовано |
|---|-----------------|------|----------------|
| 1 | Документація Sphinx | 2.5 | `docs/` + docstrings у всіх модулях |
| 2 | Модульні тести репозиторію | 2 | `tests/test_*_repository_unit.py` |
| 3 | Інтеграційні тести маршрутів | 3 | `tests/test_integration_*.py` |
| 4 | Покриття > 75 % | 1.5 | `pytest-cov` → **89 %** |
| 5 | Кешування користувача в Redis | 2.5 | `src/services/cache.py`, `get_current_user` |
| 6 | Скидання пароля | 2 | `/auth/reset_password[/confirm]`, лист + токен |
| 7 | Ролі `user` / `admin` | 1.5 | `UserRole`, `get_current_admin_user`, avatar admin-only |
| + | Пара токенів access + refresh | +5 | `/auth/login`, `/auth/refresh_token` |
| — | Збереження секретів у `.env` | — | `pydantic-settings`, без літералів у коді |
| — | Docker Compose (усі сервіси) | — | `docker-compose.yml` (postgres + redis + app) |
