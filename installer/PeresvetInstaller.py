import shutil
import stat
import os
import json
import traceback

import requests
import zipfile
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QPixmap, QStandardItemModel, QStandardItem, QFont, QFontDatabase
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QApplication, QTreeView, QFileDialog, QLabel

from design.installer_one_ui import Ui_InstallerFirstStep

CONFIG_PATH = "config.json"
VERSIONS_PATH = "versions.json"


def load_versions():
    """Загружаем список доступных версий"""
    with open(VERSIONS_PATH, "r") as f:
        return json.load(f)


def force_remove_readonly(exc):
    func, path, _ = exc
    os.chmod(path, stat.S_IWRITE)  # Разрешаем запись
    func(path)


class InstallThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    completed = pyqtSignal(bool)

    def __init__(self, install_dir, selected_components):
        super().__init__()
        self.stop_flag = False
        self.install_dir = install_dir
        self.selected_components = selected_components

    def run(self):
        try:
            bin_dir = os.path.join(self.install_dir, "bin")
            os.makedirs(bin_dir, exist_ok=True)
            config = {}

            total_versions = sum(len(versions) for versions in self.selected_components.values())
            version_weight = 0
            if total_versions:
                version_weight = 100 / total_versions

            processed_versions = 0

            for component, versions in self.selected_components.items():
                for version in versions:
                    progress_base = int(processed_versions * version_weight)

                    self.status.emit(f"Скачивание {component} {version}...")
                    dest_folder = os.path.join(bin_dir, component, version)
                    os.makedirs(dest_folder, exist_ok=True)
                    if self.stop_flag:  # Проверяем, если остановка
                        self.status.emit("Отмена изменений")
                        self.completed.emit(False)
                        return None
                    zip_path = self.download_file(
                        url=self.selected_components[component][version]["link"],
                        dest_folder=dest_folder,
                        version_weight=version_weight,
                        progress_base=progress_base
                    )
                    if self.stop_flag:  # Проверяем, если остановка
                        self.status.emit("Отмена изменений")
                        self.completed.emit(False)
                        return None
                    self.status.emit(f"Распаковка {component} {version}...")
                    self.extract_zip(zip_path, dest_folder)
                    if self.stop_flag:  # Проверяем, если остановка
                        self.status.emit("Отмена изменений")
                        self.completed.emit(False)
                        return None
                    os.remove(zip_path)

                    config[component] = {
                        "installed_versions": [version],
                        "active_version": version
                    }

                    processed_versions += 1

            # Сохранение итоговой конфигурации (пример)
            # with open("config.json", "w", encoding="utf-8") as f:
            #     json.dump(config, f, indent=4, ensure_ascii=False)

            self.status.emit("Установка завершена!")
            self.progress.emit(100)
            self.completed.emit(True)

        except Exception as e:
            self.status.emit(f"❌ Ошибка: {str(e)}")
            traceback.print_exc()
            self.completed.emit(False)

    def download_file(self, url, dest_folder, version_weight, progress_base):
        """Скачиваем файл и учитываем прогресс в пределах [progress_base .. progress_base + version_weight]"""
        filename = os.path.join(dest_folder, "temp") + "." + url.split(".")[-1]

        try:
            with requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    stream=True,
                    proxies={"http": None, "https": None}
            ) as r:
                r.raise_for_status()
                if self.stop_flag:
                    self.status.emit("Отмена изменений")
                    self.completed.emit(False)
                    return None
                total_size = int(r.headers.get("content-length", 0))
                downloaded_size = 0

                with open(filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8096):
                        if self.stop_flag:
                            self.status.emit("Отмена изменений")
                            self.completed.emit(False)
                            return None
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                            if total_size > 0:
                                file_progress = downloaded_size / total_size
                                total_progress = int(progress_base + file_progress * version_weight)

                                self.progress.emit(total_progress)

            return filename

        except Exception as e:
            self.status.emit(f"Ошибка при загрузке: {str(e)}")
            traceback.print_exc()
            return None

    def extract_zip(self, zip_path, extract_to):
        """Распаковка ZIP-архива"""
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_to)
        except Exception as e:
            self.status.emit(f"Ошибка при распаковке: {str(e)}")
            traceback.print_exc()

    def stop(self):
        self.stop_flag = True


