import sys
import os
import platform
import time
import psutil
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

# ==========================================
# 1. БИЗНЕС-ЛОГИКА (Диагностика)
# ==========================================

def get_cpu_info():
    cpu_percent = psutil.cpu_percent(interval=1)
    cores = psutil.cpu_count(logical=False)
    threads = psutil.cpu_count(logical=True)
    return f"⚙️ Нагруженность CPU: {cpu_percent}%\n🧬 Физ. ядер: {cores} | Логических потоков: {threads}"

def get_ram_info():
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return (f"🧠 ОЗУ: Использовано {vm.percent}% ({vm.used // (1024**2)} MB / {vm.total // (1024**2)} MB)\n"
            f"🔄 Файл подкачки: {swap.percent}% ({swap.used // (1024**2)} MB / {swap.total // (1024**2)} MB)")

def get_disk_info():
    # Кроссплатформенный путь к корневому диску
    root_path = os.path.abspath(os.sep)
    usage = psutil.disk_usage(root_path)
    io = psutil.disk_io_counters()
    return (f"💾 Диск ({root_path}): Занято {usage.percent}%\n"
            f"📊 Свободно: {usage.free // (1024**3)} GB из {usage.total // (1024**3)} GB\n"
            f"📈 Чтение/Запись с момента включения: {io.read_bytes // (1024**2)} MB / {io.write_bytes // (1024**2)} MB")

def get_processes_info():
    # Берем топ-15 процессов по потреблению памяти, чтобы не спамить в UI
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    # Сортируем по памяти
    processes.sort(key=lambda p: p['memory_info'].rss if p['memory_info'] else 0, reverse=True)
    top_procs = processes[:15]
    
    result = "🏆 Топ-15 процессов по потреблению ОЗУ:\n" + "-"*40 + "\n"
    for p in top_procs:
        mem_mb = p['memory_info'].rss // (1024**2) if p['memory_info'] else 0
        result += f"PID: {p['pid']:<6} | RAM: {mem_mb:<5} MB | {p['name']}\n"
    return result

def get_system_info():
    return (f"🖥 Система: {platform.system()} {platform.release()}\n"
            f"🏗 Сборка ОС: {platform.version()}\n"
            f"🌐 Сетевое имя: {platform.node()}")

def get_iron_info():
    return (f"🏛 Архитектура: {platform.machine()}\n"
            f"🧠 Процессор: {platform.processor()}")

def get_battery_info():
    battery = psutil.sensors_battery()
    if battery is None:
        return "🔋 Батарея: Не обнаружена (вероятно, стационарный ПК)"
    status = "Заряжается" if battery.power_plugged else "Работает от батареи"
    return f"🔋 Батарея: {battery.percent}% ({status})"

def get_full_diag():
    # Выполняем всё последовательно
    return "\n\n".join([
        get_cpu_info(), get_ram_info(), get_disk_info(), 
        get_system_info(), get_iron_info(), get_battery_info()
    ])


# ==========================================
# 2. ПОТОКИ (Чтобы GUI не зависал)
# ==========================================

class DiagWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, task_func):
        super().__init__()
        self.task_func = task_func
        
    def run(self):
        try:
            result = self.task_func()
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit(f"❌ Ошибка при выполнении: {str(e)}")


# ==========================================
# 3. ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (PyQt6)
# ==========================================

class AndromedaApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Andromeda - System Diagnostics")
        self.resize(900, 650)
        
        self.worker = None
        self.init_ui()
        self.apply_styles()
        
        # Приветственное сообщение
        self.log("Добро пожаловать в Andromeda! Выберите модуль диагностики.")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Боковая панель (Сайдбар) ---
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 30, 20, 30)
        sidebar_layout.setSpacing(15)

        logo = QLabel("ANDROMEDA")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo)
        
        subtitle = QLabel("v2.0 | Diagnostics")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(subtitle)
        
        sidebar_layout.addSpacing(30)

        # Кнопки навигации
        buttons_config = [
            ("🚀 Полная диагностика", get_full_diag),
            ("⚙️ CPU (Нагрузка)", get_cpu_info),
            ("🧠 RAM (Память)", get_ram_info),
            ("💾 Disk (Накопители)", get_disk_info),
            ("🏆 Процессы (Топ-15)", get_processes_info),
            ("🖥 Система и Железо", lambda: f"{get_system_info()}\n\n{get_iron_info()}"),
            ("🔋 Батарея", get_battery_info),
        ]

        for text, func in buttons_config:
            btn = QPushButton(text)
            btn.setObjectName("nav_btn")
            btn.setCheckable(False)
            btn.clicked.connect(lambda checked, f=func: self.run_task(f))
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        btn_clear = QPushButton("🗑 Очистить логи")
        btn_clear.setObjectName("clear_btn")
        btn_clear.clicked.connect(self.clear_log)
        sidebar_layout.addWidget(btn_clear)

        # --- Основная область (Лог) ---
        main_area = QWidget()
        main_area.setObjectName("main_area")
        main_layout.addWidget(main_area)
        
        area_layout = QVBoxLayout(main_area)
        area_layout.setContentsMargins(20, 20, 20, 20)
        
        header = QLabel("Консоль вывода")
        header.setObjectName("header")
        area_layout.addWidget(header)

        self.log_display = QTextEdit()
        self.log_display.setObjectName("log_display")
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 11))
        area_layout.addWidget(self.log_display)

        main_layout.addWidget(sidebar)

    def apply_styles(self):
        # Современный темный UI (QSS)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            #sidebar {
                background-color: #181825;
                border-right: 1px solid #313244;
            }
            #logo {
                color: #cba6f7;
                font-size: 22px;
                font-weight: bold;
                letter-spacing: 2px;
            }
            #subtitle {
                color: #6c7086;
                font-size: 12px;
            }
            #nav_btn {
                background-color: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-weight: 500;
                text-align: left;
            }
            #nav_btn:hover {
                background-color: #45475a;
                color: #cba6f7;
            }
            #nav_btn:pressed {
                background-color: #585b70;
            }
            #clear_btn {
                background-color: transparent;
                color: #f38ba8;
                border: 1px solid #f38ba8;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
            }
            #clear_btn:hover {
                background-color: #f38ba8;
                color: #1e1e2e;
            }
            #main_area {
                background-color: #1e1e2e;
            }
            #header {
                color: #a6adc8;
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            #log_display {
                background-color: #11111b;
                color: #a6e3a1;
                border: 1px solid #313244;
                border-radius: 10px;
                padding: 15px;
                selection-background-color: #cba6f7;
                selection-color: #1e1e2e;
            }
        """)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f'<span style="color:#6c7086;">[{timestamp}]</span> {message}')
        # Авто-скролл вниз
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self):
        self.log_display.clear()
        self.log("Логи очищены.")

    def run_task(self, task_func):
        if self.worker and self.worker.isRunning():
            self.log("⏳ Подождите, предыдущая задача еще выполняется...")
            return

        self.log("Запуск диагностики...")
        
        self.worker = DiagWorker(task_func)
        self.worker.finished.connect(self.on_task_finished)
        self.worker.start()

    def on_task_finished(self, result):
        self.log(result.replace('\n', '<br>'))
        self.log("-" * 50)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Глобальный шрифт
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = AndromedaApp()
    window.show()
    sys.exit(app.exec())