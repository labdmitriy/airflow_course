# Агрегация данных по покупкам из различных источников

## Задача
1. Сделать DAG из нескольких шагов, собирающий данные по заказам, проверяющий
   статусы транзакций через API и складывающий результат в базу данных
2. Данные по заказам брать в виде csv-файла [отсюда](https://airflow101.python-jitsu.club/orders.csv)
3. Данные по статусам транзакций хранятся в виде json [тут](https://api.jsonbin.io/b/5ed7391379382f568bd22822)
4. Данные о товарах и пользователях живут в PostgreSQL БД (доступ в тг чате).
5. Результаты складывать в другую PostgreSQL БД (доступ к ней будет у вас в
   личке). Именно в ней должен лежить финальный датасет.

Требования к DAG:

- На каждый источник должен быть один оператор.
- Повторные выполнения DAG должны обновлять имеющиеся данные. То есть,
  если статус транзакции изменился на "оплачен", то это должно быть
  отражено в датасете.
- Из любого источника могут приходить грязные данные. Делайте чистку:
  удаляйте дубли, стрипайте строки, проверяйте на null/None.
- Логин/пароль для доступа в postgres базу надо получить у оргов
  (dbname совпадает с вашим логином).
- Прежде чем писать в постгрес, надо убедиться, что там есть схема
  и таблица.
- Вы можете использовать pandas, но вообще в благородных домах
  pandas не тянут "в продакшен".
- Финальный датасет содержит следующие колонки: `name`, `age`,
  `good_title`, `date`, `payment_status`, `total_price`, `amount`, `last_modified_at`.

## Файлы
- dags/
  - homework_2.py - код Airflow DAG для сбора статистики
- data/ - примеры файлов, скаченных из источников, и очищенные версии с необходимым набором колонок (*_clean.csv)

## Описание решения
### Установка дополнительного пакета Airflow для работы с PostreSQL
### Настройка хранения зашифрованных паролей для Connections
### Обработка данных из источников
- Скачивание оригинальных данных
  - Для csv-файла и API используется HttpHook
  - Для получения данных из таблиц БД используется PostgresHook
- Обработка полученных данных
  - Удаление лишних пробелов в начале и конце полей
  - Создание дополнительных полей
    - age - возраст клиента (вычислен из birth_date)
    - payment_status - статус платежа ('success', 'failure')
  - Фильтрация только необходимых колонок для каждого из источников
### Создание финального датасета
- Пересоздание временных таблиц для очищенных данных
- Загрузка данных во временные таблицы
- Агрегация данных из временных таблиц для формирования финального датасета
  - Создание дополнительных полей
    - total_price - суммарная цена заказа (price * amount)
    - last_modified_at - дата/время последней модификации записи
  - В случае, если в дальнейшем придет запись с уже существующим набором уникальных значений записи, будет обновлен статус платежа (payment_status) и дата/время последней модификации записи (last_modified_at)
    - В данном случае для определения уникальности записи используются 3 поля - ФИО пользователя (name), наименование товара (good_title) и дата/время заказа (date)
