import json
import os.path
import sys
import traceback

from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QPushButton, QLabel, QVBoxLayout, QDialog, QComboBox

from design.peresvet_ui import Ui_Peresvet
from panel.modules_manager import ApachePHP, NginxPHP, PHP, HybridServer

PERESVET_PATH = os.path.dirname(os.path.abspath(sys.argv[0]))

SITES_DIR = os.path.join(PERESVET_PATH, "sites")
USERDATA_DIR = os.path.join(PERESVET_PATH, "userdata")
LOGS_DIR = os.path.join(USERDATA_DIR, "logs")
MODULES_LOGS_DIR = os.path.join(USERDATA_DIR, "modules_logs")
MODULES_DIR = os.path.join(PERESVET_PATH, "bin")

CONFIG_FILE = os.path.join(USERDATA_DIR, "config.json")
NGINX_CONF_FILE = os.path.join(USERDATA_DIR, "nginx.conf")
APACHE_CONF_FILE = os.path.join(USERDATA_DIR, "apache.conf")
HYBRID_APACHE_CONF_FILE = os.path.join(USERDATA_DIR, "apache_hybrid.conf")
HYBRID_NGINX_CONF_FILE = os.path.join(USERDATA_DIR, "nginx_hybrid.conf")

for check_dir in [SITES_DIR, USERDATA_DIR, LOGS_DIR, MODULES_DIR, MODULES_LOGS_DIR]:
    not os.path.exists(check_dir) and os.makedirs(check_dir)

import os


def init_conf_files(self):
    # 1. Базовый конфиг Apache
    apache_config = f"""
        ServerRoot "{self.apache_path}"
        Listen 80
        DocumentRoot "{self.project_path}/sites/localhost"
        <Directory "{self.project_path}/sites/localhost">
            Options Indexes FollowSymLinks
            AllowOverride All
            Require all granted
        </Directory>

        ErrorLog "{self.module_log_dir}/apache_error.log"
        CustomLog "{self.module_log_dir}/apache_access.log" common

        LoadModule authz_core_module {self.authz_core_module}
        LoadModule authz_host_module {self.mod_authz_host}
        LoadModule mime_module {self.mod_mime}
        LoadModule php{self.php_e}_module "{self.apache_dll_path}"
        AddHandler application/x-httpd-php .php
        PHPIniDir "{self.php_path}"
    """

    # 2. Базовый конфиг Nginx
    nginx_config = f"""
        worker_processes  1;
        events {{
            worker_connections  1024;
        }}
        http {{
            include       mime.types;
            default_type  application/octet-stream;
            sendfile        on;
            keepalive_timeout  65;

            error_log  {self.module_log_dir}/nginx_error.log;
            access_log {self.module_log_dir}/nginx_access.log;

            server {{
                listen 80;
                server_name localhost;
                root {self.sites_path}/localhost;
                index index.php index.html;

                error_log  {self.module_log_dir}/nginx_error.log;
                access_log {self.module_log_dir}/nginx_access.log;

                location / {{
                    try_files $uri $uri/ =404;
                }}

                location ~ \\.php$ {{
                    include fastcgi_params;
                    fastcgi_pass 127.0.0.1:9000;
                    fastcgi_index index.php;
                    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
                    fastcgi_param PATH_TRANSLATED $document_root$fastcgi_script_name;
                    fastcgi_param QUERY_STRING $query_string;
                    fastcgi_param REQUEST_METHOD $request_method;
                    fastcgi_param CONTENT_TYPE $content_type;
                    fastcgi_param CONTENT_LENGTH $content_length;
                    fastcgi_param SCRIPT_NAME $fastcgi_script_name;
                    fastcgi_param REQUEST_URI $request_uri;
                    fastcgi_param DOCUMENT_URI $document_uri;
                    fastcgi_param DOCUMENT_ROOT $document_root;
                    fastcgi_param SERVER_PROTOCOL $server_protocol;
                    fastcgi_param REMOTE_ADDR $remote_addr;
                    fastcgi_param REMOTE_PORT $remote_port;
                    fastcgi_param SERVER_ADDR $server_addr;
                    fastcgi_param SERVER_PORT $server_port;
                    fastcgi_param SERVER_NAME $server_name;
                }}
            }}
        }}
    """

    # 3. Гибридный конфиг Apache (слушает на 8080)
    apache_hybrid_config = f"""
        Listen 8080
        <VirtualHost *:8080>
            ServerName site1.su
            DocumentRoot "{self.sites_path}/site1"
            <Directory "{self.sites_path}/site1">
                AllowOverride All
                Require all granted
            </Directory>
        </VirtualHost>

        <VirtualHost *:8080>
            ServerName localhost
            DocumentRoot "{self.sites_path}/site2"
            <Directory "{self.sites_path}/site2">
                AllowOverride All
                Require all granted
            </Directory>
        </VirtualHost>

        ErrorLog "{self.module_log_dir}/apache_error.log"

        LoadModule authz_core_module {self.authz_core_module}
        LoadModule authz_host_module {self.mod_authz_host}
        LoadModule mime_module {self.mod_mime}
        LoadModule php{self.php_e}_module "{self.apache_dll_path}"
        AddHandler application/x-httpd-php .php
        PHPIniDir "{self.php_path}"
    """

    # 4. Гибридный конфиг Nginx (прокси на Apache:8080)
    nginx_hybrid_config = f"""
        worker_processes  1;
        events {{
            worker_connections  1024;
        }}
        http {{
            include       mime.types;
            default_type  application/octet-stream;
            sendfile        on;
            keepalive_timeout  65;

            error_log  {self.module_log_dir}/nginx_error.log;
            access_log {self.module_log_dir}/nginx_access.log;

            server {{
                listen 80;
                server_name site1.su;

                # Реверс-прокси
                location / {{
                    proxy_pass http://127.0.0.1:8080;
                    proxy_set_header Host $host;
                    proxy_set_header X-Real-IP $remote_addr;
                }}
            }}

            server {{
                listen 80;
                server_name site2.ru;

                location / {{
                    proxy_pass http://127.0.0.1:8080;
                    proxy_set_header Host $host;
                    proxy_set_header X-Real-IP $remote_addr;
                }}
            }}
        }}
    """

    # Создаём или перезаписываем эти конфиги в userdata
    with open(APACHE_CONF_FILE, "w", encoding="utf-8") as f:
        f.write(apache_config.strip() + "\n")

    with open(NGINX_CONF_FILE, "w", encoding="utf-8") as f:
        f.write(nginx_config.strip() + "\n")

    with open(HYBRID_APACHE_CONF_FILE, "w", encoding="utf-8") as f:
        f.write(apache_hybrid_config.strip() + "\n")

    with open(HYBRID_NGINX_CONF_FILE, "w", encoding="utf-8") as f:
        f.write(nginx_hybrid_config.strip() + "\n")

    print("Все конфигурационные файлы успешно созданы или обновлены.")


