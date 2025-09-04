from flask import Flask, render_template, request, redirect, url_for, flash, session,send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///proposals.db'
app.config['UPLOAD_FOLDER'] = "uploaded_proposals"
db = SQLAlchemy(app)
app.secret_key = 'your_secret_key'  # For flash messages and sessions

# -------------------- Database Model --------------------
class Proposal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    standard = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    filename = db.Column(db.String(200), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Proposal {self.title}>"

# -------------------- Routes ----------------------
# Mock user authentication status (set to True when logged in, False otherwise)
user_authenticated = False
@app.route("/")
def home():
    return render_template('home.html', user_authenticated=user_authenticated)

# Dummy user data for authentication (this can be replaced with a database check)
users = {'admin': 'password123'}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if the username and password match
        if username in users and users[username] == password:
            # Set the user as logged in (e.g., using Flask sessions)
            session['user'] = username
            return redirect(url_for('home'))  # Redirect to home page after successful login
        else:
            flash('Invalid username or password', 'danger')  # Show an error message if login fails

    return render_template('login.html', error='Invalid username or password')

@app.route('/logout')
def logout():
    global user_authenticated
    user_authenticated = False  # Set the user to logged out
    return redirect(url_for('home'))

@app.route('/settings')
def settings():
    return render_template('Settings.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    return render_template('register.html')  # Or any logic for the register page


@app.route('/about')
def about():
    return render_template('About Us.html')

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        standard = request.form.get("standard")
        industry = request.form.get("industry")
        file = request.files.get("file")

        filename = None
        if file:
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            filename = file.filename
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        new_proposal = Proposal(
            title=title,
            description=description,
            standard=standard,
            industry=industry,
            filename=filename
        )
        db.session.add(new_proposal)
        db.session.commit()
        return redirect(url_for("home"))

    return render_template("upload.html")

@app.route("/search")
def search():
    keyword = request.args.get("keyword", "")
    description = request.args.get("description", "")
    standard = request.args.get("standard", "")
    industry = request.args.get("industry", "")

    query = Proposal.query
    if keyword:
        query = query.filter(Proposal.title.contains(keyword))
    if description:
        query = query.filter(Proposal.description.contains(description))
    if standard:
        query = query.filter(Proposal.standard.contains(standard))
    if industry:
        query = query.filter(Proposal.industry.contains(industry))

    results = query.all()
    return render_template("search_results.html", results=results)

@app.route("/download/<int:proposal_id>")
def download(proposal_id):
    proposal = Proposal.query.get_or_404(proposal_id)
    if proposal.filename:
        return send_from_directory(app.config["UPLOAD_FOLDER"], proposal.filename, as_attachment=True)
    return "File not found", 404

# -------------------- Run App --------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)















