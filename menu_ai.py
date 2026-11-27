"""Menu AI (PySide6): daftar AI di kiri, jendela AI di kanan."""
import json
import os
import re
import sys
import uuid
import time
import threading
import subprocess
import tempfile
import requests

import browser_cookie3
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtCore import QSize, QStandardPaths, Qt, QUrl, QTimer
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QPlainTextEdit, QPushButton, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget,
)

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")

GREY = "#6b7a76"

# --- PENGATURAN AUTO-UPDATE ---
CURRENT_VERSION = "v1.0.0" # Ubah angka ini setiap kali mau rilis versi baru
REPO_API = "https://api.github.com/repos/digitalendri/menui/releases/latest"

DEFAULTS = [
    {"id": "chatgpt", "n": "ChatGPT", "u": "https://chatgpt.com", "c": "#10a37f"},
    {"id": "claude", "n": "Claude", "u": "https://claude.ai", "c": "#c0603a"},
    {"id": "gemini", "n": "Gemini", "u": "https://gemini.google.com", "c": "#4a6cf7"},
    {"id": "grok", "n": "Grok", "u": "https://grok.com", "c": "#333b4a"},
    {"id": "copilot", "n": "Copilot", "u": "https://copilot.microsoft.com", "c": "#2b7bd6"},
    {"id": "perplexity", "n": "Perplexity", "u": "https://www.perplexity.ai", "c": "#1f8a9e"},
    {"id": "deepseek", "n": "DeepSeek", "u": "https://chat.deepseek.com", "c": "#4d6bfe"},
]

ALLOWED_PERMS = {"MediaAudioCapture", "MediaVideoCapture", "MediaAudioVideoCapture", "ClipboardReadWrite"}

JS_INSERT = """(function(t){
var e=document.activeElement;
function ok(x){return x&&(x.tagName==='TEXTAREA'||x.isContentEditable);}
if(!ok(e)){e=document.querySelector('#prompt-textarea')
||document.querySelector('div[contenteditable="true"][role="textbox"]')
||document.querySelector('div[contenteditable="true"]')
||document.querySelector('textarea');}
if(!e)return false;
e.focus();
document.execCommand('insertText',false,t);
return true;})(%s)"""

DATA_DIR = ""
popups = []
PROFILES = {}

# --- FUNGSI AUTO-UPDATE ---
def cek_update():
    try:
        res = requests.get(REPO_API, timeout=5)
        if res.status_code == 200:
            data = res.json()
            latest_version = data["tag_name"]
            
            if latest_version != CURRENT_VERSION:
                zip_url = None
                for asset in data.get("assets", []):
                    if asset["name"].endswith(".zip"):
                        zip_url = asset["browser_download_url"]
                        break
                
                if zip_url:
                    def show_dialog():
                        msg = QMessageBox()
                        msg.setWindowTitle("Pembaruan Tersedia")
                        msg.setText(f"Versi baru ({latest_version}) tersedia!\nVersi kamu saat ini: {CURRENT_VERSION}\n\nUpdate sekarang?")
                        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if msg.exec() == QMessageBox.StandardButton.Yes:
                            threading.Thread(target=download_and_update, args=(zip_url,), daemon=True).start()
                    
                    QTimer.singleShot(1000, show_dialog)
    except Exception as e:
        print("Gagal cek update:", e)

def download_and_update(url):
    try:
        temp_dir = tempfile.gettempdir()
        zip_path = os.path.join(temp_dir, "menuai_update.zip")
        
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        bat_path = os.path.join(temp_dir, "update_menuai.bat")
        with open(bat_path, "w") as bat:
            bat.write(f"""
@echo off
echo Menunggu aplikasi lama ditutup...
timeout /t 3 /nobreak > NUL
echo Mengekstrak pembaruan...
powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{app_dir}' -Force"
echo Membuka aplikasi kembali...
start "" "{os.path.join(app_dir, 'MenuAI.exe')}"
del "%~f0"
""")

        subprocess.Popen([bat_path], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        QApplication.quit()

    except Exception as e:
        QMessageBox.critical(None, "Update Gagal", f"Gagal mendownload update:\n{e}")
# ---------------------------

def config_path():
    return os.path.join(DATA_DIR, "config.json")

def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    cfg.setdefault("last", "")
    cfg.setdefault("prompts", [])
    cfg.setdefault("accounts", {})
    cfg.setdefault("acc_last", {})
    cfg.setdefault("side_collapsed", False)
    if "ais" not in cfg:
        ais = [dict(d, hidden=False) for d in DEFAULTS]
        for c in cfg.get("custom", []):
            ais.append({"id": "c" + uuid.uuid4().hex[:8], "n": c["n"], "u": c["u"], "c": GREY, "hidden": False})
        cfg["ais"] = ais
    cfg.pop("custom", None)
    return cfg

def save_config(cfg):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def dot_icon(letter, color, size=28):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.setPen(QColor("white"))
    f = QFont()
    f.setBold(True)
    f.setPixelSize(int(size * 0.5))
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    return QIcon(pm)

def on_download(req):
    req.setDownloadDirectory(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation))
    req.accept()