def load_config():
    not os.path.exists(USERDATA_DIR) and os.makedirs(USERDATA_DIR)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as file:
            config_data = {}
            modules = {
                "apache": {"version": None, "is_active": False},
                "nginx": {"version": None, "is_active": False},
                "php": {"version": None, "is_active": False},
                "postgresql": {"version": None, "is_active": False},
                "mysql": {"version": None, "is_active": False},
                "redis": {"version": None, "is_active": False}
            }
            config_data["modules"] = modules
            config_data["run_startup"] = False

            file.write(json.dumps(config_data))
    return json.loads(open(CONFIG_FILE, 'r').read())


def save_config(modules=None, run_startup=None):
    config_data = load_config()
    config_data["modules"] = modules if modules else None
    config_data["run_startup"] = run_startup if run_startup else None
    with open(CONFIG_FILE, 'w') as file:
        file.write(json.dumps(config_data))


class CustomDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Мануал")
        self.setGeometry(100, 100, 300, 150)

        layout = QVBoxLayout()

        self.label = QLabel("Начать мануал?")
        layout.addWidget(self.label)

        # Кнопки
        self.button_yes = QPushButton("Да")
        self.button_no = QPushButton("Нет")

        self.button_yes.clicked.connect(self.on_yes)
        self.button_no.clicked.connect(self.on_no)

        layout.addWidget(self.button_yes)
        layout.addWidget(self.button_no)

        self.setLayout(layout)
        self.center()

    def center(self):
        screen_geometry = QApplication.desktop().availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        window_width = self.width()
        window_height = self.height()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.move(x, y)

    def on_yes(self):
        self.accept()

    def on_no(self):
        self.reject()


