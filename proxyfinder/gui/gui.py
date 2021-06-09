"""ProxyFinder GUI
"""

import sys
import time

from PyQt5.QtWidgets import (QApplication, QMainWindow, QLineEdit, QGridLayout,
    QWidget, QPushButton, QProgressBar, QAction, QStatusBar, QLabel, QMenu,
    QHBoxLayout, QSpinBox, QDoubleSpinBox, QMessageBox, QComboBox, QTreeWidget,
    QTreeWidgetItem, QAbstractItemView, QCheckBox, QActionGroup)
from PyQt5.QtCore import (Qt, QThread, pyqtSignal, QRegExp, QSettings, QSize,
    QTranslator, QCoreApplication, QLocale, QLibraryInfo)
from PyQt5.QtGui import QRegExpValidator, QIcon

from .. import __version__
from .. import __author__
from .. import __email__
from .. import proxyfinder
from . import utils


settings = QSettings(utils.CONFIG_PATH, QSettings.IniFormat)


class Worker(QThread):
    """Main task
    """
    updateValueSignal = pyqtSignal(int)
    updateOutputSignal = pyqtSignal(list)
    updateTimeLeftSignal = pyqtSignal(str)
    onFinishSignal = pyqtSignal()

    def __init__(self, url, max_proxies, max_threads, timeout):
        super().__init__()
        self.pf = proxyfinder.ProxyFinder(url, max_proxies, max_threads, timeout)
        self._kill = False

    def stop(self):
        """Stop thread
        """
        self._kill = True

    def run(self):
        """Thread's start point
        """
        self.pf.start()
        while not self.pf.is_finished() or not self.pf.result_queue.empty():
            if self._kill:
                break
            progress = len(self.pf.proxy_found) - self.pf.get_proxies_left()

            self.updateOutputSignal.emit(self.pf.get_last_results())
            self.updateTimeLeftSignal.emit(self.pf.get_estimated_time())
            # -1 to reach up to 99% while process is not finished
            self.updateValueSignal.emit(progress - 1)
            time.sleep(0.2)
        if not self._kill:
            self.updateValueSignal.emit(len(self.pf.proxy_found))
        self.onFinishSignal.emit()
        self.pf.stop()