def get_profile(key):
    if key in PROFILES:
        return PROFILES[key]
    app = QApplication.instance()
    if key == "default":
        p = QWebEngineProfile("menuai", app)
        p.setPersistentStoragePath(os.path.join(DATA_DIR, "web"))
        p.setCachePath(os.path.join(DATA_DIR, "cache"))
    else:
        p = QWebEngineProfile("menuai_" + key, app)
        p.setPersistentStoragePath(os.path.join(DATA_DIR, "web_" + key))
        p.setCachePath(os.path.join(DATA_DIR, "cache_" + key))
    p.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
    p.setHttpUserAgent(re.sub(r"\s*QtWebEngine/\S+", "", p.httpUserAgent()))
    p.downloadRequested.connect(on_download)
    PROFILES[key] = p
    return p

def inject_cookies_from_chrome(profile, domain=".dola.ai"):
    print(f"Mencoba menarik cookie untuk {domain}...")
    try:
        cj = browser_cookie3.chrome(domain_name=domain)
        store = profile.cookieStore()
        store.deleteAllCookies()
        count = 0
        for c in cj:
            cookie = QNetworkCookie(c.name.encode(), c.value.encode())
            cookie.setDomain(c.domain)
            cookie.setPath(c.path)
            if c.expires:
                cookie.setExpirationDate(time.gmtime(c.expires))
            if c.secure:
                cookie.setSecure(True)
            store.setCookie(cookie, QUrl("https://" + domain.replace(".", "", 1)))
            count += 1
        print(f"Berhasil menyuntikkan {count} cookie.")
        return count
    except Exception as e:
        print(f"Gagal mengambil cookie: {e}")
        return 0

class AIPage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        if hasattr(self, "permissionRequested"):
            self.permissionRequested.connect(self._on_permission)
        else:
            self.featurePermissionRequested.connect(self._on_feature)

    def _on_permission(self, perm):
        if perm.permissionType().name in ALLOWED_PERMS:
            perm.grant()
        else:
            perm.deny()

    def _on_feature(self, origin, feature):
        ok = feature.name in ALLOWED_PERMS
        policy = (QWebEnginePage.PermissionPolicy.PermissionGrantedByUser if ok
                  else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)
        self.setFeaturePermission(origin, feature, policy)

    def createWindow(self, _type):
        view = QWebEngineView()
        page = AIPage(self.profile(), view)
        view.setPage(page)
        view.resize(900, 700)
        view.setWindowTitle("Menu AI")
        page.windowCloseRequested.connect(view.close)
        view.show()
        popups.append(view)
        return page

class AIEdit(QDialog):
    def __init__(self, title, n, u, taken, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.taken = taken
        self.val = None
        self.in_n = QLineEdit(n)
        self.in_n.setPlaceholderText("Nama, misalnya Mistral")
        self.in_u = QLineEdit(u)
        self.in_u.setPlaceholderText("chat.mistral.ai")
        form = QFormLayout(self)
        form.addRow("Nama", self.in_n)
        form.addRow("Alamat situs", self.in_u)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Simpan")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Batal")
        bb.accepted.connect(self.check)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def warn(self, text):
        QMessageBox.information(self, "Menu AI", text)

    def check(self):
        n = self.in_n.text().strip()
        u = self.in_u.text().strip()
        if not n:
            return self.warn("Isi nama AI dulu.")
        if n.lower() in self.taken:
            return self.warn("Nama itu sudah ada.")
        if not u:
            return self.warn("Isi alamat situsnya.")
        if not re.match(r"^https?://", u, re.I):
            u = "https://" + u
        q = QUrl(u)
        if not q.isValid() or "." not in q.host():
            return self.warn("Alamat situs tidak valid.")
        self.val = (n, u)
        self.accept()

