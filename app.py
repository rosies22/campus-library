from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)

from models import db, User, Group, Membership, Book, Meeting, RSVP, Comment

app = Flask(__name__)
app.config["SECRET_KEY"] = "campus-reads-dev-secret"  # fine for a local class demo
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campus_reads.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Home / browse groups
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    genre = request.args.get("genre", "").strip()
    query = request.args.get("q", "").strip()

    groups_query = Group.query
    if genre:
        groups_query = groups_query.filter(Group.genre == genre)
    if query:
        groups_query = groups_query.filter(Group.name.ilike(f"%{query}%"))

    groups = groups_query.order_by(Group.created_at.desc()).all()
    genres = sorted({g.genre for g in Group.query.all()})

    return render_template("index.html", groups=groups, genres=genres,
                            active_genre=genre, query=query)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in every field.", "error")
            return render_template("signup.html")

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("signup.html")

        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"Welcome, {user.name}!", "success")
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.name}.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))

        flash("Incorrect email or password.", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# My groups dashboard
# ---------------------------------------------------------------------------

@app.route("/my-groups")
@login_required
def my_groups():
    memberships = Membership.query.filter_by(user_id=current_user.id).all()
    groups = [m.group for m in memberships]

    upcoming = []
    for g in groups:
        for m in g.upcoming_meetings:
            upcoming.append(m)
    upcoming.sort(key=lambda m: m.datetime)

    return render_template("my_groups.html", groups=groups, upcoming=upcoming)


# ---------------------------------------------------------------------------
# Group create / detail
# ---------------------------------------------------------------------------

@app.route("/group/create", methods=["GET", "POST"])
@login_required
def create_group():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        genre = request.form.get("genre", "General").strip() or "General"
        meeting_location = request.form.get("meeting_location", "").strip()

        if not name:
            flash("Every group needs a name.", "error")
            return render_template("create_group.html")

        group = Group(name=name, description=description, genre=genre,
                      meeting_location=meeting_location, created_by=current_user.id)
        db.session.add(group)
        db.session.flush()  # get group.id before commit

        membership = Membership(user_id=current_user.id, group_id=group.id, role="organizer")
        db.session.add(membership)
        db.session.commit()

        flash(f'"{group.name}" is live. Add a current book to get things going.', "success")
        return redirect(url_for("group_detail", group_id=group.id))

    return render_template("create_group.html")


@app.route("/group/<int:group_id>")
def group_detail(group_id):
    group = db.session.get(Group, group_id) or abort(404)
    is_member = current_user.is_authenticated and current_user.is_member_of(group.id)
    is_organizer = current_user.is_authenticated and current_user.is_organizer_of(group.id)
    current_book = group.current_book

    my_rsvps = {}
    if current_user.is_authenticated:
        for m in group.meetings:
            status = m.rsvp_for(current_user.id)
            if status:
                my_rsvps[m.id] = status

    return render_template(
        "group_detail.html",
        group=group,
        is_member=is_member,
        is_organizer=is_organizer,
        current_book=current_book,
        my_rsvps=my_rsvps,
        now=datetime.utcnow(),
    )


@app.route("/group/<int:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id):
    group = db.session.get(Group, group_id) or abort(404)
    if not current_user.is_member_of(group.id):
        db.session.add(Membership(user_id=current_user.id, group_id=group.id, role="member"))
        db.session.commit()
        flash(f'You joined "{group.name}".', "success")
    return redirect(url_for("group_detail", group_id=group.id))


@app.route("/group/<int:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id):
    group = db.session.get(Group, group_id) or abort(404)
    membership = Membership.query.filter_by(user_id=current_user.id, group_id=group.id).first()
    if membership:
        if membership.role == "organizer":
            other_organizers = Membership.query.filter_by(group_id=group.id, role="organizer") \
                .filter(Membership.user_id != current_user.id).count()
            if other_organizers == 0:
                flash("You're the only organizer — promote someone else before leaving.", "error")
                return redirect(url_for("group_detail", group_id=group.id))
        db.session.delete(membership)
        db.session.commit()
        flash(f'You left "{group.name}".', "success")
    return redirect(url_for("group_detail", group_id=group.id))


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------

@app.route("/group/<int:group_id>/book/new", methods=["GET", "POST"])
@login_required
def new_book(group_id):
    group = db.session.get(Group, group_id) or abort(404)
    if not current_user.is_organizer_of(group.id):
        abort(403)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        cover_url = request.form.get("cover_url", "").strip()
        synopsis = request.form.get("synopsis", "").strip()

        if not title:
            flash("A book needs at least a title.", "error")
            return render_template("new_book.html", group=group)

        # retire the old current book
        old_current = group.current_book
        if old_current:
            old_current.status = "past"

        book = Book(group_id=group.id, title=title, author=author,
                    cover_url=cover_url, synopsis=synopsis, status="current")
        db.session.add(book)
        db.session.commit()

        flash(f'Now reading "{book.title}". The discussion thread is open.', "success")
        return redirect(url_for("group_detail", group_id=group.id))

    return render_template("new_book.html", group=group)


# ---------------------------------------------------------------------------
# Meetings + RSVP
# ---------------------------------------------------------------------------

@app.route("/group/<int:group_id>/meeting/new", methods=["GET", "POST"])
@login_required
def new_meeting(group_id):
    group = db.session.get(Group, group_id) or abort(404)
    if not current_user.is_organizer_of(group.id):
        abort(403)

    if request.method == "POST":
        date_str = request.form.get("date", "")
        time_str = request.form.get("time", "")
        location = request.form.get("location", "").strip() or group.meeting_location
        notes = request.form.get("notes", "").strip()

        try:
            when = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            flash("Please provide a valid date and time.", "error")
            return render_template("new_meeting.html", group=group)

        meeting = Meeting(group_id=group.id, datetime=when, location=location, notes=notes)
        db.session.add(meeting)
        db.session.commit()

        flash("Meeting scheduled.", "success")
        return redirect(url_for("group_detail", group_id=group.id))

    return render_template("new_meeting.html", group=group)


@app.route("/meeting/<int:meeting_id>/rsvp", methods=["POST"])
@login_required
def rsvp_meeting(meeting_id):
    meeting = db.session.get(Meeting, meeting_id) or abort(404)
    if not current_user.is_member_of(meeting.group_id):
        abort(403)

    status = request.form.get("status")
    if status not in ("going", "maybe", "no"):
        abort(400)

    existing = RSVP.query.filter_by(user_id=current_user.id, meeting_id=meeting.id).first()
    if existing:
        existing.status = status
    else:
        db.session.add(RSVP(user_id=current_user.id, meeting_id=meeting.id, status=status))
    db.session.commit()

    return redirect(url_for("group_detail", group_id=meeting.group_id))


# ---------------------------------------------------------------------------
# Discussion
# ---------------------------------------------------------------------------

@app.route("/book/<int:book_id>/comment", methods=["POST"])
@login_required
def new_comment(book_id):
    book = db.session.get(Book, book_id) or abort(404)
    if not current_user.is_member_of(book.group_id):
        abort(403)

    body = request.form.get("body", "").strip()
    is_spoiler = request.form.get("is_spoiler") == "on"

    if body:
        db.session.add(Comment(book_id=book.id, user_id=current_user.id,
                               body=body, is_spoiler=is_spoiler))
        db.session.commit()

    return redirect(url_for("group_detail", group_id=book.group_id))


# ---------------------------------------------------------------------------
# CLI helper: seed a small demo
# ---------------------------------------------------------------------------

@app.cli.command("seed")
def seed():
    """Populate the database with a couple of demo groups. Run: flask --app app seed"""
    db.drop_all()
    db.create_all()

    demo = User(name="Demo Student", email="demo@campus.edu", bio="Just here for the books.")
    demo.set_password("password123")
    db.session.add(demo)
    db.session.flush()

    g1 = Group(name="Sci-Fi & Society", genre="Science Fiction",
               description="Speculative fiction that says something about the world we live in now.",
               meeting_location="Library Room 204", created_by=demo.id)
    g2 = Group(name="Campus Poetry Circle", genre="Poetry",
               description="Bring a poem, bring an opinion. All levels welcome.",
               meeting_location="Student Union Lounge", created_by=demo.id)
    db.session.add_all([g1, g2])
    db.session.flush()

    db.session.add(Membership(user_id=demo.id, group_id=g1.id, role="organizer"))
    db.session.add(Membership(user_id=demo.id, group_id=g2.id, role="organizer"))

    book1 = Book(group_id=g1.id, title="The Left Hand of Darkness", author="Ursula K. Le Guin",
                 synopsis="An envoy on a world without fixed gender navigates politics and survival.",
                 status="current")
    db.session.add(book1)

    meeting1 = Meeting(group_id=g1.id, datetime=datetime(2026, 9, 20, 18, 0),
                       location="Library Room 204", notes="Discuss chapters 1-6.")
    db.session.add(meeting1)

    db.session.commit()
    print("Seeded database with demo data. Login as demo@campus.edu / password123")


# ---------------------------------------------------------------------------
# CLI helper: seed with university-course-themed reading groups
# ---------------------------------------------------------------------------

@app.cli.command("seed-courses")
def seed_courses():
    """
    Wipe the database and populate it with reading groups themed around
    common university subjects/courses. Each group has its own organizer
    account (password 'password123' for all of them), a current book, and
    an upcoming meeting. Run: flask --app app seed-courses
    """
    db.drop_all()
    db.create_all()

    today = datetime.utcnow()

    course_groups = [
        {
            "organizer_name": "Maya Chen",
            "organizer_email": "maya.chen@campus.edu",
            "name": "World Literature Circle",
            "genre": "Literature",
            "description": "For students in World Literature and anyone who loves fiction in translation.",
            "location": "Library Room 204",
            "book_title": "The Brief Wondrous Life of Oscar Wao",
            "book_author": "Junot Díaz",
            "book_synopsis": "A sweeping, footnoted story of a Dominican-American family across generations, "
                              "blending immigrant history with comic-book nerd culture.",
            "days_until_meeting": 5,
            "meeting_time": "18:00",
            "meeting_notes": "Discuss Part One — come with a favorite footnote.",
        },
        {
            "organizer_name": "Daniel Osei",
            "organizer_email": "daniel.osei@campus.edu",
            "name": "Intro to Psychology Book Club",
            "genre": "Psychology",
            "description": "Pairs with PSYC 101 — we read the books professors cite but never assign in full.",
            "location": "Psychology Building, Room 112",
            "book_title": "Thinking, Fast and Slow",
            "book_author": "Daniel Kahneman",
            "book_synopsis": "A Nobel laureate's account of the two systems that drive how we think, "
                              "and the biases that come with each.",
            "days_until_meeting": 3,
            "meeting_time": "17:30",
            "meeting_notes": "Chapters 1-5. Bring an example of a cognitive bias you caught yourself in.",
        },
        {
            "organizer_name": "Priya Patel",
            "organizer_email": "priya.patel@campus.edu",
            "name": "CS Beyond the Classroom",
            "genre": "Computer Science",
            "description": "For CS majors who want to read about the craft, not just the syntax.",
            "location": "Engineering Building, Lab 3",
            "book_title": "The Pragmatic Programmer",
            "book_author": "David Thomas & Andrew Hunt",
            "book_synopsis": "Practical, timeless advice on writing better software, from naming "
                              "things well to debugging effectively.",
            "days_until_meeting": 7,
            "meeting_time": "19:00",
            "meeting_notes": "Read the first three chapters. Bring one 'tip' you actually tried.",
        },
        {
            "organizer_name": "Jordan Lee",
            "organizer_email": "jordan.lee@campus.edu",
            "name": "Philosophy After Hours",
            "genre": "Philosophy",
            "description": "Open discussion group for anyone taking (or auditing) a philosophy course this term.",
            "location": "Humanities Hall, Room 208",
            "book_title": "Meditations",
            "book_author": "Marcus Aurelius",
            "book_synopsis": "The private journal of a Roman emperor, a foundational text of Stoic "
                              "philosophy on duty, mortality, and self-discipline.",
            "days_until_meeting": 4,
            "meeting_time": "18:30",
            "meeting_notes": "Book 1 and 2. No prior philosophy background needed.",
        },
        {
            "organizer_name": "Aisha Bello",
            "organizer_email": "aisha.bello@campus.edu",
            "name": "Econ & Business Reads",
            "genre": "Economics",
            "description": "For students in micro, macro, or just anyone curious how economists think.",
            "location": "Business School, Room 150",
            "book_title": "Freakonomics",
            "book_author": "Steven D. Levitt & Stephen J. Dubner",
            "book_synopsis": "A rogue economist applies economic thinking to everything from crime "
                              "rates to sumo wrestling.",
            "days_until_meeting": 6,
            "meeting_time": "17:00",
            "meeting_notes": "First four chapters — come ready to argue with the authors.",
        },
        {
            "organizer_name": "Thomas Nguyen",
            "organizer_email": "thomas.nguyen@campus.edu",
            "name": "History Majors' Book Club",
            "genre": "History",
            "description": "Big-picture history reads for anyone minoring or majoring in History.",
            "location": "Library Room 310",
            "book_title": "Sapiens: A Brief History of Humankind",
            "book_author": "Yuval Noah Harari",
            "book_synopsis": "A sweeping account of how Homo sapiens came to dominate the planet, "
                              "from cognitive revolution to the scientific era.",
            "days_until_meeting": 8,
            "meeting_time": "18:00",
            "meeting_notes": "Part One: The Cognitive Revolution.",
        },
        {
            "organizer_name": "Grace Kim",
            "organizer_email": "grace.kim@campus.edu",
            "name": "Environmental Science Reading Group",
            "genre": "Environmental Science",
            "description": "Science-backed, non-preachy reads for anyone in ENVS or just concerned about the planet.",
            "location": "Science Center, Room 220",
            "book_title": "The Sixth Extinction",
            "book_author": "Elizabeth Kolbert",
            "book_synopsis": "A Pulitzer-winning investigation into the mass extinction unfolding "
                              "right now, and humanity's role in it.",
            "days_until_meeting": 10,
            "meeting_time": "16:30",
            "meeting_notes": "Chapters 1-3. We'll also plan a campus clean-up after.",
        },
        {
            "organizer_name": "Omar Haddad",
            "organizer_email": "omar.haddad@campus.edu",
            "name": "Political Theory Forum",
            "genre": "Political Science",
            "description": "For Poli Sci students and anyone who wants to argue about power and justice.",
            "location": "Student Union, Room 3B",
            "book_title": "The Origins of Totalitarianism",
            "book_author": "Hannah Arendt",
            "book_synopsis": "A landmark analysis of how totalitarian movements rose in the 20th "
                              "century, and the conditions that make them possible.",
            "days_until_meeting": 2,
            "meeting_time": "19:30",
            "meeting_notes": "Preface and Part One. Fair warning: dense but worth it.",
        },
    ]

    for data in course_groups:
        organizer = User(name=data["organizer_name"], email=data["organizer_email"],
                          bio=f"Organizes {data['name']}.")
        organizer.set_password("password123")
        db.session.add(organizer)
        db.session.flush()

        group = Group(name=data["name"], genre=data["genre"], description=data["description"],
                      meeting_location=data["location"], created_by=organizer.id)
        db.session.add(group)
        db.session.flush()

        db.session.add(Membership(user_id=organizer.id, group_id=group.id, role="organizer"))

        book = Book(group_id=group.id, title=data["book_title"], author=data["book_author"],
                    synopsis=data["book_synopsis"], status="current")
        db.session.add(book)

        meeting_date = today + timedelta(days=data["days_until_meeting"])
        hour, minute = map(int, data["meeting_time"].split(":"))
        meeting_dt = meeting_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        meeting = Meeting(group_id=group.id, datetime=meeting_dt, location=data["location"],
                          notes=data["meeting_notes"])
        db.session.add(meeting)

    db.session.commit()

    print(f"Seeded {len(course_groups)} university-course reading groups.")
    print("Every organizer account uses the password: password123")
    print("Organizer emails:")
    for data in course_groups:
        print(f"  {data['organizer_email']}  ->  {data['name']}")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
