- [eXwonder-backend](#exwonder-backend)
   * [Установка](#installation)
   * [Краткое описание функционала](#description)
   * [Скриншоты из frontend клиента](#screenshots)
   * [Лицензия](#license)

<!-- TOC --><a name="exwonder-backend"></a>
# eXwonder-backend
Backend онлайн хостинга картинок __eXwonder__, являющегося по функционалу урезанной версией Instagram. 
Код написан на Python фреймворке __[Django 5](https://www.djangoproject.com/)__, использует __[PostgreSQL](https://www.postgresql.org/)__ как основную БД, 
__[Redis](https://github.com/redis/redis)__ для кэширования, __[RabbitMQ](https://github.com/rabbitmq/rabbitmq-server)__ в качестве брокера сообщений, __[Celery](https://docs.celeryq.dev/en/stable/getting-started/introduction.html)__ 
для обработки очередей задач. Также применяется библиотека __[dj-rest-auth](https://github.com/iMerica/dj-rest-auth)__ для операций с аккаунтом 
через REST API, к которому также имеется Swagger-схема, сгенерированная при помощи 
__[drf-spectacular](https://github.com/tfranzel/drf-spectacular/)__. Используемый линтер и форматер кода - __[ruff](https://github.com/astral-sh/ruff)__. 
<!-- TOC --><a name="installation"></a>
## Установка
Перед установкой убедитесь, что у вас установлен менеджер пакетов `uv`, `Redis` и `RabbitMQ` (если вы хотите использовать его как брокер сообщений вместо `Redis`).
1. Клонируем репозиторий:
```cmd
git clone https://github.com/waflawe/eXwonder-backend.git
cd eXwonder-backend/
```
2. Устанавливаем зависимости:
```cmd
uv sync
```
3. Создайте файл `.env` и настройте его по примеру файла `.env.template`.
4. Применяем миграции:
```cmd
uv run python manage.py migrate
```
5. Запускаем отдельно два окна терминала. В первом запускаем `celery`:
```cmd
./scripts/celery.sh
```
6. Во втором запускаем сервер:
```cmd
./scripts/run.sh
```
7. API будет доступно по адресу: `http://localhost:8000/api/v1/`, а документация - `http://localhost:8000/api/v1/schema/docs/`.
<!-- TOC --><a name="description"></a>
## Краткое описание функционала
1. Создание и вход в аккаунт.
2. Сброс пароля, двухфакторная аутентификация, изменение пароля аккаунта.
3. Подписки и подписчики.
4. Страница новостей (посты от аккаунтов в подписках за время вашего отсутствия).
5. Создание поста, его удаление, просмотр, лайки, добавление в сохраненные, теги.
6. Комментарии к посту, лайки комментариев, удаление комментариев.
7. Глобальный поиск аккаунтов.
8. Страница с рекоммендациями, последними добавленными и самыми залайканными постами.
9. Просмотр аккаунтов пользователей.
10. Изменение настроек аккаунта (временная зона, 2FA, почта для сброса пароля, аватарка, имя, описание). 
<!-- TOC --><a name="screenshots"></a>
## Скриншоты из frontend клиента
Доступны [здесь](https://github.com/waflawe/eXwonder-frontend/blob/main/README.md).
<!-- TOC --><a name="license"></a>
## Лицензия
У этого проекта [MIT лицензия](https://github.com/waflawe/eXwonder-backend/blob/main/LICENSE).

