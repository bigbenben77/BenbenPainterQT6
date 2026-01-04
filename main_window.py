# main_window.py - 完整修复版（含透明色支持）
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QToolBar, QLabel, QStatusBar,
    QMdiArea, QMdiSubWindow, QMessageBox, QDockWidget, QPushButton, QSlider
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QPointF
from PyQt6.QtGui import QAction, QIcon, QPixmap, QKeySequence, QFont, QColor, QPainter, QPen, QBrush
from ui_components import ToolPanel, Canvas, PropertyPanel, LayerPanel, DARK_THEME_STYLE, ValueSlider
from menu_system import MenuBar
from controller import Controller


def create_toolbar_icon(text: str, size: int = 24) -> QIcon:
    """创建工具栏图标"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 设置字体
    font = QFont()
    font.setPointSize(12)
    painter.setFont(font)
    
    # 绘制文字
    painter.setPen(QPen(QColor(255, 255, 255)))  # 白色文字
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
    
    painter.end()
    return QIcon(pixmap)


class DocumentSubWindow(QMdiSubWindow):
    """文档子窗口"""
    
    about_to_close = pyqtSignal(object)  # 传递自身实例
    
    def closeEvent(self, close_event):
        """重写关闭事件"""
        if hasattr(self, 'controller') and self.controller.is_modified:
            reply = QMessageBox.question(
                self, '保存更改',
                "当前图像已修改,是否保存?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.controller.save_file()
                if self.controller.is_modified:  # 保存失败
                    close_event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                close_event.ignore()
                return
        
        # 调用父类关闭事件
        super().closeEvent(close_event)
        
        # 如果关闭被接受,发出信号
        if not close_event.isAccepted():
            return
        self.about_to_close.emit(self)


class MainWindow(QMainWindow):
    """主窗口 - 添加曲线工具快捷键处理"""
    
    def __init__(self, controller_instance=None):
        super().__init__()

        # 窗口设置
        self.setWindowTitle("笨笨画图 - 旗舰版 v3.0 - MDI")
        self.setGeometry(100, 100, 1400, 900)
        self.setStyleSheet(DARK_THEME_STYLE)

        # 初始化组件
        self._init_mdi_area()
        self._init_controller(controller_instance)
        self._init_menu_bar()
        self._init_status_bar()
        self._init_toolbar()
        self._init_dock_widgets()

        # 连接信号
        self.controller.status_updated.connect(self.update_status_bar)
        self.mdi_area.subWindowActivated.connect(self.on_subwindow_activated)

        # 状态变量
        self.document_counter = 0

        # 创建第一个文档
        self.create_new_document()

        # 设置焦点策略
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _init_mdi_area(self):
        """初始化 MDI 区域"""
        self.mdi_area = QMdiArea()
        self.mdi_area.setViewMode(QMdiArea.ViewMode.TabbedView)
        self.mdi_area.setTabsClosable(True)
        self.mdi_area.setTabsMovable(True)
        
        # 设置标签页样式
        tab_font = QFont()
        tab_font.setPointSize(9)
        
        self.mdi_area.setStyleSheet(f"""
            QMdiArea::tab-bar {{
                font: {tab_font.pointSize()}pt "{tab_font.family()}";
            }}
            QTabBar::tab {{
                min-width: 150px;
                max-width: 150px;
                height: 28px;
                padding: 4px 8px;
            }}
        """)
        
        self.setCentralWidget(self.mdi_area)

    def _init_controller(self, controller_instance):
        """初始化控制器"""
        self.controller = controller_instance if controller_instance else Controller(self)

    def _init_menu_bar(self):
        """初始化菜单栏"""
        self.menu_bar = MenuBar(self.controller)
        self.setMenuBar(self.menu_bar)

    def _init_status_bar(self):
        """初始化状态栏"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")
        
        # 坐标标签
        self.coords_label = QLabel("X: 0, Y: 0")
        self.status_bar.addPermanentWidget(self.coords_label)
        
        # 缩放标签
        self.zoom_label = QLabel("缩放: 100%")
        self.status_bar.addPermanentWidget(self.zoom_label)

    def _init_toolbar(self):
        """初始化工具栏"""
        self.top_toolbar = QToolBar("主工具栏")
        self.top_toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.top_toolbar)
        
        self._init_toolbar_actions()

    def _init_toolbar_actions(self):
        """初始化工具栏动作 - 移除所有快捷键以避免冲突"""
        # 工具栏动作配置 - 只保留工具选择快捷键（单键），移除所有Ctrl组合键
        toolbar_actions = [
            # 文件操作 - 移除快捷键，由菜单统一管理
            ("📄", "新建", None, self.create_new_document),
            ("📁", "打开", None, self.open_file),
            ("💾", "保存", None, self.save_current_document),
            ("⇨", "另存为", None, self.save_file_as),
            ("", "分隔符", None, None),
            
            # 编辑操作 - 移除快捷键，由菜单统一管理
            ("↶", "撤销", None, self.undo_action),
            ("↻", "重做", None, self.redo_action),
            ("", "分隔符", None, None),
            
            # 选择操作 - 移除快捷键，由菜单统一管理
            ("✔", "全选", None, self.select_all_action),
            ("✂", "剪切", None, self.cut_action),
            ("📋", "复制", None, self.copy_action),
            ("📌", "粘贴", None, self.paste_action),
            ("🗑", "删除", None, self.delete_action),
            ("", "分隔符", None, None),
            
            # 绘图工具 - 保留单键快捷键
            ("✎", "画笔", "B", lambda: self._select_tool('brush')),
            ("💨", "喷枪", "A", lambda: self._select_tool('airbrush')),
            ("🧽", "橡皮擦", "E", lambda: self._select_tool('eraser')),
            ("🪣", "填充", "F", lambda: self._select_tool('fill')),
            ("〜", "曲线", "V", lambda: self._select_tool('curve')),  # 添加曲线工具，使用V键
            ("", "分隔符", None, None),
            
            # 几何工具 - 保留单键快捷键
            ("╱", "直线", "L", lambda: self._select_tool('line')),
            ("▭", "矩形", "R", lambda: self._select_tool('rectangle')),
            ("◯", "椭圆", "O", lambda: self._select_tool('ellipse')),
            ("★", "五角星", "S", lambda: self._select_tool('star')),
            ("⬠", "多边形", "P", lambda: self._select_tool('polygon')),
            ("▬", "圆角矩形", "U", lambda: self._select_tool('rounded_rect')),
            ("", "分隔符", None, None),
            
            # 其他工具 - 保留单键快捷键
            ("T", "文字", "T", lambda: self._select_tool('text')),
            ("🧪", "取色", "I", lambda: self._select_tool('picker')),
            ("▢", "矩形选区", "M", lambda: self._select_tool('rect_select')),
            ("◯", "椭圆选区", "E", lambda: self._select_tool('ellipse_select')),
            ("⬠", "多边形选区", "P", lambda: self._select_tool('polygon_select')),
            ("", "分隔符", None, None),
            
            # 视图操作 - 移除快捷键，在keyPressEvent中处理
            ("➕", "放大", None, self.zoom_in_action),
            ("➖", "缩小", None, self.zoom_out_action),
            ("🔍", "实际大小", None, self.reset_zoom_action),
            ("⛶", "适应窗口", None, self.fit_to_window_action),
            ("🖥️", "全屏", None, self.toggle_fullscreen),
            ("", "分隔符", None, None),
            
            # 滤镜操作 - 移除快捷键，在keyPressEvent中处理
            ("🌫", "高斯模糊", None, lambda: self.apply_filter_action("高斯模糊")),
            ("💨", "运动模糊", None, lambda: self.apply_filter_action("运动模糊")),
            ("🔪", "锐化", None, lambda: self.apply_filter_action("锐化")),
            ("⬆", "浮雕", None, lambda: self.apply_filter_action("浮雕")),
            ("▪", "马赛克", None, lambda: self.apply_filter_action("马赛克")),
            ("", "分隔符", None, None),
            
            # 其他操作 - 移除快捷键
            ("🖨", "打印", None, self.print_action),
            ("👁", "打印预览", None, self.print_preview_action),
            ("", "分隔符", None, None),
            
            # 帮助操作
            ("❓", "帮助", None, self.help_action),
        ]
        
        # 创建工具栏动作
        for icon_text, text, shortcut, callback in toolbar_actions:
            if text == "分隔符":
                self.top_toolbar.addSeparator()
                continue
            
            action = self._create_toolbar_action(icon_text, text, shortcut, callback)
            self.top_toolbar.addAction(action)

    def _create_toolbar_action(self, icon_text, text, shortcut, callback):
        """创建工具栏动作 - 简化版"""
        # 创建图标
        icon = create_toolbar_icon(icon_text) if icon_text else QIcon()
        
        # 创建动作
        action = QAction(icon, text, self)
        
        # 只为工具选择设置快捷键(单键,不与Ctrl冲突)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setToolTip(f"{text} ({shortcut})")
        else:
            action.setToolTip(text)
        
        if callback:
            action.triggered.connect(callback)
        
        return action

    def _init_dock_widgets(self):
        """初始化停靠部件"""
        # 左侧工具面板
        self.tool_panel = ToolPanel(self.controller)
        self.left_dock = QDockWidget("工具面板", self)
        self.left_dock.setWidget(self.tool_panel)
        self.left_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)

        # 连接关闭事件
        self.left_dock.visibilityChanged.connect(self._on_left_dock_visibility_changed)

        # 右侧属性/图层面板
        right_panel_container = self._create_right_panel()
        self.right_dock = QDockWidget("属性面板", self)
        self.right_dock.setWidget(right_panel_container)
        self.right_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)

        # 连接关闭事件
        self.right_dock.visibilityChanged.connect(self._on_right_dock_visibility_changed)

    def _create_right_panel(self):
        """创建右侧面板"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 初始化面板
        self.property_panel = PropertyPanel(self.controller)
        self.layer_panel = LayerPanel(self.controller)
        
        # 添加到布局
        layout.addWidget(self.property_panel)
        layout.addWidget(self.layer_panel)
        
        # 设置拉伸因子
        layout.setStretch(0, 3)
        layout.setStretch(1, 1)
        
        return container

    def _select_tool(self, tool_id):
        """工具选择辅助方法"""
        # 先确保有活动文档
        controller = self.get_active_document()
        if controller:
            # 使用工具面板选择工具
            self.tool_panel.select_tool(tool_id)
            # 更新控制器
            controller.on_tool_selected(tool_id)

    # ===================== 键盘快捷键处理 =====================
    
    def keyPressEvent(self, event):
        """键盘按下事件处理 - 添加曲线工具C键处理"""
        # 先尝试让当前活动文档的控制器处理
        controller = self.get_active_document()
        if controller and hasattr(controller, 'on_key_press'):
            if controller.on_key_press(event):
                return

        # 特殊处理：如果文字工具正在编辑，阻止所有快捷键，只让文字工具处理
        if controller and controller.current_tool == 'text':
            if hasattr(controller.tool_manager, 'get_tool'):
                tool = controller.tool_manager.get_tool('text')
                if tool and hasattr(tool, 'is_editing') and tool.is_editing:
                    # 文字工具正在编辑，只让它处理键盘事件
                    if hasattr(tool, 'key_press') and tool.key_press(event):
                        event.accept()
                        return
                    # 如果文字工具没有处理，仍然阻止其他快捷键
                    return
        
        # 检查是否是菜单快捷键
        # 如果按下了Ctrl组合键，让菜单系统处理
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 检查是否是标准菜单快捷键
            standard_shortcuts = {
                Qt.Key.Key_N: "新建",
                Qt.Key.Key_O: "打开",
                Qt.Key.Key_S: "保存",
                Qt.Key.Key_Z: "撤销",
                Qt.Key.Key_Y: "重做",
                Qt.Key.Key_X: "剪切",
                Qt.Key.Key_C: "复制",
                Qt.Key.Key_V: "粘贴",
                Qt.Key.Key_A: "全选",
                Qt.Key.Key_P: "打印",
                Qt.Key.Key_F11: "全屏",
            }
            
            key = event.key()
            if key in standard_shortcuts:
                # 让菜单系统处理这些标准快捷键
                # 菜单动作会自动调用对应的主窗口方法
                super().keyPressEvent(event)
                return
        
        # 处理工具快捷键（单键）
        if event.modifiers() == Qt.KeyboardModifier.NoModifier:
            tool_shortcuts = {
                Qt.Key.Key_B: 'brush',
                Qt.Key.Key_E: 'eraser',
                Qt.Key.Key_A: 'airbrush',
                Qt.Key.Key_F: 'fill',
                Qt.Key.Key_V: 'curve',  # 曲线工具
                Qt.Key.Key_L: 'line',
                Qt.Key.Key_R: 'rectangle',
                Qt.Key.Key_O: 'ellipse',
                Qt.Key.Key_S: 'star',
                Qt.Key.Key_P: 'polygon',
                Qt.Key.Key_U: 'rounded_rect',
                Qt.Key.Key_T: 'text',    # 文字工具
                Qt.Key.Key_I: 'picker',  # 取色工具
                Qt.Key.Key_M: 'rect_select',  # 矩形选区工具
            }
            
            if event.key() in tool_shortcuts:
                self._select_tool(tool_shortcuts[event.key()])
                event.accept()
                return
            
            # C键特殊处理：如果当前是曲线工具，用于切换封闭/开放
            elif event.key() == Qt.Key.Key_C:
                if controller and controller.current_tool == 'curve':
                    # 按键事件已经通过控制器传递给工具
                    event.accept()
                    return
                else:
                    # 其他情况，作为普通快捷键处理
                    super().keyPressEvent(event)
                    return
            
            # 其他单键快捷键
            elif event.key() == Qt.Key.Key_Delete:
                self.delete_action()
                event.accept()
                return
            
            elif event.key() == Qt.Key.Key_Escape:
                self.escape_action()
                event.accept()
                return
            
            elif event.key() == Qt.Key.Key_F11:
                self.toggle_fullscreen()
                event.accept()
                return
            
            elif event.key() == Qt.Key.Key_F1:
                self.help_action()
                event.accept()
                return
        
        # Ctrl+特殊键处理（自定义快捷键，不与菜单冲突）
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 视图缩放快捷键（不是标准菜单快捷键的）
            if event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
                self.zoom_in_action()
                event.accept()
                return
            
            elif event.key() == Qt.Key.Key_Minus:
                self.zoom_out_action()
                event.accept()
                return
            
            elif event.key() == Qt.Key.Key_0:
                self.reset_zoom_action()
                event.accept()
                return
            
            elif event.key() == Qt.Key.Key_1:
                self.fit_to_window_action()
                event.accept()
                return
            
            # 选区操作快捷键（补充菜单的快捷键）
            elif event.key() == Qt.Key.Key_C:  # Ctrl+C 复制选区
                if self.execute_on_active_document('copy_selection'):
                    event.accept()
                    return
            
            elif event.key() == Qt.Key.Key_X:  # Ctrl+X 剪切选区
                if self.execute_on_active_document('cut_selection'):
                    event.accept()
                    return
            
            elif event.key() == Qt.Key.Key_V:  # Ctrl+V 粘贴选区
                if self.execute_on_active_document('paste_selection'):
                    event.accept()
                    return
            
            # 滤镜快捷键
            elif event.key() == Qt.Key.Key_G:
                self.apply_filter_action("高斯模糊")
                event.accept()
                return
            
            elif event.key() == Qt.Key.Key_M:
                self.apply_filter_action("运动模糊")
                event.accept()
                return
            
            elif event.key() == Qt.Key.Key_K:
                self.apply_filter_action("马赛克")
                event.accept()
                return
        
        # 传递给父类处理（让菜单快捷键工作）
        super().keyPressEvent(event)

    # ===================== 文档管理 =====================
    
    def create_new_document(self):
        """创建新文档"""
        self.document_counter += 1
        doc_name = f"未命名-{self.document_counter}"
        
        # 创建文档控制器
        doc_controller = Controller(self)
        
        # 创建子窗口（先创建子窗口）
        sub_window = DocumentSubWindow()
        sub_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # 创建画布，传递子窗口作为 parent
        canvas = Canvas(doc_controller, sub_window)
        
        # 设置子窗口的widget
        sub_window.setWidget(canvas)
        sub_window.setWindowTitle(doc_name)
        
        # 添加子窗口
        self.mdi_area.addSubWindow(sub_window)
        
        # 保存引用
        sub_window.canvas = canvas
        sub_window.controller = doc_controller
        
        # 连接信号
        doc_controller.connect_signals()
        doc_controller.status_updated.connect(self.update_status_bar)
        sub_window.about_to_close.connect(self.on_subwindow_closed)
        
        # 激活子窗口
        self.mdi_area.setActiveSubWindow(sub_window)
        
        # 初始化新文档
        doc_controller.new_file()
        
        # 启用面板并选择默认工具
        self.enable_panels()
        self.tool_panel.select_tool('brush')
        
        self.status_bar.showMessage(f"已创建新文档: {doc_name}")
        sub_window.show()  # 最后显示窗口

    def get_active_document(self):
        """获取当前活动文档"""
        sub_window = self.mdi_area.activeSubWindow()
        if sub_window and hasattr(sub_window, 'controller'):
            return sub_window.controller
        return None

    def execute_on_active_document(self, method_name, *args):
        """在当前活动文档上执行方法"""
        controller = self.get_active_document()
        if controller and hasattr(controller, method_name):
            method = getattr(controller, method_name)
            method(*args)
            return True
        return False

    # ===================== 文件操作 =====================
    
    def save_current_document(self):
        """保存当前文档"""
        if self.execute_on_active_document('save_file'):
            # 更新窗口标题
            sub_window = self.mdi_area.activeSubWindow()
            if sub_window and hasattr(sub_window, 'controller'):
                controller = sub_window.controller
                if controller.image_path:
                    base_name = controller.image_path.split('/')[-1]
                    sub_window.setWindowTitle(base_name)
            self.status_bar.showMessage("文档已保存")

    def open_file(self):
        """打开文件"""
        controller = self.get_active_document()
        if controller:
            controller.open_file()
        else:
            # 如果没有活动窗口,创建新文档并打开
            self.create_new_document()
            self.execute_on_active_document('open_file')

    def save_file_as(self):
        """另存为"""
        if self.execute_on_active_document('save_file_as'):
            # 更新窗口标题
            sub_window = self.mdi_area.activeSubWindow()
            if sub_window and hasattr(sub_window, 'controller'):
                controller = sub_window.controller
                if controller.image_path:
                    base_name = controller.image_path.split('/')[-1]
                    sub_window.setWindowTitle(base_name)

    # ===================== 编辑操作 =====================
    
    def undo_action(self):
        """撤销"""
        if self.execute_on_active_document('undo'):
            self.status_bar.showMessage("已撤销操作")

    def redo_action(self):
        """重做"""
        if self.execute_on_active_document('redo'):
            self.status_bar.showMessage("已重做操作")

    def cut_action(self):
        """剪切"""
        if self.execute_on_active_document('cut'):
            self.status_bar.showMessage("剪切选区内容")

    def copy_action(self):
        """复制"""
        if self.execute_on_active_document('copy'):
            self.status_bar.showMessage("复制选区内容到剪贴板")

    def paste_action(self):
        """粘贴"""
        if self.execute_on_active_document('paste'):
            self.status_bar.showMessage("粘贴剪贴板内容")

    def select_all_action(self):
        """全选(暂未实现)"""
        if self.execute_on_active_document('select_all'):
            pass
        else:
            self.status_bar.showMessage("全选功能暂未实现")

    def delete_action(self):
        """删除"""
        # 先尝试删除选区内容
        if self.execute_on_active_document('delete_selection_shortcut'):
            self.status_bar.showMessage("删除选区内容")
        else:
            # 如果没有选区，显示消息
            self.status_bar.showMessage("没有选中内容可删除")

    # ===================== 视图操作 =====================
    
    def zoom_in_action(self):
        """放大"""
        if self.execute_on_active_document('zoom_in'):
            self.status_bar.showMessage("放大视图")

    def zoom_out_action(self):
        """缩小"""
        if self.execute_on_active_document('zoom_out'):
            self.status_bar.showMessage("缩小视图")

    def reset_zoom_action(self):
        """重置缩放"""
        if self.execute_on_active_document('reset_zoom'):
            self.status_bar.showMessage("重置缩放")

    def fit_to_window_action(self):
        """适应窗口大小"""
        controller = self.get_active_document()
        if controller and controller.canvas:
            controller.canvas.fit_to_window()
            self.status_bar.showMessage("适应窗口大小")

    def toggle_fullscreen(self):
        """切换全屏模式"""
        if self.isFullScreen():
            self.showNormal()
            self.status_bar.showMessage("退出全屏模式")
        else:
            self.showFullScreen()
            self.status_bar.showMessage("进入全屏模式")

    # ===================== 滤镜操作 =====================
    
    def apply_filter_action(self, filter_name):
        """应用滤镜"""
        if self.execute_on_active_document('apply_filter', filter_name):
            self.status_bar.showMessage(f"已应用滤镜: {filter_name}")

    # ===================== 新增功能操作 =====================
    
    def escape_action(self):
        """取消/退出当前操作"""
        controller = self.get_active_document()
        if controller:
            # 清除临时预览
            if hasattr(controller, 'temp_pixmap'):
                controller.temp_pixmap = None
                if controller.canvas:
                    controller.canvas.update()
            
            # 取消当前工具操作
            if controller.current_tool and controller.tool_manager:
                tool = controller.tool_manager.get_tool(controller.current_tool)
                if tool and hasattr(tool, 'cancel'):
                    tool.cancel()
            
            self.status_bar.showMessage("取消当前操作")
        else:
            self.status_bar.showMessage("无活动文档")

    def help_action(self):
        """显示帮助"""
        help_text = """笨笨画图 - 快捷键帮助

