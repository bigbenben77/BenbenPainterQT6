# menu_system.py（重构）
from PyQt6.QtWidgets import QMenuBar, QMenu
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import Qt


class MenuBar(QMenuBar):
    """菜单栏 - 优化版"""
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.main_window = controller.main_window if hasattr(controller, 'main_window') else None
        self._init_menus()
    
    def _init_menus(self):
        """初始化菜单"""
        self._create_file_menu()
        self._create_edit_menu()
        self._create_view_menu()
        self._create_help_menu()
    
    def _create_file_menu(self):
        """创建文件菜单"""
        file_menu = self.addMenu("&文件")
        
        actions = [
            ("新建", QKeySequence.StandardKey.New, self._menu_new_file),
            ("打开", QKeySequence.StandardKey.Open, self._menu_open_file),
            ("保存", QKeySequence.StandardKey.Save, self._menu_save_file),
            ("另存为...", QKeySequence.StandardKey.SaveAs, self._menu_save_file_as),
        ]
        
        for text, shortcut, callback in actions:
            action = self._create_action(text, shortcut, callback)
            file_menu.addAction(action)
        
        file_menu.addSeparator()
        
        exit_action = self._create_action("退出", QKeySequence.StandardKey.Quit, self._menu_exit_app)
        file_menu.addAction(exit_action)
    
    def _create_edit_menu(self):
        """创建编辑菜单"""
        edit_menu = self.addMenu("&编辑")
        
        actions = [
            ("撤销", QKeySequence.StandardKey.Undo, self._menu_undo),
            ("重做", QKeySequence.StandardKey.Redo, self._menu_redo),
        ]
        
        for text, shortcut, callback in actions:
            action = self._create_action(text, shortcut, callback)
            edit_menu.addAction(action)
        
        edit_menu.addSeparator()
        
        clipboard_actions = [
            ("剪切", QKeySequence.StandardKey.Cut, self._menu_cut),
            ("复制", QKeySequence.StandardKey.Copy, self._menu_copy),
            ("粘贴", QKeySequence.StandardKey.Paste, self._menu_paste),
        ]
        
        for text, shortcut, callback in clipboard_actions:
            action = self._create_action(text, shortcut, callback)
            edit_menu.addAction(action)
    
    def _create_view_menu(self):
        """创建视图菜单"""
        view_menu = self.addMenu("&视图")
        
        # 缩放操作
        zoom_actions = [
            ("放大", QKeySequence.StandardKey.ZoomIn, self._menu_zoom_in),
            ("缩小", QKeySequence.StandardKey.ZoomOut, self._menu_zoom_out),
            ("实际大小", "Ctrl+0", self._menu_reset_zoom),
        ]
        
        for text, shortcut, callback in zoom_actions:
            action = self._create_action(text, shortcut, callback)
            view_menu.addAction(action)
        
        view_menu.addSeparator()
        
        # 面板控制
        self._create_panel_actions(view_menu)
        
        view_menu.addSeparator()
        
        # 全屏
        fullscreen_action = QAction("全屏", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.triggered.connect(self._menu_fullscreen)
        view_menu.addAction(fullscreen_action)
    
    def _create_panel_actions(self, view_menu):
        """创建面板控制动作"""
        if not self.main_window:
            return
        
        # 工具面板
        self.tool_panel_action = QAction("工具面板", self)
        self.tool_panel_action.setCheckable(True)
        self.tool_panel_action.setChecked(True)
        self.tool_panel_action.triggered.connect(self._toggle_tool_panel)
        view_menu.addAction(self.tool_panel_action)
        
        # 属性面板
        self.property_panel_action = QAction("属性面板", self)
        self.property_panel_action.setCheckable(True)
        self.property_panel_action.setChecked(True)
        self.property_panel_action.triggered.connect(self._toggle_property_panel)
        view_menu.addAction(self.property_panel_action)
    
    def _create_help_menu(self):
        """创建帮助菜单"""
        help_menu = self.addMenu("&帮助")
        
        about_action = self._create_action("关于", None, self._menu_about)
        help_menu.addAction(about_action)
    
    def _create_action(self, text, shortcut, callback):
        """创建菜单项"""
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        if callback:
            action.triggered.connect(callback)
        return action
    
    # ===================== 菜单回调方法 =====================
    
    def _menu_new_file(self):
        """菜单新建文件"""
        if self.main_window:
            self.main_window.create_new_document()
    
    def _menu_open_file(self):
        """菜单打开文件"""
        if self.main_window:
            self.main_window.open_file()
    
    def _menu_save_file(self):
        """菜单保存文件"""
        if self.main_window:
            self.main_window.save_current_document()
    
    def _menu_save_file_as(self):
        """菜单另存为"""
        if self.main_window:
            self.main_window.save_file_as()
    
    def _menu_exit_app(self):
        """菜单退出应用"""
        if self.main_window:
            self.main_window.close()
    
    def _menu_undo(self):
        """菜单撤销"""
        if self.main_window:
            self.main_window.undo_action()
    
    def _menu_redo(self):
        """菜单重做"""
        if self.main_window:
            self.main_window.redo_action()
    
    def _menu_cut(self):
        """菜单剪切"""
        if self.main_window:
            self.main_window.cut_action()
    
    def _menu_copy(self):
        """菜单复制"""
        if self.main_window:
            self.main_window.copy_action()
    
    def _menu_paste(self):
        """菜单粘贴"""
        if self.main_window:
            self.main_window.paste_action()
    
    def _menu_zoom_in(self):
        """菜单放大"""
        if self.main_window:
            self.main_window.zoom_in_action()
    
    def _menu_zoom_out(self):
        """菜单缩小"""
        if self.main_window:
            self.main_window.zoom_out_action()
    
    def _menu_reset_zoom(self):
        """菜单重置缩放"""
        if self.main_window:
            self.main_window.reset_zoom_action()
    
    def _menu_fullscreen(self):
        """菜单全屏"""
        if self.main_window:
            self.main_window.toggle_fullscreen()
    
    def _menu_about(self):
        """菜单关于"""
        if self.main_window and hasattr(self.controller, 'about'):
            self.controller.about()
    
    # ===================== 面板控制方法 =====================
    
    def _toggle_tool_panel(self):
        """切换工具面板显示"""
        if not self.main_window:
            return
        
        is_checked = self.tool_panel_action.isChecked()
        
        if hasattr(self.main_window, 'left_dock'):
            if is_checked:
                self.main_window.left_dock.show()
            else:
                self.main_window.left_dock.hide()
        
        status = "显示" if is_checked else "隐藏"
        if hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit(f"{status}工具面板")
    
    def _toggle_property_panel(self):
        """切换属性面板显示"""
        if not self.main_window:
            return
        
        is_checked = self.property_panel_action.isChecked()
        
        if hasattr(self.main_window, 'right_dock'):
            if is_checked:
                self.main_window.right_dock.show()
            else:
                self.main_window.right_dock.hide()
        
        status = "显示" if is_checked else "隐藏"
        if hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit(f"{status}属性面板")
    
    def update_panel_visibility(self):
        """更新面板菜单项的勾选状态"""
        if not self.main_window:
            return
        
        # 更新工具面板勾选状态
        if hasattr(self, 'tool_panel_action') and hasattr(self.main_window, 'left_dock'):
            is_visible = not self.main_window.left_dock.isHidden()
            self.tool_panel_action.setChecked(is_visible)
        
        # 更新属性面板勾选状态
        if hasattr(self, 'property_panel_action') and hasattr(self.main_window, 'right_dock'):
            is_visible = not self.main_window.right_dock.isHidden()
            self.property_panel_action.setChecked(is_visible)