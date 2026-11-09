import csv
import json
import random
from pathlib import Path
from statistics import median
from time import perf_counter, sleep

import redis

import database as db
from data import generate_data

SIZES = [1000, 10000, 100000]
REPEATS = 100
FOLDER = Path(__file__).resolve().parent
raw = []


def compare(size, name, sql_query, mongo_query):
    times = {'SQL': [], 'MongoDB': []}
    for i in range(-5, REPEATS):
        calls = [('SQL', sql_query), ('MongoDB', mongo_query)]
        if i % 2 == 0:
            calls.reverse()
        answers = {}
        for database, query in calls:
            start = perf_counter()
            answers[database] = query(i)
            elapsed = (perf_counter() - start) * 1000
            if i >= 0:  # Перші п'ять запусків потрібні лише для прогріву.
                times[database].append(elapsed)
                raw.append([size, name, database, i + 1, elapsed])
        assert answers['SQL'] == answers['MongoDB'], f'Різні результати: {name}'
    a, b = sorted(times['SQL']), sorted(times['MongoDB'])
    p95 = (95 * REPEATS + 99) // 100 - 1
    return f'| {name} | {median(a):.3f} | {median(b):.3f} | {a[p95]:.3f} | {b[p95]:.3f} |'


def redis_demo():
    cache = redis.Redis(host='localhost', port=56379, decode_responses=True)
    key = 'pm:report:1:demo'
    report = db.reports.find_one({'_id': 1})
    cache.set(key, json.dumps(report, default=str, ensure_ascii=False), ex=60)
    cached = json.loads(cache.get(key))
    assert cached['_id'] == 1
    print('Redis GET:', cached['summary'])
    cached['summary'] = 'Оновлений звіт'
    cache.set(key, json.dumps(cached), xx=True, keepttl=True)
    assert json.loads(cache.get(key))['summary'] == 'Оновлений звіт'
    print('Redis TTL:', cache.ttl(key))
    assert cache.delete(key) == 1
    assert cache.get(key) is None
    cache.set(key, 'тимчасове значення', px=100)
    sleep(0.2)
    assert cache.get(key) is None
    print('Redis: створення, читання, зміна, видалення та завершення TTL перевірені')
    cache.close()


def main():
    result = ['# Результати', '', 'Час у мілісекундах; менше значення означає швидше виконання.',
              'Медіана і p95 обчислені зі 100 запусків після п’яти прогрівів.', '']
    for size in SIZES:
        print(f'Завантаження {size} звітів...', flush=True)
        data = generate_data(size)
        db.load_data(data)
        sql_counts = [db.pg.execute(f'SELECT count(*) AS n FROM lab.{table}').fetchone()['n']
                      for table in ('reports', 'report_details', 'report_checks')]
        assert sql_counts == [size, sum(len(r['details']) for r in data), sum(len(r['checks']) for r in data)]
        assert db.reports.count_documents({}) == size
        rng = random.Random(42)
        ids = [rng.randint(1, size) for _ in range(REPEATS)]
        projects = [rng.randint(2, 100) for _ in range(REPEATS)]
        result += [f'## {size} звітів', '', f'SQL: {sql_counts[0]} звітів, {sql_counts[1]} характеристик, '
                   f'{sql_counts[2]} пунктів перевірки.', '',
                   '| Операція | SQL медіана | Mongo медіана | SQL p95 | Mongo p95 |',
                   '|---|---:|---:|---:|---:|']
        cases = [('Звіт за ID', 'id', ids), ('Останні звіти проєкту', 'project', projects),
                 ('Останні звіти популярного проєкту', 'project', [1] * REPEATS),
                 ('Пошук пристрою ESP32', 'device', ['ESP32'] * REPEATS),
                 ('Кількість звітів за типом', 'count', [1] * REPEATS)]
        for name, query, values in cases:
            result.append(compare(size, name, lambda i: db.sql_select(query, values[i]),
                                  lambda i: db.mongo_select(query, values[i])))
        # Нові записи потрібні для тестів змін; після видалення основний набір не зміниться.
        extra = generate_data(REPEATS + 5, start=size + 1)
        result.append(compare(size, 'Вставка звіту', lambda i: db.sql_insert(extra[i + 5]),
                              lambda i: db.reports.insert_one(extra[i + 5]).inserted_id))
        report_id = extra[-1]['_id']
        assert db.sql_select('id', report_id) == db.mongo_select('id', report_id) == [extra[-1]]
        result.append(compare(size, 'Зміна пункту перевірки', lambda i: db.sql_update(extra[i + 5]['_id']),
                              lambda i: db.reports.update_one({'_id': extra[i + 5]['_id']},
                                        {'$set': {'checks.0.done': True}}).modified_count))
        assert db.sql_select('id', report_id) == db.mongo_select('id', report_id)
        assert db.reports.find_one({'_id': report_id})['checks'][0]['done'] is True
        result.append(compare(size, 'Видалення звіту', lambda i: db.sql_delete(extra[i + 5]['_id']),
                              lambda i: db.reports.delete_one({'_id': extra[i + 5]['_id']}).deleted_count))
        assert db.sql_select('id', report_id) == db.mongo_select('id', report_id) == []
        assert [db.pg.execute(f'SELECT count(*) AS n FROM lab.{table}').fetchone()['n']
                for table in ('reports', 'report_details', 'report_checks')] == sql_counts
        assert db.reports.count_documents({}) == size
        result.append('')
        print(f'{size}: усі запити повернули однакові результати', flush=True)
    redis_demo()
    (FOLDER / 'results.md').write_text('\n'.join(result) + '\n')
    with (FOLDER / 'raw.csv').open('w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['size', 'query', 'database', 'attempt', 'ms'])
        writer.writerows(raw)
    print('Готово: results.md і raw.csv')


if __name__ == '__main__':
    try:
        main()
    finally:
        db.pg.close()
        db.client.close()
