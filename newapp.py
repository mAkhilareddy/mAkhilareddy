from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
import os, uuid

# -------------------- Extensions --------------------
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

# -------------------- Database Models --------------------
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_client = db.Column(db.Boolean, default=False)

    proposals = db.relationship('Proposal', backref='user', lazy=True)


class Proposal(db.Model):
    __tablename__ = 'proposals'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    standard = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    filename = db.Column(db.String(200), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class ProposalComment(db.Model):
    __tablename__ = 'proposal_comments'
    id = db.Column(db.Integer, primary_key=True)
    proposal_id = db.Column(db.Integer, db.ForeignKey('proposals.id'))
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# -------------------- App Factory --------------------
def create_app():
    app = Flask(__name__)
    app.secret_key = 'your_secret_key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///proposals.db'
    app.config['UPLOAD_FOLDER'] = "uploaded_proposals"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    # -------------------- Flask-Login Setup --------------------
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # -------------------- Routes --------------------
    @app.route("/")
    def home():
        proposals = Proposal.query.all()
        return render_template("home.html",
                               user_authenticated=current_user.is_authenticated,
                               proposals=proposals)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                flash("Logged in successfully!", "success")
                return redirect(url_for('dashboard'))
            else:
                error = "Invalid username or password"
        return render_template('login.html', error=error)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash("Logged out successfully", "info")
        return redirect(url_for('home'))

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        error = None
        if request.method == 'POST':
            username = request.form.get('username').strip()
            email = request.form.get('email')   # added email field
            password = request.form.get('password')
            if not username or not password or not email:
                error = "Username, email and password are required."
            elif User.query.filter_by(username=username).first():
                error = "Username already exists."
            elif User.query.filter_by(email=email).first():
                error = "Email already registered."
            else:
                hashed_password = generate_password_hash(password)
                new_user = User(username=username, email=email, password_hash=hashed_password)
                db.session.add(new_user)
                db.session.commit()
                flash("Registration successful! You can now log in.")
                return redirect(url_for('login'))
        return render_template('register.html', error=error)

    # Keep the rest of your routes (upload, search, dashboard, etc.)

# -------------------- Proposal Routes --------------------
    @app.route("/upload", methods=["GET", "POST"])
    @login_required
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
                filename = f"{uuid.uuid4().hex}_{file.filename}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                
                new_proposal = Proposal(
                    title=title, description=description, standard=standard,
                    industry=industry, filename=filename, user_id=current_user.id
                    
                    )
                db.session.add(new_proposal)
                db.session.commit()
                flash("Proposal uploaded successfully!", "success")
                return redirect(url_for("dashboard"))
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


    @app.route("/dashboard")
    @login_required
    def dashboard():
        total_proposals = Proposal.query.count()
        user_proposals = Proposal.query.filter_by(user_id=current_user.id).count()
        
        industries = db.session.query(
            Proposal.industry, db.func.count(Proposal.id)
            ).group_by(Proposal.industry).all()
        
        proposals = Proposal.query.filter_by(user_id=current_user.id).order_by(Proposal.uploaded_at.desc()).all()
        
        chart_data = [
            {"year": "2021", "europe": 2.5, "namerica": 2.5, "asia": 2.4, "lamerica": 2.4, "meast": 2.2, "africa": 2.3},
            {"year": "2022", "europe": 2.7, "namerica": 2.9, "asia": 2.8, "lamerica": 2.8, "meast": 2.5, "africa": 2.6},
            {"year": "2023", "europe": 3.5, "namerica": 3.6, "asia": 3.1, "lamerica": 3.3, "meast": 3.0, "africa": 2.9},
            
            ]
        
        return render_template("dashboard.html",
                               total_proposals=total_proposals,
                               user_proposals=user_proposals,
                               industries=industries,
                               chart_data=chart_data,
                               proposals=proposals
                               
                               )


    @app.route("/api/dashboard-data")
    @login_required
    def dashboard_data():
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=int)
        
        query = Proposal.query
        if year:
            query = query.filter(db.extract('year', Proposal.uploaded_at) == year)
            if month:
                query = query.filter(db.extract('month', Proposal.uploaded_at) == month)
                industry_data = query.with_entities(
                    Proposal.industry, db.func.count(Proposal.id)
                    ).group_by(Proposal.industry).all()
                
                trend_data = [
                    {"year": str(year or 2023), "europe": 2.5, "namerica": 2.1,
                     "asia": 1.7, "lamerica": 1.2, "meast": 0.9, "africa": 0.5}
                     
                     ]
                
                return jsonify({"industries": industry_data, "trends": trend_data})


    @app.route('/track')
    @login_required
    def track():
        user_proposals = Proposal.query.filter_by(user_id=current_user.id).order_by(Proposal.uploaded_at.desc()).all()
        return render_template('track.html', proposals=user_proposals)


    @app.route('/clients')
    def clients():
      return render_template('clients.html')

    @app.route('/about')
    def about():
      return render_template('About Us.html')

    @app.route('/settings')
    def settings():
      return render_template('Settings.html')

    @app.route('/export')
    def export():
      return render_template('export.html')


    @app.route('/analytics')
    def analytics():
      return render_template('analytics.html')


    @app.route("/delete/<int:proposal_id>", methods=['POST'])
    @login_required
    def delete(proposal_id):
        proposal = Proposal.query.get_or_404(proposal_id)
        if proposal.user_id != current_user.id:
            flash("You do not have permission to delete this proposal.", "danger")
            return redirect(url_for('dashboard'))
        
        if proposal.filename:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], proposal.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                db.session.delete(proposal)
                db.session.commit()
                flash("Proposal deleted successfully!", "success")
                return redirect(url_for('dashboard'))
            
    return app


# -------------------- Run App --------------------
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)
