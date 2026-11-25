"""Menu AI (PySide6): daftar AI di kiri, jendela AI di kanan."""
import json
import os
import re
import sys

from PySide6.QtCore import QSize, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

# Beberapa laptop gagal membuat konteks GPU untuk Chromium (panel kanan jadi kosong).
# Pakai rendering software supaya stabil. Harus di-set sebelum QApplication dibuat.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")

DEFAULTS = [
    {"n": "ChatGPT", "u": "https://chatgpt.com", "c": "#10a37f"},
    {"n": "Claude", "u": "https://claude.ai", "c": "#c0603a"},
    {"n": "Gemini", "u": "https://gemini.google.com", "c": "#4a6cf7"},
    {"n": "Grok", "u": "https://grok.com", "c": "#333b4a"},
    {"n": "Copilot", "u": "https://copilot.microsoft.com", "c": "#2b7bd6"},
    {"n": "Perplexity", "u": "https://www.perplexity.ai", "c": "#1f8a9e"},
    {"n": "DeepSeek", "u": "https://chat.deepseek.com", "c": "#4d6bfe"},
]

# Izin yang boleh diberikan otomatis ke situs AI (mikrofon, kamera, clipboard)
ALLOWED_PERMS = {"MediaAudioCapture", "MediaVideoCapture", "MediaAudioVideoCapture", "ClipboardReadWrite"}

DATA_DIR = ""
popups = []  # jendela popup (misalnya login) supaya tidak langsung dibuang


def config_path():
    return os.path.join(DATA_DIR, "config.json")


def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.setdefault("custom", [])
        cfg.setdefault("last", "")
        return cfg
    except Exception:
        return {"custom": [], "last": ""}


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


class AIPage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        if hasattr(self, "permissionRequested"):  # Qt 6.8+
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
        # Link target=_blank / popup login dibuka di jendela terpisah dengan profil yang sama
        view = QWebEngineView()
        page = AIPage(self.profile(), view)
        view.setPage(page)
        view.resize(900, 700)
        view.setWindowTitle("Menu AI")
        page.windowCloseRequested.connect(view.close)
        view.show()
        popups.append(view)
        return page


