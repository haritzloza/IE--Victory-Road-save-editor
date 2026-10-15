"""Dark theme with Inazuma-yellow accents."""
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

BG = '#12141a'
SURFACE = '#1a1d25'
SURFACE_2 = '#222632'
SURFACE_3 = '#2b3040'
BORDER = '#2f3545'
TEXT = '#e8eaf0'
TEXT_DIM = '#8b92a5'
ACCENT = '#ffc531'
ACCENT_DARK = '#e0a800'
ACCENT_TEXT = '#1a1400'
SUCCESS = '#3ecf8e'
DANGER = '#ff5d6c'

# spirit tiers, in the game's order
TIER_COLORS = ['#3ecf6a', '#3d8bff', '#a35cff', '#ffc531', '#ff7a2f']
ELEMENT_COLORS = {'Viento': '#3ecf8e', 'Bosque': '#7bc043', 'Fuego': '#ff6b4a', 'Montaña': '#c9a26b'}
KIND_COLORS = {'Héroe': '#ff6fb5', 'Basara': '#ffb347', 'Normal': TEXT_DIM}

QSS = f"""
* {{ outline: none; }}
QWidget {{ background: {BG}; color: {TEXT}; font-size: 10.5pt; }}
QToolTip {{ background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; border-radius: 6px; }}

#Sidebar {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
#Sidebar QPushButton {{
    text-align: left; padding: 10px 16px; margin: 2px 10px; border: none; border-radius: 10px;
    background: transparent; color: {TEXT_DIM}; font-size: 11pt; font-weight: 600;
}}
#Sidebar QPushButton:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
#Sidebar QPushButton:checked {{ background: {SURFACE_3}; color: {ACCENT}; }}
#Brand {{ background: transparent; font-size: 15pt; font-weight: 800; color: {ACCENT}; padding: 18px 20px 2px 20px; }}
#BrandSub {{ background: transparent; color: {TEXT_DIM}; padding: 0 20px 14px 20px; font-size: 9pt; }}

#Header {{ background: {BG}; }}
#PageTitle {{ font-size: 18pt; font-weight: 800; background: transparent; }}
#PageSub {{ color: {TEXT_DIM}; background: transparent; }}

#Card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
#Card QLabel {{ background: transparent; }}
#CardValue {{ font-size: 20pt; font-weight: 800; }}
#CardLabel {{ color: {TEXT_DIM}; font-size: 9.5pt; }}

QLineEdit {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px; padding: 8px 12px;
    selection-background-color: {ACCENT}; selection-color: {ACCENT_TEXT};
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}

QComboBox {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px; padding: 7px 12px; min-width: 120px;
}}
QComboBox:hover {{ border-color: {TEXT_DIM}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px;
    selection-background-color: {SURFACE_3}; selection-color: {ACCENT};
}}

QPushButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px; padding: 8px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: {SURFACE_3}; border-color: {TEXT_DIM}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; }}
QPushButton#Primary {{ background: {ACCENT}; color: {ACCENT_TEXT}; border: none; }}
QPushButton#Primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#Primary:disabled {{ background: {SURFACE_3}; color: {TEXT_DIM}; }}
QPushButton#Chip {{ border-radius: 14px; padding: 5px 12px; font-weight: 600; }}
QPushButton#Chip:checked {{ background: {ACCENT}; color: {ACCENT_TEXT}; border-color: {ACCENT}; }}

QTableView {{
    background: {SURFACE}; alternate-background-color: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px;
    gridline-color: transparent; selection-background-color: {SURFACE_3}; selection-color: {TEXT};
}}
QTableView::item {{ padding: 0 10px; border-bottom: 1px solid {SURFACE_2}; }}
QTableView::item:hover {{ background: {SURFACE_2}; }}
QTableView::item:selected {{ background: #3a3420; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {SURFACE}; color: {TEXT_DIM}; border: none; border-bottom: 1px solid {BORDER};
    padding: 10px; font-weight: 700; font-size: 9pt; text-transform: uppercase;
}}
QTableCornerButton::section {{ background: {SURFACE}; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {TEXT_DIM}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 4px; }}
QScrollBar::handle:horizontal {{ background: {SURFACE_3}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QSpinBox {{ background: {SURFACE_3}; border: 1px solid {ACCENT}; border-radius: 6px; padding: 2px 6px; }}
QCheckBox {{ background: transparent; spacing: 8px; }}
QCheckBox::indicator, QTableView::indicator {{
    width: 18px; height: 18px; border-radius: 5px; border: 2px solid {TEXT_DIM}; background: transparent;
}}
QCheckBox::indicator:checked, QTableView::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QProgressBar {{ background: {SURFACE_3}; border: none; border-radius: 4px; height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}

#Toast {{ background: {SURFACE_3}; border: 1px solid {BORDER}; border-radius: 12px; padding: 12px 18px; font-weight: 600; }}
QMessageBox, QInputDialog {{ background: {SURFACE}; }}
"""


def apply(app: QApplication):
    app.setStyle('Fusion')
    pal = QPalette()
    for role, color in ((QPalette.Window, BG), (QPalette.Base, SURFACE), (QPalette.AlternateBase, SURFACE),
                        (QPalette.Text, TEXT), (QPalette.WindowText, TEXT), (QPalette.Button, SURFACE_2),
                        (QPalette.ButtonText, TEXT), (QPalette.Highlight, ACCENT),
                        (QPalette.HighlightedText, ACCENT_TEXT), (QPalette.ToolTipBase, SURFACE_3),
                        (QPalette.ToolTipText, TEXT), (QPalette.PlaceholderText, TEXT_DIM)):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    f = QFont(app.font())
    f.setFamilies(['Inter', 'Noto Sans', 'Cantarell', f.family()])
    app.setFont(f)
    app.setStyleSheet(QSS)
