# Giperion/terminal/ui/window_style.py                             v028
# Футуристическая шкура окна в духе «Кода доступа рай»: тёмный металл
# с заклёпками и зелёный терминальный лог.
# Последнее изменение: отступ подписи «СИСТЕМА» и шрифт меню.

from config import BASE_DIR

# Папка с процедурно сгенерированными текстурами интерфейса.
UI_DIR = BASE_DIR / "assets" / "ui"


def _texture(name: str) -> str:
    """Возвращает путь к текстуре в виде, понятном таблице стилей."""

    return (UI_DIR / name).as_posix()


# Цвета темы (для справки; сам стиль ниже).
#   фон окна      металлическая текстура поверх #0d0a08
#   панели        металл #1e1a17, кант #050403
#   экран ядра    фиолетовый #601460 … #260828
#   терминал      #05100a с зелёным текстом #b8f0b0
#   кнопки        металл с красной рамкой #ff4a28
#   свечение      красное #ff5a3c, фиолетовое #ec60ec

# Шаблон стиля: текстуры подставляются заменой @ИМЯ@.
_STYLE_TEMPLATE = """
QMainWindow {
    background-color: #0d0a08;
    background-image: url(@METAL@);
    background-repeat: repeat;
}

QWidget#windowShell {
    background: transparent;
    border: 1px solid #070604;
}

QWidget#centralwidget {
    background: transparent;
}

QWidget#titleBar {
    border-image: url(@BAR@) 10 fill;
    border-width: 10px;
}

QWidget#titleGlow {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0.00 rgba(255, 74, 40, 0),
        stop:0.45 rgba(255, 92, 50, 180),
        stop:0.55 rgba(255, 92, 50, 180),
        stop:1.00 rgba(255, 74, 40, 0)
    );
    border: none;
}

QLabel#titleBadge {
    background: transparent;
    color: #d09a6a;
    font-size: 15pt;
}

QLabel#titleText {
    background: transparent;
    color: #ffd7c0;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 12pt;
    font-weight: bold;
}

QLabel#titleStatus {
    background: transparent;
    color: #b98a5c;
    font-size: 8pt;
}

QPushButton#titleButton,
QPushButton#closeButton {
    border-image: url(@BUTTON@) 12 fill;
    border-width: 5px;
    color: #ffd9c4;
    font-size: 10pt;
    font-weight: bold;
    padding: 0px;
}

QPushButton#titleButton:hover,
QPushButton#closeButton:hover {
    border-image: url(@BUTTON_HOVER@) 12 fill;
    color: #fff3ea;
}

QPushButton#titleButton:pressed,
QPushButton#closeButton:pressed {
    border-image: url(@BUTTON_HOVER@) 12 fill;
    color: #ffb59a;
}

QWidget#avatarPanel,
QWidget#chatPanel {
    border-image: url(@PANEL@) 14 fill;
    border-width: 14px;
}

QWidget#toolsPanel {
    background: transparent;
    border: none;
}

QWidget#chatsPanel,
QWidget#systemPanel {
    border-image: url(@PANEL@) 14 fill;
    border-width: 14px;
}

QWidget#personalityPanel {
    border-image: url(@PANEL@) 14 fill;
    border-width: 14px;
}

QWidget#personalityScreenFrame,
QWidget#modelScreenFrame,
QWidget#skillsScreenFrame,
QWidget#conferenceScreenFrame {
    border-image: url(@PANEL@) 14 fill;
    border-width: 14px;
}

QWidget#personalityPanel QLabel {
    background: transparent;
    color: #b8f0b0;
}

QLabel#personalityTitle {
    background: transparent;
    color: #d09a6a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
}

QLabel#growthCaption {
    color: #8ee08a;
    font-size: 8pt;
    font-weight: bold;
}

QTabWidget#coreTabs::pane {
    background-color: rgba(5, 16, 10, 120);
    border: 1px solid #23421f;
    border-radius: 4px;
    top: 0;
}

QWidget#screenTabStrip {
    background: transparent;
}

QPushButton#screenTabButton {
    border-image: none;
    background-color: #1b1512;
    border: 1px solid #3d2f26;
    border-bottom: 1px solid #23421f;
    border-radius: 0;
    color: #d8b48e;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 8pt;
    padding: 2px 2px;
    margin: 0;
}

QPushButton#screenTabButton:checked {
    background-color: #123d1f;
    border-color: #7cf58f;
    color: #eaffea;
}

QPushButton#screenTabButton:hover {
    color: #ffe2d2;
}

QLabel#executiveCaption {
    background: transparent;
    color: #d09a6a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
}

QLabel#executiveHint {
    background: transparent;
    color: #9fbfa5;
    font-size: 8pt;
}

QLabel#executiveName {
    background: transparent;
    color: #8ee08a;
    font-size: 9pt;
    font-weight: bold;
}

QLabel#executiveValue {
    background: transparent;
    color: #b8f0b0;
    font-size: 9pt;
}

QScrollArea#systemScroll {
    background: transparent;
    border: none;
}

QWidget#systemContent {
    background: transparent;
}

QLabel#systemName {
    background: transparent;
    color: #8ee08a;
    font-size: 8pt;
    font-weight: bold;
}

QLabel#systemValue {
    background: transparent;
    color: #b8f0b0;
    font-size: 8pt;
}

QWidget#personalityBackdrop {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
}

QWidget#modulesPanel {
    background-color: rgba(5, 16, 10, 150);
    border-top: 1px solid #23421f;
    border-bottom: 1px solid #23421f;
}

QLabel#modulesCaption {
    background: transparent;
    color: #b98a5c;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 7pt;
    font-weight: bold;
    letter-spacing: 1px;
}

QWidget#sideActionsPanel {
    background-color: rgba(5, 16, 10, 120);
    border-top: 1px solid #23421f;
}

QPushButton#sideIconButton {
    border-image: none;
    background-color: rgba(5, 16, 10, 190);
    border: 1px solid #23421f;
    border-radius: 4px;
    padding: 0px;
}

QPushButton#sideIconButton:hover {
    background-color: #0d2816;
    border: 1px solid #5ce07a;
}

QPushButton#sideIconButton:pressed {
    background-color: #123d1f;
    border: 1px solid #7cf58f;
}

QWidget#avatarPanel QLabel {
    background: transparent;
    color: #cbb8a6;
}

QLabel#toolsCaption {
    background: transparent;
    color: #d09a6a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    padding-left: 12px;
}

QLabel#systemCaption {
    background: transparent;
    color: #d09a6a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    padding-left: 12px;
}

QWidget#performanceCard {
    background-color: rgba(5, 16, 10, 150);
    border: 1px solid #23421f;
    border-radius: 5px;
}

QLabel#perfTitle {
    background: transparent;
    color: #d09a6a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 8pt;
    font-weight: bold;
    letter-spacing: 1px;
}

QLabel#perfValue {
    background: transparent;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 13pt;
    font-weight: bold;
}

QLabel#perfDetail {
    background: transparent;
    color: #9fbfa5;
    font-size: 8pt;
}

QLabel#perfFooter {
    background: transparent;
    color: #7f9a84;
    font-size: 8pt;
}

QPushButton#perfPauseButton {
    border-image: none;
    background-color: #1b1512;
    border: 1px solid #3d2f26;
    border-radius: 3px;
    color: #d8b48e;
    font-weight: bold;
    padding: 4px 16px;
}

QPushButton#perfPauseButton:hover {
    background-color: #2a1f18;
    border: 1px solid #7a5a3c;
    color: #ffe2d2;
}

QPushButton#perfPauseButton:checked {
    background-color: #123d1f;
    border: 1px solid #7cf58f;
    color: #eaffea;
}

QTextBrowser#updateLog {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    color: #b8f0b0;
    font-family: "Consolas", "Courier New", "Lucida Console", monospace;
    font-size: 9pt;
    padding: 10px;
    selection-background-color: #1d5a2a;
    selection-color: #eaffea;
}

QLabel#updateVersion {
    background: transparent;
    color: #8ee08a;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 8pt;
}

QLabel#updateStatus {
    background: transparent;
    color: #9fbfa5;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 8pt;
}

QPushButton#updateAction {
    border-image: none;
    background-color: #10281a;
    border: 1px solid #23421f;
    border-radius: 3px;
    color: #b8f0b0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
    padding: 5px 12px;
}

QPushButton#updateAction:hover {
    background-color: #123d1f;
    border: 1px solid #5ce07a;
    color: #eaffea;
}

QPushButton#updateAction:pressed {
    background-color: #1d5a2a;
    border: 1px solid #7cf58f;
}

QPushButton#updateAction:disabled {
    background-color: #141210;
    border: 1px solid #2a2119;
    color: #6b5f52;
}

QLabel#panelCaption {
    background: transparent;
    color: #d09a6a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    padding-left: 16px;
}

QTextBrowser#chatHistory {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    padding: 10px;
    color: #b8f0b0;
    selection-background-color: #1d5a2a;
    selection-color: #eaffea;
}

QListWidget#chatList {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    color: #b8f0b0;
    outline: none;
    padding: 4px;
}

QListWidget#chatList::item {
    border-bottom: 1px solid #14301a;
    padding: 9px 34px 9px 8px;
}

QListWidget#chatList::item:hover {
    background-color: #10281a;
}

QListWidget#chatList::item:selected {
    background-color: #123d1f;
    border-left: 3px solid #7cf58f;
    color: #eaffea;
}

QPlainTextEdit#systemLog {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    padding: 3px 8px;
    color: #ffc857;
    font-size: 8pt;
}

QPlainTextEdit#agentTask {
    background-color: #04100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    padding: 6px 8px;
    color: #d6ffd0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
}

QPlainTextEdit#agentTrace {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    padding: 8px;
    color: #b8f0b0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
}

QPlainTextEdit#messageInput {
    background-color: #04100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    padding: 6px 8px 30px 8px;
    color: #d6ffd0;
}

QPlainTextEdit#messageInput:focus {
    border: 1px solid #5ce07a;
}

QPushButton {
    border-image: url(@BUTTON@) 12 fill;
    border-width: 8px;
    color: #ffe2d2;
    font-weight: bold;
    padding: 2px 10px;
}

QPushButton:hover {
    border-image: url(@BUTTON_HOVER@) 12 fill;
    color: #fff3ea;
}

QPushButton:pressed {
    border-image: url(@BUTTON_HOVER@) 12 fill;
    color: #ffb59a;
}

QPushButton:checked {
    border-image: url(@BUTTON_HOVER@) 12 fill;
    color: #ffd0bf;
}

QPushButton:disabled {
    border-image: none;
    background-color: #141110;
    border: 1px solid #251f19;
    color: #5a4f45;
}

QPushButton#sendButton,
QPushButton#newChatButton {
    color: #fff0e0;
}

QMenu {
    background-color: #1b1512;
    border: 1px solid #3d2f26;
    padding: 4px;
    font-family: "Bahnschrift", "Segoe UI";
    font-size: 9pt;
}

QMenu::item {
    padding: 6px 22px 6px 14px;
    color: #e6cfba;
    border-radius: 3px;
}

QMenu::item:selected {
    background-color: #7a1c12;
    color: #ffe8dc;
}

QMenu::separator {
    height: 1px;
    background: #3d2f26;
    margin: 4px 8px;
}

QScrollBar:vertical {
    background: #100d0b;
    width: 12px;
    margin: 2px;
    border: 1px solid #241d18;
}

QScrollBar::handle:vertical {
    background: #4b3d31;
    border: 1px solid #2a2119;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background: #a33021;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background: #100d0b;
    height: 12px;
    margin: 2px;
    border: 1px solid #241d18;
}

QScrollBar::handle:horizontal {
    background: #4b3d31;
    border: 1px solid #2a2119;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background: #a33021;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
    background: none;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
}

QStatusBar {
    background-color: #16110e;
    color: #8ce08a;
    border-top: 1px solid #2b2119;
}

QStatusBar::item {
    border: none;
}

QDialog {
    background-color: #161110;
}

QDialog#skinDialog {
    background-color: #0d0a08;
    border: 2px solid #2a2119;
}

QWidget#skinDialogBody {
    background-color: #15100d;
}

QWidget#dialogTitleBar {
    border-image: url(@BAR@) 10 fill;
    border-width: 10px;
}

QLabel#dialogTitleText {
    background: transparent;
    color: #d09a6a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
}

QWidget#settingsNav {
    background-color: #0f0c0a;
    border: 1px solid #2a2119;
}

QPushButton#settingsNavButton {
    border-image: none;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    color: #d8b48e;
    font-weight: bold;
    padding: 8px 10px;
    text-align: left;
}

QPushButton#settingsNavButton:hover {
    background-color: #1b1512;
    border: 1px solid #3d2f26;
    color: #ffe2d2;
}

QPushButton#settingsNavButton:checked {
    background-color: #123d1f;
    border: 1px solid #7cf58f;
    color: #eaffea;
}

QPushButton#viewSectionButton {
    border-image: none;
    background-color: #1b1512;
    border: 1px solid #3d2f26;
    border-radius: 3px;
    color: #d8b48e;
    font-weight: bold;
    padding: 5px 18px;
}

QPushButton#viewSectionButton:hover {
    background-color: #2a1f18;
    border: 1px solid #7a5a3c;
    color: #ffe2d2;
}

QPushButton#viewSectionButton:checked {
    background-color: #123d1f;
    border: 1px solid #7cf58f;
    color: #eaffea;
}

QLabel#settingsStatus {
    color: #9fbfa5;
    font-size: 9pt;
}

QLabel#capabilityName {
    color: #c9d8cc;
    font-size: 9pt;
}

QLabel#capabilityValue {
    color: #9fc6ff;
    font-size: 8pt;
}

QLabel#capabilityCompare {
    color: #7fa58a;
    font-size: 8pt;
}

QProgressBar#capabilityBar {
    background-color: #0a1420;
    border: 1px solid #1d3247;
    border-radius: 2px;
}

QProgressBar#capabilityBar::chunk {
    background-color: #4f8fd0;
    border-radius: 1px;
}

QDialog QLabel {
    background: transparent;
    color: #e0d2c4;
}

QLabel#dialogTitle {
    color: #d09a6a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
}

QLabel#dialogHint {
    color: #a08d7c;
    font-size: 9pt;
}

QLabel#settingsSection {
    color: #b98a5c;
    font-size: 8pt;
    font-weight: bold;
    padding: 4px 2px 2px 2px;
}

QCheckBox#companionCheck,
QCheckBox#conferenceCheck {
    color: #8fd8c8;
    font-weight: bold;
}

QTextBrowser#skillsView, QTextBrowser#helpView {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    padding: 10px;
    color: #b8f0b0;
    selection-background-color: #1d5a2a;
    selection-color: #eaffea;
}

QListWidget#modelsView,
QListWidget#conferenceModesView {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    color: #b8f0b0;
    outline: none;
}

QListWidget#modelsView::item,
QListWidget#conferenceModesView::item {
    border-bottom: 1px solid #14301a;
    padding: 9px 12px;
}

QListWidget#modelsView::item:hover,
QListWidget#conferenceModesView::item:hover {
    background-color: #10281a;
}

QListWidget#modelsView::item:selected,
QListWidget#conferenceModesView::item:selected {
    background-color: #1d5a2a;
    color: #eaffea;
}

QWidget#modelCard {
    background-color: #07120c;
    border: 1px solid #23421f;
    border-radius: 4px;
}

QWidget#petCard {
    background-color: #07120c;
    border: 1px solid #23421f;
    border-radius: 4px;
}

QLabel#petAvatar {
    background-color: #0a1a10;
    border: 1px solid #23421f;
    border-radius: 4px;
    color: #7cf58f;
    font-size: 24pt;
}

QLabel#petName {
    color: #ffb37a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 12pt;
    font-weight: bold;
}

QLabel#petType {
    color: #b98a5c;
    font-size: 9pt;
}

QLineEdit#petInput,
QPlainTextEdit#petInput,
QComboBox#petCombo {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    color: #b8f0b0;
    padding: 5px 7px;
    selection-background-color: #1d5a2a;
}

QWidget#petTrainingScreen {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
}

QLabel#petTrainingLine {
    background: transparent;
    color: #b8f0b0;
    font-size: 9pt;
}

QProgressBar#petTrainingBar {
    background-color: #04100a;
    border: 1px solid #23421f;
    border-radius: 3px;
}

QProgressBar#petTrainingBar::chunk {
    background-color: #7cf58f;
    border-radius: 2px;
}

QLabel#petDescription {
    color: #cfe8d2;
    font-size: 9pt;
}

QLabel#petHint {
    color: #9fbfa5;
    font-size: 8pt;
    font-style: italic;
}

QLabel#petStatus {
    color: #9fbfa5;
    font-size: 9pt;
}

QLabel#petStatus[active="true"] {
    color: #7cf58f;
}

QPushButton#petAttachButton {
    color: #fff0e0;
}

QWidget#petsHolder {
    background: transparent;
}

QTabBar#modelsTabs::tab {
    background-color: #1b1512;
    border: 1px solid #3d2f26;
    border-bottom: none;
    color: #d8b48e;
    font-size: 10pt;
    padding: 6px 8px;
    margin-right: 2px;
}

QTabBar#modelsTabs::tab:selected {
    background-color: #123d1f;
    border-color: #7cf58f;
    color: #eaffea;
}

QTabBar#modelsTabs::tab:hover {
    color: #ffe2d2;
}

QTabWidget#skillsTabs::pane {
    background-color: transparent;
    border: 1px solid #23421f;
    border-radius: 4px;
    top: 0;
}

QWidget#skillsTabStrip QPushButton#screenTabButton {
    font-size: 10pt;
}

QLabel#modelNickname {
    color: #9fbfa5;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 9pt;
    letter-spacing: 0.5px;
}

QWidget#closePlate {
    border-image: url(@PANEL@) 14 fill;
    border-width: 14px;
}

QLabel#closeScreen {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
    color: #eaffea;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 15pt;
    font-weight: bold;
    padding: 12px;
}

QLabel#conferenceModeName {
    color: #ffb37a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 13pt;
    font-weight: normal;
}

QScrollArea#cardScroll {
    background: transparent;
    border: none;
}

QLabel#conferenceImage {
    background-color: #0a1a10;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: 1px solid #23421f;
    border-radius: 4px;
}

QLabel#modelAvatar {
    background-color: #0a1a10;
    border: 1px solid #23421f;
    border-radius: 4px;
    color: #7cf58f;
    font-size: 32pt;
}

QLabel#strengthName {
    color: #c9d8cc;
    font-size: 9pt;
}

QLabel#strengthValue {
    color: #9fc6ff;
    font-size: 8pt;
}

QProgressBar#strengthBar {
    background-color: #0a1420;
    border: 1px solid #1d3247;
    border-radius: 2px;
}

QProgressBar#strengthBar::chunk {
    background-color: #4f8fd0;
    border-radius: 1px;
}

QLabel#infoCaption {
    color: #b98a5c;
    font-size: 8pt;
}

QLabel#infoValue {
    color: #cfe8d2;
    font-size: 9pt;
}

QPushButton#addModelButton {
    min-height: 28px;
}

QPushButton#aiParamsButton {
    border-image: none;
    background-color: #10281a;
    border: 1px solid #23421f;
    border-radius: 3px;
    color: #b8f0b0;
    font-size: 8pt;
    padding: 4px 10px;
}

QPushButton#aiParamsButton:hover {
    background-color: #123d1f;
    border: 1px solid #5ce07a;
    color: #eaffea;
}

QPushButton#aiParamsButton:pressed {
    background-color: #1d5a2a;
    border: 1px solid #7cf58f;
}

QPushButton#aiParamsButton:disabled {
    background-color: #0b0908;
    border: 1px solid #251f19;
    color: #5a4f45;
}

QPushButton#workshopAction {
    border-image: none;
    background-color: #10281a;
    border: 1px solid #23421f;
    border-radius: 3px;
    color: #b8f0b0;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
    padding: 5px 10px;
}

QPushButton#workshopAction:hover {
    background-color: #123d1f;
    border: 1px solid #5ce07a;
    color: #eaffea;
}

QPushButton#workshopAction:pressed {
    background-color: #1d5a2a;
    border: 1px solid #7cf58f;
}

QWidget#paramsContent {
    background: transparent;
}

QFrame#paramsPlate {
    background-color: #0d0a08;
    border: 1px solid #3a2e25;
    border-radius: 4px;
}

QLabel#paramsPlateTitle {
    background: transparent;
    color: #d09a6a;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    padding-bottom: 2px;
}

QWidget#paramsScreen {
    background-color: #05100a;
    background-image: url(@SCANLINE@);
    background-repeat: repeat;
    border: none;
    border-radius: 3px;
}

QWidget#paramsScreen QLabel {
    background: transparent;
    font-family: "Consolas", "Courier New", "Lucida Console", monospace;
    font-size: 9pt;
}

QLabel#paramsKey {
    color: #8ee08a;
}

QLabel#paramsValue {
    color: #b8f0b0;
}

QLabel#paramsNote {
    color: #9fbfa5;
    font-family: "Consolas", "Courier New", "Lucida Console", monospace;
    font-size: 8pt;
}

QLabel#modelName {
    color: #ffb37a;
    font-family: "Bahnschrift SemiBold", "Segoe UI";
    font-size: 13pt;
    font-weight: bold;
}

QLabel#modelProvider {
    color: #b98a5c;
    font-size: 9pt;
}

QLabel#personalityMotto {
    color: #9fc6ff;
    font-size: 10pt;
    font-style: italic;
}

QLabel#modelDescription {
    color: #cfe8d2;
    font-size: 9pt;
}

QLabel#modelStatus {
    color: #7cf58f;
    font-size: 9pt;
}

QLabel#reputationCaption {
    color: #b98a5c;
    font-size: 8pt;
    font-weight: bold;
}

QLabel#reputationLabel {
    color: #ffd479;
    font-size: 9pt;
}

QProgressBar#reputationBar {
    background-color: #0a1a10;
    border: 1px solid #23421f;
    border-radius: 3px;
}

QProgressBar#reputationBar::chunk {
    background-color: #3fa85a;
    border-radius: 2px;
}

QComboBox,
QSpinBox,
QDoubleSpinBox,
QLineEdit {
    background-color: #0f0c0a;
    border: 1px solid #3a2e25;
    border-radius: 3px;
    color: #ffd9c2;
    padding: 3px 6px;
}

QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QLineEdit:focus {
    border: 1px solid #ff6a48;
}

QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled,
QLineEdit:disabled {
    background-color: #0b0908;
    border-color: #251f19;
    color: #6b5b4d;
}

QCheckBox {
    background: transparent;
    color: #d8e8d8;
    spacing: 8px;
}

QCheckBox:disabled {
    color: #6b5b4d;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    background-color: #0f0c0a;
    border: 1px solid #3a2e25;
    border-radius: 2px;
}

QCheckBox::indicator:hover {
    border: 1px solid #ff9a62;
}

QCheckBox::indicator:checked {
    background-color: #2d6a3a;
    border: 1px solid #5ce07a;
}

QCheckBox::indicator:checked:disabled {
    background-color: #1a2a1c;
    border-color: #3a4a3a;
}

QComboBox::drop-down {
    border: none;
    width: 18px;
}

QComboBox QAbstractItemView {
    background-color: #1b1512;
    border: 1px solid #3d2f26;
    color: #e6cfba;
    selection-background-color: #7a1c12;
    selection-color: #ffe8dc;
}

QToolTip {
    background-color: #1b1512;
    color: #ffe2d2;
    border: 1px solid #7a1c12;
}
"""

# Готовый стиль окна с абсолютными путями к текстурам.
WINDOW_STYLE = (
    _STYLE_TEMPLATE
    .replace("@METAL@", _texture("metal_tile.png"))
    .replace("@PANEL_PURPLE@", _texture("panel_purple.png"))
    .replace("@PANEL@", _texture("panel.png"))
    .replace("@SCANLINE@", _texture("scanline.png"))
    .replace("@BUTTON_HOVER@", _texture("button_hover.png"))
    .replace("@BUTTON@", _texture("button.png"))
    .replace("@BAR@", _texture("bar.png"))
)
