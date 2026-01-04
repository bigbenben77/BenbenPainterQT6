# text_tool.py - 重构的专业级文字工具
# 使用方法：
# 1. 将此文件保存为 text_tool.py
# 2. 在 tool_system.py 中导入：from text_tool import TextTool
# 3. 在 tool_system.py 的 _register_tools 方法中注册：
#    self.tools['text'] = TextTool(self.controller)

from PyQt6.QtCore import Qt, QPointF, QRect, QRectF, QTimer
from PyQt6.QtGui import (QColor, QPen, QPainter, QBrush, QPixmap, QFont, 
                         QFontMetrics, QTransform, QCursor, QPolygonF)
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QTextEdit, QFontComboBox, QSpinBox,
                            QCheckBox, QColorDialog, QWidget, QSlider)
from base_tool import BaseTool
import math


class TextEditDialog(QDialog):
    """文字编辑对话框 - 轻量级非模态对话框"""
    
    def __init__(self, text_tool, parent=None):
        super().__init__(parent)
        self.text_tool = text_tool
        self.setWindowTitle("文字编辑")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        
        self.init_ui()
        self.update_from_tool()
        
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 文字输入区
        text_label = QLabel("文字内容:")
        layout.addWidget(text_label)
        
        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(100)
        self.text_edit.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.text_edit)
        
        # 字体选择
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("字体:"))
        
        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self.on_font_changed)
        font_layout.addWidget(self.font_combo)
        
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 144)
        self.size_spin.setValue(24)
        self.size_spin.setSuffix(" pt")
        self.size_spin.valueChanged.connect(self.on_font_changed)
        font_layout.addWidget(self.size_spin)
        
        layout.addLayout(font_layout)
        
        # 字体样式
        style_layout = QHBoxLayout()
        
        self.bold_check = QCheckBox("粗体")
        self.bold_check.stateChanged.connect(self.on_font_changed)
        style_layout.addWidget(self.bold_check)
        
        self.italic_check = QCheckBox("斜体")
        self.italic_check.stateChanged.connect(self.on_font_changed)
        style_layout.addWidget(self.italic_check)
        
        self.underline_check = QCheckBox("下划线")
        self.underline_check.stateChanged.connect(self.on_font_changed)
        style_layout.addWidget(self.underline_check)
        
        style_layout.addStretch()
        layout.addLayout(style_layout)
        
        # 颜色选择
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("颜色:"))
        
        self.color_button = QPushButton()
        self.color_button.setFixedSize(30, 30)
        self.color_button.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_button)
        
        self.transparent_button = QPushButton("透明")
        self.transparent_button.clicked.connect(self.choose_transparent)
        color_layout.addWidget(self.transparent_button)
        
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        # 变换控制
        transform_label = QLabel("变换:")
        layout.addWidget(transform_label)
        
        # 缩放
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("缩放:"))
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(10, 500)
        self.scale_slider.setValue(100)
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        scale_layout.addWidget(self.scale_slider)
        self.scale_label = QLabel("100%")
        scale_layout.addWidget(self.scale_label)
        layout.addLayout(scale_layout)
        
        # 旋转
        rotate_layout = QHBoxLayout()
        rotate_layout.addWidget(QLabel("旋转:"))
        self.rotate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rotate_slider.setRange(0, 360)
        self.rotate_slider.setValue(0)
        self.rotate_slider.valueChanged.connect(self.on_rotate_changed)
        rotate_layout.addWidget(self.rotate_slider)
        self.rotate_label = QLabel("0°")
        rotate_layout.addWidget(self.rotate_label)
        layout.addLayout(rotate_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        reset_button = QPushButton("重置变换")
        reset_button.clicked.connect(self.reset_transform)
        button_layout.addWidget(reset_button)
        
        button_layout.addStretch()
        
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept_text)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject_text)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # 提示文字
        hint = QLabel("提示: 在画布上拖动移动，拖动角落缩放，拖动旋转手柄旋转")
        hint.setStyleSheet("color: gray; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        
    def update_from_tool(self):
        """从工具更新UI"""
        if not self.text_tool:
            return
        
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(self.text_tool.text)
        self.text_edit.blockSignals(False)
        
        self.font_combo.blockSignals(True)
        self.font_combo.setCurrentFont(self.text_tool.font)
        self.font_combo.blockSignals(False)
        
        self.size_spin.blockSignals(True)
        self.size_spin.setValue(self.text_tool.font.pointSize())
        self.size_spin.blockSignals(False)
        
        self.bold_check.blockSignals(True)
        self.bold_check.setChecked(self.text_tool.font.bold())
        self.bold_check.blockSignals(False)
        
        self.italic_check.blockSignals(True)
        self.italic_check.setChecked(self.text_tool.font.italic())
        self.italic_check.blockSignals(False)
        
        self.underline_check.blockSignals(True)
        self.underline_check.setChecked(self.text_tool.font.underline())
        self.underline_check.blockSignals(False)
        
        self.update_color_button()
        
        self.scale_slider.blockSignals(True)
        self.scale_slider.setValue(int(self.text_tool.scale_factor * 100))
        self.scale_slider.blockSignals(False)
        self.scale_label.setText(f"{int(self.text_tool.scale_factor * 100)}%")
        
        self.rotate_slider.blockSignals(True)
        self.rotate_slider.setValue(int(self.text_tool.rotation_angle))
        self.rotate_slider.blockSignals(False)
        self.rotate_label.setText(f"{int(self.text_tool.rotation_angle)}°")
        
    def on_text_changed(self):
        """文字改变"""
        if self.text_tool:
            self.text_tool.text = self.text_edit.toPlainText()
            self.text_tool.update_text_preview()
            
    def on_font_changed(self):
        """字体改变"""
        if not self.text_tool:
            return
        
        font = self.font_combo.currentFont()
        font.setPointSize(self.size_spin.value())
        font.setBold(self.bold_check.isChecked())
        font.setItalic(self.italic_check.isChecked())
        font.setUnderline(self.underline_check.isChecked())
        
        self.text_tool.font = font
        self.text_tool.update_text_preview()
        
    def on_scale_changed(self, value):
        """缩放改变"""
        if self.text_tool:
            self.text_tool.scale_factor = value / 100.0
            self.scale_label.setText(f"{value}%")
            self.text_tool.update_text_preview()
            
    def on_rotate_changed(self, value):
        """旋转改变"""
        if self.text_tool:
            self.text_tool.rotation_angle = value
            self.rotate_label.setText(f"{value}°")
            self.text_tool.update_text_preview()
            
    def reset_transform(self):
        """重置变换"""
        self.scale_slider.setValue(100)
        self.rotate_slider.setValue(0)
        
    def choose_color(self):
        """选择颜色"""
        dialog = QColorDialog(self)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
        dialog.setCurrentColor(self.text_tool.color)
        
        if dialog.exec():
            color = dialog.selectedColor()
            self.text_tool.color = color
            self.update_color_button()
            self.text_tool.update_text_preview()
            
    def choose_transparent(self):
        """选择透明色"""
        self.text_tool.color = QColor(0, 0, 0, 0)
        self.update_color_button()
        self.text_tool.update_text_preview()
        
    def update_color_button(self):
        """更新颜色按钮"""
        pixmap = QPixmap(30, 30)
        pixmap.fill(QColor(200, 200, 200))
        
        painter = QPainter(pixmap)
        # 棋盘格
        painter.fillRect(0, 0, 15, 15, QColor(150, 150, 150))
        painter.fillRect(15, 15, 15, 15, QColor(150, 150, 150))
        
        # 颜色
        if self.text_tool.color.alpha() > 0:
            painter.setOpacity(self.text_tool.color.alpha() / 255.0)
            painter.fillRect(pixmap.rect(), self.text_tool.color)
        
        painter.end()
        
        from PyQt6.QtGui import QIcon
        self.color_button.setIcon(QIcon(pixmap))
        
    def accept_text(self):
        """确定文字"""
        if self.text_tool:
            self.text_tool.commit_text()
            
    def reject_text(self):
        """取消文字"""
        if self.text_tool:
            self.text_tool.cancel()
        self.hide()
        
    def keyPressEvent(self, event):
        """按键事件 - 阻止快捷键"""
        # 只处理Esc和Enter
        if event.key() == Qt.Key.Key_Escape:
            self.reject_text()
        elif event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.accept_text()
        else:
            # 其他按键正常处理，不传递给主窗口
            super().keyPressEvent(event)
            
    def closeEvent(self, event):
        """关闭事件"""
        if self.text_tool and self.text_tool.is_editing:
            self.text_tool.cancel()
        event.accept()


class TextTool(BaseTool):
    """重构的专业级文字工具"""
    
    def __init__(self, controller):
        super().__init__(controller)
        
        # 编辑状态
        self.is_editing = False
        self.text = ""
        self.font = QFont("Arial", 24)
        self.color = QColor("black")
        
        # 位置和变换
        self.text_position = None
        self.text_rect = None
        self.scale_factor = 1.0
        self.rotation_angle = 0.0
        
        # 交互状态
        self.is_moving = False
        self.is_scaling = False
        self.is_rotating = False
        self.last_mouse_pos = None
        self.original_scale = 1.0
        self.original_angle = 0.0
        
        # 控制点
        self.handle_size = 12
        self.scale_handle_rect = None
        self.rotate_handle_rect = None
        
        # 编辑对话框
        self.edit_dialog = None
        
    def mouse_press(self, event, image_pos):
        """鼠标按下"""
        super().mouse_press(event, image_pos)
        
        if event.button() == Qt.MouseButton.LeftButton:
            # 如果正在编辑，检查是否在控制区域
            if self.is_editing and self.text_rect:
                x, y = int(image_pos.x()), int(image_pos.y())
                
                # 检查缩放手柄
                if self.scale_handle_rect and self.scale_handle_rect.contains(x, y):
                    self.is_scaling = True
                    self.last_mouse_pos = QPointF(x, y)
                    self.original_scale = self.scale_factor
                    return
                
                # 检查旋转手柄
                if self.rotate_handle_rect and self.rotate_handle_rect.contains(x, y):
                    self.is_rotating = True
                    self.last_mouse_pos = QPointF(x, y)
                    self.original_angle = self.rotation_angle
                    return
                
                # 检查文字区域
                if self._is_point_in_text_rect(x, y):
                    self.is_moving = True
                    self.last_mouse_pos = QPointF(x, y)
                    return
                
                # 点击外部，提交文字
                self.commit_text()
                return
            
            # 开始新文字
            self.start_text_edit(image_pos)
            
        elif event.button() == Qt.MouseButton.RightButton:
            # 右键提交
            if self.is_editing:
                self.commit_text()
                
    def mouse_move(self, event, image_pos):
        """鼠标移动"""
        super().mouse_move(event, image_pos)
        
        if not self.is_editing:
            return
        
        x, y = int(image_pos.x()), int(image_pos.y())
        
        # 移动
        if self.is_moving and self.last_mouse_pos:
            dx = x - self.last_mouse_pos.x()
            dy = y - self.last_mouse_pos.y()
            
            self.text_position = QPointF(
                self.text_position.x() + dx,
                self.text_position.y() + dy
            )
            self.last_mouse_pos = QPointF(x, y)
            self.update_text_preview()
            
        # 缩放
        elif self.is_scaling and self.last_mouse_pos:
            center_x = self.text_rect.x() + self.text_rect.width() / 2
            center_y = self.text_rect.y() + self.text_rect.height() / 2
            
            # 计算鼠标到中心的距离
            dist = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            original_dist = math.sqrt(
                (self.last_mouse_pos.x() - center_x) ** 2 + 
                (self.last_mouse_pos.y() - center_y) ** 2
            )
            
            if original_dist > 0:
                scale_delta = dist / original_dist
                self.scale_factor = self.original_scale * scale_delta
                self.scale_factor = max(0.1, min(self.scale_factor, 10.0))
                
                # 更新对话框
                if self.edit_dialog:
                    self.edit_dialog.scale_slider.blockSignals(True)
                    self.edit_dialog.scale_slider.setValue(int(self.scale_factor * 100))
                    self.edit_dialog.scale_slider.blockSignals(False)
                    self.edit_dialog.scale_label.setText(f"{int(self.scale_factor * 100)}%")
                
                self.update_text_preview()
                
        # 旋转
        elif self.is_rotating and self.last_mouse_pos:
            center_x = self.text_rect.x() + self.text_rect.width() / 2
            center_y = self.text_rect.y() + self.text_rect.height() / 2
            
            dx1 = self.last_mouse_pos.x() - center_x
            dy1 = self.last_mouse_pos.y() - center_y
            dx2 = x - center_x
            dy2 = y - center_y
            
            angle1 = math.degrees(math.atan2(dy1, dx1))
            angle2 = math.degrees(math.atan2(dy2, dx2))
            
            angle_diff = angle2 - angle1
            self.rotation_angle = (self.original_angle + angle_diff) % 360
            
            # 更新对话框
            if self.edit_dialog:
                self.edit_dialog.rotate_slider.blockSignals(True)
                self.edit_dialog.rotate_slider.setValue(int(self.rotation_angle))
                self.edit_dialog.rotate_slider.blockSignals(False)
                self.edit_dialog.rotate_label.setText(f"{int(self.rotation_angle)}°")
            
            self.update_text_preview()
            
        # 更新光标
        else:
            self._update_cursor(x, y)
            
    def mouse_release(self, event, image_pos):
        """鼠标释放"""
        super().mouse_release(event, image_pos)
        
        self.is_moving = False
        self.is_scaling = False
        self.is_rotating = False
        self.last_mouse_pos = None
        
    def key_press(self, event):
        """按键处理"""
        # 如果正在编辑且对话框可见，不处理快捷键
        if self.is_editing and self.edit_dialog and self.edit_dialog.isVisible():
            # 只处理Esc
            if event.key() == Qt.Key.Key_Escape:
                self.cancel()
                return True
            # 其他按键交给对话框处理
            return True
        
        # 非编辑状态，正常处理
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.is_editing:
                self.commit_text()
                return True
                
        return False
        
    def start_text_edit(self, position):
        """开始文字编辑"""
        self.is_editing = True
        self.text_position = position
        self.text = "输入文字"
        self.scale_factor = 1.0
        self.rotation_angle = 0.0
        
        # 创建或显示编辑对话框
        if not self.edit_dialog:
            parent = self.controller.main_window if self.controller else None
            self.edit_dialog = TextEditDialog(self, parent)
        else:
            self.edit_dialog.update_from_tool()
        
        self.edit_dialog.show()
        self.edit_dialog.raise_()
        self.edit_dialog.activateWindow()
        self.edit_dialog.text_edit.setFocus()
        self.edit_dialog.text_edit.selectAll()
        
        # 更新预览
        self.update_text_preview()
        
        if self.controller and hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit(
                "文字编辑模式: 在对话框输入文字，在画布上拖动/缩放/旋转，右键或点击确定提交"
            )
            
    def update_text_preview(self):
        """更新文字预览"""
        if not self.is_editing or not self.text or not self.controller:
            return
        
        # 计算文字矩形
        metrics = QFontMetrics(self.font)
        text_width = metrics.horizontalAdvance(self.text)
        text_height = metrics.height()
        
        self.text_rect = QRectF(
            self.text_position.x(),
            self.text_position.y(),
            text_width,
            text_height
        )
        
        # 更新控制点
        self._update_handles()
        
        # 创建预览图像
        if not self.controller.current_image:
            return
        
        canvas_size = self.controller.current_image.size()
        temp_image = QPixmap(canvas_size)
        temp_image.fill(QColor(0, 0, 0, 0))
        
        painter = QPainter(temp_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # 应用变换
        center_x = self.text_rect.x() + self.text_rect.width() / 2
        center_y = self.text_rect.y() + self.text_rect.height() / 2
        
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self.rotation_angle)
        painter.scale(self.scale_factor, self.scale_factor)
        painter.translate(-center_x, -center_y)
        
        # 绘制文字
        painter.setFont(self.font)
        
        if self.color.alpha() == 0:
            # 透明色：棋盘格背景
            checker = self._create_checker_pattern()
            painter.setClipRect(self.text_rect)
            painter.drawTiledPixmap(self.text_rect.toRect(), checker)
            painter.setClipping(False)
            painter.setPen(QPen(QColor(0, 0, 0, 100), 1))
        else:
            painter.setPen(self.color)
        
        painter.drawText(self.text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.text)
        
        painter.restore()
        
        # 绘制边框和控制点
        self._draw_text_frame(painter)
        
        painter.end()
        
        self.controller.temp_pixmap = temp_image
        if self.controller.canvas:
            self.controller.canvas.update()
            
    def _update_handles(self):
        """更新控制点 - 考虑变换后的实际位置"""
        if not self.text_rect:
            return
        
        # 创建变换
        transform = QTransform()
        center_x = self.text_rect.x() + self.text_rect.width() / 2
        center_y = self.text_rect.y() + self.text_rect.height() / 2
        
        transform.translate(center_x, center_y)
        transform.rotate(self.rotation_angle)
        transform.scale(self.scale_factor, self.scale_factor)
        transform.translate(-center_x, -center_y)
        
        # 变换矩形的四个角点
        corners = [
            QPointF(self.text_rect.left(), self.text_rect.top()),      # 左上
            QPointF(self.text_rect.right(), self.text_rect.top()),     # 右上
            QPointF(self.text_rect.left(), self.text_rect.bottom()),   # 左下
            QPointF(self.text_rect.right(), self.text_rect.bottom())   # 右下
        ]
        
        transformed_corners = [transform.map(corner) for corner in corners]
        
        # 右下角 - 缩放手柄（变换后的右下角）
        br_corner = transformed_corners[3]
        hot_size = self.handle_size * 2  # 更大的热区
        self.scale_handle_rect = QRect(
            int(br_corner.x() - hot_size / 2),
            int(br_corner.y() - hot_size / 2),
            hot_size,
            hot_size
        )
        
        # 右上角 - 旋转手柄（变换后的右上角外延）
        tr_corner = transformed_corners[1]
        # 在右上角外延一段距离放置旋转手柄
        offset = 20 * self.scale_factor
        dx = tr_corner.x() - center_x
        dy = tr_corner.y() - center_y
        length = math.sqrt(dx*dx + dy*dy)
        if length > 0:
            rotate_x = tr_corner.x() + (dx / length) * offset
            rotate_y = tr_corner.y() + (dy / length) * offset
        else:
            rotate_x = tr_corner.x() + offset
            rotate_y = tr_corner.y() - offset
        
        self.rotate_handle_rect = QRect(
            int(rotate_x - hot_size / 2),
            int(rotate_y - hot_size / 2),
            hot_size,
            hot_size
        )
        
        # 保存变换后的角点用于绘制
        self.transformed_corners = transformed_corners
        self.rotate_handle_pos = QPointF(rotate_x, rotate_y)
        
    def _draw_text_frame(self, painter):
        """绘制文字框架 - 绘制变换后的虚线边框"""
        if not self.text_rect or not hasattr(self, 'transformed_corners'):
            return

        painter.save()

        # 绘制变换后的长方形虚线边框
        pen = QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 4])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # 应用与文字相同的变换绘制长方形边框
        center_x = self.text_rect.x() + self.text_rect.width() / 2
        center_y = self.text_rect.y() + self.text_rect.height() / 2

        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self.rotation_angle)
        painter.scale(self.scale_factor, self.scale_factor)
        painter.translate(-center_x, -center_y)

        painter.drawRect(self.text_rect.toRect())
        painter.restore()

        # 绘制角点
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(0, 150, 255), 2))

        for corner in self.transformed_corners:
            painter.drawRect(
                int(corner.x() - 4),
                int(corner.y() - 4),
                8, 8
            )
        
        # 绘制缩放手柄（右下角）
        br_corner = self.transformed_corners[3]
        painter.setBrush(QBrush(QColor(255, 100, 100)))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        handle_rect = QRect(
            int(br_corner.x() - self.handle_size / 2),
            int(br_corner.y() - self.handle_size / 2),
            self.handle_size,
            self.handle_size
        )
        painter.drawRect(handle_rect)
        # 绘制对角线
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawLine(
            handle_rect.topLeft(),
            handle_rect.bottomRight()
        )
        painter.drawLine(
            handle_rect.topRight(),
            handle_rect.bottomLeft()
        )

        # 绘制旋转手柄（右上角外延）
        rotate_pos = self.rotate_handle_pos

        # 绘制连接线
        painter.setPen(QPen(QColor(100, 255, 100), 1, Qt.PenStyle.DotLine))
        tr_corner = self.transformed_corners[1]
        painter.drawLine(
            int(tr_corner.x()), int(tr_corner.y()),
            int(rotate_pos.x()), int(rotate_pos.y())
        )

        # 绘制旋转手柄（圆形）
        painter.setBrush(QBrush(QColor(100, 255, 100)))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawEllipse(
            int(rotate_pos.x() - self.handle_size / 2),
            int(rotate_pos.y() - self.handle_size / 2),
            self.handle_size,
            self.handle_size
        )

        # 绘制旋转图标（小箭头）
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        arc_rect = QRect(
            int(rotate_pos.x() - 4),
            int(rotate_pos.y() - 4),
            8, 8
        )
        painter.drawArc(arc_rect, 30 * 16, 300 * 16)
        

        painter.restore()
        
    def _is_point_in_text_rect(self, x, y):
        """判断点是否在文字矩形内"""
        if not self.text_rect:
            return False
        
        # 创建变换后的矩形
        transform = QTransform()
        center_x = self.text_rect.x() + self.text_rect.width() / 2
        center_y = self.text_rect.y() + self.text_rect.height() / 2
        
        transform.translate(center_x, center_y)
        transform.rotate(self.rotation_angle)
        transform.scale(self.scale_factor, self.scale_factor)
        transform.translate(-center_x, -center_y)
        
        polygon = QPolygonF(self.text_rect)
        transformed = transform.map(polygon)
        
        return transformed.containsPoint(QPointF(x, y), Qt.FillRule.OddEvenFill)
        
    def _update_cursor(self, x, y):
        """更新光标"""
        if not self.controller or not self.controller.canvas:
            return
        
        if self.scale_handle_rect and self.scale_handle_rect.contains(x, y):
            self.controller.canvas.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        elif self.rotate_handle_rect and self.rotate_handle_rect.contains(x, y):
            self.controller.canvas.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        elif self._is_point_in_text_rect(x, y):
            self.controller.canvas.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.controller.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            
    def _create_checker_pattern(self):
        """创建棋盘格图案"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(200, 200, 200))
        
        painter = QPainter(pixmap)
        painter.fillRect(0, 0, 8, 8, QColor(150, 150, 150))
        painter.fillRect(8, 8, 8, 8, QColor(150, 150, 150))
        painter.end()
        
        return pixmap
        
    def commit_text(self):
        """提交文字到图层"""
        if not self.is_editing or not self.text or not self.controller:
            return
        
        # 保存历史
        if hasattr(self.controller, 'save_to_history'):
            self.controller.save_to_history()
        
        # 绘制文字到活动图层
        def draw_text(painter):
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            
            # 应用变换
            center_x = self.text_rect.x() + self.text_rect.width() / 2
            center_y = self.text_rect.y() + self.text_rect.height() / 2
            
            painter.save()
            painter.translate(center_x, center_y)
            painter.rotate(self.rotation_angle)
            painter.scale(self.scale_factor, self.scale_factor)
            painter.translate(-center_x, -center_y)
            
            # 绘制文字
            painter.setFont(self.font)
            
            if self.color.alpha() == 0:
                # 透明色：使用Clear模式
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.setPen(QPen(QColor(0, 0, 0, 0), 1))
            else:
                painter.setPen(self.color)
            
            painter.drawText(
                self.text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                self.text
            )
            
            painter.restore()
        
        # 绘制到活动图层
        self.controller.draw_on_active_layer(draw_text, save_history=True)
        
        # 清理状态
        self.cancel()
        
        if self.controller and hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit("文字已添加")
            
    def cancel(self):
        """取消编辑"""
        super().cancel()
        
        self.is_editing = False
        self.text = ""
        self.text_position = None
        self.text_rect = None
        self.scale_factor = 1.0
        self.rotation_angle = 0.0
        
        # 关闭对话框
        if self.edit_dialog:
            self.edit_dialog.hide()
        
        # 清除预览
        if self.controller:
            self.controller.temp_pixmap = None
            if self.controller.canvas:
                self.controller.canvas.update()
                self.controller.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))