DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS employees;


CREATE TABLE employees(

    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,

    employee_name TEXT NOT NULL,

    role TEXT NOT NULL
        CHECK(role IN (
            'admin',
            'support',
            'viewer'
        ))

);



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