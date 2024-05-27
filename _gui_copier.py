import os.path
import shutil
import sys
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QApplication, QToolBar, QAction, QWidget, QVBoxLayout, QLabel, QLineEdit, \
    QHBoxLayout, QPushButton, QFileDialog, QPlainTextEdit, QProgressBar


class PickFolder(QWidget):
    picked_a_folder = pyqtSignal(str)

    def __init__(self, parent, caption: str, *args, **kwargs):
        # Call parent constructor
        super(PickFolder, self).__init__(parent, *args, **kwargs)

        # Create utils variables
        self._folder = None
        self._caption = caption

        # Create the widget layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Add a label
        folder_label = QLabel(caption)
        layout.addWidget(folder_label)

        # Create a horizontal layout
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_input = QLineEdit()
        folder_button = QPushButton("...")
        folder_button.setFixedWidth(30)

        # Connect line edit and button
        self._folder_input.textChanged.connect(self._get_folder)
        folder_button.clicked.connect(self._get_folder)

        h_layout.addWidget(self._folder_input)
        h_layout.addWidget(folder_button)
        layout.addLayout(h_layout)
        self.setLayout(layout)

    def _get_folder(self, value=None):
        # Get folder
        if value:
            self._folder = value if os.path.exists(value) and os.path.isdir(value) else None
        else:
            self._folder = QFileDialog.getExistingDirectory(self, self._caption)
            self._folder = self._folder if os.path.exists(self._folder) else None
            self._folder_input.setText(self._folder or "")

        # Emit a signal
        self.picked_a_folder.emit(self._folder or "")

    def folder(self):
        return self._folder


# Create a PyqtSignals
class _CopyerSignals(QObject):
    copied = pyqtSignal(str)
    moved = pyqtSignal(str)
    progress = pyqtSignal(int)


# Create a QRunnable to launch files copying and moving
class _CopyerWorker(QRunnable):

    def __init__(self, files: list, source: str, destination: str, bool_copy: bool = True):
        # Call super constructor
        super(_CopyerWorker, self).__init__()

        # Get parameters
        self._files = files
        self._copy = bool_copy
        self._move = not self._copy
        self._src = source
        self._dest = destination
        self.signals = _CopyerSignals()

    def run(self):
        # Safeguard
        if not os.path.exists(self._dest) or not os.path.isdir(self._dest):
            return

        # Handle exception
        # I use base exception
        total = len(self._files)
        for prog, file in enumerate(self._files):
            # Copy all files
            to_process_file = os.path.join(self._src, file)
            if self._copy:
                try:
                    shutil.copy(to_process_file, self._dest)
                    self.signals.copied.emit(f"Copying: {file}")
                except shutil.Error as e:
                    print("Error: ", e)
                    self.signals.copied.emit(f"Failed to copy: {file}")
            else:
                try:
                    shutil.move(to_process_file, self._dest)
                    self.signals.moved.emit(f"Moving: {file}")
                except shutil.Error:
                    self.signals.moved.emit(f"Failed to move: {file}")

            # Emit progression
            self.signals.progress.emit(int(100 * ((prog + 1) / total)))


class _GuiCopier(QMainWindow):

    def __init__(self, parent=None, *args, **kwargs):
        # Set window parameters
        super(_GuiCopier, self).__init__(parent, *args, **kwargs)
        self.setWindowTitle("Gui Copier")
        self.setWindowIcon(QIcon("icons/logo.png"))
        self.setMinimumWidth(500)

        # Extensions list
        self._extensions = list()

        # Create a fake console
        self._fake_console: QPlainTextEdit = None
        self._progress_bar: QProgressBar = None
        self._src_folder: PickFolder = None
        self._dst_folder: PickFolder = None

        # Create toolbars
        self._create_the_toolbar()

        # Create tht central widget
        self._create_the_central_widget()

        # Manage status bar
        self._manage_status_bar()

        # Create a thread pool to launch runnables and manage threading
        self._thread_pool = QThreadPool()

    def _create_the_toolbar(self):
        # Add a new toolbar
        toolbar: QToolBar = self.addToolBar("Copyer")

        # Create actions
        action_copy = QAction(QIcon("icons/copy.png"), "Copy files", self)
        action_move = QAction(QIcon("icons/move.png"), "Move files", self)

        # Connect all actions
        action_copy.triggered.connect(self._perform_copy)
        action_move.triggered.connect(self._perform_move)

        # Add actions on the toolbar
        toolbar.addAction(action_copy)
        toolbar.addAction(action_move)

    def _create_the_central_widget(self):
        # Create tht widget
        central_widget = QWidget(self)
        central_layout = QVBoxLayout()

        # Extensions list to copy or move
        central_layout.addWidget(QLabel("Extensions of files to copy or move"))
        extension = QLineEdit()
        extension.textChanged.connect(self._get_extensions)
        central_layout.addWidget(extension)

        # Get folders
        self._src_folder = PickFolder(self, "Select source folder")
        self._dst_folder = PickFolder(self, "Select destination folder")

        central_layout.addWidget(self._src_folder)
        central_layout.addWidget(self._dst_folder)

        # Add QPlainTextEdit
        self._fake_console = QPlainTextEdit()
        self._fake_console.setReadOnly(True)
        central_layout.addWidget(self._fake_console)

        # Set central widget
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)

    def _manage_status_bar(self):
        # File Menus & Status Bar:
        self.statusBar().showMessage('Ready')
        self._progress_bar = QProgressBar()

        # Add it as permanent widget
        self.statusBar().addPermanentWidget(self._progress_bar)

        # Show the bar
        self._progress_bar.setGeometry(30, 40, 200, 25)

    def _get_extensions(self, value):
        try:
            self._extensions = value.split(",")
        except:
            self._extensions = []

    def _execute(self, copying: bool = True):
        # Get variables
        src = self._src_folder.folder()
        dst = self._dst_folder.folder()
        if None in [src, dst] or not os.path.exists(src) or not os.path.exists(dst):
            print("err 1s")
            return

        # Clear console content
        self._fake_console.clear()

        # Lauch copy or move
        for root, dires, files in os.walk(src):
            # Filter files
            if self._extensions and len(self._extensions):
                subjects = [item for item in files if Path(item).suffix.lower() in self._extensions or Path(item).suffix in self._extensions]
            else:
                subjects = files

            # Create the worker
            _copyer = _CopyerWorker(subjects, root, dst, copying)
            _copyer.signals.progress.connect(self._update_bar)
            if copying:
                _copyer.signals.copied.connect(self._update_console)
            else:
                _copyer.signals.moved.connect(self._update_console)

            # Start worker
            self._thread_pool.start(_copyer)

        # Manage empty folder after moving....
    def _update_console(self, value):
        self._fake_console.appendPlainText(value)

    def _perform_copy(self):
        self._execute()

    def _update_bar(self, value: int):
        self._progress_bar.setValue(value)

    def _perform_move(self):
        self._execute(False)

    @staticmethod
    def Run():
        """
        Function to run the program
        Returns:
            Void
        """
        # Create an app and pass to it the command line arguments
        # It is necessary if we want to pass arguments to our app
        # For instance the argumeent -style to give style to our app
        app = QApplication(sys.argv)

        # Load stylesheet
        # try:
        #     with open("style.qss", "r") as stylesheet:
        #         app.setStyleSheet(stylesheet.read())
        # except Exception:
        #     print("Can't load stylesheet")

        # Instantiate our object and show it
        # By defauld all QWidget is not shown
        _copier = _GuiCopier()
        _copier.show()

        # Exit the program with the app status code
        sys.exit(app.exec())
