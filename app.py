import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from werkzeug.utils import secure_filename
from models import db, Poll, Option, Vote, Comment
from forms import CreatePollForm
from sqlalchemy import func

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///polls.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4MB

db.init_app(app)

# ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


@app.before_request
def ensure_user_id():
    """Assign a pseudo user id to each visitor via session."""
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())


@app.cli.command("init-db")
def init_db():
    """Flask CLI command: flask init-db"""
    with app.app_context():
        db.create_all()
        print("Initialized DB")


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    sort = request.args.get("sort", "")

    polls_query = Poll.query

    if q:
        polls_query = polls_query.filter(Poll.title.ilike(f"%{q}%") | Poll.description.ilike(f"%{q}%"))

    if category:
        polls_query = polls_query.filter_by(category=category)

    polls = polls_query.all()

    # compute total_votes for each poll (simple)
    for p in polls:
        p.total_votes = db.session.query(func.count(Vote.id)).join(Option).filter(Option.poll_id == p.id).scalar() or 0
        p.comments_count = len(p.comments or [])

    # sort options
    if sort == "active":
        polls.sort(key=lambda x: x.total_votes or 0, reverse=True)
    elif sort == "mature":
        polls = [p for p in polls if p.event_date is not None]
        polls.sort(key=lambda x: x.event_date or datetime.max)

    # Most active and most mature
    all_polls = Poll.query.all()
    most_active = None
    most_mature = None
    if all_polls:
        for p in all_polls:
            p.total_votes = db.session.query(func.count(Vote.id)).join(Option).filter(Option.poll_id == p.id).scalar() or 0
        most_active = max(all_polls, key=lambda x: x.total_votes) if any(all_polls) else None
        upcoming = [p for p in all_polls if p.event_date and p.is_active]
        if upcoming:
            most_mature = min(upcoming, key=lambda x: x.event_date)

    return render_template("index.html", polls=polls, most_active=most_active, most_mature=most_mature)


@app.route("/admin/create", methods=["GET", "POST"])
def create_poll():
    form = CreatePollForm()
    if request.method == "POST":
        # validate required fields manually for simple dynamic options
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip() or None
        event_date_raw = request.form.get("event_date", "").strip()
        options_raw = request.form.getlist("options[]")
        # filter empty options
        options = [o.strip() for o in options_raw if o.strip()]
        if not title:
            flash("Title is required", "danger")
        elif not options or len(options) < 2:
            flash("Please provide at least 2 options", "danger")
        else:
            # parse event date
            event_date = None
            if event_date_raw:
                try:
                    event_date = datetime.fromisoformat(event_date_raw)
                except Exception:
                    event_date = None

            # handle image
            image_filename = None
            image = request.files.get("image")
            if image and image.filename:
                filename = secure_filename(image.filename)
                ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                if ext in ALLOWED_EXT:
                    unique = f"{uuid.uuid4().hex}.{ext}"
                    save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique)
                    image.save(save_path)
                    image_filename = unique
                else:
                    flash("Unsupported image type. Allowed: png,jpg,jpeg,gif", "warning")

            # create poll
            poll = Poll(
                title=title,
                description=description or None,
                category=category,
                image_filename=image_filename,
                event_date=event_date,
                is_active=True,
            )
            db.session.add(poll)
            db.session.flush()  # get poll.id

            # create options
            for opt_text in options:
                opt = Option(text=opt_text, poll_id=poll.id)
                db.session.add(opt)

            db.session.commit()
            flash("Poll created", "success")
            return redirect(url_for("poll_detail", poll_id=poll.id))

    return render_template("create_poll.html", form=form)


