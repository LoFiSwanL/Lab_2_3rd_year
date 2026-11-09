-- Збираємо той самий об'єкт, який зберігається одним документом у MongoDB.
SELECT r.id AS _id, r.project_id, r.task_id, r.author_id, r.kind, r.created_at, r.summary,
       COALESCE((SELECT jsonb_object_agg(d.name, d.value)
                 FROM lab.report_details d WHERE d.report_id = r.id), '{}'::jsonb) AS details,
       COALESCE((SELECT jsonb_agg(jsonb_build_object('text', c.text, 'done', c.done)
                                 ORDER BY c.position)
                 FROM lab.report_checks c WHERE c.report_id = r.id), '[]'::jsonb) AS checks
FROM lab.reports r
