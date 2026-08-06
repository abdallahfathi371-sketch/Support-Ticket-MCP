INSERT INTO employees
(employee_name, role)
VALUES

('Admin User','admin'),

('Support Agent','support'),

('Viewer User','viewer');



INSERT INTO teams(team_name)

VALUES

('Backend'),

('Frontend'),

('Support'),

('Product');



INSERT INTO tickets

(customer_name, issue, category, status, priority, team_id)

VALUES


('Ahmed Ali',
'Login API returns 500 error',
'Bug Report',
'Open',
'High',
1),


('Sara Mohamed',
'Add dark mode',
'Feature Request',
'Pending',
'Medium',
4),


('Omar Hassan',
'How can I change my password?',
'General Question',
'Closed',
'Low',
3),


('Mona Adel',
'Profile page crashes',
'Bug Report',
'Open',
'High',
2),


('Youssef Ibrahim',
'Need export to Excel',
'Feature Request',
'Open',
'Medium',
4),


('Nada Samir',
'Payment confirmation missing',
'Bug Report',
'Pending',
'High',
1),


('Khaled Tarek',
'How do I contact support?',
'General Question',
'Closed',
'Low',
3),


('Aya Gamal',
'Navbar overlaps content',
'Bug Report',
'Open',
'Medium',
2),


('Mahmoud Fathy',
'Need email notifications',
'Feature Request',
'Pending',
'Medium',
4),


('Heba Ahmed',
'Cannot upload image',
'Bug Report',
'Open',
'High',
2),


('Mostafa Ali',
'Refund process question',
'General Question',
'Open',
'Low',
3),


('Fatma Salah',
'Improve dashboard performance',
'Feature Request',
'Closed',
'Medium',
1),


('Ali Mahmoud',
'Search returns wrong results',
'Bug Report',
'Pending',
'High',
1),


('Nour Hassan',
'Add Arabic language',
'Feature Request',
'Open',
'Medium',
4),


('Karim Essam',
'Where can I report bugs?',
'General Question',
'Closed',
'Low',
3);