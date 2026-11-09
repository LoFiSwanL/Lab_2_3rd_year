from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient

FOLDER = Path(__file__).resolve().parent
pg = psycopg.connect('postgresql://lab:lab_password@localhost:55432/nosql_lab',
                     autocommit=True, row_factory=dict_row, prepare_threshold=None)
client = MongoClient('mongodb://localhost:57017', tz_aware=True, w=1, journal=True)
reports = client.nosql_lab.reports
document_sql = (FOLDER / 'queries.sql').read_text()
queries = {
    'id': document_sql + ' WHERE r.id = %s',
    'project': document_sql + ' WHERE r.project_id = %s ORDER BY r.created_at DESC, r.id DESC LIMIT 20',
    'device': document_sql + """ WHERE EXISTS (
        SELECT 1 FROM lab.report_details d
        WHERE d.report_id = r.id AND d.name = 'device' AND d.value = %s)
        ORDER BY r.created_at DESC, r.id DESC LIMIT 20""",
    'count': 'SELECT kind, count(*) AS count FROM lab.reports WHERE project_id = %s GROUP BY kind ORDER BY kind',
}


def sql_select(query, value):
    return pg.execute(queries[query], (value,)).fetchall()


def mongo_select(query, value):
    if query == 'id':
        return list(reports.find({'_id': value}))
    if query == 'count':
        return list(reports.aggregate([
            {'$match': {'project_id': value}},
            {'$group': {'_id': '$kind', 'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}},
            {'$project': {'_id': 0, 'kind': '$_id', 'count': 1}},
        ]))
    field = 'project_id' if query == 'project' else 'details.device'
    return list(reports.find({field: value}).sort([('created_at', -1), ('_id', -1)]).limit(20))


def sql_insert(report):
    with pg.transaction(), pg.cursor() as cursor:
        cursor.execute('INSERT INTO lab.reports VALUES (%s,%s,%s,%s,%s,%s,%s)',
                       [report[key] for key in ('_id', 'project_id', 'task_id', 'author_id', 'kind', 'created_at', 'summary')])
        cursor.executemany('INSERT INTO lab.report_details VALUES (%s,%s,%s)',
                           [(report['_id'], name, value) for name, value in report['details'].items()])
        cursor.executemany('INSERT INTO lab.report_checks VALUES (%s,%s,%s,%s)',
                           [(report['_id'], i, item['text'], item['done']) for i, item in enumerate(report['checks'])])
    return report['_id']


def sql_update(report_id):
    return pg.execute('UPDATE lab.report_checks SET done = true WHERE report_id = %s AND position = 0',
                      (report_id,)).rowcount


def sql_delete(report_id):
    return pg.execute('DELETE FROM lab.reports WHERE id = %s', (report_id,)).rowcount


def load_data(data):
    pg.execute('DROP SCHEMA IF EXISTS lab CASCADE')
    pg.execute((FOLDER / 'schema.sql').read_text())
    reports.drop()
    # Пакетне завантаження готує дані, його час не вимірюється.
    with pg.transaction(), pg.cursor() as cursor:
        with cursor.copy('COPY lab.reports FROM STDIN') as copy:
            for report in data:
                copy.write_row([report[key] for key in ('_id', 'project_id', 'task_id', 'author_id', 'kind', 'created_at', 'summary')])
        with cursor.copy('COPY lab.report_details FROM STDIN') as copy:
            for report in data:
                for name, value in report['details'].items():
                    copy.write_row((report['_id'], name, value))
        with cursor.copy('COPY lab.report_checks FROM STDIN') as copy:
            for report in data:
                for i, item in enumerate(report['checks']):
                    copy.write_row((report['_id'], i, item['text'], item['done']))
    for i in range(0, len(data), 1000):
        reports.insert_many(data[i:i + 1000])
    pg.execute('CREATE INDEX reports_project_time ON lab.reports (project_id, created_at DESC, id DESC)')
    pg.execute('CREATE INDEX reports_time ON lab.reports (created_at DESC, id DESC)')
    pg.execute('CREATE INDEX details_value ON lab.report_details (name, value, report_id)')
    for table in ('reports', 'report_details', 'report_checks'):
        pg.execute(f'VACUUM ANALYZE lab.{table}')
    reports.create_index([('project_id', 1), ('created_at', -1), ('_id', -1)])
    reports.create_index([('details.device', 1), ('created_at', -1), ('_id', -1)])