class Main(QMainWindow):
    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.cfg = load_config()
        self.views = {}
        self.current = None
        self.setWindowTitle("Menu AI")
        self.resize(1280, 800)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- kiri: daftar AI ---
        side = QWidget()
        side.setFixedWidth(240)
        side.setObjectName("side")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 14, 10, 12)
        title = QLabel("Menu AI")
        title.setObjectName("title")
        sl.addWidget(title)

        self.list = QListWidget()
        self.list.setIconSize(QSize(28, 28))
        self.list.setFrameShape(QListWidget.Shape.NoFrame)
        self.list.itemClicked.connect(self.on_item)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.on_menu)
        sl.addWidget(self.list, 1)

        sl.addWidget(QLabel("Tambah AI"))
        self.in_n = QLineEdit()
        self.in_n.setPlaceholderText("Nama, misalnya Mistral")
        self.in_u = QLineEdit()
        self.in_u.setPlaceholderText("chat.mistral.ai")
        self.msg = QLabel("")
        self.msg.setObjectName("msg")
        btn_add = QPushButton("Tambah ke daftar")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self.add_ai)
        self.in_n.textChanged.connect(lambda: self.msg.setText(""))
        self.in_u.textChanged.connect(lambda: self.msg.setText(""))
        for w in (self.in_n, self.in_u, self.msg, btn_add):
            sl.addWidget(w)
        root.addWidget(side)

        # --- kanan: jendela AI ---
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
        btn_reload = QPushButton("Muat ulang")
        btn_reload.clicked.connect(self.reload)
        btn_browser = QPushButton("Buka di browser")
        btn_browser.clicked.connect(self.open_browser)
        bl.addWidget(self.bar_title, 1)
        bl.addWidget(btn_reload)
        bl.addWidget(btn_browser)
        self.bar.hide()
        rl.addWidget(self.bar)

        self.stack = QStackedWidget()
        self.empty = QLabel("Pilih AI di kiri,\njendelanya muncul di sini.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setObjectName("empty")
        self.stack.addWidget(self.empty)
        rl.addWidget(self.stack, 1)
        root.addWidget(right, 1)

        self.setCentralWidget(central)
        self.refresh_list()

        last = self.find(self.cfg.get("last", ""))
        if last:
            self.show_ai(last)

    # ---------- data ----------
    def all(self):
        out = [dict(d, custom=False) for d in DEFAULTS]
        for c in self.cfg["custom"]:
            out.append({"n": c["n"], "u": c["u"], "c": "#6b7a76", "custom": True})
        return out

    def find(self, name):
        for a in self.all():
            if a["n"] == name:
                return a
        return None

    def refresh_list(self):
        self.list.clear()
        for a in self.all():
            it = QListWidgetItem(dot_icon(a["n"][:1].upper(), a["c"]), a["n"])
            it.setData(Qt.ItemDataRole.UserRole, a["n"])
            it.setSizeHint(QSize(0, 44))
            self.list.addItem(it)
            if self.current and a["n"] == self.current["n"]:
                self.list.setCurrentItem(it)

    # ---------- aksi ----------
    def on_item(self, item):
        a = self.find(item.data(Qt.ItemDataRole.UserRole))
        if a:
            self.show_ai(a)

    def show_ai(self, a):
        self.current = a
        if a["n"] not in self.views:
            view = QWebEngineView()
            view.setPage(AIPage(self.profile, view))
            view.load(QUrl(a["u"]))
            self.stack.addWidget(view)
            self.views[a["n"]] = view
        self.stack.setCurrentWidget(self.views[a["n"]])
        self.bar_title.setText(a["n"])
        self.bar.show()
        self.cfg["last"] = a["n"]
        save_config(self.cfg)
        self.refresh_list()

    def reload(self):
        if self.current and self.current["n"] in self.views:
            self.views[self.current["n"]].reload()

    def open_browser(self):
        if self.current:
            QDesktopServices.openUrl(QUrl(self.current["u"]))

    def on_menu(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        a = self.find(it.data(Qt.ItemDataRole.UserRole))
        if not a or not a["custom"]:
            return
        menu = QMenu(self)
        act = menu.addAction("Hapus " + a["n"])
        if menu.exec(self.list.viewport().mapToGlobal(pos)) == act:
            self.remove_ai(a)

    def remove_ai(self, a):
        self.cfg["custom"] = [c for c in self.cfg["custom"] if c["n"] != a["n"]]
        v = self.views.pop(a["n"], None)
        if v:
            self.stack.removeWidget(v)
            v.deleteLater()
        if self.current and self.current["n"] == a["n"]:
            self.current = None
            self.bar.hide()
            self.stack.setCurrentWidget(self.empty)
            self.cfg["last"] = ""
        save_config(self.cfg)
        self.refresh_list()

    def add_ai(self):
        n = self.in_n.text().strip()
        u = self.in_u.text().strip()
        if not n:
            self.msg.setText("Isi nama AI dulu.")
            return
        if not u:
            self.msg.setText("Isi alamat situsnya.")
            return
        if not re.match(r"^https?://", u, re.I):
            u = "https://" + u
        if not QUrl(u).isValid() or "." not in QUrl(u).host():
            self.msg.setText("Alamat situs tidak valid.")
            return
        if self.find(n):
            self.msg.setText("Nama itu sudah ada.")
            return
        self.cfg["custom"].append({"n": n, "u": u})
        save_config(self.cfg)
        self.in_n.clear()
        self.in_u.clear()
        self.refresh_list()


STYLE = """
#side{background:#ffffff;border-right:1px solid #d5dedb}
#title{font-size:18px;font-weight:700;padding:2px 4px}
#bar{background:#ffffff;border-bottom:1px solid #d5dedb}
#empty{color:#5d6d69;font-size:16px}
#msg{color:#b3261e;font-size:12px}
QListWidget{background:transparent;outline:0}
QListWidget::item{border-radius:10px;padding:2px 6px}
QListWidget::item:hover{background:#eef2f0}
QListWidget::item:selected{background:#d9efe8;color:#14211f;font-weight:bold}
QLineEdit{border:1px solid #d5dedb;border-radius:8px;padding:8px 10px;background:#eef2f0}
QPushButton{border:1px solid #d5dedb;border-radius:8px;padding:8px 14px;background:#ffffff}
QPushButton:hover{background:#eef2f0}
QPushButton#primary{background:#0e7c66;color:#ffffff;border:0;font-weight:bold}
QPushButton#primary:hover{background:#0b6653}
"""


def main():
    global DATA_DIR
    app = QApplication(sys.argv)
    app.setApplicationName("MenuAI")
    DATA_DIR = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    app.setStyleSheet(STYLE)

    # Profil permanen: login dan cookie tersimpan setelah aplikasi ditutup
    profile = QWebEngineProfile("menuai", app)
    profile.setPersistentStoragePath(os.path.join(DATA_DIR, "web"))
    profile.setCachePath(os.path.join(DATA_DIR, "cache"))
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
    # Buang penanda "QtWebEngine" dari user-agent supaya tampak seperti Chrome biasa
    profile.setHttpUserAgent(re.sub(r"\s*QtWebEngine/\S+", "", profile.httpUserAgent()))

    def on_download(req):
        req.setDownloadDirectory(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation))
        req.accept()

    profile.downloadRequested.connect(on_download)

    win = Main(profile)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