文件操作:
  Ctrl+N      新建文档
  Ctrl+O      打开文件
  Ctrl+S      保存当前文档
  Ctrl+Shift+S 另存为
  Ctrl+P      打印

编辑操作:
  Ctrl+Z      撤销
  Ctrl+Y      重做
  Ctrl+X      剪切选区
  Ctrl+C      复制选区
  Ctrl+V      粘贴选区
  Ctrl+A      全选
  Delete      删除选区内容

视图操作:
  Ctrl++      放大视图
  Ctrl+-      缩小视图
  Ctrl+0      实际大小
  Ctrl+1      适应窗口
  F11         全屏切换

工具选择:
  B           画笔工具
  E           橡皮擦工具
  A           喷枪工具
  F           填充工具
  V           曲线工具 (Catmull-Rom样条)
  L           直线工具
  R           矩形工具
  O           椭圆工具
  S           五角星工具
  P           多边形工具
  U           圆角矩形工具
  T           文字工具
  I           取色工具
  M           矩形选区工具
  E           椭圆选区工具
  P           多边形选区工具

透明色使用:
  左键点击透明色按钮   设置前景色为透明
  右键点击透明色按钮   设置背景色为透明
  选择透明色后，颜色按钮显示为棋盘格

曲线工具:
  左键单击    用前景色绘制控制点
  右键单击    用背景色绘制控制点，或结束绘制
  C键        切换封闭/开放曲线
  Esc键      取消绘制

