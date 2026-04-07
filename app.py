from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import json
from datetime import datetime, date
import anthropic

app = Flask(__name__)
app.secret_key = "confidence_builder_secret_2025"

DB_PATH = "database.db"

# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        points INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        confidence_score REAL DEFAULT 0.0,
        streak INTEGER DEFAULT 0,
        last_active TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT,
        difficulty TEXT,
        points INTEGER DEFAULT 10
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_id INTEGER,
        completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(task_id) REFERENCES tasks(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        content TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS streak_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        log_date TEXT,
        UNIQUE(user_id, log_date),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Seed tasks
    c.execute("SELECT COUNT(*) FROM tasks")
    if c.fetchone()[0] == 0:
        tasks = [
            # Coding
            ("Reverse a String", "Write a program to reverse any string without using built-in reverse().", "Coding", "Easy", 10),
            ("Find Factorial", "Write a recursive function to find factorial of a number.", "Coding", "Easy", 10),
            ("List Comprehension", "Create a list of squares of numbers from 1-20 using list comprehension.", "Coding", "Easy", 15),
            ("FizzBuzz Challenge", "Print numbers 1-100. For multiples of 3 print 'Fizz', 4 print 'Buzz', both print 'FizzBuzz'.", "Coding", "Medium", 20),
            ("Binary Search", "Implement binary search algorithm from scratch.", "Coding", "Medium", 25),
            ("Linked List Insert", "Implement insert at beginning for a singly linked list.", "Coding", "Medium", 25),
            ("Palindrome Check", "Write a function to check if a string is a palindrome.", "Coding", "Easy", 10),
            ("Stack using Array", "Implement a Stack with push, pop, peek using an array.", "Coding", "Medium", 30),
            # Communication
            ("2-Min Concept Explain", "Pick any tech concept (e.g., API, recursion) and explain it in under 2 minutes out loud.", "Communication", "Easy", 15),
            ("Write a LinkedIn Post", "Write a short LinkedIn post about something you learned today.", "Communication", "Easy", 20),
            ("Email a Doubt", "Write a formal email to a professor asking for help with a topic.", "Communication", "Easy", 15),
            ("Elevator Pitch", "Describe yourself + your goals in under 60 seconds as if talking to a recruiter.", "Communication", "Medium", 25),
            # Problem Solving
            ("Sudoku Strategy", "Learn and explain one technique for solving Sudoku puzzles.", "Problem Solving", "Easy", 15),
            ("Daily Bug Fix", "Find and fix a bug in any of your existing programs.", "Problem Solving", "Medium", 20),
            ("Plan Your Week", "Create a structured weekly study timetable for next 7 days.", "Problem Solving", "Easy", 15),
            ("LeetCode Easy", "Solve any 1 Easy problem on LeetCode and note your approach.", "Problem Solving", "Medium", 30),
        ]
        c.executemany(
            "INSERT INTO tasks (title, description, category, difficulty, points) VALUES (?,?,?,?,?)",
            tasks
        )

    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def logged_in():
    return "user_id" in session

def get_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def calc_level(points):
    if points < 50:   return 1
    if points < 150:  return 2
    if points < 300:  return 3
    if points < 500:  return 4
    if points < 750:  return 5
    if points < 1100: return 6
    if points < 1600: return 7
    if points < 2200: return 8
    if points < 3000: return 9
    return 10

def calc_confidence(user_id, conn):
    total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    done  = conn.execute("SELECT COUNT(DISTINCT task_id) FROM user_tasks WHERE user_id=?", (user_id,)).fetchone()[0]
    streak = conn.execute("SELECT streak FROM users WHERE id=?", (user_id,)).fetchone()[0]
    score = round(min(100, (done / max(total,1)) * 60 + min(streak, 7) * 4 + min(done * 2, 20)), 1)
    return score

def update_streak(user_id, conn):
    today = date.today().isoformat()
    try:
        conn.execute("INSERT INTO streak_log (user_id, log_date) VALUES (?,?)", (user_id, today))
        # Count consecutive days
        logs = conn.execute(
            "SELECT log_date FROM streak_log WHERE user_id=? ORDER BY log_date DESC", (user_id,)
        ).fetchall()
        streak = 1
        for i in range(1, len(logs)):
            d1 = datetime.fromisoformat(logs[i-1]["log_date"])
            d2 = datetime.fromisoformat(logs[i]["log_date"])
            if (d1 - d2).days == 1:
                streak += 1
            else:
                break
        conn.execute("UPDATE users SET streak=?, last_active=? WHERE id=?", (streak, today, user_id))
    except:
        pass  # Already logged today

def get_badges(user):
    badges = []
    p = user["points"]
    done_count = user.get("done_count", 0)
    streak = user["streak"]
    if p >= 10:      badges.append(("🌱", "First Step",    "Earned first points!"))
    if p >= 100:     badges.append(("⚡", "Momentum",      "100+ points earned"))
    if p >= 300:     badges.append(("🔥", "On Fire",       "300+ points — beast mode"))
    if p >= 750:     badges.append(("💎", "Diamond Coder", "750+ points — elite level"))
    if streak >= 3:  badges.append(("🗓️", "Consistent",   "3-day streak"))
    if streak >= 7:  badges.append(("🏆", "Week Warrior",  "7-day streak — legendary"))
    if done_count >= 5:  badges.append(("✅", "Task Crusher", "5 tasks completed"))
    if done_count >= 10: badges.append(("🚀", "Rocket",       "10 tasks done — unstoppable"))
    return badges

# ─────────────────────────────────────────────
# ROUTES — AUTH
# ─────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("home.html", logged_in=logged_in())

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if logged_in():
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        username = request.form["username"].strip()
        email    = request.form["email"].strip()
        password = request.form["password"]
        if not username or not email or not password:
            error = "All fields are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            conn = get_db()
            try:
                conn.execute(
                    "INSERT INTO users (username, email, password) VALUES (?,?,?)",
                    (username, email, generate_password_hash(password))
                )
                conn.commit()
                user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                conn.close()
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                error = "Username or email already exists."
            finally:
                conn.close()
    return render_template("signup.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    if logged_in():
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        email    = request.form["email"].strip()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"]  = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        error = "Invalid email or password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ─────────────────────────────────────────────
# ROUTES — MAIN PAGES
# ─────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    if not logged_in():
        return redirect(url_for("login"))
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    completed_ids = [r["task_id"] for r in
        conn.execute("SELECT task_id FROM user_tasks WHERE user_id=?", (session["user_id"],)).fetchall()]
    recent = conn.execute(
        """SELECT t.title, t.category, t.points, ut.completed_at
           FROM user_tasks ut JOIN tasks t ON ut.task_id = t.id
           WHERE ut.user_id=? ORDER BY ut.completed_at DESC LIMIT 5""",
        (session["user_id"],)
    ).fetchall()
    confidence = calc_confidence(session["user_id"], conn)
    conn.execute("UPDATE users SET confidence_score=? WHERE id=?", (confidence, session["user_id"]))
    conn.commit()
    user_dict = dict(user)
    user_dict["done_count"] = len(completed_ids)
    badges = get_badges(user_dict)
    next_level_pts = [0,50,150,300,500,750,1100,1600,2200,3000,9999]
    lvl = calc_level(user["points"])
    pts_for_next = next_level_pts[min(lvl, 9)]
    pts_current_lvl = next_level_pts[lvl-1]
    progress_pct = int((user["points"] - pts_current_lvl) / max(pts_for_next - pts_current_lvl, 1) * 100)
    conn.close()
    return render_template("dashboard.html",
        user=user_dict,
        confidence=confidence,
        badges=badges,
        recent=recent,
        completed_count=len(completed_ids),
        level=lvl,
        progress_pct=min(progress_pct, 100),
        pts_for_next=pts_for_next
    )

@app.route("/challenges")
def challenges():
    if not logged_in():
        return redirect(url_for("login"))
    conn = get_db()
    tasks = conn.execute("SELECT * FROM tasks ORDER BY category, difficulty").fetchall()
    completed_ids = {r["task_id"] for r in
        conn.execute("SELECT task_id FROM user_tasks WHERE user_id=?", (session["user_id"],)).fetchall()}
    conn.close()
    categories = {}
    for t in tasks:
        cat = t["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(dict(t))
    return render_template("challenges.html",
        categories=categories,
        completed_ids=completed_ids
    )

@app.route("/ai-chat")
def ai_chat():
    if not logged_in():
        return redirect(url_for("login"))
    conn = get_db()
    history = conn.execute(
        "SELECT role, content FROM chat_history WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    history = list(reversed(history))
    return render_template("ai_chat.html", history=history)

@app.route("/progress")
def progress():
    if not logged_in():
        return redirect(url_for("login"))
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    # Last 14 days task completions
    daily_data = conn.execute(
        """SELECT date(completed_at) as day, COUNT(*) as cnt
           FROM user_tasks WHERE user_id=?
           GROUP BY day ORDER BY day DESC LIMIT 14""",
        (session["user_id"],)
    ).fetchall()
    # Category breakdown
    cat_data = conn.execute(
        """SELECT t.category, COUNT(*) as cnt
           FROM user_tasks ut JOIN tasks t ON ut.task_id = t.id
           WHERE ut.user_id=? GROUP BY t.category""",
        (session["user_id"],)
    ).fetchall()
    total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    done_tasks  = conn.execute("SELECT COUNT(DISTINCT task_id) FROM user_tasks WHERE user_id=?",
                               (session["user_id"],)).fetchone()[0]
    confidence  = calc_confidence(session["user_id"], conn)
    conn.close()

    daily_labels = [r["day"] for r in reversed(daily_data)]
    daily_counts = [r["cnt"] for r in reversed(daily_data)]
    cat_labels   = [r["category"] for r in cat_data]
    cat_counts   = [r["cnt"] for r in cat_data]

    return render_template("progress.html",
        user=dict(user),
        daily_labels=json.dumps(daily_labels),
        daily_counts=json.dumps(daily_counts),
        cat_labels=json.dumps(cat_labels),
        cat_counts=json.dumps(cat_counts),
        total_tasks=total_tasks,
        done_tasks=done_tasks,
        confidence=confidence,
        level=calc_level(user["points"])
    )

# ─────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────
@app.route("/api/complete-task", methods=["POST"])
def complete_task():
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    task_id = data.get("task_id")
    user_id = session["user_id"]
    conn = get_db()
    # Check already done
    existing = conn.execute(
        "SELECT id FROM user_tasks WHERE user_id=? AND task_id=?", (user_id, task_id)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Already completed"}), 400
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    conn.execute("INSERT INTO user_tasks (user_id, task_id) VALUES (?,?)", (user_id, task_id))
    new_points = conn.execute("SELECT points FROM users WHERE id=?", (user_id,)).fetchone()[0] + task["points"]
    new_level  = calc_level(new_points)
    conn.execute("UPDATE users SET points=?, level=? WHERE id=?", (new_points, new_level, user_id))
    update_streak(user_id, conn)
    confidence = calc_confidence(user_id, conn)
    conn.execute("UPDATE users SET confidence_score=? WHERE id=?", (confidence, user_id))
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "points_earned": task["points"],
        "total_points": new_points,
        "level": new_level,
        "confidence": confidence
    })

@app.route("/api/chat", methods=["POST"])
def chat():
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    data    = request.json
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    user_id = session["user_id"]
    conn = get_db()

    # Load history for context
    history = conn.execute(
        "SELECT role, content FROM chat_history WHERE user_id=? ORDER BY created_at ASC LIMIT 20",
        (user_id,)
    ).fetchall()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

    messages = [{"role": r["role"], "content": r["content"]} for r in history]
    messages.append({"role": "user", "content": message})

    system_prompt = f"""You are an AI mentor and study buddy for {user['username']}, 
a B.Tech CSE (AI & ML) student who is passionate about becoming a software engineer at top tech companies like Microsoft.

Your personality: Encouraging, direct, knowledgeable, slightly casual (like a smart senior student).
You help with: Python, Java, DSA, career advice, study planning, motivation, and doubt-solving.

Student stats: Points: {user['points']}, Level: {calc_level(user['points'])}, 
Streak: {user['streak']} days, Confidence Score: {user['confidence_score']}%

Keep responses concise (2-4 paragraphs max). Use emojis occasionally. 
If they ask a coding question, always give working code examples.
Always end with an encouraging one-liner."""

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )
        reply = response.content[0].text
    except Exception as e:
        reply = f"⚠️ AI temporarily unavailable. Set ANTHROPIC_API_KEY env variable to enable AI chat. Error: {str(e)[:100]}"

    # Save to history
    conn.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?,?,?)",
                 (user_id, "user", message))
    conn.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?,?,?)",
                 (user_id, "assistant", reply))
    conn.commit()
    conn.close()
    return jsonify({"reply": reply})

@app.route("/api/clear-chat", methods=["POST"])
def clear_chat():
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    conn = get_db()
    conn.execute("DELETE FROM chat_history WHERE user_id=?", (session["user_id"],))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
import os

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