class AIDialog(QDialog):
    def __init__(self, ais, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Atur daftar AI")
        self.resize(460, 460)
        self.ais = [dict(a) for a in ais]
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Centang untuk menampilkan di daftar. Seret untuk mengubah urutan."))
        self.lst = QListWidget()
        self.lst.setIconSize(QSize(24, 24))
        self.lst.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        lay.addWidget(self.lst, 1)
        row = QHBoxLayout()
        for text, fn in (("Tambah AI", self.add), ("Ubah", self.edit), ("Hapus", self.delete)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Simpan")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Batal")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for a in self.ais:
            self.add_item(a)

    def add_item(self, a):
        it = QListWidgetItem(dot_icon(a["n"][:1].upper(), a["c"], 24), a["n"])
        it.setData(Qt.ItemDataRole.UserRole, a["id"])
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Unchecked if a.get("hidden") else Qt.CheckState.Checked)
        self.lst.addItem(it)

    def by_id(self, i):
        for a in self.ais:
            if a["id"] == i:
                return a
        return None

    def taken(self, exclude=None):
        return {a["n"].lower() for a in self.ais if a["id"] != exclude}

    def add(self):
        d = AIEdit("Tambah AI", "", "", self.taken(), self)
        if d.exec():
            n, u = d.val
            a = {"id": "c" + uuid.uuid4().hex[:8], "n": n, "u": u, "c": GREY, "hidden": False}
            self.ais.append(a)
            self.add_item(a)

    def edit(self):
        it = self.lst.currentItem()
        if not it:
            return
        a = self.by_id(it.data(Qt.ItemDataRole.UserRole))
        d = AIEdit("Ubah AI", a["n"], a["u"], self.taken(a["id"]), self)
        if d.exec():
            a["n"], a["u"] = d.val
            it.setText(a["n"])
            it.setIcon(dot_icon(a["n"][:1].upper(), a["c"], 24))

    def delete(self):
        it = self.lst.currentItem()
        if not it:
            return
        a = self.by_id(it.data(Qt.ItemDataRole.UserRole))
        ok = QMessageBox.question(self, "Hapus AI", "Hapus %s dari daftar?" % a["n"])
        if ok == QMessageBox.StandardButton.Yes:
            self.ais = [x for x in self.ais if x["id"] != a["id"]]
            self.lst.takeItem(self.lst.row(it))

    def result_list(self):
        out = []
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            a = self.by_id(it.data(Qt.ItemDataRole.UserRole))
            a["hidden"] = it.checkState() != Qt.CheckState.Checked
            out.append(a)
        return out

