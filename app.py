from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, Response
import json
import os
import io
import traceback
from datetime import datetime
import pandas as pd

app = Flask(__name__)
app.secret_key = 'sdit_pendisiplinan_hafalan_secret_key'

DATA_SISWA_PATH = 'data/siswa.json'
DATA_GURU_PATH = 'data/guru.json'

def load_data(filename):
    if not os.path.exists(filename):
        return {} if 'guru' in filename else []
    with open(filename, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {} if 'guru' in filename else []

def save_data(filename, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def normalize_siswa(s):
    """Pastikan setiap record siswa punya semua key yang dibutuhkan template
    (data lama / hasil import excel mungkin belum punya 'tahsin'/'tahfidz'/'catatan'),
    supaya {% for %} di template tidak pernah error karena key hilang."""
    if not isinstance(s, dict):
        return s
    s.setdefault('id', '')
    s.setdefault('nama', '')
    s.setdefault('kelas', '')
    s.setdefault('poin', 100)
    s.setdefault('catatan', [])
    s.setdefault('tahsin', [])
    s.setdefault('tahfidz', [])
    if not isinstance(s.get('catatan'), list):
        s['catatan'] = []
    if not isinstance(s.get('tahsin'), list):
        s['tahsin'] = []
    if not isinstance(s.get('tahfidz'), list):
        s['tahfidz'] = []
    return s

def load_siswa():
    """Selalu gunakan fungsi ini (bukan load_data langsung) untuk membaca data siswa,
    supaya data lama otomatis dilengkapi dan tidak menyebabkan error di halaman cetak/export."""
    data = load_data(DATA_SISWA_PATH)
    if not isinstance(data, list):
        return []
    return [normalize_siswa(s) for s in data if isinstance(s, dict)]

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        gurus = load_data(DATA_GURU_PATH)

        # Cek apakah username terdaftar
        if username in gurus:
            user_data = gurus[username]
            # Verifikasi password
            if user_data.get('password') == password:
                role = user_data.get('role', 'guru') # Otomatis deteksi role dari JSON
                
                session['user'] = user_data.get('nama', username)
                session['role'] = role
                session['kelas'] = user_data.get('kelas', '4A')

                # Auto Redirect sesuai Role
                if role == 'admin':
                    return redirect(url_for('dashboard_admin'))
                else:
                    return redirect(url_for('dashboard_guru'))

        flash('Username atau Password salah!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard_admin')
def dashboard_admin():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    siswa_list = load_siswa()
    guru_dict = load_data(DATA_GURU_PATH)
    q = request.args.get('q', '').lower()
    if q and isinstance(siswa_list, list):
        siswa_list = [s for s in siswa_list if isinstance(s, dict) and (q in s.get('nama', '').lower() or q in s.get('id', '').lower() or q in s.get('kelas', '').lower())]

    return render_template('dashboard_admin.html', siswa_list=siswa_list, guru_dict=guru_dict)

@app.route('/dashboard_guru')
def dashboard_guru():
    if session.get('role') != 'guru':
        return redirect(url_for('login'))

    siswa_list = load_siswa()
    q = request.args.get('q', '').lower()
    if q and isinstance(siswa_list, list):
        siswa_list = [s for s in siswa_list if isinstance(s, dict) and (q in s.get('nama', '').lower() or q in s.get('id', '').lower() or q in s.get('kelas', '').lower())]

    return render_template('dashboard_guru.html', siswa_list=siswa_list)

# FITUR TOMBOL KLIK POIN CEPAT (INSTAN)
@app.route('/quick_poin/<id_siswa>/<kategori>/<int:poin_val>')
def quick_poin(id_siswa, kategori, poin_val):
    if not session.get('role'):
        return redirect(url_for('login'))

    siswa_list = load_siswa()
    deskripsi_map = {
        'sholat': 'Melaksanakan Sholat Tepat Waktu',
        'pakaian': 'Pakaian Rapi & Bersih',
        'terlambat': 'Terlambat Masuk Sekolah',
        'atribut': 'Atribut Seragam Tidak Lengkap'
    }

    if isinstance(siswa_list, list):
        for s in siswa_list:
            if isinstance(s, dict) and s.get('id') == id_siswa:
                if kategori in ['terlambat', 'atribut']:
                    s['poin'] = s.get('poin', 100) - poin_val
                    kat_title = 'pelanggaran'
                else:
                    s['poin'] = s.get('poin', 100) + poin_val
                    kat_title = 'prestasi'

                s.setdefault('catatan', []).append({
                    "tanggal": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "kategori": kat_title,
                    "deskripsi": deskripsi_map.get(kategori, 'Poin Otomatis'),
                    "poin": poin_val,
                    "pencatat": session.get('user')
                })
                break

    save_data(DATA_SISWA_PATH, siswa_list)
    flash('Poin berhasil diperbarui!', 'success')
    return redirect(request.referrer or url_for('dashboard_guru'))

# INPUT TAHSIN PERMINGGU
@app.route('/catat_tahsin/<id_siswa>', methods=['POST'])
def catat_tahsin(id_siswa):
    if not session.get('role'):
        return redirect(url_for('login'))

    siswa_list = load_siswa()
    if isinstance(siswa_list, list):
        for s in siswa_list:
            if isinstance(s, dict) and s.get('id') == id_siswa:
                s.setdefault('tahsin', []).append({
                    "tanggal": request.form.get('tanggal'),
                    "halaman_akhir": request.form.get('halaman_akhir'),
                    "catatan": request.form.get('catatan'),
                    "ceklist_guru": 'ceklist_guru' in request.form,
                    "ceklist_ortu": 'ceklist_ortu' in request.form,
                    "penilai": session.get('user')
                })
                break

    save_data(DATA_SISWA_PATH, siswa_list)
    flash('Nilai Tahsin Mingguan berhasil disimpan!', 'success')
    return redirect(request.referrer or url_for('dashboard_guru'))

# INPUT TAHFIDZ PERMINGGU
@app.route('/catat_tahfidz/<id_siswa>', methods=['POST'])
def catat_tahfidz(id_siswa):
    if not session.get('role'):
        return redirect(url_for('login'))

    siswa_list = load_siswa()
    if isinstance(siswa_list, list):
        for s in siswa_list:
            if isinstance(s, dict) and s.get('id') == id_siswa:
                s.setdefault('tahfidz', []).append({
                    "tanggal": request.form.get('tanggal'),
                    "hafalan_terakhir": request.form.get('hafalan_terakhir'),
                    "catatan": request.form.get('catatan'),
                    "ceklist_guru": 'ceklist_guru' in request.form,
                    "ceklist_ortu": 'ceklist_ortu' in request.form,
                    "penilai": session.get('user')
                })
                break

    save_data(DATA_SISWA_PATH, siswa_list)
    flash('Nilai Tahfidz Mingguan berhasil disimpan!', 'success')
    return redirect(request.referrer or url_for('dashboard_guru'))

# IMPORT DARI EXCEL (Admin & Guru)
@app.route('/import_excel', methods=['POST'])
def import_excel():
    if session.get('role') not in ('admin', 'guru'):
        return redirect(url_for('login'))

    file = request.files.get('file_excel')
    if file and file.filename.endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(file)
            siswa_list = load_siswa()
            if not isinstance(siswa_list, list):
                siswa_list = []

            for _, row in df.iterrows():
                new_siswa = {
                    "id": f"S{len(siswa_list) + 1:03d}",
                    "nama": str(row.get('Nama', '')),
                    "kelas": str(row.get('Kelas', '')),
                    "poin": int(row.get('Poin', 100)),
                    "catatan": [],
                    "tahsin": [],
                    "tahfidz": []
                }
                siswa_list.append(new_siswa)

            save_data(DATA_SISWA_PATH, siswa_list)
            flash('Import data siswa dari Excel berhasil!', 'success')
        except Exception as e:
            flash(f'Gagal membaca file Excel: {str(e)}', 'danger')
    else:
        flash('Format file harus berupa Excel (.xlsx / .xls)!', 'danger')

    redirect_target = 'dashboard_admin' if session.get('role') == 'admin' else 'dashboard_guru'
    return redirect(url_for(redirect_target))

def _redirect_dashboard():
    target = 'dashboard_admin' if session.get('role') == 'admin' else 'dashboard_guru'
    return redirect(url_for(target))

def _send_file_compat(path, download_name):
    """send_file(download_name=...) baru ada di Flask 2.0+. Kalau Flask versi
    lama dipakai (download_name belum dikenal), otomatis coba attachment_filename."""
    try:
        return send_file(path, as_attachment=True, download_name=download_name)
    except TypeError:
        return send_file(path, as_attachment=True, attachment_filename=download_name)

# EXPORT KE EXCEL (AMAN TANPA CRASH)
@app.route('/export_excel')
def export_excel():
    if not session.get('role'):
        return redirect(url_for('login'))

    try:
        siswa_list = load_siswa()
        data_export = []

        for s in siswa_list:
            if isinstance(s, dict):
                data_export.append({
                    "ID Siswa": s.get('id', ''),
                    "Nama Siswa": s.get('nama', ''),
                    "Kelas": s.get('kelas', ''),
                    "Akumulasi Poin": s.get('poin', 100)
                })

        df = pd.DataFrame(data_export)

        os.makedirs('data', exist_ok=True)
        export_path = os.path.join('data', 'Laporan_Siswa_SDIT.xlsx')

        try:
            df.to_excel(export_path, index=False, engine='openpyxl')
        except ModuleNotFoundError:
            flash('Export Excel gagal: library "openpyxl" belum terinstall di server. Jalankan: pip install openpyxl', 'danger')
            return _redirect_dashboard()

        return _send_file_compat(export_path, 'Laporan_Siswa_SDIT.xlsx')

    except Exception as e:
        traceback.print_exc()
        flash(f'Export Excel gagal: {str(e)}', 'danger')
        return _redirect_dashboard()

# EXPORT KE CSV (Admin & Guru)
@app.route('/export_csv')
def export_csv():
    if not session.get('role'):
        return redirect(url_for('login'))

    try:
        siswa_list = load_siswa()
        data_export = []

        for s in siswa_list:
            if isinstance(s, dict):
                data_export.append({
                    "ID Siswa": s.get('id', ''),
                    "Nama Siswa": s.get('nama', ''),
                    "Kelas": s.get('kelas', ''),
                    "Akumulasi Poin": s.get('poin', 100)
                })

        df = pd.DataFrame(data_export)

        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        csv_bytes = buffer.getvalue().encode('utf-8-sig')  # BOM agar Excel baca UTF-8 dgn benar

        return Response(
            csv_bytes,
            mimetype='text/csv',
            headers={"Content-Disposition": "attachment; filename=Laporan_Siswa_SDIT.csv"}
        )
    except Exception as e:
        traceback.print_exc()
        flash(f'Export CSV gagal: {str(e)}', 'danger')
        return _redirect_dashboard()

# EXPORT / CETAK LAPORAN SEMUA SISWA (bisa disimpan sbg PDF lewat dialog Print browser)
@app.route('/export_pdf')
def export_pdf():
    if not session.get('role'):
        return redirect(url_for('login'))

    try:
        siswa_list = load_siswa()
        tanggal_cetak = datetime.now().strftime("%d %B %Y")
        return render_template('laporan_semua.html', siswa_list=siswa_list, tanggal=tanggal_cetak)
    except Exception as e:
        traceback.print_exc()
        flash(f'Cetak/Export PDF gagal: {str(e)}', 'danger')
        return _redirect_dashboard()

@app.route('/tambah_siswa', methods=['POST'])
def tambah_siswa():
    if session.get('role') not in ('admin', 'guru'):
        return redirect(url_for('login'))

    siswa_list = load_siswa()
    if not isinstance(siswa_list, list):
        siswa_list = []

    new_siswa = {
        "id": f"S{len(siswa_list) + 1:03d}",
        "nama": request.form.get('nama'),
        "kelas": request.form.get('kelas'),
        "poin": 100,
        "catatan": [],
        "tahsin": [],
        "tahfidz": []
    }
    siswa_list.append(new_siswa)
    save_data(DATA_SISWA_PATH, siswa_list)
    flash('Data siswa berhasil ditambahkan!', 'success')
    redirect_target = 'dashboard_admin' if session.get('role') == 'admin' else 'dashboard_guru'
    return redirect(url_for(redirect_target))

@app.route('/tambah_guru', methods=['POST'])
def tambah_guru():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    guru_dict = load_data(DATA_GURU_PATH)
    if not isinstance(guru_dict, dict):
        guru_dict = {}

    username = request.form.get('username')
    guru_dict[username] = {
        "password": request.form.get('password'),
        "role": "guru",
        "nama": request.form.get('nama'),
        "kelas": request.form.get('kelas', '-')
    }
    save_data(DATA_GURU_PATH, guru_dict)
    flash('Data guru berhasil ditambahkan!', 'success')
    return redirect(url_for('dashboard_admin'))

@app.route('/cetak_hafalan/<id_siswa>')
def cetak_hafalan(id_siswa):
    if not session.get('role'):
        return redirect(url_for('login'))

    siswa_list = load_siswa()
    siswa = None
    if isinstance(siswa_list, list):
        siswa = next((s for s in siswa_list if isinstance(s, dict) and s.get('id') == id_siswa), None)

    if not siswa:
        flash('Data siswa tidak ditemukan!', 'danger')
        return _redirect_dashboard()

    try:
        tanggal_cetak = datetime.now().strftime("%d %B %Y")
        return render_template('lembar_hafalan.html', siswa=siswa, tanggal=tanggal_cetak)
    except Exception as e:
        traceback.print_exc()
        flash(f'Cetak laporan gagal: {str(e)}', 'danger')
        return _redirect_dashboard()

@app.route('/hapus_siswa/<id_siswa>')
def hapus_siswa(id_siswa):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    siswa_list = load_siswa()
    if isinstance(siswa_list, list):
        siswa_list = [s for s in siswa_list if isinstance(s, dict) and s.get('id') != id_siswa]
        save_data(DATA_SISWA_PATH, siswa_list)

    flash('Data siswa berhasil dihapus!', 'warning')
    return redirect(url_for('dashboard_admin'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
