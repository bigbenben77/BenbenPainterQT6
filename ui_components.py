# ui_components.py - GPU加速优化版（修复多重继承问题，完整透明色支持）
import sys
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QGridLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy,
    QHBoxLayout, QSlider, QListWidget, QColorDialog, QInputDialog, QSpinBox, QWidget,
    QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QTimer, QPointF, QRectF
from PyQt6.QtGui import QColor, QPixmap, QPainter, QPen, QBrush, QFont, QImage, QPolygonF, QTransform
from functools import lru_cache
import math

# 强制使用CPU渲染以避免OpenGL兼容性问题
USE_OPENGL = False
print("[INFO] Using CPU rendering for compatibility")

# ===================== 通用工具函数 =====================
class CanvasCommon:
    """Canvas通用功能（不用于继承，只包含工具方法）"""
    
    @staticmethod
    def draw_checkerboard(painter, width, height, checker_cache):
        """绘制棋盘格背景"""
        cache_key = f"{width}_{height}"
        
        if cache_key not in checker_cache:
            # 创建棋盘格纹理
            checker_size = 16
            texture_w = math.ceil(width / checker_size) * checker_size
            texture_h = math.ceil(height / checker_size) * checker_size
            pixmap = QPixmap(texture_w, texture_h)
            pixmap.fill(QColor(200, 200, 200))
            
            texture_painter = QPainter(pixmap)
            texture_painter.setBrush(QBrush(QColor(220, 220, 220)))
            
            for y in range(0, texture_h, checker_size * 2):
                for x in range(0, texture_w, checker_size * 2):
                    texture_painter.drawRect(x, y, checker_size, checker_size)
                    if x + checker_size < texture_w and y + checker_size < texture_h:
                        texture_painter.drawRect(x + checker_size, y + checker_size, checker_size, checker_size)
            
            texture_painter.end()
            checker_cache[cache_key] = pixmap
        
        painter.drawTiledPixmap(0, 0, width, height, checker_cache[cache_key])

