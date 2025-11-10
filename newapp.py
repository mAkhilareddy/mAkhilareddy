from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
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
    file_size = db.Column(db.Float, nullable=True)  # ✅ new field added
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class ProposalComment(db.Model):
    __tablename__ = 'proposal_comments'
    id = db.Column(db.Integer, primary_key=True)
    proposal_id = db.Column(db.Integer, db.ForeignKey('proposals.id'))
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class CaseStudy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    standard = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(100), nullable=False)
    file_name = db.Column(db.String(255))
    file_path = db.Column(db.String(255))
    file_size = db.Column(db.Float)  # in KB
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.String(100))


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
    @app.route('/')
    def main_home():
        return render_template('main_home.html')
    

    @app.route('/proposal_manager')
    @login_required
    def proposal_manager():
        proposals = Proposal.query.filter_by(user_id=current_user.id).order_by(Proposal.uploaded_at.desc()).all()
        return render_template(
            'home.html',
            user_authenticated=current_user.is_authenticated,
            proposals=proposals
            )

    @app.route('/research_development')
    def research_development():
        return render_template('research_development.html', datetime=datetime)
    

    @app.route('/npd')
    def npd():
        return render_template('npd.html', datetime=datetime)



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
                return redirect(url_for('home'))
            else:
                error = "Invalid username or password"
        return render_template('login.html', error=error)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash("Logged out successfully", "info")
        return redirect(url_for('home'))
    
    

    @app.route('/case_upload', methods=['GET', 'POST'])
    @login_required
    def case_upload():
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            standard = request.form.get('standard') or 'all'   # ✅ Default if missing
            industry = request.form.get('industry') or 'all'   # ✅ Default if missing
            file = request.files.get('file')
            
            if file:
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(app.root_path, 'static/uploads/casestudies')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                
                file_size = round(os.path.getsize(filepath) / 1024, 2)  # KB
                
                new_case = CaseStudy(
                    title=title,
                    description=description,
                    standard=standard,   # ✅ Added missing field
                    industry=industry,
                    file_name=filename,
                    file_path=filepath,
                    file_size=file_size,
                    uploaded_by=current_user.username
                    )
                db.session.add(new_case)
                db.session.commit()
                
                flash('✅ Case Study uploaded successfully!', 'success')
                return redirect(url_for('case_upload'))
            
        return render_template('case_upload.html')



    # ---------------- Case Study Home ----------------
    @app.route('/case_study')
    @login_required
    def case_study():return render_template('case_study.html')




    @app.route('/case_search', methods=['GET', 'POST'])
    @login_required
    def case_search():
    # Get search filters from form or query params
       keyword = request.values.get('keyword', '').strip()
       standard = request.values.get('standard', '').strip()
       industry = request.values.get('industry', '').strip()

       # Base query
       results = CaseStudy.query

       # Apply filters
       if keyword:
           results = results.filter(
               (CaseStudy.title.ilike(f"%{keyword}%")) |
               (CaseStudy.description.ilike(f"%{keyword}%"))
               
            )
       if standard:
        results = results.filter(CaseStudy.industry.ilike(f"%{standard}%"))  # optional field
       if industry:
           results = results.filter(CaseStudy.industry.ilike(f"%{industry}%"))

       # Final result list
       results = results.order_by(CaseStudy.upload_date.desc()).all()

       return render_template(
         'case_search.html',
         results=results,
         keyword=keyword,
         standard=standard,
         industry=industry,
         year=datetime.now().year
     )

    @app.route('/case_download/<int:case_study_id>')
    @login_required
    def case_download(case_study_id):
        case = CaseStudy.query.get_or_404(case_study_id)
        if case.file_path and os.path.exists(case.file_path):
            return send_from_directory(os.path.dirname(case.file_path), os.path.basename(case.file_path), as_attachment=True)
        flash("File not found!", "danger")
        return redirect(url_for('case_search'))


    @app.route('/case_delete/<int:case_study_id>', methods=['POST'])
    @login_required
    def case_delete(case_study_id):
        case = CaseStudy.query.get_or_404(case_study_id)

        # If file exists, delete it
        if case.file_path and os.path.exists(case.file_path):
            os.remove(case.file_path)

        # Always delete the database record
        db.session.delete(case)
        db.session.commit()
        flash("Case study deleted successfully!", "success")
        
        return redirect(url_for('case_search'))



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
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file_size = round(os.path.getsize(file_path) / (1024 * 1024), 2)  # MB size

                
                new_proposal = Proposal(
                    title=title,
                    description=description,
                    standard=standard,
                    industry=industry,
                    filename=filename,
                    file_size=file_size,
                    user_id=current_user.id
                    
                    )
                db.session.add(new_proposal)
                db.session.commit()
                flash("Proposal uploaded successfully!", "success")
                return redirect(url_for("dashboard"))
        return render_template("upload.html")



    

    @app.route('/search', methods=['GET', 'POST'])
    def search():
        keyword = request.args.get('keyword', '').lower()
        standard = request.args.get('standard', '').lower()
        industry = request.args.get('industry', '').lower()
        
        query = Proposal.query
        
        if keyword:
            query = query.filter(Proposal.title.ilike(f'%{keyword}%') | Proposal.description.ilike(f'%{keyword}%'))
        if standard:
            query = query.filter(Proposal.standard.ilike(f'%{standard}%'))
        if industry:
            query = query.filter(Proposal.industry.ilike(f'%{industry}%'))

        results = query.all()
        return render_template('search_results.html', results=results, year=datetime.now().year)


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
    # Example: Fetch client data from the database
      clients = [
          {"id": 1, "name": "Tata Motors", "industry": "Automotive", "projects": 12, "status": "Active"},
          {"id": 2, "name": "Siemens", "industry": "Electrical", "projects": 8, "status": "Active"},
          {"id": 3, "name": "Bosch", "industry": "Power Electronics", "projects": 10, "status": "Inactive"},
          {"id": 4, "name": "ABB", "industry": "Automation", "projects": 6, "status": "Active"},
          
          ]
      
      return render_template("clients.html", clients=clients)

    

    @app.route('/about')
    def about():
      return render_template('About Us.html')

    @app.route('/settings')
    def settings():
      return render_template('Settings.html')

    #@app.route('/export')
    #def export():
      #return render_template('export.html')
    
    @app.route('/export')
    @login_required
    def export():
        proposals = Proposal.query.filter_by(user_id=current_user.id).all()
        data = [
            {
                "Title": p.title,
                "Description": p.description,
                "Standard": p.standard,
                "Industry": p.industry,
                "Uploaded": p.uploaded_at.strftime("%Y-%m-%d"),
                }
                for p in proposals
                ]
        import pandas as pd
        df = pd.DataFrame(data)
        file_path = "exported_proposals.csv"
        df.to_csv(file_path, index=False)
        return send_from_directory(".", file_path, as_attachment=True)



    @app.route('/analytics')
    @login_required
    def analytics():
        total_proposals = Proposal.query.count()
        by_standard = db.session.query(
            Proposal.standard, db.func.count(Proposal.id)
            ).group_by(Proposal.standard).all()
        
        by_industry = db.session.query(
            Proposal.industry, db.func.count(Proposal.id)
            ).group_by(Proposal.industry).all()
        
        monthly_trends = db.session.query(
            db.func.strftime("%Y-%m", Proposal.uploaded_at),
            db.func.count(Proposal.id)
            ).group_by(db.func.strftime("%Y-%m", Proposal.uploaded_at)).all()
        
        return render_template(
            'analytics.html',
            total_proposals=total_proposals,
            by_standard=by_standard,
            by_industry=by_industry,
            monthly_trends=monthly_trends
            
            )



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
