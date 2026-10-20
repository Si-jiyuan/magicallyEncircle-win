"""Settings window and recording dialogs."""

from __future__ import annotations

import html

from PySide6.QtCore import QPoint, QSettings, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..constants import (
    CLOSE_QUIT_APP,
    CLOSE_TAB,
    CLOSE_WINDOW,
    MULTI_DOUBLE_PRESS,
    MULTI_SINGLE_PRESS,
    TRIGGER_ALT_LEFT,
    TRIGGER_MIDDLE,
)
from ..controller import MagicController
from ..gesture.builtin import BUILT_INS
from ..model.gestures import Strokes
from ..platform_support.overlay import STYLES, STYLE_TITLES
from ..platform_support import win32
from .canvas import PatternCanvas
from .theme import app_icon, asset_path, is_dark_mode, preview_pixmap

AUTHOR_URL = (
    "https://www.xiaohongshu.com/user/profile/60046a230000000001004f31"
    "?xsec_token=YBLDwnjN2eGZx9O3CXGjM4vs9CoMKtL-HD7O6KLqU35tM="
    "&xsec_source=app_share&xhsshare=CopyLink"
    "&shareRedId=ODYyNDlGNjw2NzUyOTgwNjY0OTc4Szk6"
    "&apptime=1791476230&share_id=3aa2798892c24177b928812d98c4eb6d"
)

CARD_STYLE = """
QFrame#card {
    background: rgba(128, 128, 138, 14);
    border: 1px solid rgba(128, 128, 138, 55);
    border-radius: 8px;
}
QFrame#card[selected="true"] {
    border: 1px solid #4a8cff;
    background: rgba(74, 140, 255, 28);
}
"""


def _title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size: 19px; font-weight: 600;")
    return label


def _caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("role", "caption")
    label.setStyleSheet("color: rgba(128, 128, 138, 255);")
    return label


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    line.setStyleSheet("color: rgba(128, 128, 138, 55);")
    return line


