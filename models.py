from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Poll(db.Model):
    __tablename__ = "poll"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(80))
    image_filename = db.Column(db.String(255))
    event_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    outcome = db.Column(db.String(255), nullable=True)  # final outcome text when resolved

    options = db.relationship("Option", backref="poll", cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="poll", cascade="all, delete-orphan")


class Option(db.Model):
    __tablename__ = "option"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(255), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey("poll.id"), nullable=False)
    votes = db.relationship("Vote", backref="option", cascade="all, delete-orphan")


class Vote(db.Model):
    __tablename__ = "vote"
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey("option.id"), nullable=False)
    user_id = db.Column(db.String(255), nullable=False)  # pseudo-user via session
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Comment(db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    poll_id = db.Column(db.Integer, db.ForeignKey("poll.id"), nullable=False)
    user_id = db.Column(db.String(255), nullable=True)
