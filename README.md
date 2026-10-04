# Campus Reads

A campus reading-group directory: browse groups, join one, see what it's
currently reading, RSVP to meetings, and discuss the book with other members.

## Setup (local demo)

Requires Python 3.9+.

```bash
cd campus-reads

# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Load data (pick ONE of the two seed commands below)
flask --app app seed            # a couple of generic demo groups, OR
flask --app app seed-courses    # 8 groups themed around university subjects

# 4. Run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Two seed options

**`flask --app app seed`** — minimal demo data:
- **Email:** `demo@campus.edu`
- **Password:** `password123`
- One account organizing two groups ("Sci-Fi & Society" and "Campus Poetry
  Circle").

**`flask --app app seed-courses`** — a fuller, university-course-themed
dataset with 8 groups, each with its own organizer account, a current book,
and an upcoming meeting:

| Group | Genre | Current Book | Organizer login |
|---|---|---|---|
| World Literature Circle | Literature | *The Brief Wondrous Life of Oscar Wao* | maya.chen@campus.edu |
| Intro to Psychology Book Club | Psychology | *Thinking, Fast and Slow* | daniel.osei@campus.edu |
| CS Beyond the Classroom | Computer Science | *The Pragmatic Programmer* | priya.patel@campus.edu |
| Philosophy After Hours | Philosophy | *Meditations* | jordan.lee@campus.edu |
| Econ & Business Reads | Economics | *Freakonomics* | aisha.bello@campus.edu |
| History Majors' Book Club | History | *Sapiens* | thomas.nguyen@campus.edu |
| Environmental Science Reading Group | Environmental Science | *The Sixth Extinction* | grace.kim@campus.edu |
| Political Theory Forum | Political Science | *The Origins of Totalitarianism* | omar.haddad@campus.edu |

Every organizer account in `seed-courses` uses the password **`password123`**.
Running either seed command wipes and rebuilds the database, so it's safe to
switch between them or re-run before a fresh demo.

## What to click through for the demo

1. **Browse** (`/`) — search and filter groups by genre.
2. **Sign in** as one of the organizer accounts above (or sign up fresh).
3. **Start a group** of your own — you become its organizer.
4. **Set a current book** and **schedule a meeting** (organizer-only actions).
5. **Join a group** as a different account, **RSVP** to its meeting, and
   **post a comment** in the discussion thread (try the spoiler checkbox —
   spoiler comments render blurred until hovered/clicked).
6. **My Groups** (`/my-groups`) — a dashboard of every group you're in and
   your upcoming meetings across all of them.

## Project structure

```
campus-reads/
├── app.py              # Flask app: all routes + both seed commands
├── models.py           # SQLAlchemy models (User, Group, Book, Meeting, ...)
├── requirements.txt
├── templates/           # Jinja2 HTML templates
└── static/
    └── style.css
```

## Adding your own real groups

You don't need to touch the code to add real groups — just sign up through
the site and click "Start a Group." If you'd rather preload a longer list at
once (so you don't have to click through the UI for each one), add entries
to the `course_groups` list inside the `seed_courses()` function in `app.py`
following the same pattern, then re-run `flask --app app seed-courses`.

## Notes for extending it

- The database is SQLite (`campus_reads.db`, created on first run) — fine for
  a class demo, and a straightforward swap to PostgreSQL later since it's
  accessed entirely through SQLAlchemy.
- `SECRET_KEY` in `app.py` is a hardcoded dev value — replace it with an
  environment variable before deploying anywhere real.
- There's no email verification or campus-domain restriction on sign-up;
  that's a natural next feature if you want to limit membership to students.