class ProxyFinderGUI(QMainWindow):
    """ProxyFinder GUI Class
    """

    # pylint: disable=invalid-name
    # pylint: disable=attribute-defined-outside-init

    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        """PyQt init
        """
        self.setMinimumSize(QSize(600, 400))
        self.resize(800, 500)
        self.setWindowTitle("ProxyFinder")
        self.setWindowIcon(QIcon(utils.image("icon.png")))

        self.createMenuBar()
        self.setupWidgets()
        self.loadSettings()

        self.show()

    def tr(self, message):
        """Text translation

        Args:
            message (str): Text to translate

        Returns:
            QString: Translated string
        """
        return QCoreApplication.translate("ProxyFinderGUI", message)

    def createMenuBar(self):
        """Create the menu bar and actions.
        """
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)

        # File actions
        exit_act = QAction(self.tr("Exit"), self)
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)

        # Settings actions
        restore_settings_act = QAction(self.tr("Restore default settings"), self)
        restore_settings_act.triggered.connect(self.restoreSettings)

        # Language actions
        lang_group_acts = QActionGroup(self)
        for loc, name in utils.LANGUAGES.items():
            lang_act = QAction(name, self)
            lang_act.setCheckable(True)
            lang_act.triggered.connect(lambda x, y=loc: self.onChangeLanguage(y))
            if loc == QLocale().name():
                lang_act.setChecked(True)
            lang_group_acts.addAction(lang_act)

        # Help actions
        about_act = QAction(self.tr("About ProxyFinder"), self)
        about_act.triggered.connect(self.aboutDialog)

        # Create menu in menubar
        file_menu = menu_bar.addMenu(self.tr("File"))
        file_menu.addAction(exit_act)

        settings_menu = menu_bar.addMenu(self.tr("Settings"))
        language_menu = settings_menu.addMenu(self.tr("Language"))
        language_menu.addActions(lang_group_acts.actions())
        settings_menu.addAction(restore_settings_act)

        help_menu = menu_bar.addMenu(self.tr("Help"))
        help_menu.addAction(about_act)

        # Create statusbar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

    def treeContextMenu(self, position):
        """Context menu for the tree widget output
        """
        # Actions
        select_all = QAction(self.tr("Select all"))
        select_all.triggered.connect(self.onSelectAll)
        if self.tree_widget_out.topLevelItemCount() == 0:
            select_all.setDisabled(True)

        copy_all = QAction(self.tr("Copy all"))
        copy_all.triggered.connect(self.copyAllToClipboard)
        if self.tree_widget_out.topLevelItemCount() == 0:
            copy_all.setDisabled(True)

        copy_selected = QAction(self.tr("Copy selected"))
        copy_selected.triggered.connect(self.copySelectionToClipboard)
        if not self.tree_widget_out.selectedItems():
            copy_selected.setDisabled(True)

        # Create menu
        context_menu = QMenu(self)

        context_menu.addAction(select_all)
        context_menu.addSeparator()
        context_menu.addAction(copy_selected)
        context_menu.addAction(copy_all)

        # show menu at position
        context_menu.exec_(self.tree_widget_out.viewport().mapToGlobal(position))

    def setupWidgets(self):
        """Set up widgets.
        """
        # Url input
        url_label = QLabel("URL:")

        le = QLineEdit()
        le.setPlaceholderText("Es.: http://www.easybytez.com")
        self.url_input_cb = QComboBox()
        self.url_input_cb.setLineEdit(le)
        reg_ex = QRegExp(r"^https?://([a-z0-9]{2,256}\.)?[a-z0-9]{2,256}\.[a-z]{2,6}$")
        self.url_input_cb.setValidator(QRegExpValidator(reg_ex, self.url_input_cb))
        self.url_input_cb.setEditText("")
        self.url_input_cb.setStatusTip(self.tr("Website to verify proxies"))

        # Tree Widget output
        self.tree_widget_out = QTreeWidget()
        self.tree_widget_out.setHeaderLabels(["#", "IP", self.tr("Port"),
            self.tr("Protocol"), self.tr("Error"), self.tr("State")])
        self.tree_widget_out.setAlternatingRowColors(True)
        self.tree_widget_out.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree_widget_out.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget_out.customContextMenuRequested.connect(self.treeContextMenu)

        # Tree Widget icons
        self.fail_icon = QIcon(utils.image("fail.png"))
        self.succ_icon = QIcon(utils.image("success.png"))

        # Max proxies, threads and connections timeout
        proxies_max_label = QLabel(self.tr("Max proxies"))
        self.proxies_max_sb = QSpinBox()
        self.proxies_max_sb.setRange(0, 100000)
        self.proxies_max_sb.setSingleStep(500)
        self.proxies_max_sb.setStatusTip(self.tr("Maximum number of proxies to "
            "scan. [0 = No limit]"))

        threads_max_label = QLabel(self.tr("Max threads"))
        self.threads_max_sb = QSpinBox()
        self.threads_max_sb.setRange(1, 100)
        self.threads_max_sb.setStatusTip(self.tr("Maximum number of connections "
            "at the same time. [Recommended = 20]"))

        timeout_max_label = QLabel(self.tr("Connection timeout"))
        self.timeout_max_sb = QDoubleSpinBox()
        self.timeout_max_sb.setRange(0, 30)
        self.timeout_max_sb.setSingleStep(0.5)
        self.timeout_max_sb.setSuffix("s")
        self.timeout_max_sb.setStatusTip(self.tr("Maximum time to wait to "
            "establish a connection. [Recommended = 3.05]"))

        max_h_box = QHBoxLayout()
        max_h_box.addWidget(proxies_max_label)
        max_h_box.addWidget(self.proxies_max_sb)
        max_h_box.addStretch()
        max_h_box.addWidget(threads_max_label)
        max_h_box.addWidget(self.threads_max_sb)
        max_h_box.addStretch()
        max_h_box.addWidget(timeout_max_label)
        max_h_box.addWidget(self.timeout_max_sb)

        # Buttons
        self.start_button = QPushButton(self.tr("Start"))
        self.start_button.clicked.connect(self.startScan)

        self.stop_button = QPushButton(self.tr("Cancel"))
        self.stop_button.setDisabled(True)
        self.stop_button.clicked.connect(self.stopScan)

        copy_all_button = QPushButton(self.tr("Copy all"))
        copy_all_button.clicked.connect(self.copyAllToClipboard)

        copy_sel_button = QPushButton(self.tr("Copy selected"))
        copy_sel_button.clicked.connect(self.copySelectionToClipboard)

        # Show only working checkbox
        self.only_working_cb = QCheckBox(self.tr("Show only\nworking proxies"))
        self.only_working_cb.stateChanged.connect(self.onOnlyWorking)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)

        self.time_left_label = QLabel()
        self.time_left_label.setText("00:00:00")

        # Widgets layout
        grid = QGridLayout()
        grid.addWidget(url_label, 0, 0)
        grid.addWidget(self.url_input_cb, 0, 1)
        grid.addWidget(self.start_button, 0, 2)
        grid.addLayout(max_h_box, 1, 1, Qt.AlignCenter)
        grid.addWidget(self.stop_button, 1, 2)
        grid.addWidget(self.tree_widget_out, 2, 0, 4, 2)
        grid.addWidget(copy_all_button, 2, 2)
        grid.addWidget(copy_sel_button, 3, 2)
        grid.addWidget(self.only_working_cb, 4, 2)
        grid.addWidget(self.progress_bar, 6, 0, 1, 2)
        grid.addWidget(self.time_left_label, 6, 2, Qt.AlignCenter)

        central_widget = QWidget()
        central_widget.setLayout(grid)

        self.setCentralWidget(central_widget)

    def addUrlToInput(self, text):
        """Check if the text is already in input combobox, then add it

        Args:
            text (str): Valid url
        """
        items = [self.url_input_cb.itemText(i) for i in range(self.url_input_cb.count())]
        if not text in items:
            self.url_input_cb.addItem(text)

    def startScan(self):
        """Start scan process
        """
        # check url input
        if not self.url_input_cb.currentText():
            QMessageBox.critical(self, self.tr("Enter a valid URL"),
                self.tr("A valid URL must be entered to start the scan."))
            return
        self.addUrlToInput(self.url_input_cb.currentText())

        # Initialize worker
        self.worker = Worker(url=self.url_input_cb.currentText(),
                             max_proxies=self.proxies_max_sb.value(),
                             max_threads=self.threads_max_sb.value(),
                             timeout=self.timeout_max_sb.value())
        self.worker.updateValueSignal.connect(self.updateProgressBar)
        self.worker.updateOutputSignal.connect(self.updateOutputTree)
        self.worker.updateTimeLeftSignal.connect(self.updateTimeLeft)
        self.worker.onFinishSignal.connect(self.onFinishedProcess)

        # Initialize values
        self.tree_widget_out.clear()
        self.progress_bar.setRange(0, len(self.worker.pf.get_proxies()))
        self.progress_bar.setValue(0)
        self.stop_button.setDisabled(False)
        self.start_button.setDisabled(True)

        # start scan
        self.worker.start()

    def stopScan(self):
        """Stop scan process
        """
        message = QMessageBox.question(self, self.tr("Stop the scan"),
            self.tr("Are you sure you want to stop the scan?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if message == QMessageBox.Yes:
            self.worker.stop()
            self.progress_bar.setValue(0)
            self.time_left_label.setText("00:00:00")

    def updateProgressBar(self, value):
        """Update progress bar value

        Args:
            value (int): Progress bar value
        """
        self.progress_bar.setValue(value)

    def updateOutputTree(self, last_results):
        """Update TreeWidget output

        Args:
            last_results (list): List of dictionary results.
                                 Keys: ip, port, protocol, error
        """
        row = self.tree_widget_out.topLevelItemCount()
        for i, res in enumerate(last_results, 1):
            item = QTreeWidgetItem()
            item.setText(0, str(row + i))
            item.setText(1, res["ip"])
            item.setText(2, str(res["port"]))
            item.setText(3, res["protocol"])
            item.setText(4, res["error"])
            # item.setText(5, "Fallito" if res["error"] else "Ok")
            item.setIcon(5, self.fail_icon if res["error"] else self.succ_icon)
            self.tree_widget_out.addTopLevelItem(item)
            if self.only_working_cb.isChecked() and res["error"]:
                item.setHidden(True)

    def updateTimeLeft(self, time_left):
        """Update time left

        Args:
            time_left (str): Time left (hh:mm:ss)
        """
        self.time_left_label.setText(time_left)

    def onFinishedProcess(self):
        """When the process is finished, restore disabled buttons and
        copy results to the clipboard
        """
        # Restor button status
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)

        # Copy all found proxies to clipboard
        self.copyAllToClipboard()

    def onOnlyWorking(self, checked):
        """Show only working proxies in tree widget output

        Args:
            checked (bool): checkbox state
        """
        rows = self.tree_widget_out.topLevelItemCount()
        for row in range(rows):
            item = self.tree_widget_out.topLevelItem(row)
            if checked and item.text(4):
                item.setHidden(True)
            else:
                item.setHidden(False)

    def onSelectAll(self):
        """Select all visible rows in tree widget output
        """
        self.tree_widget_out.selectAll()

    def onChangeLanguage(self, locale):
        """Change localeuage

        Args:
            locale (str): Locale name
        """
        QLocale.setDefault(QLocale(locale))
        QMessageBox.information(self, self.tr("Relaunch required"),
            self.tr("You have to quit and relaunch ProxyFinder "
                    "for this change to take effect."))

    def copySelectionToClipboard(self):
        """Copy selected rows in tree widget to the clipboard
        """
        item_list = []
        selection = self.tree_widget_out.selectedItems()
        cols = self.tree_widget_out.columnCount()
        for row in selection:
            data = [row.text(c) for c in range(cols)]
            text_line = "{3}://{1}:{2}".format(*data)
            item_list.append(text_line)

        text = "\n".join(item_list)
        if text:
            QApplication.clipboard().setText(text)
            self.status_bar.showMessage(self.tr("The selected proxies have been "
                "copied to the clipboard."))

    def copyAllToClipboard(self):
        """Copy all rows in tree widget to the clipboard
        """
        item_list = []
        rows = self.tree_widget_out.topLevelItemCount()
        cols = self.tree_widget_out.columnCount()
        for row in range(rows):
            item = self.tree_widget_out.topLevelItem(row)
            if item.isHidden():
                continue
            data = [item.text(c) for c in range(cols)]
            text_line = "{3}://{1}:{2}".format(*data)
            item_list.append(text_line)

        text = "\n".join(item_list)
        if text:
            QApplication.clipboard().setText(text)
            self.status_bar.showMessage(self.tr("All proxies have been copied "
                "to the clipboard."))

    def aboutDialog(self):
        """Show simple about dialog
        """
        QMessageBox.about(self, self.tr("About ProxyFinder"),
            f"ProxyFinder v{__version__}\n\n"
            f"Author: {__author__}\n"
            f"e-mail: {__email__}")

    def saveSettings(self):
        """Save current widgets value
        """
        settings.setValue("MainWindow/geometry", self.saveGeometry())
        settings.setValue("MainWindow/locale", QLocale().name())
        settings.setValue("max_proxies", self.proxies_max_sb.value())
        settings.setValue("max_threads", self.threads_max_sb.value())
        settings.setValue("conn_timeout", self.timeout_max_sb.value())
        settings.setValue("only_working_cb", self.only_working_cb.isChecked())
        settings.setValue("url_input_combo",
            [self.url_input_cb.itemText(i) for i in range(self.url_input_cb.count())])

    def loadSettings(self):
        """Load saved widgets value
        """
        if settings.value("MainWindow/geometry"):
            self.restoreGeometry(settings.value("MainWindow/geometry"))

        self.proxies_max_sb.setValue(
            settings.value("max_proxies", 0, type=int))
        self.threads_max_sb.setValue(
            settings.value("max_threads", 20, type=int))
        self.timeout_max_sb.setValue(
            settings.value("conn_timeout", 3.05, type=float))
        self.url_input_cb.addItems(
            settings.value("url_input_combo", [], type=list))
        self.only_working_cb.setChecked(
            settings.value("only_working_cb", False, type=bool))

    def restoreSettings(self):
        """Restore default settings
        """
        message = QMessageBox.question(self, "Ripristina imporstazioni",
            "Sei sicuro di voler ripristinare le impostazioni a quelle iniziali?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if message == QMessageBox.Yes:
            settings.clear()
            self.loadSettings()

    def closeEvent(self, event):
        """Things to do when user close the application
        """
        message = QMessageBox.question(self, self.tr("Quit application"),
            self.tr("Are you sure you want to Quit?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if message == QMessageBox.Yes:
            self.saveSettings()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)

    # translate app
    locale = QLocale().system()
    if settings.value("MainWindow/locale"):
        locale = QLocale(settings.value("MainWindow/locale", type=str))

    app_translator = QTranslator()
    if app_translator.load(locale, "proxyfinder", ".", utils.LOCALE_PATH, ".qm"):
        app.installTranslator(app_translator)

    base_translator = QTranslator()
    if base_translator.load(locale, "qtbase", "_",
        QLibraryInfo.location(QLibraryInfo.TranslationsPath), ".qm"):
        app.installTranslator(base_translator)

    # Set default locale
    QLocale.setDefault(locale)

    window = ProxyFinderGUI()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
