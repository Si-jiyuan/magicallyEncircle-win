"""System tray icon and dynamic menu."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Qt
from PySide6.QtGui import QAction, QCursor, QDesktopServices, QIcon
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMenu, QMessageBox, QSystemTrayIcon

from ..config import LOG_DIR
from ..controller import MagicController
from ..gesture.builtin import BUILT_INS
from ..platform_support.overlay import STYLE_TITLES
from .theme import app_icon, preview_pixmap


class TrayController(QObject):
    def __init__(self, controller: MagicController, open_settings) -> None:
        super().__init__()
        self.controller = controller
        self.open_settings = open_settings
        self.tray = QSystemTrayIcon(app_icon())
        self.tray.setToolTip("magicallyEncircle")
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.rebuild)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()
        controller.stateChanged.connect(self._update_tooltip)
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        state = "已启用" if self.controller.settings.enabled else "已停用"
        self.tray.setToolTip(f"magicallyEncircle · {state}")
        self.tray.setIcon(app_icon())

    def _activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.menu.popup(QCursor.pos())

    def _action(self, menu: QMenu, title: str, callback=None, *, checkable: bool = False, checked: bool = False):
        action = QAction(title, menu)
        action.setCheckable(checkable)
        action.setChecked(checked)
        if callback is not None:
            action.triggered.connect(lambda _checked=False: callback())
        menu.addAction(action)
        return action

    def rebuild(self) -> None:
        self.menu.clear()
        controller = self.controller
        settings = controller.settings

        self._action(
            self.menu,
            "停用魔法线条" if settings.enabled else "启用魔法线条",
            controller.toggle_enabled,
        )
        self.menu.addSeparator()

        style_menu = self.menu.addMenu("视觉风格")
        for key, title in STYLE_TITLES.items():
            action = QAction(title, style_menu)
            action.setCheckable(True)
            action.setChecked(settings.style == key)
            action.triggered.connect(lambda _checked=False, name=key: controller.set_style(name))
            style_menu.addAction(action)

        self._action(
            self.menu,
            "隐藏识别反馈" if settings.show_hud else "显示识别反馈",
            controller.toggle_hud,
        )

        built_in_menu = self.menu.addMenu("内置图案")
        for built_in in BUILT_INS:
            item = built_in_menu.addMenu(f"{built_in.title}（{controller.builtin_description(built_in.id)}）")
            has_sample = controller.override_count(built_in.id) > 0 or bool(built_in.default_samples)
            self._action(item, "播放图案", lambda ident=built_in.id: controller.play_builtin(ident))
            item.actions()[-1].setEnabled(has_sample)
            self._action(item, "录制图案…", lambda ident=built_in.id: controller.begin_recording_builtin_override(ident))
            if built_in.action != "close":
                if controller.pending_key_target == ("builtin", built_in.id):
                    waiting = item.addAction("等待按键…（Esc 取消）")
                    waiting.setEnabled(False)
                    self._action(item, "取消绑定", controller.cancel_key_capture)
                else:
                    self._action(
                        item,
                        "设置快捷键…",
                        lambda ident=built_in.id: controller.begin_key_capture(("builtin", ident)),
                    )
            self._action(
                item,
                "恢复默认",
                lambda ident=built_in.id: controller.reset_builtin(ident),
            )
            item.actions()[-1].setEnabled(
                controller.override_count(built_in.id) > 0
                or controller.has_builtin_shortcut_override(built_in.id)
            )
        built_in_menu.addSeparator()
        note = built_in_menu.addAction("画闭环快松=复制文本 / 按住1秒=截图")
        note.setEnabled(False)
        self._action(built_in_menu, "全部恢复默认图案", controller.reset_all_builtin_overrides)

        self.menu.addSeparator()
        if controller.is_recording:
            self._action(self.menu, "取消记录", controller.cancel_recording)
        else:
            self._action(self.menu, "记录新图案", controller.begin_recording_gesture)

        if controller.custom_gestures:
            custom_menu = self.menu.addMenu("自定义图案")
            for gesture in controller.custom_gestures:
                icon = QIcon(preview_pixmap(gesture.strokes, 22))
                submenu = custom_menu.addMenu(icon, gesture.menu_title)
                self._action(submenu, "播放图案", lambda ident=gesture.id: controller.play_custom_gesture(ident))
                self._action(submenu, "重命名…", lambda ident=gesture.id: self._rename(ident))
                if controller.pending_key_target == ("custom", gesture.id):
                    waiting = submenu.addAction("等待按键…（Esc 取消）")
                    waiting.setEnabled(False)
                    self._action(submenu, "取消绑定", controller.cancel_key_capture)
                else:
                    self._action(
                        submenu,
                        "设置快捷键…",
                        lambda ident=gesture.id: controller.begin_key_capture(("custom", ident)),
                    )
                self._action(submenu, "绑定 App…", lambda ident=gesture.id: self._bind_app(ident))
                self._action(submenu, "清除绑定", lambda ident=gesture.id: controller.clear_custom_binding(ident))
                submenu.addSeparator()
                self._action(submenu, "删除", lambda ident=gesture.id: self._delete(ident))

        self.menu.addSeparator()
        self._action(self.menu, "导出自定义图案…", lambda: controller.export_gestures(None))
        self._action(self.menu, "导入自定义图案…", lambda: controller.import_gestures(None))
        self.menu.addSeparator()
        self._action(self.menu, "设置…", self.open_settings)
        self._action(self.menu, "打开日志文件夹", self._open_logs)
        self._action(self.menu, "检查更新…", controller.check_for_updates)
        self.menu.addSeparator()
        self._action(self.menu, "退出", self._quit)

    def _rename(self, identifier: str) -> None:
        gesture = next((g for g in self.controller.custom_gestures if g.id == identifier), None)
        if gesture is None:
            return
        name, ok = QInputDialog.getText(None, "重命名图案", "名称：", text=gesture.name)
        if ok:
            self.controller.rename_gesture(identifier, name)

    def _bind_app(self, identifier: str) -> None:
        paths, _filter = QFileDialog.getOpenFileNames(
            None,
            "选择要打开的 App（可多选）",
            "",
            "Applications (*.exe *.lnk);;All files (*)",
        )
        if paths:
            self.controller.set_custom_apps(identifier, paths)

    def _delete(self, identifier: str) -> None:
        gesture = next((g for g in self.controller.custom_gestures if g.id == identifier), None)
        if gesture is None:
            return
        answer = QMessageBox.question(
            None,
            "删除图案",
            f"确定删除「{gesture.name}」吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.controller.delete_gesture(identifier)

    def _quit(self) -> None:
        from PySide6.QtWidgets import QApplication

        instance = QApplication.instance()
        if instance is not None:
            instance.exit(0)

    @staticmethod
    def _open_logs() -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR)))

    def hide(self) -> None:
        self.tray.hide()
