from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from flask.json.provider import DefaultJSONProvider
import json
import os
import io
import traceback
from datetime import datetime
import pandas as pd

app = Flask(__name__)
app.secret_key = 'sdit_pendisiplinan_hafalan_secret_key'

# Konfigurasi Database SQLite di folder instance/pkm_sdit.db
os.makedirs(app.instance_path, exist_ok=True)
db_path = os.path.join(app.instance_path, 'pkm_sdit.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Provider JSON Khusus agar Model SQLAlchemy Otomatis Ter-serialize saat | tojson di Jinja2
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if hasattr(obj, 'to_dict') and callable(obj.to_dict):
            return obj.to_dict()
        return super().default(obj)

app.json = CustomJSONProvider(app)
db = SQLAlchemy(app)

DATA_SISWA_PATH = 'data/siswa.json'
DATA_GURU_PATH = 'data/guru.json'

# ========================================================
# MODEL DATABASE SQLALCHEMY (SQLITE)
# ========================================================

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'guru', 'ortu'
    nama = db.Column(db.String(150), nullable=True)
    kelas = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='Aktif')  # 'Aktif' / 'Tidak Aktif'

    siswa_binaan = db.relationship('Siswa', backref='ortu', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "nama": self.nama or self.username,
            "kelas": self.kelas or "-",
            "status": self.status or "Aktif"
        }

    def __getitem__(self, key):
        return getattr(self, key)


class Siswa(db.Model):
    __tablename__ = 'siswa'
    id = db.Column(db.String(50), primary_key=True)
    nama = db.Column(db.String(150), nullable=False)
    kelas = db.Column(db.String(50), nullable=False)
    poin = db.Column(db.Integer, default=0)  # Poin awal nol (0)
    user_id_ortu = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    catatan = db.relationship('RecordsPoin', backref='siswa', lazy=True, cascade="all, delete-orphan", order_by="RecordsPoin.id.asc()")
    tahsin = db.relationship('RecordsTahsin', backref='siswa', lazy=True, cascade="all, delete-orphan", order_by="RecordsTahsin.id.asc()")
    tahfidz = db.relationship('RecordsTahfidz', backref='siswa', lazy=True, cascade="all, delete-orphan", order_by="RecordsTahfidz.id.asc()")

    def to_dict(self):
        return {
            "id": self.id,
            "nama": self.nama,
            "kelas": self.kelas,
            "poin": self.poin,
            "catatan": [c.to_dict() for c in self.catatan],
            "tahsin": [t.to_dict() for t in self.tahsin],
            "tahfidz": [f.to_dict() for f in self.tahfidz]
        }

    def __getitem__(self, key):
        if key == 'catatan':
            return [c.to_dict() for c in self.catatan]
        if key == 'tahsin':
            return [t.to_dict() for t in self.tahsin]
        if key == 'tahfidz':
            return [f.to_dict() for f in self.tahfidz]
        return getattr(self, key)


class RecordsPoin(db.Model):
    __tablename__ = 'records_poin'
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.String(50), db.ForeignKey('siswa.id'), nullable=False)
    tanggal = db.Column(db.String(50), nullable=False)
    kategori = db.Column(db.String(50), nullable=False)  # 'prestasi' / 'pelanggaran'
    deskripsi = db.Column(db.String(255), nullable=False)
    poin = db.Column(db.Integer, nullable=False)
    pencatat = db.Column(db.String(100), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "tanggal": self.tanggal,
            "kategori": self.kategori,
            "deskripsi": self.deskripsi,
            "poin": self.poin,
            "pencatat": self.pencatat or ""
        }

    def __getitem__(self, key):
        return getattr(self, key)


