DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS teams;

CREATE TABLE teams(
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT UNIQUE NOT NULL
);

CREATE TABLE tickets(
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,

    customer_name TEXT NOT NULL,

    issue TEXT NOT NULL,

    category TEXT NOT NULL
        CHECK(category IN (
            'Bug Report',
            'Feature Request',
            'General Question'
        )),

    status TEXT NOT NULL
        CHECK(status IN (
            'Open',
            'Pending',
            'Closed'
        )),

    priority TEXT NOT NULL
        CHECK(priority IN (
            'Low',
            'Medium',
            'High'
        )),

    team_id INTEGER NOT NULL,

    FOREIGN KEY(team_id)
        REFERENCES teams(team_id)
);