多边形选区工具:
  左键单击    用直线绘制多边形
  右键单击    切换曲线/直线模式，或完成绘制
  拖动控制点  调整选区

选区工具:
  左键拖动     创建/移动选区
  Shift+拖动   创建正方形/圆形选区
  拖动右下角   缩放选区
  拖动右上角   旋转选区
  Enter键     提交选区
  Esc键       取消选区

取色工具:
  左键单击    取色为前景色
  右键单击    取色为背景色

文字工具:
  左键单击    创建文字
  双击文字    重新编辑
  右键单击    提交文字
  Enter键     提交文字
  Esc键       取消编辑
  拖动控制点  移动、缩放、旋转文字

选区操作:
  左键拖动     创建/移动选区
  Shift+拖动   创建正方形/圆形选区
  拖动右下角   缩放选区
  拖动右上角   旋转选区
  Ctrl+C      复制选区内容
  Ctrl+X      剪切选区内容
  Ctrl+V      粘贴剪贴板内容
  Delete      删除选区内容
  Enter键     提交选区

几何工具技巧:
  按住 Shift   约束为正方形/圆形/45度角
  按住 Ctrl    填充模式(前景色边框+背景色填充)
  右键绘制     使用背景色(或填充时前景色)

图像调整:
  亮度滑块     调整图像亮度 (-100 到 +100)
  对比度滑块   调整图像对比度 (-100 到 +100)
  饱和度滑块   调整图像饱和度 (-100 到 +100)
  重置按钮     重置所有调整

