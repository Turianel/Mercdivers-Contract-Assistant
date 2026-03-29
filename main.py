import sys
import re
import datetime
import requests
import os
import win32gui
import win32con
import win32api
import ctypes
import configparser
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QSystemTrayIcon, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QRectF, QThread, pyqtSignal
from PyQt6.QtGui import (QPainter, QColor, QFont, QPen, QBrush, QPolygon, 
                         QTextDocument, QAbstractTextDocumentLayout, QPixmap, QIcon)

# --- CLOUD CONFIGURATION ---
# Replace with your actual Gist data
GIST_RAW_URL = "https://gist.githubusercontent.com/Turianel/f25010ca0aa2b8e39cc1185bc67d4746/raw/latest_transmission.json"

# --- KEYBINDING MAPPING ---
# VK_MENU covers both Alts. VK_LMENU/VK_RMENU are specific.
VK_MAP = {
    'NUMPAD0': win32con.VK_NUMPAD0, 'NUMPAD1': win32con.VK_NUMPAD1,
    'NUMPAD2': win32con.VK_NUMPAD2, 'NUMPAD3': win32con.VK_NUMPAD3,
    'ALT': win32con.VK_MENU,       # Both Alts
    'LALT': win32con.VK_LMENU,     # Left Alt only
    'RALT': win32con.VK_RMENU,     # Right Alt only
    'CTRL': win32con.VK_CONTROL,   # Both Ctrls
    'LCTRL': win32con.VK_LCONTROL, # Left Ctrl only
    'RCTRL': win32con.VK_RCONTROL, # Right Ctrl only
    'SHIFT': win32con.VK_SHIFT,    # Both Shifts
    'LSHIFT': win32con.VK_LSHIFT,
    'F1': win32con.VK_F1, 'F2': win32con.VK_F2, 'F3': win32con.VK_F3,
    'F4': win32con.VK_F4, 'F5': win32con.VK_F5, 'F6': win32con.VK_F6,
    'F7': win32con.VK_F7, 'F8': win32con.VK_F8, 'F9': win32con.VK_F9,
    'F10': win32con.VK_F10, 'F11': win32con.VK_F11, 'F12': win32con.VK_F12,
    'TILDE': 0xC0, 'INSERT': win32con.VK_INSERT, 'HOME': win32con.VK_HOME,
    'XBUTTON1': win32con.VK_XBUTTON1, 'XBUTTON2': win32con.VK_XBUTTON2,
}

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_settings_path():
    """ Return the path to settings.ini next to the executable """
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "settings.ini")

def load_settings():
    """ Load settings from ini file or create defaults if missing """
    config = configparser.ConfigParser()
    settings_path = get_settings_path()
    
    defaults = {
        'toggle_overlay': 'NUMPAD0',
        'interactive_mode': 'ALT', # Default responds to both Alts
        'force_update': 'F5'
    }

    if not os.path.exists(settings_path):
        config['Keybinds'] = defaults
        try:
            with open(settings_path, 'w') as f:
                config.write(f)
        except Exception as e:
            print(f"Failed to create settings.ini: {e}")
        return defaults

    config.read(settings_path)
    return {
        'toggle_overlay': config['Keybinds'].get('toggle_overlay', 'NUMPAD0').upper(),
        'interactive_mode': config['Keybinds'].get('interactive_mode', 'ALT').upper(),
        'force_update': config['Keybinds'].get('force_update', 'F5').upper()
    }