class PromptDialog(QDialog):
    def __init__(self, prompts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Prompt favorit")
        self.resize(680, 420)
        self.prompts = [dict(p) for p in prompts]
        self.row = -1
        self._loading = False

        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        self.lst = QListWidget()
        self.lst.currentRowChanged.connect(self.on_row)
        btn_new = QPushButton("Prompt baru")
        btn_new.clicked.connect(self.new)
        left.addWidget(self.lst, 1)
        left.addWidget(btn_new)
        lay.addLayout(left, 2)

        right = QVBoxLayout()
        self.in_t = QLineEdit()
        self.in_t.setPlaceholderText("Judul, misalnya Ringkas teks")
        self.in_x = QPlainTextEdit()
        self.in_x.setPlaceholderText("Isi prompt")
        right.addWidget(QLabel("Judul"))
        right.addWidget(self.in_t)
        right.addWidget(QLabel("Isi prompt"))
        right.addWidget(self.in_x, 1)
        row = QHBoxLayout()
        btn_save = QPushButton("Simpan")
        btn_save.setObjectName("primary")
        btn_save.clicked.connect(self.save)
        btn_del = QPushButton("Hapus")
        btn_del.clicked.connect(self.delete)
        btn_close = QPushButton("Tutup")
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_save)
        row.addWidget(btn_del)
        row.addStretch(1)
        row.addWidget(btn_close)
        right.addLayout(row)
        lay.addLayout(right, 3)
        self.refresh(-1)

    def refresh(self, select):
        self._loading = True
        self.lst.clear()
        for p in self.prompts:
            self.lst.addItem(p["t"])
        self._loading = False
        self.lst.setCurrentRow(select)
        self.on_row(select)

    def on_row(self, r):
        if self._loading:
            return
        self.row = r
        if 0 <= r < len(self.prompts):
            self.in_t.setText(self.prompts[r]["t"])
            self.in_x.setPlainText(self.prompts[r]["x"])
        else:
            self.in_t.clear()
            self.in_x.clear()

    def new(self):
        self.lst.setCurrentRow(-1)
        self.row = -1
        self.in_t.clear()
        self.in_x.clear()
        self.in_t.setFocus()

    def save(self):
        t = self.in_t.text().strip()
        x = self.in_x.toPlainText().strip()
        if not t or not x:
            QMessageBox.information(self, "Prompt favorit", "Isi judul dan isi prompt dulu.")
            return
        if 0 <= self.row < len(self.prompts):
            self.prompts[self.row] = {"t": t, "x": x}
            sel = self.row
        else:
            self.prompts.append({"t": t, "x": x})
            sel = len(self.prompts) - 1
        self.refresh(sel)

    def delete(self):
        if 0 <= self.row < len(self.prompts):
            del self.prompts[self.row]
            self.refresh(-1)

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.views = {}
        self.current = None
        self.cur_acc = None
        self.collapsed = bool(self.cfg.get("side_collapsed"))
        self.setWindowTitle("Menu AI")
        self.resize(1280, 800)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.side = QWidget()
        self.side.setObjectName("side")
        sl = QVBoxLayout(self.side)
        sl.setContentsMargins(10, 14, 10, 12)
        top = QHBoxLayout()
        self.btn_toggle = QPushButton("\u2630")
        self.btn_toggle.setObjectName("ghost")
        self.btn_toggle.setFixedSize(36, 32)
        self.btn_toggle.setToolTip("Lipat atau buka sidebar")
        self.btn_toggle.clicked.connect(lambda: self.set_collapsed(not self.collapsed))
        self.side_title = QLabel("Menu AI")
        self.side_title.setObjectName("title")
        top.addWidget(self.btn_toggle)
        top.addWidget(self.side_title, 1)
        sl.addLayout(top)

        self.list = QListWidget()
        self.list.setIconSize(QSize(28, 28))
        self.list.setFrameShape(QListWidget.Shape.NoFrame)
        self.list.itemClicked.connect(self.on_item)
        sl.addWidget(self.list, 1)

        self.btn_manage = QPushButton("Atur daftar AI")
        self.btn_manage.setToolTip("Atur daftar AI")
        self.btn_manage.clicked.connect(self.manage_ais)
        sl.addWidget(self.btn_manage)
        root.addWidget(self.side)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        self.bar = QWidget()
        self.bar.setObjectName("bar")
        bl = QHBoxLayout(self.bar)
        bl.setContentsMargins(12, 6, 12, 6)
        self.bar_title = QLabel("")
        self.bar_title.setObjectName("title")

        self.combo = QComboBox()
        self.combo.setToolTip("Pilih akun untuk AI ini")
        self.combo.activated.connect(self.on_account)

        self.btn_kelola = QToolButton()
        self.btn_kelola.setText("Kelola akun")
        self.btn_kelola.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.btn_kelola)
        menu.addAction("Tambah akun...").triggered.connect(self.add_account)
        menu.addAction("Ubah nama akun...").triggered.connect(self.rename_account)
        menu.addAction("Hapus akun...").triggered.connect(self.remove_account)
        self.btn_kelola.setMenu(menu)

        self.btn_prompt = QPushButton("Prompt")
        self.btn_prompt.setToolTip("Prompt favorit")
        self.btn_prompt.clicked.connect(self.show_prompts)
        self.btn_reload = QPushButton("Muat ulang")
        self.btn_reload.clicked.connect(self.reload)
        self.btn_browser = QPushButton("Buka di browser")
        self.btn_browser.clicked.connect(self.open_browser)

        bl.addWidget(self.bar_title, 1)
        for w in (self.combo, self.btn_kelola, self.btn_prompt, self.btn_reload, self.btn_browser):
            bl.addWidget(w)
        self.set_bar_enabled(False)
        rl.addWidget(self.bar)

        self.stack = QStackedWidget()
        self.empty = QLabel("Pilih AI di kiri,\njendelanya muncul di sini.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setObjectName("empty")
        self.stack.addWidget(self.empty)
        rl.addWidget(self.stack, 1)
        root.addWidget(right, 1)

        self.setCentralWidget(central)
        self.set_collapsed(self.collapsed, save=False)

        last = self.find(self.cfg.get("last", ""))
        if last:
            self.show_ai(last)

    def find(self, key):
        for a in self.cfg["ais"]:
            if a["id"] == key or a["n"] == key:
                return a
        return None

    def accounts(self, ai_id):
        lst = self.cfg["accounts"].get(ai_id)
        if not lst:
            lst = [{"id": "default", "name": "Akun 1"}]
            self.cfg["accounts"][ai_id] = lst
        return lst

    def current_view(self):
        if not self.current:
            return None
        return self.views.get((self.current["id"], self.cur_acc))

    def drop_views(self, ai_id, acc_id=None):
        for k in list(self.views):
            if k[0] == ai_id and (acc_id is None or k[1] == acc_id):
                v = self.views.pop(k)
                self.stack.removeWidget(v)
                v.deleteLater()

    def set_bar_enabled(self, on):
        for w in (self.combo, self.btn_kelola, self.btn_reload, self.btn_browser):
            w.setEnabled(on)

    def refresh_list(self):
        self.list.clear()
        for a in self.cfg["ais"]:
            if a.get("hidden"):
                continue
            it = QListWidgetItem(dot_icon(a["n"][:1].upper(), a["c"]), "" if self.collapsed else a["n"])
            it.setToolTip(a["n"])
            it.setData(Qt.ItemDataRole.UserRole, a["id"])
            it.setSizeHint(QSize(0, 44))
            self.list.addItem(it)
            if self.current and a["id"] == self.current["id"]:
                self.list.setCurrentItem(it)

    def fill_combo(self, accs, acc_id):
        self.combo.clear()
        for x in accs:
            self.combo.addItem(x["name"], x["id"])
        self.combo.setCurrentIndex(max(0, self.combo.findData(acc_id)))

    def set_collapsed(self, c, save=True):
        self.collapsed = c
        self.side.setFixedWidth(64 if c else 240)
        self.side_title.setVisible(not c)
        self.btn_manage.setText("\u2699" if c else "Atur daftar AI")
        self.cfg["side_collapsed"] = c
        if save:
            save_config(self.cfg)
        self.refresh_list()

    def on_item(self, item):
        a = self.find(item.data(Qt.ItemDataRole.UserRole))
        if a:
            self.show_ai(a)

    def show_ai(self, a, acc_id=None):
        accs = self.accounts(a["id"])
        ids = [x["id"] for x in accs]
        if acc_id not in ids:
            acc_id = self.cfg["acc_last"].get(a["id"])
            if acc_id not in ids:
                acc_id = ids[0]
        self.current = a
        self.cur_acc = acc_id
        key = (a["id"], acc_id)
        
        if key not in self.views:
            pkey = "default" if acc_id == "default" else a["id"] + "_" + acc_id
            profile = get_profile(pkey)
            
            if "dola.ai" in a["u"]:
                inject_cookies_from_chrome(profile, domain=".dola.ai")

            view = QWebEngineView()
            view.setPage(AIPage(profile, view))
            view.load(QUrl(a["u"]))
            self.stack.addWidget(view)
            self.views[key] = view

        self.stack.setCurrentWidget(self.views[key])
        self.bar_title.setText(a["n"])
        self.fill_combo(accs, acc_id)
        self.set_bar_enabled(True)
        self.cfg["last"] = a["id"]
        self.cfg["acc_last"][a["id"]] = acc_id
        save_config(self.cfg)
        self.refresh_list()

    def show_empty(self):
        self.current = None
        self.cur_acc = None
        self.bar_title.setText("")
        self.combo.clear()
        self.set_bar_enabled(False)
        self.stack.setCurrentWidget(self.empty)
        self.cfg["last"] = ""

    def reload(self):
        v = self.current_view()
        if v:
            v.reload()

    def open_browser(self):
        if self.current:
            QDesktopServices.openUrl(QUrl(self.current["u"]))

    def on_account(self, index):
        if self.current:
            self.show_ai(self.current, self.combo.itemData(index))

    def current_account(self):
        for x in self.accounts(self.current["id"]):
            if x["id"] == self.cur_acc:
                return x
        return None

    def name_taken(self, accs, name, exclude=None):
        return any(x["name"].lower() == name.lower() and x["id"] != exclude for x in accs)

    def add_account(self):
        if not self.current:
            return
        accs = self.accounts(self.current["id"])
        name, ok = QInputDialog.getText(self, "Tambah akun", "Nama akun:", text="Akun %d" % (len(accs) + 1))
        name = name.strip()
        if not ok or not name:
            return
        if self.name_taken(accs, name):
            QMessageBox.information(self, "Menu AI", "Nama akun itu sudah ada.")
            return
        acc = {"id": uuid.uuid4().hex[:8], "name": name}
        accs.append(acc)
        self.show_ai(self.current, acc["id"])

    def rename_account(self):
        acc = self.current_account() if self.current else None
        if not acc:
            return
        accs = self.accounts(self.current["id"])
        name, ok = QInputDialog.getText(self, "Ubah nama akun", "Nama akun:", text=acc["name"])
        name = name.strip()
        if not ok or not name:
            return
        if self.name_taken(accs, name, acc["id"]):
            QMessageBox.information(self, "Menu AI", "Nama akun itu sudah ada.")
            return
        acc["name"] = name
        save_config(self.cfg)
        self.fill_combo(accs, acc["id"])

    def remove_account(self):
        acc = self.current_account() if self.current else None
        if not acc:
            return
        accs = self.accounts(self.current["id"])
        if len(accs) <= 1:
            QMessageBox.information(self, "Menu AI", "Harus ada minimal satu akun.")
            return
        ok = QMessageBox.question(self, "Hapus akun", "Hapus akun %s dari daftar?" % acc["name"])
        if ok != QMessageBox.StandardButton.Yes:
            return
        ai = self.current
        accs.remove(acc)
        self.drop_views(ai["id"], acc["id"])
        self.cfg["acc_last"].pop(ai["id"], None)
        self.show_ai(ai)

    def manage_ais(self):
        old = {a["id"]: a["u"] for a in self.cfg["ais"]}
        d = AIDialog(self.cfg["ais"], self)
        if not d.exec():
            return
        new = d.result_list()
        ids = {a["id"] for a in new}
        for a in new:
            if a["id"] in old and old[a["id"]] != a["u"]:
                self.drop_views(a["id"])
        for i in old:
            if i not in ids:
                self.drop_views(i)
                self.cfg["accounts"].pop(i, None)
                self.cfg["acc_last"].pop(i, None)
        self.cfg["ais"] = new
        cur = self.find(self.current["id"]) if self.current else None
        if self.current and not cur:
            self.show_empty()
        elif cur:
            self.show_ai(cur, self.cur_acc)
        save_config(self.cfg)
        self.refresh_list()

    def show_prompts(self):
        m = QMenu(self)
        ps = self.cfg["prompts"]
        if ps:
            for p in ps:
                title = p["t"] if len(p["t"]) <= 40 else p["t"][:40] + "..."
                act = m.addAction(title.replace("&", "&&"))
                act.triggered.connect(lambda checked=False, x=p["x"]: self.insert_prompt(x))
        else:
            m.addAction("(Belum ada prompt)").setEnabled(False)
        m.addSeparator()
        m.addAction("Kelola prompt...").triggered.connect(self.manage_prompts)
        m.exec(self.btn_prompt.mapToGlobal(self.btn_prompt.rect().bottomLeft()))

    def manage_prompts(self):
        d = PromptDialog(self.cfg["prompts"], self)
        d.exec()
        self.cfg["prompts"] = d.prompts
        save_config(self.cfg)

    def insert_prompt(self, text):
        v = self.current_view()
        if not v:
            QMessageBox.information(self, "Prompt favorit", "Pilih AI dulu, lalu pilih prompt.")
            return

        def done(ok):
            if not ok:
                QMessageBox.information(
                    self, "Prompt favorit",
                    "Kotak chat tidak ditemukan. Klik kotak chat di situs AI dulu, lalu coba lagi.")

        v.page().runJavaScript(JS_INSERT % json.dumps(text), done)
        v.setFocus()

STYLE = """
#side{background:#ffffff;border-right:1px