class RecordDialog(QDialog):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(app_icon())
        self.resize(460, 360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        layout.addWidget(QLabel(f"录制「{title}」图案"))
        hint = _caption("可多笔画绘制；抬笔后笔画会保留。")
        layout.addWidget(hint)
        self.canvas = PatternCanvas(self)
        layout.addWidget(self.canvas, 1)
        buttons = QHBoxLayout()
        clear = QPushButton("清空")
        clear.clicked.connect(self.canvas.clear)
        buttons.addWidget(clear)
        buttons.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("保存")
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _save(self) -> None:
        if not self.canvas.current_strokes():
            QMessageBox.information(self, "无法保存", "请先在画布上绘制图案。")
            return
        self.accept()

    def strokes(self) -> Strokes:
        return self.canvas.current_strokes()


class CoffeePopup(QWidget):
    """Small popup with the WeChat / Alipay support QR codes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("coffeePopup")
        dark = is_dark_mode()
        background = "#2a2a31" if dark else "#fbfbfd"
        border = "#4a4a56" if dark else "#d7d7df"
        text = "#ececf0" if dark else "#202024"
        self.setStyleSheet(
            f"QWidget#coffeePopup {{ background: {background}; border: 1px solid {border}; border-radius: 12px; }}"
            f"QLabel {{ color: {text}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel("Buy Me A Coffee ☕️")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(self._qr("wechat.jpg", "微信"))
        row.addWidget(self._qr("alipay.jpg", "支付宝"))
        layout.addLayout(row)
        self.setFixedWidth(480)
        self.adjustSize()

    def _qr(self, filename: str, title: str) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        image.setFixedSize(200, 260)
        path = asset_path("buyMeCoffee", filename)
        pixmap = QPixmap(str(path)) if path.exists() else QPixmap()
        if pixmap.isNull():
            image.setText("图片缺失")
            image.setStyleSheet("color: rgba(128,128,138,255);")
        else:
            image.setPixmap(
                pixmap.scaled(200, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        layout.addWidget(image)
        label = QLabel(title)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 12px; color: rgba(128,128,138,255);")
        layout.addWidget(label)
        return wrapper

    def show_at(self, anchor: QWidget) -> None:
        self.adjustSize()
        point = anchor.mapToGlobal(QPoint(0, anchor.height() + 8))
        screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            if point.x() + self.width() > available.right():
                point.setX(available.right() - self.width())
            if point.y() + self.height() > available.bottom():
                point = anchor.mapToGlobal(QPoint(0, -self.height() - 8))
        self.move(point)
        self.show()
        self.raise_()
        self.activateWindow()


class GeneralSection(QWidget):
    def __init__(self, controller: MagicController) -> None:
        super().__init__()
        self.controller = controller
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        layout.addWidget(_title("通用设置"))

        self.enabled = QCheckBox("启用魔法线条")
        self.hud = QCheckBox("显示识别反馈")
        self.login = QCheckBox("开机自启动")
        self.updates = QCheckBox("启动时检查更新")
        for checkbox in (self.enabled, self.hud, self.login, self.updates):
            layout.addWidget(checkbox)
        self.enabled.toggled.connect(controller.set_enabled)
        self.hud.toggled.connect(controller.set_show_hud)
        self.login.toggled.connect(controller.set_launch_at_login)
        self.updates.toggled.connect(controller.set_auto_check_updates)

        layout.addWidget(_divider())
        layout.addWidget(QLabel("绘图方式"))
        self.trigger_group = QButtonGroup(self)
        self.alt_radio = QRadioButton("Alt + 鼠标左键")
        self.middle_radio = QRadioButton("鼠标中键")
        self.trigger_group.addButton(self.alt_radio, 0)
        self.trigger_group.addButton(self.middle_radio, 1)
        layout.addWidget(self.alt_radio)
        layout.addWidget(self.middle_radio)
        self.trigger_group.buttonClicked.connect(self._trigger_changed)
        layout.addWidget(_caption("Alt + 左键会吞掉左键事件；如果某些程序仍弹出菜单，可改用鼠标中键。"))

        self.multi_box = QWidget()
        multi_layout = QVBoxLayout(self.multi_box)
        multi_layout.setContentsMargins(0, 4, 0, 0)
        multi_layout.addWidget(QLabel("多笔画触发方式"))
        self.multi_group = QButtonGroup(self)
        self.multi_double = QRadioButton("双击 Alt（轻点一下再按住）")
        self.multi_single = QRadioButton("单击 Alt（不松开）")
        self.multi_group.addButton(self.multi_double, 0)
        self.multi_group.addButton(self.multi_single, 1)
        multi_layout.addWidget(self.multi_double)
        multi_layout.addWidget(self.multi_single)
        multi_layout.addWidget(_caption("多笔画期间笔画保持显示，松开 Alt 后统一识别。"))
        self.multi_group.buttonClicked.connect(self._multi_changed)
        layout.addWidget(self.multi_box)

        self.speed_box = QWidget()
        speed_layout = QVBoxLayout(self.speed_box)
        speed_layout.setContentsMargins(0, 4, 0, 0)
        speed_layout.addWidget(QLabel("多笔画识别速度"))
        self.speed_group = QButtonGroup(self)
        self.speed_fast = QRadioButton("快（0.2 秒）")
        self.speed_normal = QRadioButton("适中（0.5 秒）")
        self.speed_slow = QRadioButton("慢（0.75 秒）")
        for index, button in enumerate((self.speed_fast, self.speed_normal, self.speed_slow)):
            self.speed_group.addButton(button, index)
            speed_layout.addWidget(button)
        speed_layout.addWidget(_caption("鼠标中键绘图时，停止操作该时长后自动开始识别。"))
        self.speed_group.buttonClicked.connect(self._speed_changed)
        layout.addWidget(self.speed_box)

        layout.addWidget(_divider())
        layout.addWidget(QLabel("「关闭」图案的动作"))
        self.close_combo = QComboBox()
        self.close_combo.addItem("关闭当前窗口（Alt+F4）", CLOSE_WINDOW)
        self.close_combo.addItem("关闭当前标签页（Ctrl+W）", CLOSE_TAB)
        self.close_combo.addItem("退出当前程序（Alt+F4）", CLOSE_QUIT_APP)
        self.close_combo.currentIndexChanged.connect(self._close_changed)
        layout.addWidget(self.close_combo)
        layout.addWidget(_caption("识别到「关闭」图案（叉号）时执行上面的动作；图案本身可在「内置图案」里修改。"))

        layout.addWidget(_divider())
        layout.addWidget(QLabel("图案播放速度"))
        self.playback_combo = QComboBox()
        for speed in (0.25, 0.5, 0.75):
            self.playback_combo.addItem(f"{speed:g}×", speed)
        self.playback_combo.currentIndexChanged.connect(self._playback_changed)
        layout.addWidget(self.playback_combo)
        layout.addWidget(_caption("点击图案旁的播放按钮时，按该速度演示绘制过程。"))

        layout.addWidget(_divider())
        buttons = QHBoxLayout()
        import_button = QPushButton("导入图案…")
        export_button = QPushButton("导出图案…")
        import_button.clicked.connect(lambda: controller.import_gestures(self))
        export_button.clicked.connect(lambda: controller.export_gestures(self))
        buttons.addWidget(import_button)
        buttons.addWidget(export_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        layout.addStretch(1)
        author = QLabel(
            f'Made With By 💌 <a href="{html.escape(AUTHOR_URL, quote=True)}">Si-Jiyuan</a>'
        )
        author.setTextFormat(Qt.RichText)
        author.setOpenExternalLinks(True)
        author.setStyleSheet("font-size: 12px;")
        layout.addWidget(author)

        self.coffee_button = QPushButton("Buy Me A Coffee Pleeeeeease 🥺")
        self.coffee_button.setFlat(True)
        self.coffee_button.setCursor(Qt.PointingHandCursor)
        self.coffee_button.setStyleSheet(
            "QPushButton { border: none; color: #4a8cff; text-align: left; padding: 0; font-size: 12px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self.coffee_button.clicked.connect(self._show_coffee)
        layout.addWidget(self.coffee_button, alignment=Qt.AlignLeft)
        self._coffee_popup: CoffeePopup | None = None

        about = _caption(
            f"magicallyEncircle {__version__} · Windows\n"
            "用 Alt + 左键或鼠标中键画出图案来触发快捷键。\n"
            "配置保存在本地，不会上传任何数据。"
        )
        layout.addWidget(about)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.refresh()

    def _trigger_changed(self, button) -> None:
        self.controller.set_draw_trigger(
            TRIGGER_ALT_LEFT if self.trigger_group.id(button) == 0 else TRIGGER_MIDDLE
        )
        self.refresh()

    def _multi_changed(self, button) -> None:
        self.controller.set_multi_stroke_mode(
            MULTI_DOUBLE_PRESS if self.multi_group.id(button) == 0 else MULTI_SINGLE_PRESS
        )

    def _speed_changed(self, button) -> None:
        index = self.speed_group.id(button)
        self.controller.set_middle_speed(("fast", "normal", "slow")[max(0, min(2, index))])

    def _close_changed(self, _index: int) -> None:
        value = self.close_combo.currentData()
        if value:
            self.controller.set_close_action(str(value))

    def _playback_changed(self, _index: int) -> None:
        value = self.playback_combo.currentData()
        if value is not None:
            self.controller.set_playback_speed(float(value))

    def _show_coffee(self) -> None:
        if self._coffee_popup is None:
            self._coffee_popup = CoffeePopup(self)
        if self._coffee_popup.isVisible():
            self._coffee_popup.hide()
            return
        self._coffee_popup.show_at(self.coffee_button)

    def refresh(self) -> None:
        settings = self.controller.settings
        widgets = [
            self.enabled,
            self.hud,
            self.login,
            self.updates,
            self.alt_radio,
            self.middle_radio,
            self.multi_double,
            self.multi_single,
            self.speed_fast,
            self.speed_normal,
            self.speed_slow,
            self.close_combo,
            self.playback_combo,
        ]
        for widget in widgets:
            widget.blockSignals(True)
        self.enabled.setChecked(settings.enabled)
        self.hud.setChecked(settings.show_hud)
        self.login.setChecked(settings.launch_at_login)
        self.updates.setChecked(settings.auto_check_updates)
        if settings.draw_trigger == TRIGGER_MIDDLE:
            self.middle_radio.setChecked(True)
        else:
            self.alt_radio.setChecked(True)
        self.multi_double.setChecked(settings.multi_stroke_mode != MULTI_SINGLE_PRESS)
        self.multi_single.setChecked(settings.multi_stroke_mode == MULTI_SINGLE_PRESS)
        speed_index = {"fast": 0, "normal": 1, "slow": 2}.get(settings.middle_speed, 1)
        (self.speed_fast, self.speed_normal, self.speed_slow)[speed_index].setChecked(True)
        close_index = self.close_combo.findData(settings.close_action)
        self.close_combo.setCurrentIndex(max(0, close_index))
        playback_index = self.playback_combo.findData(settings.playback_speed)
        if playback_index < 0:
            for index in range(self.playback_combo.count()):
                if abs(float(self.playback_combo.itemData(index)) - settings.playback_speed) < 1e-6:
                    playback_index = index
                    break
        self.playback_combo.setCurrentIndex(max(0, playback_index))
        for widget in widgets:
            widget.blockSignals(False)
        self.multi_box.setVisible(settings.draw_trigger != TRIGGER_MIDDLE)
        self.speed_box.setVisible(settings.draw_trigger == TRIGGER_MIDDLE)


class StyleSection(QWidget):
    def __init__(self, controller: MagicController) -> None:
        super().__init__()
        self.controller = controller
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        layout.addWidget(_title("视觉风格"))
        layout.addWidget(_caption("魔法线条的外观样式；「随机」会让每一笔随机选择一种颜色。"))
        self.group = QButtonGroup(self)
        self.radios: dict[str, QRadioButton] = {}
        for key, title in STYLE_TITLES.items():
            row = QFrame()
            row.setObjectName("card")
            row.setStyleSheet(CARD_STYLE)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)
            swatch = QLabel()
            swatch.setFixedSize(18, 18)
            if key == "random":
                swatch.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ff8c1f, stop:0.5 #8c5cff, stop:1 #33aaff); border-radius: 9px;")
            else:
                rgb = STYLES[key].glow
                swatch.setStyleSheet(f"background: rgb({rgb[0]},{rgb[1]},{rgb[2]}); border-radius: 9px;")
            radio = QRadioButton(title)
            radio.toggled.connect(lambda checked, name=key: self._select(name) if checked else None)
            self.group.addButton(radio)
            self.radios[key] = radio
            row_layout.addWidget(swatch)
            row_layout.addWidget(radio)
            row_layout.addStretch(1)
            layout.addWidget(row)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.refresh()

    def _select(self, style: str) -> None:
        if self.controller.settings.style != style:
            self.controller.set_style(style)

    def refresh(self) -> None:
        current = self.controller.settings.style
        for key, radio in self.radios.items():
            radio.blockSignals(True)
            radio.setChecked(key == current)
            radio.blockSignals(False)


class BuiltInSection(QWidget):
    def __init__(self, controller: MagicController) -> None:
        super().__init__()
        self.controller = controller
        self.rows: dict[str, dict] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(8)
        layout.addWidget(_title("内置图案"))
        layout.addWidget(_caption("为每个动作录制自己的图案，或在识别后发送的快捷键。"))
        for built_in in BUILT_INS:
            row = QFrame()
            row.setObjectName("card")
            row.setStyleSheet(CARD_STYLE)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 8, 10, 8)
            play = QPushButton("▶")
            play.setFixedWidth(32)
            play.setToolTip("播放图案")
            play.clicked.connect(lambda _checked=False, ident=built_in.id: controller.play_builtin(ident))
            row_layout.addWidget(play)

            text_box = QVBoxLayout()
            text_box.setSpacing(2)
            title = QLabel(built_in.title)
            title.setStyleSheet("font-weight: 600;")
            description = _caption("")
            text_box.addWidget(title)
            text_box.addWidget(description)
            row_layout.addLayout(text_box, 1)

            record = QPushButton("录制…")
            record.clicked.connect(lambda _checked=False, ident=built_in.id: self._record(ident))
            row_layout.addWidget(record)
            bind = QPushButton("设置快捷键")
            bind.clicked.connect(lambda _checked=False, ident=built_in.id: controller.begin_key_capture(("builtin", ident)))
            bind.setEnabled(built_in.action != "close")
            row_layout.addWidget(bind)
            reset = QPushButton("恢复默认")
            reset.clicked.connect(lambda _checked=False, ident=built_in.id: controller.reset_builtin(ident))
            row_layout.addWidget(reset)
            layout.addWidget(row)
            self.rows[built_in.id] = {
                "play": play,
                "description": description,
                "bind": bind,
                "reset": reset,
            }
        reset_all = QPushButton("全部恢复默认图案")
        reset_all.clicked.connect(controller.reset_all_builtin_overrides)
        layout.addWidget(reset_all)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.refresh()

    def _record(self, identifier: str) -> None:
        built_in = next((item for item in BUILT_INS if item.id == identifier), None)
        if built_in is None:
            return
        dialog = RecordDialog(built_in.title, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.controller.set_builtin_override(identifier, dialog.strokes())

    def refresh(self) -> None:
        for built_in in BUILT_INS:
            widgets = self.rows[built_in.id]
            description = self.controller.builtin_description(built_in.id)
            if self.controller.pending_key_target == ("builtin", built_in.id):
                description += " · 等待按键…（Esc 取消）"
            widgets["description"].setText(description)
            has_sample = self.controller.override_count(built_in.id) > 0 or bool(built_in.default_samples)
            widgets["play"].setEnabled(has_sample)
            widgets["reset"].setEnabled(
                self.controller.override_count(built_in.id) > 0
                or self.controller.has_builtin_shortcut_override(built_in.id)
            )
            widgets["bind"].setEnabled(
                built_in.action != "close"
                and self.controller.pending_key_target is None
            )


class CustomCard(QFrame):
    clicked = Signal(str)

    def __init__(self, controller: MagicController, gesture, parent=None) -> None:
        super().__init__(parent)
        self.gesture = gesture
        self.setObjectName("card")
        self.setStyleSheet(CARD_STYLE)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(170)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)
        preview = QLabel()
        preview.setAlignment(Qt.AlignCenter)
        preview.setPixmap(controller.preview_image(gesture))
        preview.setFixedHeight(68)
        layout.addWidget(preview)
        name = QLabel(gesture.name)
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet("font-weight: 600;")
        name.setToolTip(gesture.name)
        layout.addWidget(name)
        binding = QLabel(controller.binding_summary(gesture))
        binding.setAlignment(Qt.AlignCenter)
        binding.setStyleSheet("color: rgba(128,128,138,255); font-size: 11px;")
        binding.setToolTip(controller.binding_summary(gesture))
        layout.addWidget(binding)
        play = QPushButton("播放")
        play.setFixedHeight(24)
        play.clicked.connect(lambda: controller.play_custom_gesture(gesture.id))
        layout.addWidget(play)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.gesture.id)
        super().mousePressEvent(event)


class CustomSection(QWidget):
    def __init__(self, controller: MagicController) -> None:
        super().__init__()
        self.controller = controller
        self.selected_id: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(8)
        layout.addWidget(_title("自定义图案"))

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

        self.action_bar = QFrame()
        self.action_bar.setObjectName("card")
        self.action_bar.setStyleSheet(CARD_STYLE)
        bar = QVBoxLayout(self.action_bar)
        bar.setContentsMargins(10, 8, 10, 8)
        bar.setSpacing(6)
        button_row = QHBoxLayout()
        self.rename_button = QPushButton("重命名…")
        self.shortcut_button = QPushButton("设置快捷键")
        self.app_button = QPushButton("绑定 App…")
        self.clear_button = QPushButton("清除绑定")
        self.delete_button = QPushButton("删除")
        self.hint = _caption("点击上方图案以设置快捷键、绑定 App 或重命名。")
        button_row.addWidget(self.rename_button)
        button_row.addWidget(self.shortcut_button)
        button_row.addWidget(self.app_button)
        button_row.addWidget(self.clear_button)
        button_row.addWidget(self.delete_button)
        button_row.addStretch(1)
        bar.addLayout(button_row)
        bar.addWidget(self.hint)
        layout.addWidget(self.action_bar)

        self.rename_button.clicked.connect(self._rename)
        self.shortcut_button.clicked.connect(self._bind_shortcut)
        self.app_button.clicked.connect(self._bind_app)
        self.clear_button.clicked.connect(self._clear)
        self.delete_button.clicked.connect(self._delete)
        self.refresh()

    def _selected_gesture(self):
        if self.selected_id is None:
            return None
        return next((g for g in self.controller.custom_gestures if g.id == self.selected_id), None)

    def _select(self, identifier: str) -> None:
        self.selected_id = identifier
        self.refresh()

    def _rename(self) -> None:
        gesture = self._selected_gesture()
        if gesture is None:
            return
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "重命名图案", "名称：", text=gesture.name)
        if ok:
            self.controller.rename_gesture(gesture.id, name)

    def _bind_shortcut(self) -> None:
        gesture = self._selected_gesture()
        if gesture is not None:
            self.controller.begin_key_capture(("custom", gesture.id))

    def _bind_app(self) -> None:
        gesture = self._selected_gesture()
        if gesture is None:
            return
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            "选择要打开的 App（可多选）",
            "",
            "Applications (*.exe *.lnk);;All files (*)",
        )
        if paths:
            self.controller.set_custom_apps(gesture.id, paths)

    def _clear(self) -> None:
        gesture = self._selected_gesture()
        if gesture is not None:
            self.controller.clear_custom_binding(gesture.id)

    def _delete(self) -> None:
        gesture = self._selected_gesture()
        if gesture is None:
            return
        answer = QMessageBox.question(
            self,
            "删除图案",
            f"确定删除「{gesture.name}」吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.controller.delete_gesture(gesture.id)
            self.selected_id = None
            self.refresh()

    def _clear_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh(self) -> None:
        self._clear_grid()
        gestures = self.controller.custom_gestures
        if not gestures:
            empty = QLabel("还没有自定义图案。到「记录图案」里画一个吧。")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: rgba(128,128,138,255);")
            self.grid.addWidget(empty, 0, 0, 1, 3)
            self.selected_id = None
        else:
            if self.selected_id not in {g.id for g in gestures}:
                self.selected_id = None
            for index, gesture in enumerate(gestures):
                card = CustomCard(self.controller, gesture, self.container)
                card.setProperty("selected", gesture.id == self.selected_id)
                card.clicked.connect(self._select)
                self.grid.addWidget(card, index // 3, index % 3)
            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 1)
            self.grid.setColumnStretch(2, 1)

        gesture = self._selected_gesture()
        has_selection = gesture is not None
        self.rename_button.setEnabled(has_selection)
        self.shortcut_button.setEnabled(has_selection and not (gesture and gesture.is_app_bound))
        self.app_button.setEnabled(has_selection and not (gesture and gesture.is_shortcut_bound))
        self.clear_button.setEnabled(has_selection and bool(gesture and gesture.is_bound))
        self.delete_button.setEnabled(has_selection)
        if self.controller.pending_key_target and self.controller.pending_key_target[0] == "custom":
            self.hint.setText("等待按键…（Esc 取消）")
        elif has_selection and gesture is not None:
            self.hint.setText(f"当前绑定：{self.controller.binding_summary(gesture)}")
        else:
            self.hint.setText("点击上方图案以设置快捷键、绑定 App 或重命名。")
        self.hint.setVisible(True)


class RecordSection(QWidget):
    def __init__(self, controller: MagicController) -> None:
        super().__init__()
        self.controller = controller
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)
        layout.addWidget(_title("记录图案"))
        layout.addWidget(_caption("在下方画布上绘制（无需按 Alt，可多笔画），然后保存为自定义图案。"))
        self.canvas = PatternCanvas()
        self.canvas.setMinimumHeight(260)
        layout.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("名称（可选）")
        self.name.setMaximumWidth(220)
        row.addWidget(self.name)
        clear = QPushButton("清空")
        clear.clicked.connect(self.canvas.clear)
        row.addWidget(clear)
        row.addStretch(1)
        save = QPushButton("保存为自定义图案")
        save.clicked.connect(self._save)
        row.addWidget(save)
        layout.addLayout(row)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _save(self) -> None:
        strokes = self.canvas.current_strokes()
        if not strokes:
            self.controller.show_hud("无法保存", "请先在画布上画一个图案")
            return
        self.controller.add_custom_gesture(self.name.text(), strokes)
        self.canvas.clear()
        self.name.clear()

    def refresh(self) -> None:
        # The recording canvas is intentionally independent from the saved
        # gesture list; nothing to refresh.
        return


class SettingsWindow(QMainWindow):
    def __init__(self, controller: MagicController) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("magicallyEncircle")
        self.setWindowIcon(app_icon())
        self.resize(720, 560)
        self.setMinimumSize(600, 450)
        self._qt_settings = QSettings("magicallyEncircle", "magicallyEncircle")
        self._positioned = False
        saved_geometry = self._qt_settings.value("settingsGeometry")
        if saved_geometry is not None:
            try:
                self.restoreGeometry(saved_geometry)
                self._positioned = True
            except Exception:
                pass

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(168)
        self.sidebar.setFrameShape(QFrame.NoFrame)
        self.sidebar.setStyleSheet(
            "QListWidget { background: rgba(128,128,138,18); border: none; padding-top: 8px; }"
            "QListWidget::item { padding: 10px 14px; }"
            "QListWidget::item:selected { background: rgba(74,140,255,55); border-radius: 6px; }"
        )
        self.stack = QStackedWidget()
        self.sections = [
            ("通用设置", GeneralSection(controller)),
            ("视觉风格", StyleSection(controller)),
            ("内置图案", BuiltInSection(controller)),
            ("自定义图案", CustomSection(controller)),
            ("记录图案", RecordSection(controller)),
        ]
        for title, widget in self.sections:
            item = QListWidgetItem(title)
            item.setSizeHint(QSize(0, 40))
            self.sidebar.addItem(item)
            self.stack.addWidget(widget)
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        controller.stateChanged.connect(self.refresh_all)

    def show_and_raise(self) -> None:
        self.refresh_all()
        if not self._positioned:
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                self.move(
                    available.x() + (available.width() - self.width()) // 2,
                    available.y() + (available.height() - self.height()) // 2,
                )
            self._positioned = True
        self.show()
        self.raise_()
        self.activateWindow()
        try:
            hwnd = int(self.winId())
            win32.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            win32.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def refresh_all(self) -> None:
        for _title_text, section in self.sections:
            section.refresh()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._qt_settings.setValue("settingsGeometry", self.saveGeometry())
        event.ignore()
        self.hide()
