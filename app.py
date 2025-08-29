from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

# In-memory storage
topics = []
topic_id = 1

@app.route("/")
def home():
    return render_template("index.html", topics=topics)

@app.route("/create", methods=["GET", "POST"])
def create_topic():
    global topic_id
    if request.method == "POST":
        title = request.form["title"]
        event_date = request.form["event_date"]
        outcomes = request.form.getlist("outcomes")

        topics.append({
            "id": topic_id,
            "title": title,
            "event_date": event_date,
            "outcomes": outcomes,  # possible outcomes (poll options)
            "votes": {o: 0 for o in outcomes},  # count of votes
            "messages": [],  # discussion thread
            "outcome": None
        })
        topic_id += 1
        return redirect(url_for("home"))
    return render_template("create.html")

@app.route("/topic/<int:id>", methods=["GET", "POST"])
def topic_detail(id):
    topic = next((t for t in topics if t["id"] == id), None)
    if not topic:
        return "Topic not found", 404

    # Handle voting
    if request.method == "POST":
        if "vote" in request.form:
            choice = request.form["vote"]
            if choice in topic["votes"]:
                topic["votes"][choice] += 1
        elif "message" in request.form:
            msg = request.form["message"]
            if msg.strip():
                topic["messages"].append(msg)

    return render_template("topic.html", topic=topic)

@app.route("/resolve/<int:id>", methods=["POST"])
def resolve_topic(id):
    topic = next((t for t in topics if t["id"] == id), None)
    if topic:
        outcome = request.form["outcome"]
        if outcome in topic["outcomes"]:
            topic["outcome"] = outcome
    return redirect(url_for("topic_detail", id=id))

if __name__ == "__main__":
    app.run(debug=True)
