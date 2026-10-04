from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(280), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship("Membership", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def role_in(self, group_id):
        m = Membership.query.filter_by(user_id=self.id, group_id=group_id).first()
        return m.role if m else None

    def is_member_of(self, group_id):
        return self.role_in(group_id) is not None

    def is_organizer_of(self, group_id):
        return self.role_in(group_id) == "organizer"


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), default="")
    genre = db.Column(db.String(80), default="General")
    meeting_location = db.Column(db.String(160), default="")
    is_private = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship("Membership", back_populates="group", cascade="all, delete-orphan")
    books = db.relationship("Book", back_populates="group", cascade="all, delete-orphan", order_by="Book.start_date.desc()")
    meetings = db.relationship("Meeting", back_populates="group", cascade="all, delete-orphan", order_by="Meeting.datetime")

    @property
    def member_count(self):
        return len(self.memberships)

    @property
    def current_book(self):
        return next((b for b in self.books if b.status == "current"), None)

    @property
    def past_books(self):
        return [b for b in self.books if b.status == "past"]

    @property
    def upcoming_meetings(self):
        now = datetime.utcnow()
        return [m for m in self.meetings if m.datetime >= now]


class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    role = db.Column(db.String(20), default="member")  # 'member' or 'organizer'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="memberships")
    group = db.relationship("Group", back_populates="memberships")

    __table_args__ = (db.UniqueConstraint("user_id", "group_id", name="unique_membership"),)


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(160), default="")
    cover_url = db.Column(db.String(400), default="")
    synopsis = db.Column(db.String(800), default="")
    status = db.Column(db.String(20), default="current")  # 'current' or 'past'
    start_date = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("Group", back_populates="books")
    comments = db.relationship("Comment", back_populates="book", cascade="all, delete-orphan", order_by="Comment.created_at")


class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200), default="")
    notes = db.Column(db.String(400), default="")

    group = db.relationship("Group", back_populates="meetings")
    rsvps = db.relationship("RSVP", back_populates="meeting", cascade="all, delete-orphan")

    def rsvp_counts(self):
        counts = {"going": 0, "maybe": 0, "no": 0}
        for r in self.rsvps:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts

    def rsvp_for(self, user_id):
        r = next((r for r in self.rsvps if r.user_id == user_id), None)
        return r.status if r else None


class RSVP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meeting.id"), nullable=False)
    status = db.Column(db.String(10), default="going")  # 'going', 'maybe', 'no'

    user = db.relationship("User")
    meeting = db.relationship("Meeting", back_populates="rsvps")

    __table_args__ = (db.UniqueConstraint("user_id", "meeting_id", name="unique_rsvp"),)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.String(1000), nullable=False)
    is_spoiler = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    book = db.relationship("Book", back_populates="comments")
    user = db.relationship("User")
