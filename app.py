# app.py
from flask import (
    Flask,
    render_template,
    request,
    make_response,
    redirect,
    url_for,
    session,
)
from scraper import scrape_jobs
from database import init_db, save_jobs, get_all_jobs
from werkzeug.utils import secure_filename
from openai import OpenAI
import os
import tempfile
import re

app = Flask(__name__)
init_db()
app.secret_key = "CHANGE_THIS_SECRET_KEY"   

saved_jobs = {}   # {"username": [ {title, company, location}, ... ]}


# ---------- HOME / JOB SEARCH ----------
@app.route("/")
def index():
    jobs = get_all_jobs()
    user = session.get("user")
    return render_template(
        "index.html",
        jobs=jobs,
        letter=None,
        message=None,
        match_result=None,
        user=user,
    )


@app.route("/scrape", methods=["GET"])
def scrape():
    keyword = request.args.get("keyword", "developer")
    city = request.args.get("city", "Toronto")
    postal = request.args.get("postal", "")
    location = f"{city} {postal}".strip()

    print(f"🔍 Searching for jobs: keyword='{keyword}', location='{location}'")

    jobs = scrape_jobs(keyword=keyword, city=city)
    save_jobs(jobs)

    message = None if jobs else f"⚠️ No jobs found for '{keyword}' in '{location}'. Try another search."

    return render_template(
        "index.html",
        jobs=get_all_jobs(),
        letter=None,
        message=message,
        match_result=None,
        user=session.get("user"),
    )


# ---------- CLEAN AI OUTPUT ----------
def clean_output(text):
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = text.replace(" --- ", "<br><br>")
    text = text.replace("\n", "<br>")
    return text