@app.route("/poll/<int:poll_id>", methods=["GET", "POST"])
def poll_detail(poll_id):
    poll = Poll.query.get_or_404(poll_id)

    # compute counts
    poll.total_votes = db.session.query(func.count(Vote.id)).join(Option).filter(Option.poll_id == poll.id).scalar() or 0

    # handle POSTs: voting or comment or admin actions
    if request.method == "POST":
        # Vote submission
        if "vote_submit" in request.form:
            option_id = request.form.get("option")
            if not poll.is_active:
                flash("Poll is closed.", "warning")
                return redirect(url_for("poll_detail", poll_id=poll.id))

            if option_id:
                # ensure option belongs to this poll
                opt = Option.query.filter_by(id=option_id, poll_id=poll.id).first()
                if opt:
                    user_id = session.get("user_id")
                    # allow changing vote: if vote exists, update; else create
                    existing = (
                        Vote.query.join(Option)
                        .filter(Option.poll_id == poll.id, Vote.user_id == user_id)
                        .first()
                    )
                    if existing:
                        existing.option_id = opt.id
                        db.session.commit()
                        flash("Vote updated", "success")
                    else:
                        v = Vote(option_id=opt.id, user_id=user_id)
                        db.session.add(v)
                        db.session.commit()
                        flash("Vote recorded", "success")
                else:
                    flash("Invalid option", "danger")
            return redirect(url_for("poll_detail", poll_id=poll.id))

        # Comment submission
        if "comment_submit" in request.form:
            text = request.form.get("comment", "").strip()
            if text:
                c = Comment(content=text, poll_id=poll.id, user_id=session.get("user_id"))
                db.session.add(c)
                db.session.commit()
                flash("Comment posted", "success")
            else:
                flash("Empty comment", "warning")
            return redirect(url_for("poll_detail", poll_id=poll.id))

        # Admin: resolve poll (set outcome) or close/open or edit options via admin form fields
        if "resolve_submit" in request.form:
            chosen = request.form.get("outcome")
            if chosen:
                # verify chosen is an option text
                opt = Option.query.filter_by(id=chosen, poll_id=poll.id).first()
                if opt:
                    poll.outcome = opt.text
                    poll.is_active = False
                    db.session.commit()
                    flash("Poll resolved", "success")
                else:
                    flash("Invalid outcome", "danger")
            return redirect(url_for("poll_detail", poll_id=poll.id))

        if "toggle_active" in request.form:
            poll.is_active = not poll.is_active
            db.session.commit()
            flash("Poll status updated", "success")
            return redirect(url_for("poll_detail", poll_id=poll.id))

    # queries for template
    options = Option.query.filter_by(poll_id=poll.id).all()
    # attach votes count to options
    for o in options:
        o.votes_count = Vote.query.filter_by(option_id=o.id).count()

    comments = Comment.query.filter_by(poll_id=poll.id).order_by(Comment.created_at.desc()).all()

    # figure out user's vote (if any)
    user_vote = None
    user_id = session.get("user_id")
    if user_id:
        existing = Vote.query.join(Option).filter(Option.poll_id == poll.id, Vote.user_id == user_id).first()
        if existing:
            user_vote = existing.option_id

    return render_template("poll_detail.html", poll=poll, options=options, comments=comments, user_vote=user_vote)


@app.route("/dashboard")
def dashboard():
    user_id = session.get("user_id")
    # polls the user voted in
    votes = Vote.query.filter_by(user_id=user_id).all()
    participated_poll_ids = {Option.query.get(v.option_id).poll_id for v in votes}
    participated_count = len(participated_poll_ids)

    # correct vs incorrect
    correct = 0
    incorrect = 0
    open_votes = 0
    recent_voted_polls = []

    for v in votes:
        opt = Option.query.get(v.option_id)
        poll = Poll.query.get(opt.poll_id)
        # skip duplicates for counting participated polls
        if poll.id not in [p.id for p in recent_voted_polls]:
            # determine correctness only if poll has outcome
            if poll.outcome:
                if opt.text == poll.outcome:
                    correct += 1
                else:
                    incorrect += 1
            else:
                open_votes += 1
            recent_voted_polls.append(poll)

    accuracy = (correct / (correct + incorrect) * 100) if (correct + incorrect) > 0 else 0

    # add helper attribute for template
    for p in recent_voted_polls:
        # find user's vote option text and correctness
        v = Vote.query.join(Option).filter(Option.poll_id == p.id, Vote.user_id == user_id).first()
        if v:
            o = Option.query.get(v.option_id)
            p.user_correct = None
            if p.outcome is not None:
                p.user_correct = (o.text == p.outcome)
            else:
                p.user_correct = None
        p.total_votes = db.session.query(func.count(Vote.id)).join(Option).filter(Option.poll_id == p.id).scalar() or 0

    user_stats = {
        "participated": participated_count,
        "correct": correct,
        "incorrect": incorrect,
        "open_votes": open_votes,
        "accuracy_pct": accuracy,
    }

    return render_template("dashboard.html", user_stats=user_stats, recent_voted_polls=recent_voted_polls, open_participations=[p for p in recent_voted_polls if not p.outcome])


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    # on first run create DB
    with app.app_context():
        db.create_all()
        # print("✅ Tables created:", db.engine.table_names())
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
