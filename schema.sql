CREATE SCHEMA lab;

CREATE TABLE lab.reports (
    id integer PRIMARY KEY,
    project_id integer NOT NULL,
    task_id integer NOT NULL,
    author_id integer NOT NULL,
    kind text NOT NULL,
    created_at timestamptz NOT NULL,
    summary text NOT NULL
);

CREATE TABLE lab.report_details (
    report_id integer REFERENCES lab.reports(id) ON DELETE CASCADE,
    name text NOT NULL,
    value text NOT NULL,
    PRIMARY KEY (report_id, name)
);

CREATE TABLE lab.report_checks (
    report_id integer REFERENCES lab.reports(id) ON DELETE CASCADE,
    position integer CHECK (position BETWEEN 0 AND 7),
    text text NOT NULL,
    done boolean NOT NULL,
    PRIMARY KEY (report_id, position)
);