# ---------- GENERATE COVER LETTER ----------
@app.route("/generate", methods=["POST"])
def generate():
    job_title = request.form["title"]
    company = request.form["company"]
    location = request.form["location"]

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = (
            f"Write a short professional job application letter for a {job_title} "
            f"position at {company} in {location}. Make it sound confident and polished."
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = resp.choices[0].message.content
        letter = clean_output(raw_text)
        return render_template(
            "index.html",
            jobs=get_all_jobs(),
            letter=letter,
            message=None,
            match_result=None,
            user=session.get("user"),
        )

    except Exception as e:
        return render_template(
            "index.html",
            jobs=get_all_jobs(),
            letter=f"Error generating letter: {e}",
            message=None,
            match_result=None,
            user=session.get("user"),
        )


# ---------- RESUME OPTIMIZER ----------
@app.route("/optimize", methods=["POST"])
def optimize_resume():
    job_title = request.form["title"]
    company = request.form["company"]
    location = request.form["location"]
    file = request.files.get("resume")

    if not file:
        return render_template(
            "index.html",
            jobs=get_all_jobs(),
            letter="⚠️ Please upload a resume file.",
            user=session.get("user"),
        )

    filename = secure_filename(file.filename)
    temp_path = tempfile.mktemp()
    file.save(temp_path)

    try:
        # Extract text
        text = ""
        if filename.lower().endswith(".txt"):
            with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        elif filename.lower().endswith(".pdf"):
            import PyPDF2
            reader = PyPDF2.PdfReader(temp_path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif filename.lower().endswith(".docx"):
            import docx
            doc = docx.Document(temp_path)
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            return render_template(
                "index.html",
                jobs=get_all_jobs(),
                letter="⚠️ Unsupported file format (use .txt, .pdf, or .docx).",
                user=session.get("user"),
            )

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = (
            f"Optimize this resume for a job as '{job_title}' at '{company}' in '{location}'. "
            "Improve clarity, add strong bullet points, and include relevant keywords.\n\n"
            f"Resume:\n{text}"
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )

        optimized = clean_output(resp.choices[0].message.content)

        return render_template(
            "index.html",
            jobs=get_all_jobs(),
            letter=optimized,
            message="✅ Resume optimized.",
            match_result=None,
            user=session.get("user"),
        )

    except Exception as e:
        return render_template(
            "index.html",
            jobs=get_all_jobs(),
            letter=f"Error optimizing resume: {e}",
            user=session.get("user"),
        )

    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

# ---------- NEW: RESUME vs JOB MATCH SCORE (Embeddings-based) ----------
@app.route("/match_score", methods=["POST"])
def match_score():
    resume_file = request.files.get("resume")
    job_title = request.form.get("title", "").strip()
    company = request.form.get("company", "").strip()
    location = request.form.get("location", "").strip()
    job_desc = request.form.get("description", "").strip()

    # Validate Input
    if not resume_file or not job_desc:
        return render_template(
            "index.html",
            jobs=get_all_jobs(),
            letter=None,
            message="⚠️ Please upload a resume AND include a job description.",
            match_result=None,
            user=session.get("user"),
        )

    # Read resume file
    try:
        resume_text = resume_file.read().decode("utf-8", errors="ignore")
    except:
        resume_text = ""

    # Handle empty resume
    if resume_text.strip() == "":
        return render_template(
            "index.html",
            jobs=get_all_jobs(),
            message="⚠️ Could not read the resume file.",
            match_result=None,
            user=session.get("user"),
        )

    # AI Request
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = f"""
Compare this resume to the job description and give a match score (0-100%).

Respond ONLY in this format:
Match Score: XX% - explanation

Job Title: {job_title}
Company: {company}
Location: {location}

Job Description:
{job_desc}

Resume:
{resume_text}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        match_result = resp.choices[0].message.content.strip()

    except Exception as e:
        if "insufficient_quota" in str(e):
            match_result = "⚠️ OpenAI API limit reached — add billing or use cheaper model"
        else:
            match_result = f"⚠️ Error computing match score: {e}"

    return render_template(
        "index.html",
        jobs=get_all_jobs(),
        letter=None,
        message=None,
        match_result=match_result,
        user=session.get("user"),
    )


    

# ---------- DOWNLOAD AS TEXT ----------
@app.route("/download", methods=["POST"])
def download_text():
    text = request.form.get("text", "")
    text = text.replace("<br>", "\n").replace("<b>", "").replace("</b>", "")
    response = make_response(text)
    response.headers["Content-Disposition"] = "attachment; filename=job_letter.txt"
    response.headers["Content-Type"] = "text/plain"
    return response


# ---------- RESUME BUILDER ----------
@app.route("/resume_builder")
def resume_builder():
    return render_template("resume_builder.html", user=session.get("user"))


@app.route("/generate_resume", methods=["POST"])
def generate_resume():
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    experience = request.form.get("experience")
    skills = request.form.get("skills")
    job_goal = request.form.get("job_goal")

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = f"""
Generate a full professional resume based on this information.
Format cleanly with bullet points, resume headings, and clear layout.

Name: {name}
Email: {email}
Phone: {phone}

Career Objective: {job_goal}

Experience:
{experience}

Skills:
{skills}

Do NOT use markdown. Output in formatted plain text.
"""

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )

        resume = resp.choices[0].message.content.replace("\n", "<br>")

        return render_template(
            "resume_builder.html",
            resume=resume,
            user=session.get("user"),
        )

    except Exception as e:
        return render_template(
            "resume_builder.html",
            resume=f"⚠️ Error generating resume: {e}",
            user=session.get("user"),
        )


# ---------- LOGIN ----------
DEMO_USER = {"username": "student", "password": "1234"}

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (
            request.form.get("username") == DEMO_USER["username"]
            and request.form.get("password") == DEMO_USER["password"]
        ):
            session["user"] = DEMO_USER["username"]
            return redirect(url_for("index"))

        return render_template("login.html", error="Invalid username or password.")

    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


# ---------- SAVE JOBS ----------
@app.route("/save_job", methods=["POST"])
def save_job():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    saved_jobs.setdefault(user, []).append(
        {
            "title": request.form["title"],
            "company": request.form["company"],
            "location": request.form["location"],
        }
    )

    return redirect(url_for("index"))


@app.route("/saved")
def view_saved():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    return render_template(
        "saved.html", jobs=saved_jobs.get(user, []), user=user
    )


# ---------- HEALTH CHECK ----------
@app.route("/health")
def health():
    return "ok"


# ---------- RUN APP ----------
if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
