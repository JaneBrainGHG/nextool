from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import shutil
from functools import wraps
from datetime import datetime

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Bitte logge dich ein, um diese Seite zu sehen.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Benutzername existiert bereits!', 'danger')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = User(username=username)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registrierung erfolgreich! Du kannst dich jetzt einloggen.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Ungültiger Benutzername oder Passwort!', 'danger')
            return redirect(url_for('login'))
        
        session['user_id'] = user.id
        session['username'] = user.username
        
        # Use a default registration date if the column doesn't exist
        try:
            session['registration_date'] = user.registration_date.strftime('%d.%m.%Y')
        except:
            session['registration_date'] = '01.01.2023'  # Default date
        
        flash(f'Willkommen zurück, {user.username}!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('registration_date', None)
    flash('Du wurdest ausgeloggt.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Get current user
        user = User.query.get(session['user_id'])
        
        # Check if current password is correct
        if not user.check_password(current_password):
            flash('Aktuelles Passwort ist falsch!', 'danger')
            return redirect(url_for('dashboard'))
        
        # Check if new passwords match
        if new_password != confirm_password:
            flash('Neue Passwörter stimmen nicht überein!', 'danger')
            return redirect(url_for('dashboard'))
        
        # Update password
        user.set_password(new_password)
        db.session.commit()
        
        flash('Passwort erfolgreich geändert!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('dashboard.html')

@app.route('/download-jar')
@login_required
def download_jar():
    # Get the requested filename from the query parameter
    filename = request.args.get('filename', 'download.jar')
    
    # Ensure the filename ends with .jar
    if not filename.lower().endswith('.jar'):
        filename += '.jar'
    
    # Path to the original JAR file
    original_jar_path = os.path.join(app.static_folder, 'downloads', 'test.jar')
    
    # Create a temporary directory if it doesn't exist
    temp_dir = os.path.join(app.static_folder, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Path for the temporary copy with the custom filename
    temp_jar_path = os.path.join(temp_dir, filename)
    
    # Copy the original JAR to the temp directory with the new filename
    shutil.copy2(original_jar_path, temp_jar_path)
    
    # Serve the file
    response = send_from_directory(temp_dir, filename, as_attachment=True)
    
    # Schedule the temporary file for deletion after sending
    # (This is a simple approach - in production you might want to use a cleanup task)
    @response.call_on_close
    def cleanup():
        try:
            os.remove(temp_jar_path)
        except:
            pass
    
    return response

# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Make sure the static/downloads directory exists
    os.makedirs(os.path.join(app.static_folder, 'downloads'), exist_ok=True)
    app.run(debug=True)