if USE_OPENGL:
    # GPU加速版本
    class Canvas(QOpenGLWidget):
        """GPU加速Canvas"""
        
        def __init__(self, controller, parent=None):
            super().__init__(parent)
            
            # 配置OpenGL
            fmt = QSurfaceFormat()
            fmt.setSamples(4)  # 4x MSAA
            self.setFormat(fmt)
            
            self.controller = controller
            self.controller.canvas = self
            
            # 状态变量
            self.scale_factor = 1.0
            self.pixmap = None
            self.draw_buffer = []
            
            # 缓存
            self._checker_cache = {}
            
            # 初始化
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setStyleSheet("background-color: #2d2d2d;")
            
            # 定时器
            self.buffer_timer = QTimer(self)
            self.buffer_timer.timeout.connect(self._flush_buffer)
            self.buffer_timer.setInterval(16)
        
        # OpenGL方法
        def initializeGL(self):
            """初始化OpenGL"""
            pass
        
        def resizeGL(self, w: int, h: int):
            """调整大小"""
            self.fit_to_window()
        
        def paintGL(self):
            """OpenGL绘制"""
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            
            painter.fillRect(self.rect(), QColor(45, 45, 45))
            
            self._draw_main_image(painter)
            self._draw_temp(painter)
            
            painter.end()
        
        # 绘制方法
        def _draw_main_image(self, painter):
            """绘制主图像"""
            if not self.controller or not self.controller.current_image:
                return
            
            if not self.pixmap or self.pixmap.size() != self.controller.current_image.size():
                self.pixmap = QPixmap.fromImage(self.controller.current_image)
            
            if self.pixmap.width() <= 0 or self.pixmap.height() <= 0 or self.scale_factor <= 0:
                return
            
            scaled_width = int(self.pixmap.width() * self.scale_factor)
            scaled_height = int(self.pixmap.height() * self.scale_factor)
            image_rect = QRect(0, 0, scaled_width, scaled_height)
            
            painter.save()
            painter.setClipRect(image_rect)
            CanvasCommon.draw_checkerboard(painter, scaled_width, scaled_height, self._checker_cache)
            painter.restore()
            
            scaled_pixmap = self.pixmap.scaled(
                scaled_width, scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(0, 0, scaled_pixmap)
        
        def _draw_temp(self, painter):
            """绘制临时预览"""
            if (not self.controller or not hasattr(self.controller, 'temp_pixmap') or 
                not self.controller.temp_pixmap):
                return
            
            temp = self.controller.temp_pixmap
            if temp.width() <= 0 or temp.height() <= 0 or self.scale_factor <= 0:
                return
            
            temp_scaled = temp.scaled(
                int(temp.width() * self.scale_factor),
                int(temp.height() * self.scale_factor),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(0, 0, temp_scaled)
        
        # 坐标转换
        def map_to_image(self, point):
            """将Canvas坐标映射到图像坐标"""
            if self.scale_factor > 0:
                return point / self.scale_factor
            return point
        
        # 视图控制
        def fit_to_window(self):
            """自适应窗口大小"""
            if not self.controller or not self.controller.current_image:
                return
            
            self.pixmap = QPixmap.fromImage(self.controller.current_image)
            
            if self.pixmap.width() > 0 and self.pixmap.height() > 0:
                self.scale_factor = min(
                    self.width() / self.pixmap.width(),
                    self.height() / self.pixmap.height()
                )
                self.scale_factor = max(self.scale_factor, 0.1)
            
            self.update()
        
        # 事件处理
        def mousePressEvent(self, event):
            """鼠标按下事件"""
            self.setFocus()
            pos = self.map_to_image(event.position())
            int_pos = QPointF(int(pos.x()), int(pos.y()))
            
            if self.controller:
                self.controller.on_canvas_mouse_press(event, int_pos)
            self.buffer_timer.start()
        
        def mouseMoveEvent(self, event):
            """鼠标移动事件"""
            pos = self.map_to_image(event.position())
            int_pos = QPointF(int(pos.x()), int(pos.y()))
            
            if self.controller and self.controller.main_window:
                self.controller.main_window.update_coords_label(int(pos.x()), int(pos.y()))
            
            if self.controller:
                self.controller.on_canvas_mouse_move(event, int_pos)
        
        def mouseReleaseEvent(self, event):
            """鼠标释放事件"""
            pos = self.map_to_image(event.position())
            int_pos = QPointF(int(pos.x()), int(pos.y()))
            
            if self.controller:
                self.controller.on_canvas_mouse_release(event, int_pos)
            
            self.buffer_timer.stop()
            self._flush_buffer()
        
        def wheelEvent(self, event):
            """滚轮缩放事件"""
            if self.controller:
                if event.angleDelta().y() > 0:
                    self.controller.zoom_in()
                else:
                    self.controller.zoom_out()
            event.accept()
        
        def resizeEvent(self, event):
            """窗口大小变化事件"""
            super().resizeEvent(event)
            self.fit_to_window()
        
        # 工具方法
        def _flush_buffer(self):
            """刷新绘制缓冲区"""
            if self.draw_buffer:
                self.draw_buffer.clear()
                self.update()
        
        def clear_cache(self):
            """清除纹理缓存"""
            self._checker_cache.clear()
        
        def setMinimumSize(self, width, height):
            """设置最小尺寸"""
            super().setMinimumSize(width, height)

else:
    # CPU回退版本
    class Canvas(QFrame):
        """CPU渲染Canvas"""
        
        def __init__(self, controller, parent=None):
            super().__init__(parent)
            self.controller = controller
            self.controller.canvas = self
            
            # 状态变量
            self.scale_factor = 1.0
            self.pixmap = None
            self.draw_buffer = []
            
            # 缓存
            self._checker_cache = {}
            
            # 初始化
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setStyleSheet("background-color: #2d2d2d;")
            self.setMinimumSize(400, 300)
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            
            # 定时器
            self.buffer_timer = QTimer(self)
            self.buffer_timer.timeout.connect(self._flush_buffer)
            self.buffer_timer.setInterval(16)
        
        # 绘制方法
        def paintEvent(self, event):
            """CPU绘制"""
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            painter.fillRect(self.rect(), QColor("#2d2d2d"))

            self._draw_main_image(painter)
            self._draw_temp(painter)

        def _draw_main_image(self, painter):
            """绘制主图像"""
            if not self.controller or not self.controller.current_image:
                return
            
            if not self.pixmap or self.pixmap.size() != self.controller.current_image.size():
                self.pixmap = QPixmap.fromImage(self.controller.current_image)
            
            if self.pixmap.width() <= 0 or self.pixmap.height() <= 0 or self.scale_factor <= 0:
                return
            
            scaled_width = int(self.pixmap.width() * self.scale_factor)
            scaled_height = int(self.pixmap.height() * self.scale_factor)
            image_rect = QRect(0, 0, scaled_width, scaled_height)
            
            painter.save()
            painter.setClipRect(image_rect)
            CanvasCommon.draw_checkerboard(painter, scaled_width, scaled_height, self._checker_cache)
            painter.restore()
            
            scaled_pixmap = self.pixmap.scaled(
                scaled_width, scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(0, 0, scaled_pixmap)
        
        def _draw_temp(self, painter):
            """绘制临时预览"""
            if (not self.controller or not hasattr(self.controller, 'temp_pixmap') or 
                not self.controller.temp_pixmap):
                return
            
            temp = self.controller.temp_pixmap
            if temp.width() <= 0 or temp.height() <= 0 or self.scale_factor <= 0:
                return
            
            temp_scaled = temp.scaled(
                int(temp.width() * self.scale_factor),
                int(temp.height() * self.scale_factor),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(0, 0, temp_scaled)
        
        # 坐标转换
        def map_to_image(self, point):
            """将Canvas坐标映射到图像坐标"""
            if self.scale_factor > 0:
                return point / self.scale_factor
            return point
        
        # 视图控制
        def fit_to_window(self):
            """自适应窗口大小"""
            if not self.controller or not self.controller.current_image:
                return
            
            self.pixmap = QPixmap.fromImage(self.controller.current_image)
            
            if self.pixmap.width() > 0 and self.pixmap.height() > 0:
                self.scale_factor = min(
                    self.width() / self.pixmap.width(),
                    self.height() / self.pixmap.height()
                )
                self.scale_factor = max(self.scale_factor, 0.1)
            
            self.update()
        
        # 事件处理
        def mousePressEvent(self, event):
            """鼠标按下事件"""
            self.setFocus()
            image_pos = self.map_to_image(event.position())
            int_pos = QPointF(int(image_pos.x()), int(image_pos.y()))
            
            if self.controller:
                self.controller.on_canvas_mouse_press(event, int_pos)
            self.buffer_timer.start()
        
        def mouseMoveEvent(self, event):
            """鼠标移动事件"""
            image_pos = self.map_to_image(event.position())
            int_pos = QPointF(int(image_pos.x()), int(image_pos.y()))
            
            if self.controller and self.controller.main_window and hasattr(self.controller.main_window, 'update_coords_label'):
                self.controller.main_window.update_coords_label(int(image_pos.x()), int(image_pos.y()))
            
            if self.controller:
                self.controller.on_canvas_mouse_move(event, int_pos)
        
        def mouseReleaseEvent(self, event):
            """鼠标释放事件"""
            image_pos = self.map_to_image(event.position())
            int_pos = QPointF(int(image_pos.x()), int(image_pos.y()))
            
            if self.controller:
                self.controller.on_canvas_mouse_release(event, int_pos)
            
            self.buffer_timer.stop()
            self._flush_buffer()
        
        def wheelEvent(self, event):
            """滚轮缩放事件"""
            if self.controller:
                if event.angleDelta().y() > 0:
                    self.controller.zoom_in()
                else:
                    self.controller.zoom_out()
            event.accept()
        
        def resizeEvent(self, event):
            """窗口大小变化事件"""
            super().resizeEvent(event)
            self.fit_to_window()
        
        # 工具方法
        def _flush_buffer(self):
            """刷新绘制缓冲区"""
            if self.draw_buffer:
                self.draw_buffer.clear()
                self.update()
        
        def clear_cache(self):
            """清除纹理缓存"""
            self._checker_cache.clear()

# ===================== 常量定义 =====================
DEFAULT_COLORS = [
    '#ffffff', '#000000', '#ff0000', '#00ff00',
    '#0000ff', '#ffff00', '#ff00ff', '#00ffff'
]

TOOL_INFO = {
    'brush': ("画笔", "🖌"),
    'eraser': ("橡皮擦", "🧽"),
    'airbrush': ("喷枪", "💨"),
    'fill': ("填充", "🪣"),
    'line': ("直线", "╱"),
    'curve': ("曲线", "〜"),
    'rectangle': ("矩形", "▭"),
    'ellipse': ("椭圆", "◯"),
    'star': ("多角星", "★"),
    'polygon': ("多边形", "⬠"),
    'rounded_rect': ("圆角矩形", "▬"),
    'picker': ("取色", "🧪"),
    'text': ("文字", "T"),
    'rect_select': ("矩形选区", "▢"),
    'ellipse_select': ("椭圆选区", "◯"),
    'polygon_select': ("多边形选区", "⬠"),
}

FILTER_NAMES = ["高斯模糊", "运动模糊", "锐化", "浮雕", "马赛克"]

# ===================== 缓存优化的辅助函数 =====================
@lru_cache(maxsize=8)
def create_pattern(pattern_type="transparent", size=16):
    """创建图案 - 缓存优化"""
    pixmap = QPixmap(size, size)
    
    if pattern_type == "transparent":
        pixmap.fill(QColor(200, 200, 200))
        painter = QPainter(pixmap)
        painter.setBrush(QBrush(QColor(150, 150, 150)))
        painter.drawRect(0, 0, size//2, size//2)
        painter.drawRect(size//2, size//2, size//2, size//2)
        painter.end()
    elif pattern_type == "checkerboard":
        pattern_size = size * 2
        pixmap = QPixmap(pattern_size, pattern_size)
        pixmap.fill(QColor(200, 200, 200))
        painter = QPainter(pixmap)
        painter.setBrush(QBrush(QColor(150, 150, 150)))
        painter.drawRect(0, 0, size, size)
        painter.drawRect(size, size, size, size)
        painter.end()
    
    return pixmap

# ===================== 优化的滑块控件 =====================
class ValueSlider(QWidget):
    """带数值显示的滑块控件"""
    valueChanged = pyqtSignal(int)
    
    def __init__(self, min_val, max_val, default_val=0, label="", parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.label = label
        self._init_ui(default_val)
        self._connect_signals()
    
    def _init_ui(self, default_val):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        if self.label:
            label_widget = QLabel(self.label)
            label_widget.setFixedWidth(60)
            layout.addWidget(label_widget)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(self.min_val, self.max_val)
        self.slider.setValue(default_val)
        self.slider.setFixedHeight(20)
        layout.addWidget(self.slider)
        
        self.spin_box = QSpinBox()
        self.spin_box.setRange(self.min_val, self.max_val)
        self.spin_box.setValue(default_val)
        self.spin_box.setFixedWidth(60)
        layout.addWidget(self.spin_box)
    
    def _connect_signals(self):
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spin_box.valueChanged.connect(self._on_spinbox_changed)
    
    def _on_slider_changed(self, value):
        self.spin_box.blockSignals(True)
        self.spin_box.setValue(value)
        self.spin_box.blockSignals(False)
        self.valueChanged.emit(value)
    
    def _on_spinbox_changed(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self.valueChanged.emit(value)
    
    def value(self):
        return self.slider.value()
    
    def setValue(self, value):
        self.slider.setValue(value)
        self.spin_box.setValue(value)

# ===================== 颜色按钮基类 =====================
class BaseColorButton(QPushButton):
    """颜色按钮基类"""
    color_selected = pyqtSignal(QColor, bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor()
        self._checker_pattern = None
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    
    def set_color(self, color: QColor):
        """设置颜色 - 确保颜色对象正确创建"""
        if isinstance(color, str):
            self.color = QColor(color)
        else:
            self.color = QColor(color)
        self.update()
    
    def _create_checker_pattern(self, size=None):
        """创建棋盘格图案"""
        if size is None:
            size = min(self.width(), self.height())
        
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(200, 200, 200))
        
        painter = QPainter(pixmap)
        painter.fillRect(0, 0, size//2, size//2, QColor(150, 150, 150))
        painter.fillRect(size//2, size//2, size//2, size//2, QColor(150, 150, 150))
        painter.end()
        
        return pixmap
    
    def paintEvent(self, event):
        """绘制事件 - 支持透明色显示为棋盘格"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制棋盘格背景（对于透明色或alpha < 255的颜色）
        if not self.color.isValid() or self.color.alpha() < 255:
            # 创建或获取棋盘格图案
            if self._checker_pattern is None:
                self._checker_pattern = self._create_checker_pattern()
            painter.drawTiledPixmap(self.rect(), self._checker_pattern)
        
        # 绘制颜色（如果有alpha，会与棋盘格混合）
        if self.color.isValid() and self.color.alpha() > 0:
            # 保存当前状态
            painter.save()
            painter.setOpacity(self.color.alpha() / 255.0)
            painter.fillRect(self.rect(), self.color)
            painter.restore()
        
        # 绘制边框
        painter.setPen(QPen(QColor("#5d5d5d"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._choose_color(False)  # 前景色
        elif event.button() == Qt.MouseButton.RightButton:
            self._choose_color(True)   # 背景色
        else:
            super().mousePressEvent(event)
    
    def _choose_color(self, is_background):
        """选择颜色 - 由子类实现"""
        raise NotImplementedError

class ColorButton(BaseColorButton):
    """颜色选择按钮 - 完全支持透明色"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 30)
    
    def _choose_color(self, is_background):
        """颜色按钮：弹出对话框选择颜色（支持透明色）"""
        # 创建自定义颜色对话框
        color_dialog = QColorDialog(self.parent() if self.parent() else self)
        color_dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
        
        initial = self.color if self.color.isValid() else QColor("black")
        color_dialog.setCurrentColor(initial)
        
        if color_dialog.exec():
            color = color_dialog.selectedColor()
            self.set_color(color)
            self.color_selected.emit(color, is_background)

class QuickColorButton(BaseColorButton):
    """快速颜色选择按钮 - 完全支持透明色"""
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        # 确保颜色对象被正确创建
        if isinstance(color, str):
            self.color = QColor(color)
        else:
            self.color = QColor(color)
        self.setFixedSize(20, 20)
    
    def _choose_color(self, is_background):
        """快速颜色按钮：直接使用预设颜色"""
        if self.color.isValid():
            self.color_selected.emit(self.color, is_background)

# ===================== 透明色按钮 =====================
class TransparentColorButton(QuickColorButton):
    """透明色按钮 - 专门用于选择透明色"""
    def __init__(self, parent=None):
        # 创建完全透明的颜色
        transparent_color = QColor(0, 0, 0, 0)
        super().__init__(transparent_color, parent)
        
    def paintEvent(self, event):
        """绘制事件 - 总是显示为棋盘格"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 总是绘制棋盘格背景
        if self._checker_pattern is None:
            self._checker_pattern = self._create_checker_pattern(8)
        painter.drawTiledPixmap(self.rect(), self._checker_pattern)
        
        # 绘制边框
        painter.setPen(QPen(QColor("#5d5d5d"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
    
    def _choose_color(self, is_background):
        """透明色按钮：发送透明色"""
        transparent_color = QColor(0, 0, 0, 0)
        self.color_selected.emit(transparent_color, is_background)

# ===================== 工具面板 =====================
class ToolPanel(QFrame):
    """工具面板"""
    tool_selected = pyqtSignal(str)
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.selected_button = None
        self.setFixedWidth(100)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)
        
        title = QLabel("工具")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; color: white; background-color: #3d3d3d; padding: 0px;")
        title.setFixedHeight(20)
        layout.addWidget(title)
        
        tools_layout = QGridLayout()
        tools_layout.setSpacing(2)
        
        all_tools = list(TOOL_INFO.keys())
        
        for i, tool_id in enumerate(all_tools):
            if tool_id in TOOL_INFO:
                name, icon = TOOL_INFO[tool_id]
                btn = QPushButton(icon)
                btn.setObjectName(f"tool_{tool_id}")
                btn.setFixedSize(44, 44)
                btn.setToolTip(name)
                btn.setStyleSheet(self._get_style(False))
                btn.clicked.connect(lambda checked, tid=tool_id: self.select_tool(tid))
                tools_layout.addWidget(btn, i // 2, i % 2)
        
        layout.addLayout(tools_layout)
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
    
    def _get_style(self, selected=False):
        base_style = """
            QPushButton {
                background-color: %s; color: white;
                border: %s; font-size: 16px; border-radius: 4px;
            }
            QPushButton:hover { background-color: %s; }
        """
        
        if selected:
            return base_style % ("#5d5d5d", "2px solid #ffffff", "#6d6d6d")
        return base_style % ("#4d4d4d", "1px solid #5d5d5d", "#5d5d5d")
    
    def select_tool(self, tool_id):
        """选择工具"""
        if self.selected_button:
            self.selected_button.setStyleSheet(self._get_style(False))
        
        button = self.findChild(QPushButton, f"tool_{tool_id}")
        if button:
            button.setStyleSheet(self._get_style(True))
            self.selected_button = button
        else:
            self.selected_button = None
        
        self.tool_selected.emit(tool_id)

# ===================== 属性面板 =====================
class PropertyPanel(QFrame):
    """属性面板"""
    
    # 信号定义
    size_changed = pyqtSignal(int)
    opacity_changed = pyqtSignal(int)
    foreground_color_changed = pyqtSignal(QColor)
    background_color_changed = pyqtSignal(QColor)
    brightness_changed = pyqtSignal(int)
    contrast_changed = pyqtSignal(int)
    saturation_changed = pyqtSignal(int)
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setFixedWidth(250)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        layout.addWidget(self._create_tool_properties())
        layout.addWidget(self._create_image_adjustments())
        layout.addWidget(self._create_filter_effects())
    
    def _create_section(self, title, widget):
        section = QFrame()
        section.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; color: white; background-color: #3d3d3d; padding: 2px;")
        title_label.setFixedHeight(20)
        layout.addWidget(title_label)
        layout.addWidget(widget)
        
        return section
    
    def _create_tool_properties(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.size_slider = ValueSlider(1, 100, 10, "大小:")
        self.size_slider.valueChanged.connect(self.size_changed.emit)
        layout.addWidget(self.size_slider)
        
        self.opacity_slider = ValueSlider(0, 100, 100, "不透明度:")
        self.opacity_slider.valueChanged.connect(self.opacity_changed.emit)
        layout.addWidget(self.opacity_slider)
        
        layout.addWidget(self._create_color_selection())
        
        return self._create_section("工具属性", widget)
    
    def _create_color_selection(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
    
        color_layout = QHBoxLayout()
    
        # 前景色
        fg_layout = QVBoxLayout()
        fg_layout.addWidget(QLabel("前景色:"))
        self.fg_button = ColorButton()
        self.fg_button.set_color(QColor("black"))
        self.fg_button.color_selected.connect(self._on_color_chosen)
        fg_layout.addWidget(self.fg_button)
        color_layout.addLayout(fg_layout)
    
        # 背景色
        bg_layout = QVBoxLayout()
        bg_layout.addWidget(QLabel("背景色:"))
        self.bg_button = ColorButton()
        self.bg_button.set_color(QColor("white"))
        self.bg_button.color_selected.connect(self._on_color_chosen)
        bg_layout.addWidget(self.bg_button)
        color_layout.addLayout(bg_layout)
    
        color_layout.addStretch()
        layout.addLayout(color_layout)
    
        # 快速颜色选择
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(2)
        
        # 添加默认颜色按钮
        for color in DEFAULT_COLORS:
            btn = QuickColorButton(color)
            btn.color_selected.connect(self._on_quick_color)
            quick_layout.addWidget(btn)
    
        # 透明色按钮 - 永远保持透明
        trans_btn = TransparentColorButton()
        trans_btn.color_selected.connect(self._on_transparent_color)
        quick_layout.addWidget(trans_btn)
    
        layout.addLayout(quick_layout)
        return widget

    def _on_transparent_color(self, color, is_bg):
        """处理透明色选择"""
        if is_bg:
            self.bg_button.set_color(color)
            self.background_color_changed.emit(color)
        else:
            self.fg_button.set_color(color)
            self.foreground_color_changed.emit(color)
    
    def _create_image_adjustments(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.brightness_slider = ValueSlider(-100, 100, 0, "亮度:")
        self.brightness_slider.valueChanged.connect(self.brightness_changed.emit)
        layout.addWidget(self.brightness_slider)
        
        self.contrast_slider = ValueSlider(-100, 100, 0, "对比度:")
        self.contrast_slider.valueChanged.connect(self.contrast_changed.emit)
        layout.addWidget(self.contrast_slider)
        
        self.saturation_slider = ValueSlider(-100, 100, 0, "饱和度:")
        self.saturation_slider.valueChanged.connect(self.saturation_changed.emit)
        layout.addWidget(self.saturation_slider)
        
        # 添加重置按钮
        reset_btn = QPushButton("重置调整")
        reset_btn.clicked.connect(self._reset_adjustments)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #4d4d4d; color: white;
                border: 1px solid #5d5d5d; padding: 4px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        layout.addWidget(reset_btn)
        
        return self._create_section("图像调整", widget)
    
    def _reset_adjustments(self):
        """重置所有调整"""
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(0)
        self.saturation_slider.setValue(0)
        
        if self.controller and hasattr(self.controller, 'reset_adjustments'):
            self.controller.reset_adjustments()
    
    def _create_filter_effects(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        button_style = """
            QPushButton {
                background-color: #4d4d4d; color: white;
                border: 1px solid #5d5d5d; padding: 2px;
            }
            QPushButton:hover { background-color: #5d5d5d; }
        """
        
        for name in FILTER_NAMES:
            btn = QPushButton(name)
            btn.setStyleSheet(button_style)
            btn.clicked.connect(lambda checked, n=name: self.controller.apply_filter(n))
            layout.addWidget(btn)
        
        return self._create_section("滤镜效果", widget)
    
    def _on_color_chosen(self, color: QColor, is_bg: bool):
        if is_bg:
            self.background_color_changed.emit(color)
        else:
            self.foreground_color_changed.emit(color)
    
    def _on_quick_color(self, color: QColor, is_bg: bool):
        if is_bg:
            self.bg_button.set_color(color)
            self.background_color_changed.emit(color)
        else:
            self.fg_button.set_color(color)
            self.foreground_color_changed.emit(color)

# ===================== 图层面板 =====================
class LayerPanel(QFrame):
    """图层面板"""
    
    # 信号定义
    layer_added = pyqtSignal(str)
    layer_removed = pyqtSignal(int)
    layer_toggled = pyqtSignal(int, bool)
    layer_selected = pyqtSignal(int)
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setFixedWidth(250)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        title = QLabel("图层")
        title.setStyleSheet("font-weight: bold; color: white; background-color: #3d3d3d; padding: 2px;")
        title.setFixedHeight(20)
        layout.addWidget(title)
        
        self.layer_list = QListWidget()
        self.layer_list.currentRowChanged.connect(self.layer_selected.emit)
        self.layer_list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.layer_list)
        
        layout.addWidget(self._create_buttons())
    
    def _create_buttons(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        buttons = [
            ("+", self.add_layer, "添加图层"),
            ("−", self.remove_layer, "删除图层"),
            ("↑", self.move_up, "上移图层"),
            ("↓", self.move_down, "下移图层")
        ]
        
        for text, callback, tip in buttons:
            btn = QPushButton(text)
            btn.setFixedSize(30, 30)
            btn.setToolTip(tip)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #4d4d4d; color: white;
                    border: 1px solid #5d5d5d; border-radius: 4px; font-weight: bold;
                }
                QPushButton:hover { background-color: #5d5d5d; }
            """)
            btn.clicked.connect(callback)
            layout.addWidget(btn)
            
            # 保存按钮引用
            if text == "+":
                self.add_btn = btn
            elif text == "−":
                self.rm_btn = btn
            elif text == "↑":
                self.up_btn = btn
            elif text == "↓":
                self.down_btn = btn
        
        layout.addStretch()
        return widget
    
    def add_layer(self):
        """添加图层"""
        name, ok = QInputDialog.getText(self, "添加图层", "图层名称:", 
                                       text=f"图层 {self.layer_list.count()}")
        if ok and name:
            self.layer_added.emit(name)
    
    def remove_layer(self):
        """删除图层"""
        row = self.layer_list.currentRow()
        if row == 0:
            if hasattr(self.controller, 'status_updated'):
                self.controller.status_updated.emit("无法删除背景图层")
            return
        
        if 0 <= row < self.layer_list.count():
            self.layer_removed.emit(row)
    
    def move_up(self):
        """上移图层"""
        row = self.layer_list.currentRow()
        if row <= 1:
            return
        
        if hasattr(self.controller, 'move_layer_up'):
            if self.controller.move_layer_up(row):
                self.layer_list.setCurrentRow(row - 1)
    
    def move_down(self):
        """下移图层"""
        row = self.layer_list.currentRow()
        if row == 0 or row >= self.layer_list.count() - 1:
            return
        
        if hasattr(self.controller, 'move_layer_down'):
            if self.controller.move_layer_down(row):
                self.layer_list.setCurrentRow(row + 1)
    
    def _on_item_changed(self, item):
        """图层可见性变化"""
        row = self.layer_list.row(item)
        if row == 0 and item.checkState() == Qt.CheckState.Unchecked:
            item.setCheckState(Qt.CheckState.Checked)
            return
        
        visible = item.checkState() == Qt.CheckState.Checked
        self.layer_toggled.emit(row, visible)

# ===================== 样式表 =====================
DARK_THEME_STYLE = """
QMainWindow, QWidget {
    background-color: #2b2b2b;
    color: #ffffff;
}

QMdiArea {
    background-color: #2d2d2d;
}

QMenuBar {
    background-color: #3c3c3c;
    color: #ffffff;
    border-bottom: 1px solid #1b1b1b;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 8px;
}

QMenuBar::item:selected {
    background: #555555;
}

QMenu {
    background-color: #3c3c3c;
    color: #ffffff;
    border: 1px solid #1b1b1b;
}

QMenu::item {
    padding: 4px 20px;
}

QMenu::item:selected {
    background-color: #555555;
}

QToolBar {
    background-color: #3c3c3c;
    border: 1px solid #1b1b1b;
    padding: 2px;
    spacing: 2px;
}

QStatusBar {
    background-color: #3c3c3c;
    color: #ffffff;
    border-top: 1px solid #1b1b1b;
}

QSlider::groove:horizontal {
    border: 1px solid #555;
    height: 8px;
    background: #3c3c3c;
    margin: 2px 0;
}

QSlider::handle:horizontal {
    background: #5d5d5d;
    border: 1px solid #555;
    width: 18px;
    margin: -2px 0;
    border-radius: 3px;
}

QPushButton {
    background-color: #4d4d4d;
    color: white;
    border: 1px solid #5d5d5d;
    padding: 4px;
    border-radius: 4px;
}

QPushButton:hover {
    background-color: #5d5d5d;
}

QListWidget {
    background-color: #3c3c3c;
    border: 1px solid #5d5d5d;
    color: #ffffff;
}

QListWidget::item:selected {
    background-color: #555555;
}

QSpinBox {
    background-color: #3c3c3c;
    color: #ffffff;
    border: 1px solid #5d5d5d;
    padding: 2px;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #5d5d5d;
    border: 1px solid #5d5d5d;
    width: 16px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #6d6d6d;
}

QScrollBar:vertical {
    background: #3c3c3c;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #5d5d5d;
    min-height: 20px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #6d6d6d;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    background: none;
    height: 0px;
}

QScrollBar:horizontal {
    background: #3c3c3c;
    height: 12px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #5d5d5d;
    min-width: 20px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover {
    background: #6d6d6d;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    background: none;
    width: 0px;
}
"""