class MercParser:
    @staticmethod
    def clean_discord_emojis(text):
        if not text: return ""
        text = re.sub(r"<a?:supercredits:\d+>", "[SC_ICON]", text, flags=re.I)
        text = re.sub(r":supercredits:", "[SC_ICON]", text, flags=re.I)
        text = re.sub(r"<a?:\w+:\d+>", "", text)
        return text.strip()

    @staticmethod
    def extract_quotes(text):
        if not text: return ""
        quotes = re.findall(r"^>\s*(.*)", text, re.M)
        return "\n".join(quotes) if quotes else ""

    @staticmethod
    def remove_quotes(text):
        if not text: return ""
        return re.sub(r"^>\s*.*(?:\n|$)", "", text, flags=re.M).strip()

    @staticmethod
    def parse_contract(data):
        if not data or not data.get('contract'): return None
        text = data['contract'].get('content', '')
        try:
            title_match = re.search(r"Contract:\s*(.*)", text)
            title = title_match.group(1).strip() if title_match else "UNKNOWN OPERATION"
            ts_match = re.search(r"<t:(\d+):?\w*>", text)
            timestamp = int(ts_match.group(1)) if ts_match else None
            dl_match = re.search(r"(?:Deadline|Complete date):\s*(.*?)(?=\s*<t:|\n|$)", text, re.I)
            deadline_text = dl_match.group(1).strip() if dl_match else "NO DATA"
            obj_match = re.search(r"###[^#\n]*?OBJECTIVES[^#\n]*?###\s*(.*?)(?=\s*(?:##|###)|$)", text, re.S | re.I)
            conditions = MercParser.clean_discord_emojis(obj_match.group(1).strip() if obj_match else "")
            rew_match = re.search(r"###[^#\n]*?REWARD[^#\n]*?###\s*(.*?)(?=\s*(?:##|###)|$)", text, re.S | re.I)
            reward = rew_match.group(1).strip() if rew_match else "PENDING"
            return {
                "type": "CONTRACTS", "title": title.upper(), "deadline_text": deadline_text,
                "timestamp": timestamp, "conditions": conditions,
                "reward": MercParser.clean_discord_emojis(reward).upper(), "color": QColor("#ffe81f")
            }
        except: return None

    @staticmethod
    def parse_bounty(data):
        if not data or not data.get('bounty'): return None
        text = data['bounty'].get('content', '')
        try:
            title_match = re.search(r"Bounty:\s*(.*)", text)
            title = title_match.group(1).split('\n')[0].strip() if title_match else "TARGET ELIMINATION"
            ts_match = re.search(r"<t:(\d+):?\w*>", text)
            timestamp = int(ts_match.group(1)) if ts_match else None
            dl_match = re.search(r"(?:Deadline|Complete date):\s*(.*?)(?=\s*<t:|\n|$)", text, re.I)
            deadline_text = dl_match.group(1).strip() if dl_match else "UNTIL ELIMINATED"
            obj_section_match = re.search(r"###[^#\n]*?Objectives[^#\n]*?###\s*(.*?)(?=\s*(?:##|###)|$)", text, re.S | re.I)
            raw_section = obj_section_match.group(1).strip() if obj_section_match else ""
            conditions_text = MercParser.extract_quotes(text) 
            rewards_list = []
            clean_section = MercParser.remove_quotes(raw_section)
            for line in clean_section.split('\n'):
                line = MercParser.clean_discord_emojis(line).strip().lstrip('*').lstrip('-').strip()
                if not line: continue
                match = re.match(r"(\+)?\s*(\d+)\s*(?:SC|Credits|\[SC_ICON\])?\s*(.*)", line, re.I)
                if match:
                    rewards_list.append({
                        "val": f"{'+' if match.group(1) else ''}{match.group(2)} SC", 
                        "task": match.group(3).strip() if match.group(3) else "Mission Objective",
                        "is_bonus": bool(match.group(1))
                    })
            return {
                "type": "BOUNTIES", "title": title.upper(), "deadline_text": deadline_text,
                "timestamp": timestamp, "difficulty": conditions_text,
                "rewards_list": rewards_list, "color": QColor("#73c229")
            }
        except: return None

class NetworkWorker(QThread):
    data_fetched = pyqtSignal(dict, bool)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            url_with_t = f"{self.url}?t={int(datetime.datetime.now().timestamp())}"
            response = requests.get(url_with_t, timeout=5)
            if response.status_code == 200:
                self.data_fetched.emit(response.json(), True)
            else:
                self.data_fetched.emit({}, False)
        except Exception:
            self.data_fetched.emit({}, False)

class MercOverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {"CONTRACTS": None, "BOUNTIES": None}
        self.current_tab = "CONTRACTS"
        self.is_online = False
        self.bg_color = QColor(15, 15, 15, 245)
        self.accent_yellow = QColor("#ffe81f")
        self.accent_green = QColor("#73c229")
        self.accent_cyan = QColor("#00ffff")
        
        logo_path = resource_path("PMC_Logo.webp")
        self.logo_pixmap = QPixmap(logo_path) if os.path.exists(logo_path) else QPixmap()
        self.sc_icon_path = resource_path("supercredits.png").replace("\\", "/")
        
        self.scroll_offsets = {"OBJECTIVES": 0.0, "REWARD": 0.0, "BOUNTIES": 0.0, "COND_ROW": 0.0, "DEADLINE": 0.0}
        self.scroll_dirs = {k: 1 for k in self.scroll_offsets}
        self.max_scrolls = {k: 0 for k in self.scroll_offsets}
        
        QTimer(self, timeout=self.update_animation).start(50)
        QTimer(self, timeout=self.update).start(1000)
        
    def update_full_payload(self, raw_json, success=True):
        self.is_online = success
        if success and raw_json:
            c_data = MercParser.parse_contract(raw_json)
            b_data = MercParser.parse_bounty(raw_json)
            if c_data: self.data["CONTRACTS"] = c_data
            if b_data: self.data["BOUNTIES"] = b_data
            last_type = raw_json.get('last_update_type')
            if last_type in self.data: self.current_tab = last_type
        self.update()

    def update_animation(self):
        needs_update = False
        for key in self.scroll_offsets.keys():
            max_s = self.max_scrolls.get(key, 0)
            if max_s > 0:
                self.scroll_offsets[key] += 0.4 * self.scroll_dirs[key]
                if self.scroll_offsets[key] >= max_s + 20: self.scroll_dirs[key] = -1
                elif self.scroll_offsets[key] <= -20: self.scroll_dirs[key] = 1
                needs_update = True
            else: self.scroll_offsets[key] = 0.0
        if needs_update: self.update()

    def get_time_remaining(self, ts):
        if not ts: return None
        try:
            diff = ts - datetime.datetime.now().timestamp()
            if diff <= 0: return "EXPIRED"
            h, m, s = int(diff // 3600), int((diff % 3600) // 60), int(diff % 60)
            return f"{h}h:{m:02d}m:{s:02d}s" if h > 0 else f"{m:02d}m:{s:02d}s"
        except: return None

    def mousePressEvent(self, event):
        if 70 <= event.pos().y() <= 115:
            self.current_tab = "CONTRACTS" if event.pos().x() < self.width() / 2 else "BOUNTIES"
            for k in self.scroll_offsets: self.scroll_offsets[k] = 0.0
            self.update()

    def draw_html_text(self, painter, rect, text, font, color, v_align_center=False, scroll_key=None):
        doc = QTextDocument()
        doc.setDefaultFont(font)
        doc.setTextWidth(rect.width())
        doc.setDocumentMargin(0)
        
        html_text = text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        if os.path.exists(self.sc_icon_path):
            html_text = html_text.replace("[SC_ICON]", f'<img src="{self.sc_icon_path}" width="14" height="14" style="vertical-align: middle;">')
        else:
            html_text = html_text.replace("[SC_ICON]", "SC")

        doc.setHtml(f"<div style='color: {color.name()}; line-height: 1.2; font-weight: 600;'>{html_text}</div>")
        text_height = doc.size().height()
        if scroll_key: self.max_scrolls[scroll_key] = max(0, int(text_height - rect.height() + 5))
        y_offset = (rect.height() - text_height) / 2 if v_align_center and text_height < rect.height() else 0
        
        painter.save()
        painter.setClipRect(rect, Qt.ClipOperation.IntersectClip)
        scroll_val = max(0, int(self.scroll_offsets.get(scroll_key, 0))) if scroll_key else 0
        painter.translate(rect.x(), rect.y() + y_offset - scroll_val)
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.clip = QRectF(0, scroll_val, rect.width(), rect.height())
        doc.documentLayout().draw(painter, ctx)
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cut = 30
        points = [QPoint(0,0), QPoint(w,0), QPoint(w, h-cut), QPoint(w-cut, h), QPoint(0,h)]
        painter.setPen(QPen(self.accent_yellow, 2))
        painter.setBrush(QBrush(self.bg_color))
        painter.drawPolygon(QPolygon(points))
        
        self.draw_header(painter)
        self.draw_tabs(painter, w)
        
        item = self.data.get(self.current_tab)
        if not item:
            painter.setPen(QColor(100, 100, 100)); painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "ESTABLISHING UPLINK...")
            return
            
        painter.setPen(QColor(240, 240, 240)); painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        painter.drawText(15, 145, item['title'])
        
        if self.current_tab == "CONTRACTS": self.draw_contracts_view(painter, item, w, h)
        else: self.draw_bounties_view(painter, item, w, h)
        
        self.draw_footer(painter, w, h)

    def draw_header(self, painter):
        if self.logo_pixmap and not self.logo_pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(15, 15, 40, 40, self.logo_pixmap)
        else:
            painter.setBrush(QBrush(self.accent_yellow)); painter.drawRect(15, 15, 40, 40)
        
        painter.setPen(self.accent_yellow)
        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        painter.drawText(65, 32, "MERCDIVERS PMC")
        
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.drawText(220, 32, "CONTRACT ASSISTANT")
        
        status_color = QColor("#00ff00") if self.is_online else QColor("#ff4444")
        painter.setPen(QColor(120, 120, 120)); painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        painter.drawText(65, 50, "Uplink status: ")
        painter.setPen(status_color)
        painter.drawText(140, 50, "ONLINE" if self.is_online else "OFFLINE")

    def draw_tabs(self, painter, w):
        for i, label in enumerate(["Contracts", "Bounties"]):
            tab_type = label.upper()
            is_active = self.current_tab == tab_type
            x, tw = (15, w/2 - 20) if i == 0 else (w/2 + 5, w/2 - 20)
            color = self.accent_yellow if tab_type == "CONTRACTS" else self.accent_green
            if is_active:
                painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 40)))
                painter.setPen(QPen(color, 1)); painter.drawRect(int(x), 75, int(tw), 35)
                painter.setBrush(QBrush(color)); painter.drawRect(int(x), 108, int(tw), 2)
                painter.setPen(color)
            else: painter.setPen(QColor(70, 70, 70))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(QRect(int(x), 75, int(tw), 35), Qt.AlignmentFlag.AlignCenter, label)

    def draw_contracts_view(self, painter, item, w, h):
        acc = item['color']
        time = self.get_time_remaining(item.get('timestamp'))
        dl = f"{item['deadline_text']} ({time})" if time else item['deadline_text']
        y_ptr = 165
        f_content = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        self.draw_block(painter, 15, y_ptr, w-30, 150, "OBJECTIVES", item['conditions'], QColor(240, 240, 240), acc, f_content)
        y_ptr += 160
        self.draw_block(painter, 15, y_ptr, w-30, 90, "REWARD", item['reward'], acc, acc, f_content)
        y_ptr += 100
        self.draw_block(painter, 15, y_ptr, w-30, 60, "DEADLINE", dl, acc, acc, f_content)
        if time == "EXPIRED": self.draw_expired_overlay(painter, 15, 165, w-30, 360, "CONTRACT EXPIRED")

    def draw_bounties_view(self, painter, item, w, h):
        view = QRect(15, 165, w - 30, 210)
        rewards = item.get('rewards_list', [])
        row_height = 65
        self.max_scrolls["BOUNTIES"] = max(0, len(rewards) * row_height - view.height())
        y_off = view.y() - int(self.scroll_offsets.get("BOUNTIES", 0))
        painter.save()
        painter.setClipRect(view)
        if not rewards:
            painter.setPen(QColor(100, 100, 100)); painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            painter.drawText(view, Qt.AlignmentFlag.AlignCenter, "NO OBJECTIVES DEFINED")
        else:
            for i, r in enumerate(rewards): self.draw_bounty_row(painter, 15, y_off + i*row_height, w-30, 55, r)
        painter.restore() 
        self.draw_info_row(painter, 15, 385, w-30, "Conditions:", item.get('difficulty', "N/A"), "COND_ROW", self.accent_green)
        time = self.get_time_remaining(item.get('timestamp'))
        dl = f"{item['deadline_text']} ({time})" if time else item['deadline_text']
        self.draw_info_row(painter, 15, 460, w-30, "Deadline:", dl, "DEADLINE", self.accent_green)
        if time == "EXPIRED": self.draw_expired_overlay(painter, 15, 165, w-30, 360, "BOUNTY EXPIRED")

    def draw_bounty_row(self, painter, x, y, w, h, obj):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(115, 194, 41, 15 if not obj.get('is_bonus') else 8)))
        painter.drawRect(x, y, w, h)
        line_c = QColor(115, 194, 41, 255 if not obj.get('is_bonus') else 120)
        painter.setBrush(QBrush(line_c)); painter.drawRect(x, y, 4, h)
        rect = QRect(int(x+15), int(y), int(w-105), int(h))
        self.draw_html_text(painter, rect, obj['task'], QFont("Segoe UI", 9, QFont.Weight.DemiBold), QColor(240, 240, 240), v_align_center=True)
        bx = x + w - 85
        painter.setBrush(QBrush(self.accent_cyan)); painter.drawRect(bx, y+16, 75, 22)
        painter.setPen(QColor(0,0,0)); painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.drawText(QRect(bx, y+16, 75, 22), Qt.AlignmentFlag.AlignCenter, obj['val'])

    def draw_info_row(self, painter, x, y, w, lbl, val, scroll_key, acc_color):
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(acc_color)); painter.drawRect(x, y, 4, 65)
        painter.setBrush(QBrush(QColor(255, 255, 255, 5))); painter.drawRect(x+4, y, w-4, 65)
        painter.setPen(self.accent_yellow); painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(x+15, y+18, lbl)
        rect = QRect(int(x+15), int(y+22), int(w-25), int(38))
        self.draw_html_text(painter, rect, val, QFont("Segoe UI", 9, QFont.Weight.DemiBold), QColor(200, 200, 200), scroll_key=scroll_key)

    def draw_block(self, painter, x, y, w, h, lbl, cnt, c_clr, acc, font):
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(QColor(255, 255, 255, 5))); painter.drawRect(x, y, w, h)
        painter.setBrush(QBrush(acc)); painter.drawRect(x, y, 3, h)
        painter.setPen(QColor(100, 100, 100)); painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(x+12, y+15, lbl)
        text_rect = QRect(int(x+12), int(y+25), int(w-24), int(h-30))
        self.draw_html_text(painter, text_rect, cnt, font, c_clr, scroll_key=lbl)

    def draw_expired_overlay(self, painter, x, y, w, h, txt):
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(QColor(0, 0, 0, 210))); painter.drawRect(x, y, w, h)
        painter.setPen(QColor(220, 20, 20)); painter.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        painter.drawText(QRect(x, y, w, h), Qt.AlignmentFlag.AlignCenter, txt)

    def draw_footer(self, painter, w, h):
        painter.setPen(QColor(80, 80, 80)); painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        now = datetime.datetime.now().strftime("%H:%M:%S")
        painter.drawText(15, h-10, f"TIME: {now}")
        painter.drawText(w-120, h-10, "v.1.1 | By Turianel")

class MercOverlayApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 580)
        self.ui = MercOverlayWidget(self)
        self.setCentralWidget(self.ui)
        self.game_title = "HELLDIVERS™ 2"
        self.is_visible_master = True 
        self.global_ts = None
        self.is_interactive = False 
        self.game_hwnd = None
        self.setup_tray()
        
        self.cloud_timer = QTimer(self)
        self.cloud_timer.timeout.connect(self.update_from_cloud)
        self.cloud_timer.start(60000) 
        
        QTimer.singleShot(1000, self.update_from_cloud)
        
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_with_game)
        self.sync_timer.start(200) 
        
        self.input_timer = QTimer(self)
        self.input_timer.timeout.connect(self.process_native_input)
        self.input_timer.start(50)
        
        self.toggle_was_pressed = False
        self.update_was_pressed = False
        
        QTimer.singleShot(100, lambda: self.set_clickthrough(True))

    def setup_tray(self):
        try:
            self.tray = QSystemTrayIcon(self)
            logo_path = resource_path("PMC_Logo.webp")
            if os.path.exists(logo_path):
                self.tray.setIcon(QIcon(logo_path))
            else:
                self.tray.setIcon(QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_ComputerIcon))
                
            menu = QMenu()
            toggle_key = self.settings.get('toggle_overlay', 'NUMPAD0')
            update_key = self.settings.get('force_update', 'F5')
            
            menu.addAction(f"Toggle Visibility ({toggle_key})", self.toggle_visibility)
            menu.addAction(f"Force Update ({update_key})", self.update_from_cloud)
            menu.addSeparator()
            menu.addAction("Exit", QApplication.instance().quit)
            
            self.tray.setContextMenu(menu)
            self.tray.show()
        except: pass

    def update_from_cloud(self):
        if hasattr(self, 'net_worker') and self.net_worker.isRunning():
            return
        self.net_worker = NetworkWorker(GIST_RAW_URL)
        self.net_worker.data_fetched.connect(self.on_data_fetched)
        self.net_worker.start()

    def on_data_fetched(self, data, success):
        if success:
            ts = data.get("global_timestamp")
            if ts != self.global_ts:
                self.global_ts = ts
                self.ui.update_full_payload(data, success=True)
            else:
                self.ui.is_online = True
                self.ui.update()
        else: 
            self.ui.is_online = False
            self.ui.update()

    def toggle_visibility(self):
        self.is_visible_master = not self.is_visible_master
        if not self.is_visible_master: self.hide()
        else: self.sync_with_game()

    def set_clickthrough(self, transparent):
        try:
            hwnd = int(self.winId())
            exStyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if transparent: win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exStyle | win32con.WS_EX_TRANSPARENT)
            else: win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, exStyle & ~win32con.WS_EX_TRANSPARENT)
        except: pass

    def force_foreground(self, target_hwnd):
        try:
            fg_hwnd = win32gui.GetForegroundWindow()
            if fg_hwnd == target_hwnd: return
            fg_thread = ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, None)
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            if fg_thread and current_thread and fg_thread != current_thread:
                ctypes.windll.user32.AttachThreadInput(current_thread, fg_thread, True)
                win32gui.SetForegroundWindow(target_hwnd); win32gui.BringWindowToTop(target_hwnd)
                ctypes.windll.user32.AttachThreadInput(current_thread, fg_thread, False)
            else: win32gui.SetForegroundWindow(target_hwnd); win32gui.BringWindowToTop(target_hwnd)
        except: pass

    def is_game_active(self):
        try:
            active_hwnd = win32gui.GetForegroundWindow()
            if not self.game_hwnd or not win32gui.IsWindow(self.game_hwnd): 
                self.game_hwnd = win32gui.FindWindow(None, self.game_title)
            return active_hwnd == self.game_hwnd or active_hwnd == int(self.winId())
        except: return False

    def process_native_input(self):
        try:
            if not self.is_game_active(): return
            
            # Key mappings from config
            toggle_vk = VK_MAP.get(self.settings.get('toggle_overlay'), win32con.VK_NUMPAD0)
            update_vk = VK_MAP.get(self.settings.get('force_update'), win32con.VK_F5)
            interact_vk = VK_MAP.get(self.settings.get('interactive_mode'), win32con.VK_MENU)

            # Check for toggle press
            toggle_state = win32api.GetAsyncKeyState(toggle_vk) & 0x8000
            if toggle_state:
                if not self.toggle_was_pressed: 
                    self.toggle_visibility()
                    self.toggle_was_pressed = True
            else: self.toggle_was_pressed = False
                
            # Check for update press
            update_state = win32api.GetAsyncKeyState(update_vk) & 0x8000
            if update_state:
                if not self.update_was_pressed:
                    self.update_from_cloud()
                    self.update_was_pressed = True
            else: self.update_was_pressed = False
            
            if not self.is_visible_master: return
            
            # Interactive mode (Holding the key)
            is_interact_pressed = (win32api.GetAsyncKeyState(interact_vk) & 0x8000) != 0
            if is_interact_pressed and not self.is_interactive:
                self.is_interactive = True
                self.set_clickthrough(False)
                self.force_foreground(int(self.winId()))
            elif not is_interact_pressed and self.is_interactive:
                self.is_interactive = False
                self.set_clickthrough(True)
                if self.game_hwnd: self.force_foreground(self.game_hwnd)
        except: pass

    def sync_with_game(self):
        try:
            self.game_hwnd = win32gui.FindWindow(None, self.game_title)
            if self.game_hwnd:
                rect = win32gui.GetWindowRect(self.game_hwnd)
                new_pos = QPoint(rect[0] + 50, rect[1] + 50)
                if self.pos() != new_pos: self.move(new_pos)
                if self.is_visible_master and self.is_game_active():
                    if not self.isVisible(): self.show()
                elif self.isVisible(): self.hide()
            else:
                if self.isVisible(): self.hide()
        except: pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon_path = resource_path("PMC_Logo.webp")
    if os.path.exists(icon_path): app.setWindowIcon(QIcon(icon_path))
    window = MercOverlayApp()
    sys.exit(app.exec())
