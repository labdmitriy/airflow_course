# Настройка мониторинга

## Задача
В этом задании мы апгрейдим ваш стенд, в качестве дагов можно написать какие-то новые или использовать любые два пайплайна из предыдущих заданий.

1. Установите на свой сервер графану, закройте её с помощью nginx через **тот же** basic auth. Пусть графана отвечает по порту 3333
2. Добавьте дашборд с мониторингом ваших дагов. На дашборде должны присутствовать больше одного дага.
3. Добавьте пайплайн-канарейку, опционально проверяющий доступность какого-то источника. Отобразите здоровье канарейки на дашборде.
4. Для мониторинга состояния самого airflow поставьте [airflow-exporter](https://github.com/epoch8/airflow-exporter).
5. Один из ваших пайплайнов должен использовать `on_failure_callback` (пинг в телеграм).
6. Один таск в одном из ваших пайплайнов должен приводить к тому что пайплайн _примерно_ каждый пятый запуск будет делать SLA miss.

Дополнительные требования:

- На дашборде всё может быть максимально захардкожено, не надо мудрить;
- Технические метрики дагов выбирайте на ваше усмотрение, но можно просто дать те что есть. 
  Обычно интересует следующее: количество запусков за какой-то период, time since последний запуск, время выполнения отдельных критичных тасок.
  Соберите на дашборде метрики, помогающие ответить на эти вопросы;
- На пайплайн-канарейку добавьте `sla_miss_callback` и `on_failure_callback`;
- Сделайте **максимум** два дашборда (можно один);
- В графану так просто данные не польются, вам нужен локальный prometheus на той же машине.
  Его можно не вытаскивать наружу, но для дебага удобно;
- (Опционально) Добавьте в микс statsd и используйте его для отправки бизнес-метрик из ваших пайплайнов.
  Это может быть число строчек в базе, количество грязи в данных, число отправленных tg-сообщений или какая-то ещё _контекстно-релевантная_ метрика для пайплайна.

## Файлы
- dags/
  - homework_5_1.py - основной код Airflow DAG Telegram-бота (ДЗ 3)
  - homework_5_2.py - основной код Airflow DAG обработки данных о покупках  (ДЗ 4)
  - homework_5_3.py - основной код пайплайна-канарейки

## Решение
### Описание
- В качестве DAGов для мониторинга используются DAGs из ДЗ 3 (homework_5_1) и ДЗ 4 (homework_5_2), а также созданный пайплайн-канарейка (homework_5_3)
- В DAG homework_5_2 изменена реализация отправки Telegram-сообщения в случае некачественных данных: вместо отдельного task используется on_failure_callback на уровке DAG 
- Пайплайн-канарейка реализован следующим образом:
  - Происходит обработка двух событий - failure и SLA miss
  - С вероятностью 10% генерируется событие failure. В случае failure автоматически генерируется событие SLA miss.
  - С вероятностью 10% генерируется событие SLA miss.
  - Таким образом, мы должны получить срабатывание SLA miss примерно в 20% (10% + 10%) случаев. Однако, в связи со случайностью процесса генерации событий, а также срабатывания SLA miss по пропущенным событиям в случае остановки сервера и его повторного запуска, доля событий SLA miss может варьироваться.
- События SLA miss можно посмотреть через Airflow UI, а также в файле /home/jupyter/data/canary_callback, используемый для демонстрации возможности обработки данного события через sla_miss_callback
- Установлен airflow-exporter для экспорта метрик 
- Установлен и настроен Prometheus для получения метрик, генерируемых с помощью airflow-exporter
- Установлена и настроена Grafana, для получения метрик из Prometheus
- Настроен Dashboard в Grafana (Airflow Dashboard), где отображены следующие метрики:
  - Кол-во запусков 3х DAGs в разрезе статусов failed/success за указанный промежуток времени
  - Статистика по статусам обработки нажатий по кнопке Telegram-бота
  - Общее кол-во полностью успешных обработок данных по покупкам
  - Статистика по статусам запусков пайплайна-канарейки
  - Среднее время работы каждого из 3х DAGs (в секундах) за указанный промежуток времени 
