# app.py

import os
import json
import random
import operator 
import re 
from uuid import uuid4

from flask import Flask, jsonify, request, render_template, session, redirect, url_for, flash
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import google.generativeai as genai

# --- 1. KONFIGURASI AWAL ---
load_dotenv()
app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kunci-rahasia-yang-sangat-aman-dan-unik')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# --- 2. MODEL DATABASE ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    profiles = db.relationship('Profile', backref='parent', lazy=True, cascade="all, delete-orphan")
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    pin_hash = db.Column(db.String(256), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scores = db.relationship('UserScore', backref='profile', lazy=True, cascade="all, delete-orphan")
    # PERUBAHAN DI SINI: Menambahkan kolom untuk menyimpan nama file avatar
    avatar = db.Column(db.String(100), nullable=True, default='default.png')
    
    def set_pin(self, pin): self.pin_hash = generate_password_hash(str(pin))
    def check_pin(self, pin): return check_password_hash(self.pin_hash, str(pin))

class UserScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(80), nullable=False)
    score = db.Column(db.Integer, default=0)
    profile_id = db.Column(db.Integer, db.ForeignKey('profile.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('profile_id', 'topic', name='_profile_topic_uc'),)

# --- 3. KONFIGURASI AI & BANK PROMPT ---
api_key = os.getenv("GEMINI_API_KEY")
if not api_key: raise ValueError("GEMINI_API_KEY tidak ditemukan di file .env Anda.")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')
QUESTION_STYLES = ["soal cerita fantasi singkat", "teka-teki matematika sederhana", "petualangan mencari harta karun", "Permainan videogame yang menyenangkan", "Penjelajahan Luar Angkasa", "Cerita dongeng dengan karakter lucu"]
CHARACTERS = ["Dino si Dinosaurus", "Kiki si Kucing Cerdas", "Pyro si naga api", "Jack si pelaut", "Evan si Penjelajah", "Luna si Astronot", "Milo si Robot Pintar", "Zara si Penyihir", "Leo si Pahlawan Kecil", "Nina si Detektif Cilik", "Riko si Pemburu Harta Karun", "Tina si Penari Bintang", "Bobo si Penjelajah Hutan", "Coco si Penyanyi Cilik", "Rara si Pelukis Ajaib", "Fifi si Pahlawan Super", "Gigi si Gadis Petualang", "Lulu si Penyelam Laut"]
OBJECTS = {
    "penjumlahan": ["koin emas", "permata ajaib", "buah beri", "ramuan penyembuh", "anak panah", "kue bulan", "kantong bibit pohon", "tumpukan buku sihir", "kotak berisi kunang-kunang", "bunga ajaib", "potongan pizza jamur", "kelompok kunang-kunang", "kue ajaib", "bintang-bintang", "kepingan es", "balok kayu", "kepingan kue", "batu permata", "kepingan puzzle", "kepingan permen", "kepingan kertas origami"],
    "pengurangan": ["koin emas", "permata ajaib", "buah beri", "ramuan penyembuh", "anak panah", "kue bulan", "kantong bibit pohon", "tumpukan buku sihir", "kotak berisi kunang-kunang", "bunga ajaib", "potongan pizza jamur", "kelompok kunang-kunang", "kue ajaib", "bintang-bintang", "kepingan es", "balok kayu", "kepingan kue", "batu permata", "kepingan puzzle", "kepingan permen", "kepingan kertas origami"],
    "perkalian": ["koin emas", "permata ajaib", "buah beri", "ramuan penyembuh", "anak panah", "kue bulan", "kantong bibit pohon", "tumpukan buku sihir", "kotak berisi kunang-kunang", "bunga ajaib", "potongan pizza jamur", "kelompok kunang-kunang", "kue ajaib", "bintang-bintang", "kepingan es", "balok kayu", "kepingan kue", "batu permata", "kepingan puzzle", "kepingan permen", "kepingan kertas origami"],
    "pembagian": ["koin emas", "permata ajaib", "buah beri", "ramuan penyembuh", "anak panah", "kue bulan", "kantong bibit pohon", "tumpukan buku sihir", "kotak berisi kunang-kunang", "bunga ajaib", "potongan pizza jamur", "kelompok kunang-kunang", "kue ajaib", "bintang-bintang", "kepingan es", "balok kayu", "kepingan kue", "batu permata", "kepingan puzzle", "kepingan permen", "kepingan kertas origami"]
}
TOPIC_TO_OP_FUNC = {'penjumlahan': operator.add, 'pengurangan': operator.sub, 'perkalian': operator.mul, 'pembagian': operator.truediv}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- 4. ROUTES & ENDPOINTS ---

@app.route("/")
def home():
    if 'user_id' in session: return redirect(url_for('parent_dashboard'))
    if 'current_profile_id' in session: return redirect(url_for('student_dashboard'))
    return render_template('splash.html')

@app.route('/petualangan')
def student_dashboard():
    if 'current_profile_id' not in session:
        if 'user_id' in session:
            flash("Silakan pilih profil anak untuk melanjutkan.", "info")
            return redirect(url_for('parent_dashboard'))
        return redirect(url_for('child_login'))
    profile_id = session['current_profile_id']
    scores = UserScore.query.filter_by(profile_id=profile_id).all()
    unlocked_topics = {'penjumlahan', 'pengurangan'}
    score_map = {s.topic: s.score for s in scores}
    if score_map.get('penjumlahan', 0) >= 50:
        unlocked_topics.add('perkalian')
    if score_map.get('perkalian', 0) >= 50:
        unlocked_topics.add('pembagian')
    return render_template("dashboard.html", unlocked_topics=unlocked_topics)

@app.route("/game")
def game_page():
    if 'current_profile_id' not in session: return redirect(url_for('child_login'))
    topic = request.args.get('topic', 'penjumlahan')
    profile_id = session.get('current_profile_id')
    return render_template("index.html", game_topic=topic, profile_id=profile_id)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash('Email dan password tidak boleh kosong.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email sudah terdaftar. Silakan gunakan email lain atau login.', 'warning')
            return redirect(url_for('register'))
        new_user = User(email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Pendaftaran berhasil! Silakan masuk.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('parent_dashboard'))
        flash('Email atau password salah. Silakan coba lagi.', 'danger')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/login-anak', methods=['GET', 'POST'])
def child_login():
    if request.method == 'POST':
        username = request.form.get('username')
        pin = request.form.get('pin')
        profile = Profile.query.filter_by(username=username).first()
        if profile and profile.check_pin(pin):
            session.clear()
            session['current_profile_id'] = profile.id
            session['current_profile_name'] = profile.name
            return redirect(url_for('student_dashboard'))
        flash('Username atau PIN salah. Coba lagi ya!', 'danger')
        return redirect(url_for('child_login'))
    return render_template('child_login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah berhasil keluar.', 'success')
    return redirect(url_for('home'))

@app.route('/dashboard-orang-tua')
def parent_dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    parent = User.query.get(session['user_id'])
    return render_template('parent_dashboard.html', profiles=parent.profiles)

@app.route('/pilih-profil/<int:profile_id>')
def select_profile(profile_id):
    profile = Profile.query.get_or_404(profile_id)
    if 'user_id' not in session or session['user_id'] != profile.parent_id:
        flash("Akses ditolak.", "danger")
        return redirect(url_for('parent_dashboard'))
    session['current_profile_id'] = profile.id
    session['current_profile_name'] = profile.name
    return redirect(url_for('student_dashboard'))

@app.route('/tambah-profil', methods=['GET', 'POST'])
def add_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        pin = request.form.get('pin')
        if not all([name, username, pin]):
            flash('Semua kolom harus diisi.', 'danger')
            return redirect(url_for('add_profile'))
        if Profile.query.filter_by(username=username).first():
            flash('Username tersebut sudah digunakan. Pilih yang lain.', 'warning')
            return redirect(url_for('add_profile'))
        new_profile = Profile(name=name, username=username, parent_id=session['user_id'])
        new_profile.set_pin(pin)
        db.session.add(new_profile)
        db.session.commit()
        flash(f'Profil untuk {name} berhasil dibuat!', 'success')
        return redirect(url_for('parent_dashboard'))
    return render_template('add_profile.html')

@app.route('/edit-profil/<int:profile_id>', methods=['GET', 'POST'])
def edit_profile(profile_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    profile_to_edit = Profile.query.get_or_404(profile_id)
    if session['user_id'] != profile_to_edit.parent_id:
        flash("Akses ditolak.", "danger")
        return redirect(url_for('parent_dashboard'))

    if request.method == 'POST':
        profile_to_edit.name = request.form.get('name')
        new_username = request.form.get('username')
        existing_profile = Profile.query.filter(Profile.username == new_username, Profile.id != profile_id).first()
        if existing_profile:
            flash('Username tersebut sudah digunakan. Pilih yang lain.', 'warning')
            return redirect(url_for('edit_profile', profile_id=profile_id))
        profile_to_edit.username = new_username
        
        new_pin = request.form.get('pin')
        if new_pin:
            profile_to_edit.set_pin(new_pin)

        # --- LOGIKA UNGGAH FILE YANG DIKEMBALIKAN ---
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = str(uuid4()) + "_" + filename
                # Pastikan folder avatars ada
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                profile_to_edit.avatar = unique_filename
        
        db.session.commit()
        flash('Profil berhasil diperbarui!', 'success')
        return redirect(url_for('parent_dashboard'))
        
    return render_template('edit_profile.html', profile=profile_to_edit)

@app.route('/hapus-profil/<int:profile_id>', methods=['POST'])
def delete_profile(profile_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    profile_to_delete = Profile.query.get_or_404(profile_id)
    if session['user_id'] != profile_to_delete.parent_id:
        flash("Akses ditolak.", "danger")
        return redirect(url_for('parent_dashboard'))
    db.session.delete(profile_to_delete)
    db.session.commit()
    flash('Profil berhasil dihapus.', 'success')
    return redirect(url_for('parent_dashboard'))

@app.route('/laporan/<int:profile_id>')
def report_page(profile_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    profile = Profile.query.get_or_404(profile_id)
    if session['user_id'] != profile.parent_id:
        flash("Akses ditolak.", "danger")
        return redirect(url_for('parent_dashboard'))
    scores = UserScore.query.filter_by(profile_id=profile_id).all()
    scores_for_chart = [{"topic": s.topic, "score": s.score} for s in scores]
    return render_template('report.html', profile=profile, scores=scores, scores_for_chart=scores_for_chart)

@app.route('/get-ai-summary/<int:profile_id>')
def get_ai_summary(profile_id):
    if 'user_id' not in session: return jsonify({"summary": "Akses ditolak."}), 403
    profile = Profile.query.get_or_404(profile_id)
    if session['user_id'] != profile.parent_id: return jsonify({"summary": "Akses ditolak."}), 403
    scores = UserScore.query.filter_by(profile_id=profile_id).all()
    if not scores:
        return jsonify({"summary": f"{profile.name} belum memiliki data skor untuk dianalisis."})
    try:
        scores_text = ", ".join([f"topik {s.topic} skor {s.score}" for s in scores])
        prompt = f'Peran: Anda adalah psikolog pendidikan. Tugas: Analisis data skor anak bernama "{profile.name}" dan berikan ringkasan singkat (2-3 kalimat) untuk orang tuanya. Data: {scores_text}. Skor <20 perlu perhatian, 20-50 berkembang, >50 mahir. Berikan kalimat positif, area latihan, dan satu saran aktivitas. Tulis sebagai satu paragraf.'
        response = model.generate_content(prompt, request_options={'timeout': 100})
        summary = response.text
    except Exception as e:
        print(f"Gagal dapat ringkasan AI: {e}")
        summary = "Maaf, terjadi kesalahan saat mencoba membuat ringkasan AI. Coba lagi nanti."
    return jsonify({"summary": summary})

@app.route('/get-initial-score', methods=['POST'])
def get_initial_score():
    if 'current_profile_id' not in session:
        return jsonify({"error": "User not logged in"}), 401
    try:
        data = request.get_json()
        topic = data.get('topic')
        profile_id = session.get('current_profile_id')
        if not topic:
            return jsonify({"error": "Topic is required"}), 400
        score_entry = UserScore.query.filter_by(profile_id=profile_id, topic=topic).first()
        initial_score = 0
        if score_entry:
            initial_score = score_entry.score
        return jsonify({"initial_score": initial_score})
    except Exception as e:
        print(f"Error di get_initial_score: {e}")
        return jsonify({"error": "Internal server error"}), 500

# --- FUNGSI get_next_question DENGAN LOGIKA VERIFIKASI ---
@app.route("/get-next-question", methods=['POST'])
def get_next_question():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            data = request.get_json()
            topic = data.get('topic', 'penjumlahan')
            level = data.get('level', 'mudah')
            selected_style = random.choice(QUESTION_STYLES)
            selected_character = random.choice(CHARACTERS)
            selected_object = random.choice(OBJECTS.get(topic, ["benda"]))

            # Meminta AI untuk memberikan 'numbers' (bahan mentah), bukan jawaban akhir
            prompt = f'Peran: Anda penulis soal cerita anak-anak. Tugas: Buat satu soal matematika gaya dengan tema "{selected_style}" untuk anak 10 tahun, tentang "{selected_character}" dan "{selected_object}". Topik: "{topic}", Kesulitan: "{level}". PENTING: Buat narasi unik. Format Output: HANYA JSON dengan struktur: {{"question": "narasi soal...", "numbers": [angka1, angka2], "options": ["angka1", "angka2", "angka3", "angka4"]}}'
            
            response = model.generate_content(prompt)
            cleaned_json_string = response.text.strip().replace('```json', '').replace('```', '')
            question_data = json.loads(cleaned_json_string)

            # --- Langkah Verifikasi Dimulai ---
            numbers = question_data.get("numbers")
            op_func = TOPIC_TO_OP_FUNC.get(topic)

            if not (isinstance(numbers, list) and len(numbers) == 2 and op_func):
                print(f"Attempt {attempt+1}: Data 'numbers' atau 'topic' tidak valid dari AI. Mencoba lagi...")
                continue

            # Hitung jawaban yang benar menggunakan Python
            try:
                correct_answer = op_func(numbers[0], numbers[1])
                # Untuk pembagian, pastikan hasilnya bulat
                if topic == 'pembagian' and correct_answer != int(correct_answer):
                    print(f"Attempt {attempt+1}: Hasil pembagian tidak bulat. Mencari soal baru...")
                    continue
                correct_answer = int(correct_answer)
            except ZeroDivisionError:
                print(f"Attempt {attempt+1}: AI mencoba pembagian dengan nol. Mencari soal baru...")
                continue
            
            # Bersihkan dan validasi pilihan ganda
            options_as_numbers = []
            raw_options = question_data.get("options", [])
            for opt in raw_options:
                try:
                    match = re.search(r'-?\d+', str(opt))
                    if match:
                        options_as_numbers.append(int(match.group(0)))
                except (TypeError, ValueError): continue
            
            # Jika jawaban benar ada di pilihan, kirim soal ke pengguna
            if correct_answer in options_as_numbers:
                verified_index = options_as_numbers.index(correct_answer)
                question_data["correct_answer_index"] = verified_index
                question_data["options"] = [str(n) for n in options_as_numbers] # Kirim pilihan yang sudah bersih
                return jsonify(question_data)
            else:
                # Jika jawaban benar tidak ada di pilihan, coba lagi
                print(f"Attempt {attempt+1}: Jawaban terhitung ({correct_answer}) tidak ada di pilihan {options_as_numbers}. Mencoba lagi...")
                continue

        except Exception as e:
            print(f"Error di attempt #{attempt + 1} get_next_question: {e}")
            continue

    # Jika semua percobaan gagal
    return jsonify({"error": "Gagal membuat soal yang valid setelah beberapa kali percobaan."}), 500


@app.route("/submit-answer", methods=['POST'])
def submit_answer():
    data = request.get_json()
    profile_id = data.get('profile_id')
    topic = data.get('topic')
    is_correct = data.get('is_correct')
    if not all([profile_id, topic, isinstance(is_correct, bool)]): return jsonify({"error": "Data tidak lengkap"}), 400
    score_entry = UserScore.query.filter_by(profile_id=profile_id, topic=topic).first()
    if score_entry is None:
        score_entry = UserScore(profile_id=int(profile_id), topic=topic, score=0)
        db.session.add(score_entry)
    if is_correct: score_entry.score += 5
    else: score_entry.score = max(0, score_entry.score - 3)
    db.session.commit()
    return jsonify({"profile_id": profile_id, "topic": topic, "new_score": score_entry.score})

# --- 5. PERINTAH DATABASE ---
@app.cli.command("init-db")
def init_db_command():
    """Membersihkan data yang ada dan membuat tabel baru."""
    with app.app_context():
        db.drop_all()
        db.create_all()
    print("Database telah diinisialisasi.")