class RecordsTahsin(db.Model):
    __tablename__ = 'records_tahsin'
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.String(50), db.ForeignKey('siswa.id'), nullable=False)
    tanggal = db.Column(db.String(50), nullable=False)
    halaman_akhir = db.Column(db.String(150), nullable=False)
    catatan = db.Column(db.Text, nullable=True)
    ceklist_guru = db.Column(db.Boolean, default=True)
    ceklist_ortu = db.Column(db.Boolean, default=False)
    catatan_ortu = db.Column(db.Text, nullable=True)
    penilai = db.Column(db.String(100), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "tanggal": self.tanggal,
            "halaman_akhir": self.halaman_akhir,
            "catatan": self.catatan or "",
            "ceklist_guru": bool(self.ceklist_guru),
            "ceklist_ortu": bool(self.ceklist_ortu),
            "catatan_ortu": self.catatan_ortu or "",
            "penilai": self.penilai or ""
        }

    def __getitem__(self, key):
        return getattr(self, key)


class RecordsTahfidz(db.Model):
    __tablename__ = 'records_tahfidz'
    id = db.Column(db.Integer, primary_key=True)
    siswa_id = db.Column(db.String(50), db.ForeignKey('siswa.id'), nullable=False)
    tanggal = db.Column(db.String(50), nullable=False)
    hafalan_terakhir = db.Column(db.String(150), nullable=False)
    catatan = db.Column(db.Text, nullable=True)
    ceklist_guru = db.Column(db.Boolean, default=True)
    ceklist_ortu = db.Column(db.Boolean, default=False)
    catatan_ortu = db.Column(db.Text, nullable=True)
    penilai = db.Column(db.String(100), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "tanggal": self.tanggal,
            "hafalan_terakhir": self.hafalan_terakhir,
            "catatan": self.catatan or "",
            "ceklist_guru": bool(self.ceklist_guru),
            "ceklist_ortu": bool(self.ceklist_ortu),
            "catatan_ortu": self.catatan_ortu or "",
            "penilai": self.penilai or ""
        }

    def __getitem__(self, key):
        return getattr(self, key)


# ========================================================
# AUTO-SEEDER & MIGRASI DATABASE SQLITE
# ========================================================
def init_db_and_seed():
    db.create_all()

    # Auto Migration untuk kolom baru tanpa perlu hapus DB
    import sqlite3 as _sqlite3
    try:
        conn = _sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Migrasi catatan_ortu
        for tbl, col in [('records_tahsin', 'catatan_ortu'), ('records_tahfidz', 'catatan_ortu')]:
            cur.execute(f"PRAGMA table_info({tbl})")
            cols = [r[1] for r in cur.fetchall()]
            if col not in cols:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} TEXT")

        # Migrasi status keaktifan user/guru
        cur.execute("PRAGMA table_info(user)")
        cols_user = [r[1] for r in cur.fetchall()]
        if 'status' not in cols_user:
            cur.execute("ALTER TABLE user ADD COLUMN status TEXT DEFAULT 'Aktif'")

        conn.commit()
        conn.close()
    except Exception as _e:
        print("Info migrasi database:", _e)

    # 1. Migrasi Data Guru / User jika tabel User masih kosong
    if not User.query.first():
        guru_data = {}
        if os.path.exists(DATA_GURU_PATH):
            try:
                with open(DATA_GURU_PATH, 'r', encoding='utf-8') as f:
                    guru_data = json.load(f)
            except Exception as e:
                print("Info: Gagal load guru.json:", e)

        if guru_data and isinstance(guru_data, dict):
            for uname, udata in guru_data.items():
                if not User.query.filter_by(username=uname).first():
                    new_user = User(
                        username=uname,
                        password=str(udata.get('password', '123')),
                        role=udata.get('role', 'guru'),
                        nama=udata.get('nama', uname),
                        kelas=udata.get('kelas', '-'),
                        status='Aktif'
                    )
                    db.session.add(new_user)
        else:
            admin_user = User(
                username='admin',
                password='admin',
                role='admin',
                nama='Administrator SDIT',
                kelas='-',
                status='Aktif'
            )
            db.session.add(admin_user)

        db.session.commit()

    # 2. Migrasi Data Siswa jika tabel Siswa masih kosong
    if not Siswa.query.first():
        siswa_data = []
        if os.path.exists(DATA_SISWA_PATH):
            try:
                with open(DATA_SISWA_PATH, 'r', encoding='utf-8') as f:
                    siswa_data = json.load(f)
            except Exception as e:
                print("Info: Gagal load siswa.json:", e)

        if siswa_data and isinstance(siswa_data, list):
            for s in siswa_data:
                if not isinstance(s, dict) or not s.get('id'):
                    continue

                nama_siswa = s.get('nama', '').strip()
                kelas_siswa = s.get('kelas', '4A')

                ortu_user = User.query.filter_by(username=nama_siswa, role='ortu').first()
                if not ortu_user and nama_siswa:
                    ortu_user = User(
                        username=nama_siswa,
                        password='1234',
                        role='ortu',
                        nama=f"Wali {nama_siswa}",
                        kelas=kelas_siswa,
                        status='Aktif'
                    )
                    db.session.add(ortu_user)
                    db.session.flush()

                new_siswa = Siswa(
                    id=s.get('id'),
                    nama=nama_siswa,
                    kelas=kelas_siswa,
                    poin=int(s.get('poin', 0)),
                    user_id_ortu=ortu_user.id if ortu_user else None
                )
                db.session.add(new_siswa)

            db.session.commit()

