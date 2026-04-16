import sys
from PySide6.QtWidgets import QApplication
from pyfemm_gui.gui import MainWindow, QSS

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
