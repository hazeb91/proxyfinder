"""ProxyFinder GUI
"""

import os.path
import sys
import time

from PyQt5.QtWidgets import (QApplication, QMainWindow, QLineEdit, QGridLayout,
    QWidget, QPushButton, QProgressBar, QAction, QStatusBar, QLabel, QMenu,
    QHBoxLayout, QSpinBox, QDoubleSpinBox, QMessageBox, QComboBox, QTreeWidget,
    QTreeWidgetItem, QAbstractItemView, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRegExp, QSettings, QSize
from PyQt5.QtGui import QRegExpValidator, QIcon

from .. import proxyfinder
from .. import __version__
from .. import __author__
from .. import __email__

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "user_settings.ini")
IMAGES_PATH = os.path.join(os.path.dirname(__file__), "images")


def _image(filename):
    return os.path.join(IMAGES_PATH, filename)


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
            # -1 to not reach 100% while process is not finished
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

    settings = QSettings(CONFIG_PATH, QSettings.IniFormat)

    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        """PyQt init
        """
        self.setMinimumSize(QSize(600, 400))
        self.resize(800, 500)
        self.setWindowTitle("Proxy Finder")
        self.setWindowIcon(QIcon(_image("icon.png")))

        self.createMenu()
        self.setupWidgets()
        self.loadSettings()

    def createMenu(self):
        """Create the menu bar and actions.
        """
        # Create actions
        exit_act = QAction("Esci", self)
        exit_act.setStatusTip("Esci dal programma")
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)

        restore_settings_act = QAction("Ripristina impostazioni", self)
        restore_settings_act.setStatusTip("Ripristina le impostazioni a quelle predefinite")
        restore_settings_act.triggered.connect(self.restoreSettings)

        about_act = QAction("A proposito di ProxyFinder", self)
        about_act.triggered.connect(self.aboutDialog)

        # Create menubar
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)

        # Create menu in menubar
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(exit_act)

        settings_menu = menu_bar.addMenu("Impostazioni")
        settings_menu.addAction(restore_settings_act)

        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction(about_act)

        # Create statusbar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

    def treeContextMenu(self, position):
        """Context menu for the tree widget output
        """
        # Actions
        select_all = QAction("Seleziona tutto")
        select_all.triggered.connect(self.onSelectAll)
        if self.tree_widget_out.topLevelItemCount() == 0:
            select_all.setDisabled(True)

        copy_all = QAction("Copia tutto")
        copy_all.triggered.connect(self.copyAllToClipboard)
        if self.tree_widget_out.topLevelItemCount() == 0:
            copy_all.setDisabled(True)

        copy_selected = QAction("Copia selezionati")
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
        url_label = QLabel("Url:")

        le = QLineEdit()
        le.setPlaceholderText("Es.: http://www.easybytez.com")
        self.url_input_cb = QComboBox()
        self.url_input_cb.setLineEdit(le)
        reg_ex = QRegExp(r"^https?://([a-z0-9]{2,256}\.)?[a-z0-9]{2,256}\.[a-z]{2,6}$")
        self.url_input_cb.setValidator(QRegExpValidator(reg_ex, self.url_input_cb))
        self.url_input_cb.setEditText("")
        self.url_input_cb.setStatusTip("Sito web su cui verificare i proxy")

        # Tree Widget output
        self.tree_widget_out = QTreeWidget()
        self.tree_widget_out.setHeaderLabels(["#", "IP", "Porta", "Protocollo", "Errore", "Stato"])
        self.tree_widget_out.setAlternatingRowColors(True)
        self.tree_widget_out.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree_widget_out.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget_out.customContextMenuRequested.connect(self.treeContextMenu)

        # Tree Widget icons
        self.fail_icon = QIcon(_image("fail.png"))
        self.succ_icon = QIcon(_image("success.png"))

        # Max proxies, threads and connections timeout
        proxies_max_label = QLabel("Proxy Max.")
        self.proxies_max_sb = QSpinBox()
        self.proxies_max_sb.setRange(0, 100000)
        self.proxies_max_sb.setSingleStep(500)
        self.proxies_max_sb.setStatusTip("Numero di proxy da scansionare "
                                         "(0 = tutti)")

        threads_max_label = QLabel("Threads Max.")
        self.threads_max_sb = QSpinBox()
        self.threads_max_sb.setRange(1, 100)
        self.threads_max_sb.setStatusTip("Numero di connessioni possibili "
                                         "allo stesso tempo (Raccomandato: 20)")

        timeout_max_label = QLabel("Conn. Timeout Max.")
        self.timeout_max_sb = QDoubleSpinBox()
        self.timeout_max_sb.setRange(0, 30)
        self.timeout_max_sb.setSingleStep(0.5)
        self.timeout_max_sb.setSuffix("s")
        self.timeout_max_sb.setStatusTip("Tempo massimo per ogni connessione "
                                         "(Raccomandato: 3.05)")

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
        self.start_button = QPushButton("Avvia")
        self.start_button.clicked.connect(self.startScan)

        self.stop_button = QPushButton("Annulla")
        self.stop_button.setDisabled(True)
        self.stop_button.clicked.connect(self.stopScan)

        copy_all_button = QPushButton("Copia tutto")
        copy_all_button.clicked.connect(self.copyAllToClipboard)

        copy_sel_button = QPushButton("Copia selezionati")
        copy_sel_button.clicked.connect(self.copySelectionToClipboard)

        # Show only working checkbox
        self.only_working_cb = QCheckBox("Mostra solo funzionanti")
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
            QMessageBox.critical(self, "Specificare URL",
                "Per avviare la scansione è necessario inserire un URL valido.")
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

        # start worker
        self.worker.start()

    def stopScan(self):
        """Stop scan process
        """
        message = QMessageBox.question(self, "Ferma scansione",
            "Sei sicuro di voler fermare la scansione?",
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
            self.status_bar.showMessage("Tutti i proxy selezionati sono " \
                                        "stati copiati negli appunti")

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
            self.status_bar.showMessage("Tutti i proxy sono stati copiati " \
                                        "negli appunti")

    def aboutDialog(self):
        """Show simple about dialog
        """
        QMessageBox.about(self, "A proposito di ProxyFinder",
            f"ProxyFinder v{__version__}\n\n"
            f"Autore: {__author__}\n"
            f"e-mail: {__email__}")

    def saveSettings(self):
        """Save current widgets value
        """
        self.settings.setValue("MainWindow/geometry", self.saveGeometry())
        self.settings.setValue("max_proxies", self.proxies_max_sb.value())
        self.settings.setValue("max_threads", self.threads_max_sb.value())
        self.settings.setValue("conn_timeout", self.timeout_max_sb.value())
        self.settings.setValue("only_working_cb", self.only_working_cb.isChecked())
        self.settings.setValue("url_input_combo",
            [self.url_input_cb.itemText(i) for i in range(self.url_input_cb.count())])

    def loadSettings(self):
        """Load saved widgets value
        """
        if self.settings.value("MainWindow/geometry"):
            self.restoreGeometry(self.settings.value("MainWindow/geometry"))

        self.proxies_max_sb.setValue(
            self.settings.value("max_proxies", 0, type=int))
        self.threads_max_sb.setValue(
            self.settings.value("max_threads", 20, type=int))
        self.timeout_max_sb.setValue(
            self.settings.value("conn_timeout", 3.05, type=float))
        self.url_input_cb.addItems(
            self.settings.value("url_input_combo", [], type=list))
        self.only_working_cb.setChecked(
            self.settings.value("only_working_cb", False, type=bool))

    def restoreSettings(self):
        """Restore default settings
        """
        message = QMessageBox.question(self, "Ripristina imporstazioni",
            "Sei sicuro di voler ripristinare le impostazioni a quelle iniziali?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if message == QMessageBox.Yes:
            self.proxies_max_sb.setValue(0)
            self.threads_max_sb.setValue(20)
            self.timeout_max_sb.setValue(3.05)

    def closeEvent(self, event):
        """Things to do when user close the application
        """
        message = QMessageBox.question(self, "Uscire da ProxyFinder",
            "Sei sicuro di voler uscrire da ProxyFinder?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if message == QMessageBox.Yes:
            self.saveSettings()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    window = ProxyFinderGUI()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