滤镜操作:
  Ctrl+G      高斯模糊
  Ctrl+M      运动模糊
  Ctrl+K      马赛克

其他:
  F1          显示帮助
  Esc         取消当前操作"""
        
        QMessageBox.information(self, "快捷键帮助", help_text)

    def print_action(self):
        """打印"""
        if self.execute_on_active_document('print_document'):
            pass
        else:
            self.status_bar.showMessage("打印功能暂未实现")

    def print_preview_action(self):
        """打印预览"""
        if self.execute_on_active_document('print_preview'):
            pass
        else:
            self.status_bar.showMessage("打印预览功能暂未实现")

    # ===================== 事件处理 =====================
    
    def on_subwindow_activated(self, sub_window):
        """子窗口激活事件"""
        if sub_window and hasattr(sub_window, 'controller'):
            # 更新控制器引用
            self.controller = sub_window.controller
            
            # 更新面板控制器引用
            self._update_panel_controllers()
            
            # 选择当前文档的工具
            current_tool = self.controller.current_tool or 'brush'
            self.tool_panel.select_tool(current_tool)
            
            # 确保画布获得焦点，以便接收键盘事件
            if hasattr(sub_window, 'canvas') and sub_window.canvas:
                sub_window.canvas.setFocus()
            
            # 更新状态栏
            self.status_bar.showMessage(f"已激活: {sub_window.windowTitle()}")
            
            # 启用面板并更新撤销/重做按钮状态
            self.enable_panels()
            
            # 更新撤销/重做按钮状态
            if hasattr(self.controller, '_update_undo_redo_buttons'):
                self.controller._update_undo_redo_buttons()
            
            # 更新缩放标签
            if hasattr(sub_window, 'canvas') and sub_window.canvas:
                self.update_zoom_label(sub_window.canvas.scale_factor)
            
            # 更新菜单面板勾选状态
            if hasattr(self, 'menu_bar') and hasattr(self.menu_bar, 'update_panel_visibility'):
                self.menu_bar.update_panel_visibility()
        else:
            self.check_and_disable_panels()
            self.status_bar.showMessage("无活动文档")

    def _update_panel_controllers(self):
        """更新面板控制器引用"""
        if hasattr(self, 'tool_panel'):
            self.tool_panel.controller = self.controller
            
        if hasattr(self, 'property_panel'):
            self.property_panel.controller = self.controller
            
        if hasattr(self, 'layer_panel'):
            self.layer_panel.controller = self.controller

    def on_subwindow_closed(self, sub_window_instance):
        """子窗口关闭事件"""
        QTimer.singleShot(0, self.check_and_disable_panels)

    def update_status_bar(self, message: str):
        """更新状态栏"""
        self.status_bar.showMessage(message)

    def update_coords_label(self, x: int, y: int):
        """更新坐标标签"""
        self.coords_label.setText(f"X: {x}, Y: {y}")

    def update_zoom_label(self, zoom_factor: float):
        """更新缩放标签"""
        self.zoom_label.setText(f"缩放: {zoom_factor*100:.0f}%")

    # ===================== 面板控制 =====================
    
    def enable_panels(self):
        """启用所有面板"""
        # 工具面板
        for child in self.tool_panel.findChildren(QPushButton):
            child.setEnabled(True)
        
        # 属性面板
        for child in self.property_panel.findChildren((ValueSlider, QPushButton)):
            child.setEnabled(True)
        
        # 图层面板
        for child in self.layer_panel.findChildren(QPushButton):
            child.setEnabled(True)

    def check_and_disable_panels(self):
        """检查并禁用面板"""
        if self.mdi_area.subWindowList():
            return
        
        # 禁用工具面板
        for child in self.tool_panel.findChildren(QPushButton):
            child.setEnabled(False)
        
        # 禁用属性面板
        for child in self.property_panel.findChildren((ValueSlider, QPushButton)):
            child.setEnabled(False)
        
        # 清空并禁用图层面板
        self.layer_panel.layer_list.clear()
        for child in self.layer_panel.findChildren(QPushButton):
            child.setEnabled(False)

    # ===================== 停靠面板可见性控制 =====================
    
    def _on_left_dock_visibility_changed(self, visible):
        """左侧面板可见性改变"""
        # 更新菜单勾选状态
        if hasattr(self, 'menu_bar') and hasattr(self.menu_bar, 'tool_panel_action'):
            self.menu_bar.tool_panel_action.setChecked(visible)
        
        status = "显示" if visible else "隐藏"
        self.status_bar.showMessage(f"{status}工具面板")

    def _on_right_dock_visibility_changed(self, visible):
        """右侧面板可见性改变"""
        # 更新菜单勾选状态
        if hasattr(self, 'menu_bar') and hasattr(self.menu_bar, 'property_panel_action'):
            self.menu_bar.property_panel_action.setChecked(visible)
        
        status = "显示" if visible else "隐藏"
        self.status_bar.showMessage(f"{status}属性面板")

    # ===================== 窗口事件 =====================
    
    def closeEvent(self, event):
        """关闭事件"""
        # 检查所有子窗口是否需要保存
        sub_windows = self.mdi_area.subWindowList()
        
        for sub_window in sub_windows:
            if hasattr(sub_window, 'controller') and sub_window.controller.is_modified:
                # 激活该子窗口
                self.mdi_area.setActiveSubWindow(sub_window)
                
                # 触发关闭逻辑
                sub_window.close()
                
                # 如果子窗口仍然存在(用户点击了取消)
                if sub_window in self.mdi_area.subWindowList():
                    event.ignore()
                    return
        
        # 所有子窗口已处理完毕
        event.accept()