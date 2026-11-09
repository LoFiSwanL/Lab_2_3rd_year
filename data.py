import random
from datetime import datetime, timedelta, timezone


def generate_data(count, start=1):
    random_generator = random.Random(42)
    reports = []
    for i in range(start, start + count):
        kind = ['development', 'testing', 'deployment'][i % 3]
        if kind == 'development':
            details = {'language': random_generator.choice(['Python', 'C++']), 'branch': f'task-{i}'}
        elif kind == 'testing':
            details = {'device': random_generator.choice(['ESP32', 'Jetson', 'Desktop']), 'firmware': f'v{i % 5}'}
        else:
            details = {'environment': random_generator.choice(['test', 'production']), 'version': f'1.{i % 20}'}
        if i % 4 == 0:
            details['note'] = 'Перевірка після оновлення'
        reports.append({
            '_id': i,
            'project_id': 1 if random_generator.random() < 0.2 else random_generator.randint(2, 100),
            'task_id': i,
            'author_id': random_generator.randint(1, 1000),
            'kind': kind,
            'created_at': datetime(2026, 1, 1, tzinfo=timezone.utc)
                          + timedelta(seconds=random_generator.randrange(180 * 86400)),
            'summary': f'Звіт до завдання {i}',
            'details': details,
            'checks': [{'text': f'Перевірка {j + 1}', 'done': False}
                       for j in range(random_generator.randint(3, 6))],
        })
    return reports