class InstallerApp(QMainWindow, Ui_InstallerFirstStep):
    def __init__(self):
        super().__init__()

        self.setupUi(self)
        self.molodost_font_id = QFontDatabase.addApplicationFont("design/ofont.ru_Molodost.ttf")

        self.versions = load_versions()

        self.install_dir = "C:\\PeresvetPanel"
        self.label_delete_info = None
        self.modules_values = []
        self.child_values = []
        self.load_modules()

        self.modules.clicked.connect(self.on_item_clicked)
        self.view.clicked.connect(self.select_installation_folder)

        self.cancle1.clicked.connect(self.cancel_installation)
        self.cancle2.clicked.connect(self.cancel_installation)
        self.cancle3.clicked.connect(self.cancel_installation)
        self.cancle4.clicked.connect(self.cancel_installation)
        self.cancle5.clicked.connect(self.cancel_installation)
        self.cancle6.clicked.connect(self.cancel_installation)
        self.cancle_installation.clicked.connect(self.cancel_installation_remove)

        self.continue1.clicked.connect(self.next_page)
        self.continue2.clicked.connect(self.next_page)
        self.continue3.clicked.connect(self.next_page)
        self.continue4.clicked.connect(self.next_page)
        self.continue5.clicked.connect(self.next_page)

        self.back1.clicked.connect(self.prev_page)
        self.back2.clicked.connect(self.prev_page)
        self.back3.clicked.connect(self.prev_page)
        self.back4.clicked.connect(self.prev_page)
        self.back5.clicked.connect(self.prev_page)

        self.i_accept.clicked.connect(self.accept_politic)
        self.i_decline.clicked.connect(self.decline_politic)

        self.install.clicked.connect(self.start_installation)

        pixmap = QPixmap("images/background.png")
        self.set_pixmaps(pixmap,
                         [self.background1, self.background2, self.background3, self.background4,
                          self.background5, self.background6, self.background7, self.background8])

        pixmap = QPixmap("images/small_icon.ico")
        self.set_pixmaps(pixmap,
                         [self.icon1, self.icon2, self.icon3, self.icon4, self.icon5, self.icon6,
                          self.icon7, self.icon8])
        self.icon1.mousePressEvent = lambda event: self.on_icon_clicked(
            self.icon1, "Благодарю тя за избрание нашея понели сърверныя.")
        self.icon2.mousePressEvent = lambda event: self.on_icon_clicked(
            self.icon2, "Чти уставы и грамоты, яко закон нерушимый. Примешь ли условие сие, али отступишься?")
        self.icon3.mousePressEvent = lambda event: self.on_icon_clicked(
            self.icon3, "Въ какое место вознамерился ты всадити понель сию?")
        self.icon4.mousePressEvent = lambda event: self.on_icon_clicked(
            self.icon4, "Возжелаешь ли весь наборъ, али лишь избранное? Разсудись добре, да не пожалеешь.")
        self.icon5.mousePressEvent = lambda event: self.on_icon_clicked(
            self.icon5, "Руце твои да утвердятъ путь сей. Не оплошай въ выборе своёмъ!")
        self.icon6.mousePressEvent = lambda event: self.on_icon_clicked(
            self.icon6, "Постави понель на радость сърверному пространству твоего числителя.")
        self.icon7.mousePressEvent = lambda event: self.on_icon_clicked(
            self.icon7, "Делаю устроение, да споспешествует мне благосклонность числителя!")
        self.icon8.mousePressEvent = lambda event: self.on_icon_clicked(
            self.icon8, "Благодарю тя за поставление сие, буду помощником твоим в палате серверной.")

    def on_icon_clicked(self, label, text):
        """Создаёт или удаляет QLabel с текстом при клике по иконке"""
        if hasattr(label, "info_label") and label.info_label is not None:
            label.info_label.deleteLater()
            label.info_label = None
        else:
            label.info_label = QLabel(text, self)
            label.info_label.setStyleSheet("background-color: rgba(30, 30, 30, 255); color: white; padding: 10px;"
                                           "border-radius: 10px; border-width: 2px; "
                                           "border-color: rgba(10, 10, 10, 200); border-style: solid;")

            font_family = QFontDatabase.applicationFontFamilies(self.molodost_font_id)[0]

            label.info_label.setFont(QFont(font_family, 10))

            label.info_label.adjustSize()
            pos = label.mapToParent(label.rect().bottomRight())

            position_x = -80 - label.info_label.sizeHint().width()
            position_y = -100
            if pos.x() < 350:
                position_x = -10
            if pos.y() < 250:
                position_y = -100
            label.info_label.move(pos.x() + position_x, pos.y() + position_y)
            label.info_label.show()
            self.label_delete_info = label

    def set_pixmaps(self, pixmap: QPixmap, backgrounds: []):
        [background.setPixmap(pixmap) for background in backgrounds]
        [background.setScaledContents(True) for background in backgrounds]

    def decline_politic(self):
        self.continue2.setDisabled(True)

    def accept_politic(self):
        self.continue2.setDisabled(False)

    def next_page(self):
        if hasattr(self.label_delete_info, "info_label") and self.label_delete_info.info_label is not None:
            self.label_delete_info.info_label.deleteLater()
            self.label_delete_info.info_label = None
        current_index = self.switcher.currentIndex()
        self.switcher.setCurrentIndex(current_index + 1)

    def prev_page(self):
        if hasattr(self.label_delete_info, "info_label") and self.label_delete_info.info_label is not None:
            self.label_delete_info.info_label.deleteLater()
            self.label_delete_info.info_label = None
        current_index = self.switcher.currentIndex()
        self.switcher.setCurrentIndex(current_index - 1)

    def cancel_installation(self):
        sys.exit(app.exec_())

    def cancel_installation_remove(self):
        if hasattr(self, "install_thread") and self.install_thread.isRunning():
            self.install_thread.stop()
            self.status_label.setText("Установка остановлена!")
        if os.path.exists(self.install_dir):
            shutil.rmtree(self.install_dir, onexc=force_remove_readonly)

        sys.exit(app.exec_())

    def start_installation(self):
        if hasattr(self.label_delete_info, "info_label") and self.label_delete_info.info_label is not None:
            self.label_delete_info.info_label.deleteLater()
            self.label_delete_info.info_label = None
        current_index = self.switcher.currentIndex()
        self.switcher.setCurrentIndex(current_index + 1)

        selected_components = {}
        all_versions = load_versions()
        for module_row in range(self.model.rowCount()):
            parent = self.model.item(module_row, 0)
            module_name = parent.text()
            for row in range(parent.rowCount()):
                child = parent.child(row, 0)
                if child.checkState() == Qt.CheckState.Checked:
                    if module_name not in selected_components:
                        selected_components[module_name] = {}
                    selected_components[module_name][child.text()] = {
                        "link": all_versions[module_name][child.text()]["link"]}

        self.install_thread = InstallThread(self.install_dir, selected_components)
        self.install_thread.progress.connect(self.update_progress)
        self.install_thread.status.connect(self.update_status)
        self.install_thread.completed.connect(self.installation_finished)
        self.install_thread.start()

    def update_progress(self, percent):
        """Обновляет прогресс-бар"""
        self.progress_install.setValue(percent)

    def update_status(self, status_text):
        """Обновляет текст статуса"""
        self.status_label.setText(status_text)

    def installation_finished(self, success):
        """Сообщает о завершении"""
        if success:
            if hasattr(self.label_delete_info, "info_label") and self.label_delete_info.info_label is not None:
                self.label_delete_info.info_label.deleteLater()
                self.label_delete_info.info_label = None
            current_index = self.switcher.currentIndex()
            self.switcher.setCurrentIndex(current_index + 1)
        else:
            QMessageBox.warning(self, "Ошибка", "Что-то пошло не так!")

    def select_installation_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Выберите папку установки")
        if folder_path:
            full_path = os.path.normpath(os.path.join(folder_path, "PeresvetPanel"))
            self.install_dir = full_path
            self.project_path.setText(full_path)

    def load_modules(self):
        """Загружает данные из versions.json в QTreeView"""
        with open(VERSIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Именование", "Весище"])

        for module_name, versions in data.items():
            module_item = QStandardItem(module_name)
            module_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            module_item.setCheckState(Qt.CheckState.Unchecked)

            for version, info in versions.items():
                size_mb = info.get("size", 0) / (1024 * 1024)
                size_str = f"{size_mb:.2f} MB" if size_mb > 0 else "Не указано"

                version_item = QStandardItem(version)
                size_item = QStandardItem(size_str)

                version_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                version_item.setCheckState(Qt.CheckState.Unchecked)

                size_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemNeverHasChildren)
                size_item.setTextAlignment(Qt.AlignRight)

                module_item.appendRow([version_item, size_item])
            zero_module = QStandardItem()
            zero_module.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemNeverHasChildren)
            self.model.appendRow([module_item, zero_module])

        self.modules.setModel(self.model)
        self.modules.expandAll()
        self.modules.setColumnWidth(0, 450)
        self.modules.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Interactive)

        root = self.model.invisibleRootItem()
        items = [root.child(row, 0) for row in range(root.rowCount())]

        self.modules_values = [0 for _ in range(self.model.rowCount())]
        self.child_values = [[0 for _ in range(parent.rowCount())] for parent in items]

    def update_total_size(self):
        total_size = 0

        for row in range(self.model.rowCount()):
            module_item = self.model.item(row, 0)
            for version_row in range(module_item.rowCount()):
                version_item = module_item.child(version_row, 0)
                size_item = module_item.child(version_row, 1)

                if version_item.checkState() == Qt.CheckState.Checked:
                    try:
                        size_str = size_item.text().split()[0]
                        size_mb = float(size_str)
                        total_size += size_mb
                    except ValueError:
                        pass
        self.label.setText(f"Вес кладовых файлов: {total_size:.2f} MB")

    def on_item_clicked(self, index):
        """Обрабатывает клики по элементу QTreeView"""

        if index.column() == 1:
            index = index.siblingAtColumn(0)

        item = self.model.itemFromIndex(index)
        if not item or not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        item_row = index.row()

        parent_item = item.parent()

        if parent_item:
            parent_row = parent_item.row()
            new_state = Qt.CheckState.Unchecked if self.child_values[parent_row][item_row] else Qt.CheckState.Checked
            self.child_values[parent_row][item_row] = (self.child_values[parent_row][item_row] + 1) % 2
            self.update_parent_checkbox(item)
        else:
            new_state = Qt.CheckState.Unchecked if self.modules_values[item_row] else Qt.CheckState.Checked
            self.modules_values[item_row] = (self.modules_values[item_row] + 1) % 2
            self.update_children_checkboxes(item, new_state, item_row)

        item.setCheckState(new_state)

        self.update_total_size()

    def update_children_checkboxes(self, item, state, parent_row):
        for row in range(item.rowCount()):
            child = item.child(row)
            if child:
                child.setCheckState(state)
                child_row = child.row()
                if Qt.CheckState.PartiallyChecked != state:
                    self.child_values[parent_row][child_row] = 1 if state == Qt.CheckState.Checked else 0

    def update_parent_checkbox(self, item):
        parent = item.parent()
        parent_row = parent.index().row()

        if not parent:
            return
        checked_count = sum(self.child_values[parent_row])
        unchecked_count = len(self.child_values[parent_row]) - checked_count
        if checked_count == parent.rowCount():
            parent.setCheckState(Qt.CheckState.Checked)
            self.modules_values[parent_row] = 1
        elif unchecked_count == parent.rowCount():
            parent.setCheckState(Qt.CheckState.Unchecked)
            self.modules_values[parent_row] = 0
        else:
            parent.setCheckState(Qt.CheckState.PartiallyChecked)
            self.modules_values[parent_row] = 0


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = InstallerApp()
    window.show()
    sys.exit(app.exec_())