with app.app_context():
    init_db_and_seed()


# ========================================================
# ROUTES & LOGIKA APLIKASI
# ========================================================

@app.route('/')
def index():
    if session.get('role') == 'admin':
        return redirect(url_for('dashboard_admin'))
    elif session.get('role') == 'guru':
        return redirect(url_for('dashboard_guru'))
    elif session.get('role') == 'ortu':
        return redirect(url_for('dashboard_ortu'))
    return redirect(url_for('login'))


# LOGIN MULTI-ROLE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter(db.func.lower(User.username) == username.lower()).first()

        if user and user.password == password:
            if user.status == 'Tidak Aktif':
                flash('Akun Anda telah dinonaktifkan oleh Administrator!', 'danger')
                return render_template('login.html')

            session['user_id'] = user.id
            session['user'] = user.nama or user.username
            session['username'] = user.username
            session['role'] = user.role
            session['kelas'] = user.kelas or '4A'

            if user.role == 'admin':
                return redirect(url_for('dashboard_admin'))
            elif user.role == 'guru':
                return redirect(url_for('dashboard_guru'))
            elif user.role == 'ortu':
                siswa = Siswa.query.filter(
                    (Siswa.user_id_ortu == user.id) | 
                    (db.func.lower(Siswa.nama) == username.lower())
                ).first()
                if siswa:
                    session['siswa_id'] = siswa.id
                    session['kelas'] = siswa.kelas
                return redirect(url_for('dashboard_ortu'))

        # Login Ortu via Nama Siswa & Default Password '1234'
        siswa = Siswa.query.filter(db.func.lower(Siswa.nama) == username.lower()).first()
        if siswa and password == '1234':
            ortu = User.query.filter_by(username=siswa.nama, role='ortu').first()
            if not ortu:
                ortu = User(
                    username=siswa.nama,
                    password='1234',
                    role='ortu',
                    nama=f"Wali {siswa.nama}",
                    kelas=siswa.kelas,
                    status='Aktif'
                )
                db.session.add(ortu)
                db.session.flush()
                siswa.user_id_ortu = ortu.id
                db.session.commit()

            session['user_id'] = ortu.id
            session['user'] = ortu.nama
            session['username'] = ortu.username
            session['role'] = 'ortu'
            session['kelas'] = siswa.kelas
            session['siswa_id'] = siswa.id
            return redirect(url_for('dashboard_ortu'))

        flash('Username atau Password salah!', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# DASHBOARD ADMINISTRATOR
@app.route('/dashboard_admin')
def dashboard_admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    guru_list = User.query.filter_by(role='guru').all()
    return render_template('dashboard_admin.html', guru_list=guru_list)


# ROUTE KELOLA GURU (ADMIN)
@app.route('/admin/tambah_guru', methods=['POST'])
def admin_tambah_guru():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    nama = request.form.get('nama', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    kelas = request.form.get('kelas', '-').strip()
    status = request.form.get('status', 'Aktif')

    if User.query.filter_by(username=username).first():
        flash(f'Username "{username}" sudah digunakan guru lain!', 'danger')
    else:
        new_guru = User(
            nama=nama,
            username=username,
            password=password,
            role='guru',
            kelas=kelas,
            status=status
        )
        db.session.add(new_guru)
        db.session.commit()
        flash(f'Guru {nama} berhasil ditambahkan!', 'success')

    return redirect(url_for('dashboard_admin'))


@app.route('/admin/edit_guru/<int:guru_id>', methods=['POST'])
def admin_edit_guru(guru_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    guru = User.query.get_or_404(guru_id)
    guru.nama = request.form.get('nama', '').strip()
    guru.username = request.form.get('username', '').strip()
    guru.kelas = request.form.get('kelas', '-').strip()
    guru.status = request.form.get('status', 'Aktif')

    password_baru = request.form.get('password', '').strip()
    if password_baru:
        guru.password = password_baru

    db.session.commit()
    flash(f'Data guru {guru.nama} berhasil diperbarui!', 'success')
    return redirect(url_for('dashboard_admin'))


@app.route('/admin/hapus_guru/<int:guru_id>')
def admin_hapus_guru(guru_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    guru = User.query.get_or_404(guru_id)
    nama = guru.nama
    db.session.delete(guru)
    db.session.commit()
    flash(f'Akun guru {nama} berhasil dihapus!', 'success')
    return redirect(url_for('dashboard_admin'))


@app.route('/admin/import_guru', methods=['POST'])
def admin_import_guru():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    file = request.files.get('file_excel_guru')
    if file and file.filename.endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(file)
            imported_count = 0
            for _, row in df.iterrows():
                nama = str(row.get('Nama Lengkap', row.get('Nama', ''))).strip()
                username = str(row.get('Username', '')).strip()
                password = str(row.get('Password', '123456')).strip()
                kelas = str(row.get('Kelas', '-')).strip()

                if nama and username and not User.query.filter_by(username=username).first():
                    new_guru = User(
                        nama=nama,
                        username=username,
                        password=password,
                        role='guru',
                        kelas=kelas,
                        status='Aktif'
                    )
                    db.session.add(new_guru)
                    imported_count += 1

            db.session.commit()
            flash(f'Berhasil mengimpor {imported_count} data guru!', 'success')
        except Exception as e:
            flash(f'Gagal mengimpor file Excel: {str(e)}', 'danger')
    else:
        flash('Format file harus berupa Excel (.xlsx / .xls)!', 'danger')

    return redirect(url_for('dashboard_admin'))


# DASHBOARD GURU
@app.route('/dashboard_guru')
def dashboard_guru():
    if session.get('role') != 'guru':
        return redirect(url_for('login'))

    q = request.args.get('q', '').strip().lower()
    query = Siswa.query
    if q:
        query = query.filter(
            (db.func.lower(Siswa.nama).contains(q)) |
            (db.func.lower(Siswa.id).contains(q)) |
            (db.func.lower(Siswa.kelas).contains(q))
        )
    siswa_list = query.all()
    return render_template('dashboard_guru.html', siswa_list=siswa_list, now_date=datetime.now().strftime("%Y-%m-%d"))


# DASHBOARD ORANG TUA
@app.route('/dashboard_ortu')
def dashboard_ortu():
    if session.get('role') != 'ortu':
        return redirect(url_for('login'))

    siswa_id = session.get('siswa_id')
    siswa = None
    if siswa_id:
        siswa = Siswa.query.get(siswa_id)
    if not siswa and session.get('user_id'):
        siswa = Siswa.query.filter_by(user_id_ortu=session.get('user_id')).first()

    if not siswa:
        flash('Data santri binaan tidak ditemukan!', 'warning')
        return redirect(url_for('logout'))

    return render_template('dashboard_ortu.html', siswa=siswa)


# TAMBAH SISWA BARU (POIN AWAL 0)
@app.route('/tambah_siswa', methods=['POST'])
def tambah_siswa():
    if session.get('role') not in ('admin', 'guru'):
        return redirect(url_for('login'))

    nama = request.form.get('nama', '').strip()
    kelas = request.form.get('kelas', '').strip()
    custom_id = request.form.get('nisn', '').strip()

    if not custom_id:
        count = Siswa.query.count()
        custom_id = f"S{count + 1:03d}"
        idx = count + 1
        while Siswa.query.get(custom_id):
            idx += 1
            custom_id = f"S{idx:03d}"

    ortu = User.query.filter_by(username=nama, role='ortu').first()
    if not ortu:
        ortu = User(
            username=nama,
            password='1234',
            role='ortu',
            nama=f"Wali {nama}",
            kelas=kelas,
            status='Aktif'
        )
        db.session.add(ortu)
        db.session.flush()

    new_siswa = Siswa(
        id=custom_id,
        nama=nama,
        kelas=kelas,
        poin=0,  # Poin awal nol (0)
        user_id_ortu=ortu.id
    )
    db.session.add(new_siswa)
    db.session.commit()

    flash('Data santri berhasil ditambahkan dengan poin awal 0!', 'success')
    return redirect(request.referrer or url_for('dashboard_guru'))


# INPUT TAHSIN
@app.route('/catat_tahsin/<id_siswa>', methods=['POST'])
def catat_tahsin(id_siswa):
    if not session.get('role'):
        return redirect(url_for('login'))

    s = Siswa.query.get_or_404(id_siswa)
    juz_pilihan = request.form.get('juz', '')
    surat_ayat = request.form.get('halaman_akhir', '-')
    gabungan_halaman = f"{juz_pilihan} - {surat_ayat}" if juz_pilihan else surat_ayat

    poin_bonus = int(request.form.get('poin_bonus', 10))
    s.poin = s.poin + poin_bonus

    rec = RecordsTahsin(
        siswa_id=s.id,
        tanggal=request.form.get('tanggal') or datetime.now().strftime("%Y-%m-%d"),
        halaman_akhir=gabungan_halaman,
        catatan=request.form.get('catatan', ''),
        penilai=session.get('user', 'Musyrif')
    )
    db.session.add(rec)
    db.session.commit()

    flash(f'Setoran Tahsin disimpan & mendapat +{poin_bonus} poin!', 'success')
    return redirect(request.referrer or url_for('dashboard_guru'))


# INPUT TAHFIDZ
@app.route('/catat_tahfidz/<id_siswa>', methods=['POST'])
def catat_tahfidz(id_siswa):
    if not session.get('role'):
        return redirect(url_for('login'))

    s = Siswa.query.get_or_404(id_siswa)
    juz_pilihan = request.form.get('juz', '')
    surat_ayat = request.form.get('hafalan_terakhir', '-')
    gabungan_hafalan = f"{juz_pilihan} - {surat_ayat}" if juz_pilihan else surat_ayat

    poin_bonus = int(request.form.get('poin_bonus', 10))
    s.poin = s.poin + poin_bonus

    rec = RecordsTahfidz(
        siswa_id=s.id,
        tanggal=request.form.get('tanggal') or datetime.now().strftime("%Y-%m-%d"),
        hafalan_terakhir=gabungan_hafalan,
        catatan=request.form.get('catatan', ''),
        penilai=session.get('user', 'Musyrif')
    )
    db.session.add(rec)
    db.session.commit()

    flash(f'Setoran Tahfidz disimpan & mendapat +{poin_bonus} poin!', 'success')
    return redirect(request.referrer or url_for('dashboard_guru'))


# IMPORT SISWA DARI EXCEL
@app.route('/import_excel', methods=['POST'])
def import_excel():
    if session.get('role') not in ('admin', 'guru'):
        return redirect(url_for('login'))

    file = request.files.get('file_excel')
    if file and file.filename.endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(file)
            imported_count = 0
            for _, row in df.iterrows():
                nama = str(row.get('Nama', row.get('Nama_Siswa', ''))).strip()
                if not nama or nama.lower() == 'nan':
                    continue
                
                kelas = str(row.get('Kelas', '4A')).strip()
                custom_id = str(row.get('NISN', row.get('NISN_ID', ''))).strip()

                if not custom_id or custom_id.lower() == 'nan':
                    count = Siswa.query.count()
                    custom_id = f"S{count + 1:03d}"
                    idx = count + 1
                    while Siswa.query.get(custom_id):
                        idx += 1
                        custom_id = f"S{idx:03d}"

                existing_siswa = Siswa.query.get(custom_id)
                if existing_siswa:
                    existing_siswa.nama = nama
                    existing_siswa.kelas = kelas
                else:
                    ortu = User.query.filter_by(username=nama, role='ortu').first()
                    if not ortu:
                        ortu = User(username=nama, password='1234', role='ortu', nama=f"Wali {nama}", kelas=kelas, status='Aktif')
                        db.session.add(ortu)
                        db.session.flush()

                    new_siswa = Siswa(id=custom_id, nama=nama, kelas=kelas, poin=0, user_id_ortu=ortu.id)
                    db.session.add(new_siswa)
                imported_count += 1

            db.session.commit()
            flash(f'Berhasil mengimpor {imported_count} data santri!', 'success')
        except Exception as e:
            flash(f'Gagal membaca file Excel: {str(e)}', 'danger')
    else:
        flash('Format file harus berupa Excel (.xlsx / .xls)!', 'danger')

    return redirect(request.referrer or url_for('dashboard_guru'))


# EXPORT DATA & CETAK
@app.route('/export_excel')
def export_excel():
    if not session.get('role'):
        return redirect(url_for('login'))

    try:
        siswa_list = Siswa.query.all()
        data_export = [{"ID / NISN": s.id, "Nama Santri": s.nama, "Kelas": s.kelas, "Akumulasi Poin": s.poin} for s in siswa_list]
        df = pd.DataFrame(data_export)
        os.makedirs('data', exist_ok=True)
        export_path = os.path.join('data', 'Laporan_Siswa_SDIT.xlsx')
        df.to_excel(export_path, index=False, engine='openpyxl')
        return send_file(export_path, as_attachment=True, download_name='Laporan_Siswa_SDIT.xlsx')
    except Exception as e:
        flash(f'Export Excel gagal: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('dashboard_guru'))


@app.route('/export_csv')
def export_csv():
    if not session.get('role'):
        return redirect(url_for('login'))

    try:
        siswa_list = Siswa.query.all()
        data_export = [{"ID / NISN": s.id, "Nama Santri": s.nama, "Kelas": s.kelas, "Akumulasi Poin": s.poin} for s in siswa_list]
        df = pd.DataFrame(data_export)
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        return Response(buffer.getvalue().encode('utf-8-sig'), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=Laporan_Siswa_SDIT.csv"})
    except Exception as e:
        flash(f'Export CSV gagal: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('dashboard_guru'))


@app.route('/export_pdf')
def export_pdf():
    if not session.get('role'):
        return redirect(url_for('login'))

    siswa_list = Siswa.query.all()
    return render_template('laporan_semua.html', siswa_list=siswa_list, tanggal=datetime.now().strftime("%d %B %Y"))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