class PeresvetPanel(QMainWindow, Ui_Peresvet):
    def __init__(self):
        super().__init__()
        self.hybrid = None
        self.nginx = None
        self.apache = None
        self.setupUi(self)

        self.load_versions()
        self.load_config()
        self.check_server_status()

        self.run_me.clicked.connect(self.run_server)
        self.stop_me.clicked.connect(self.stop_server)

        self.apache_list.currentTextChanged.connect(lambda text: self.update_version("apache", text))
        self.nginx_list.currentTextChanged.connect(lambda text: self.update_version("nginx", text))
        self.php_list.currentTextChanged.connect(lambda text: self.update_version("php", text))
        self.postgresql_list.currentTextChanged.connect(lambda text: self.update_version("postgresql", text))
        self.mysql_list.currentTextChanged.connect(lambda text: self.update_version("mysql", text))
        self.redis_list.currentTextChanged.connect(lambda text: self.update_version("redis", text))

        self.apache_checkbox.stateChanged.connect(
            lambda state: self.update_checkbox("apache", state, [self.apache_list, self.php_list], ["apache", "php"]))
        self.nginx_checkbox.stateChanged.connect(
            lambda state: self.update_checkbox("nginx", state, [self.nginx_list, self.php_list], ["nginx", "php"]))
        self.postgresql_checkbox.stateChanged.connect(
            lambda state: self.update_checkbox("postgresql", state, [self.postgresql_list], ["postgresql"]))
        self.mysql_checkbox.stateChanged.connect(
            lambda state: self.update_checkbox("mysql", state, [self.mysql_list], ["mysql"]))
        self.redis_checkbox.stateChanged.connect(
            lambda state: self.update_checkbox("redis", state, [self.redis_list], ["redis"]))

        pixmap = QPixmap("images/small_icon.ico")
        self.set_pixmaps(pixmap, [self.icon1, self.icon2])

        self.icon1.mousePressEvent = lambda event: self.start_manual()

    def load_versions(self):
        all_modules = {}
        for item in os.listdir(MODULES_DIR):
            item_path = os.path.join(MODULES_DIR, item)
            if os.path.isdir(item_path):
                all_modules[item] = []
        for module in all_modules:
            for item in os.listdir(os.path.join(MODULES_DIR, module)):
                item_path = os.path.join(MODULES_DIR, module, item)
                if os.path.isdir(item_path):
                    all_modules[module].append(item)
        self.open_adminer.setDisabled(True) if "adminer" not in all_modules else None
        self.open_phpmyadmin.setDisabled(True) if "phpmyadmin" not in all_modules else None

        self.apache_checkbox.setDisabled(True) if "apache" not in all_modules else None
        self.nginx_checkbox.setDisabled(True) if "nginx" not in all_modules else None
        self.postgresql_checkbox.setDisabled(True) if "postgresql" not in all_modules else None
        self.mysql_checkbox.setDisabled(True) if "mysql" not in all_modules else None
        self.redis_checkbox.setDisabled(True) if "redis" not in all_modules else None

        self.apache_list.addItems(all_modules["apache"] if "apache" in all_modules else [])
        self.nginx_list.addItems(all_modules["nginx"] if "nginx" in all_modules else [])
        self.php_list.addItems(all_modules["php"] if "php" in all_modules else [])
        self.postgresql_list.addItems(all_modules["postgresql"] if "postgresql" in all_modules else [])
        self.mysql_list.addItems(all_modules["mysql"] if "mysql" in all_modules else [])
        self.redis_list.addItems(all_modules["redis"] if "redis" in all_modules else [])

    def load_config(self):

        config = load_config()
        modules = config["modules"]

        def set_version_for_combobox(modules_, module_name, combo_box):
            version = modules_.get(module_name, {}).get("version", None)
            combo_box.setCurrentText(version if version else "")

        def set_checkbox_state(modules_, module_name, checkbox):
            is_active = modules_.get(module_name, {}).get("is_active", False)
            checkbox.setChecked(is_active)

        set_version_for_combobox(modules, "apache", self.apache_list)
        set_version_for_combobox(modules, "nginx", self.nginx_list)
        set_version_for_combobox(modules, "postgresql", self.postgresql_list)
        set_version_for_combobox(modules, "mysql", self.mysql_list)
        set_version_for_combobox(modules, "redis", self.redis_list)

        set_checkbox_state(modules, "apache", self.apache_checkbox)
        set_checkbox_state(modules, "nginx", self.nginx_checkbox)
        set_checkbox_state(modules, "postgresql", self.postgresql_checkbox)
        set_checkbox_state(modules, "mysql", self.mysql_checkbox)
        set_checkbox_state(modules, "redis", self.redis_checkbox)

    @staticmethod
    def update_version(module_name, text):
        config = load_config()
        modules = config["modules"]
        modules[module_name]["version"] = text
        save_config(modules)

    def update_checkbox(self, module_name, state, combo_boxes: [QComboBox], combo_names: [str]):
        for i, combo_box in enumerate(combo_boxes):
            self.update_version(combo_names[i], combo_box.currentText())
        config = load_config()
        modules = config["modules"]
        modules[module_name]["is_active"] = bool(state)
        save_config(modules)
        self.check_server_status()

    def set_pixmaps(self, pixmap: QPixmap, backgrounds: []):
        [background.setPixmap(pixmap) for background in backgrounds]
        [background.setScaledContents(True) for background in backgrounds]

    def start_manual(self):
        dialog = CustomDialog()
        result = dialog.exec_()
        print(result)

    def check_server_status(self):
        if (self.apache_checkbox.checkState() == Qt.CheckState.Checked and
                self.nginx_checkbox.checkState() == Qt.CheckState.Checked):
            self.server_type.setText("Гибридный режим")
        elif (self.apache_checkbox.checkState() == Qt.CheckState.Unchecked and
              self.nginx_checkbox.checkState() == Qt.CheckState.Checked):
            self.server_type.setText("Nginx активен")
        elif (self.apache_checkbox.checkState() == Qt.CheckState.Checked and
              self.nginx_checkbox.checkState() == Qt.CheckState.Unchecked):
            self.server_type.setText("Apache активен")
        else:
            self.server_type.setText("Веб-сервер отключён")

    def run_server(self):
        config = load_config()
        modules = config["modules"]
        if modules["apache"]["is_active"] and not modules["nginx"]["is_active"] and modules["php"]["version"]:
            apache_path = os.path.join(PERESVET_PATH, "bin", "apache", modules["apache"]["version"], "Apache24")
            php_path = os.path.join(PERESVET_PATH, "bin", "php", modules["php"]["version"])
            self.apache = ApachePHP(apache_path, php_path, PERESVET_PATH)
            try:
                self.apache.run()
            except:
                traceback.print_exc()
        elif not modules["apache"]["is_active"] and modules["nginx"]["is_active"] and modules["php"]["version"]:
            nginx_v = modules["nginx"]["version"]
            nginx_path = os.path.join(PERESVET_PATH, "bin", "nginx", nginx_v, f"nginx-{nginx_v}")
            php_path = os.path.join(PERESVET_PATH, "bin", "php", modules["php"]["version"])
            self.nginx = NginxPHP(nginx_path, php_path, PERESVET_PATH)
            try:
                self.nginx.run()
            except:
                traceback.print_exc()
        elif modules["apache"]["is_active"] and modules["nginx"]["is_active"] and modules["php"]["version"]:
            apache_path = os.path.join(PERESVET_PATH, "bin", "apache", modules["apache"]["version"], "Apache24")
            nginx_v = modules["nginx"]["version"]
            nginx_path = os.path.join(PERESVET_PATH, "bin", "nginx", nginx_v, f"nginx-{nginx_v}")
            php_path = os.path.join(PERESVET_PATH, "bin", "php", modules["php"]["version"])

            self.hybrid = HybridServer(apache_path, nginx_path, php_path, PERESVET_PATH)
            try:
                self.hybrid.run()
            except:
                traceback.print_exc()

    def stop_server(self):
        self.apache.stop() if self.apache else None
        self.nginx.stop() if self.nginx else None
        self.hybrid.stop() if self.hybrid else None
        PHP.stop_php()

    def closeEvent(self, event):
        self.apache.stop() if self.apache else None
        self.nginx.stop() if self.nginx else None
        self.hybrid.stop() if self.hybrid else None
        PHP.stop_php()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = PeresvetPanel()
    window.show()
    sys.exit(app.exec_())
