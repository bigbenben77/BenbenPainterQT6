# other_tools.py - 其他工具
from PyQt6.QtCore import Qt, QPointF, QRect, QTimer
from PyQt6.QtGui import QColor, QPen, QPainter, QBrush, QImage, QPixmap, QCursor, QFont, QFontMetrics
from PyQt6.QtWidgets import QApplication, QInputDialog, QColorDialog
import math
from base_tool import BaseTool


class PickerTool(BaseTool):
    """取色工具"""
    def __init__(self, controller):
        super().__init__(controller)
        self.last_color = None

    def mouse_press(self, event, image_pos):
        """鼠标按下事件"""
        super().mouse_press(event, image_pos)

        if not self.controller or not self.controller.current_image:
            return

        x = int(image_pos.x())
        y = int(image_pos.y())

        # 检查坐标是否在图像范围内
        if (0 <= x < self.controller.current_image.width() and
            0 <= y < self.controller.current_image.height()):

            # 获取颜色
            color = self.controller.current_image.pixelColor(x, y)

            if color.isValid():
                self.last_color = color

                # 根据鼠标按钮设置前景色或背景色
                is_background = (event.button() == Qt.MouseButton.RightButton or
                                self.tool_state['mouse_button'] == 'right' or
                                self.tool_state['is_right_button_during_drag'])

                if is_background:
                    # 设置为背景色
                    if hasattr(self.controller, 'on_bg_color_changed'):
                        self.controller.on_bg_color_changed(color)
                else:
                    # 设置为前景色
                    if hasattr(self.controller, 'on_fg_color_changed'):
                        self.controller.on_fg_color_changed(color)

                # 显示提示
                if self.controller and hasattr(self.controller, 'status_updated'):
                    color_type = "背景色" if is_background else "前景色"
                    self.controller.status_updated.emit(
                        f"取色: {color_type} = RGBA({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
                    )


class TextTool(BaseTool):
    """文字工具 - 直接在画布上编辑"""

    def __init__(self, controller):
        super().__init__(controller)
        self.is_editing = False
        self.edit_position = None
        self.preview_text = ""
        self.preview_font = QFont("Arial", 24)
        self.preview_color = QColor("black")

    def mouse_press(self, event, image_pos):
        """鼠标按下事件"""
        super().mouse_press(event, image_pos)

        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_editing:
                # 检查是否点击在预览区域外
                if self._is_click_outside_preview(image_pos):
                    self._commit_text()
                return

            # 开始新文字编辑
            self._start_text_edit(image_pos)

    def _is_click_outside_preview(self, click_pos):
        """检查点击是否在预览区域外"""
        if not self.edit_position:
            return True

        # 简单距离检查
        distance = ((click_pos.x() - self.edit_position.x()) ** 2 +
                   (click_pos.y() - self.edit_position.y()) ** 2) ** 0.5

        # 如果距离大于100像素，认为在外部
        return distance > 100

    def _start_text_edit(self, position):
        """开始文字编辑"""
        if not self.controller:
            return

        # 获取当前颜色
        color = self._get_drawing_color()
        if color:
            self.preview_color = color

        self.edit_position = position
        self.preview_text = ""
        self.is_editing = True

        if self.controller and hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit("文字编辑模式: 输入文字后按Enter提交，点击外部提交")

    def _update_preview(self):
        """更新预览"""
        if not self.controller:
            return

        # 清除之前的预览
        self.controller.clear_tool_preview()

        if not self.preview_text:
            return

        # 创建预览图像
        metrics = QFontMetrics(self.preview_font)
        text_width = metrics.horizontalAdvance(self.preview_text)
        text_height = metrics.height()

        preview_width = max(200, text_width + 20)
        preview_height = text_height + 20

        preview_image = QImage(preview_width, preview_height, QImage.Format.Format_ARGB32)
        preview_image.fill(QColor(0, 0, 0, 0))

        painter = QPainter(preview_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 绘制背景
        painter.fillRect(0, 0, preview_width, preview_height, QColor(255, 255, 255, 100))

        # 绘制边框
        painter.setPen(QPen(QColor(0, 150, 255), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(1, 1, preview_width - 2, preview_height - 2)

        # 绘制文字
        painter.setFont(self.preview_font)
        painter.setPen(self.preview_color)
        painter.drawText(10, 10 + text_height, self.preview_text)

        painter.end()

        # 更新工具预览
        pixmap = QPixmap.fromImage(preview_image)
        # 计算预览位置（画布坐标）
        preview_pos = QPointF(self.edit_position.x(), self.edit_position.y())
        self.controller.update_tool_preview(pixmap, preview_pos)

        # 通知画布更新
        if hasattr(self.controller, 'canvas') and self.controller.canvas:
            self.controller.canvas.update()

    def _commit_text(self):
        """提交文字"""
        if self.preview_text.strip() and self.controller:
            self.controller.add_text(self.preview_text, self.preview_font, self.preview_color, 1.0, 0.0, self.edit_position)

        self._end_edit()

    def _cancel_edit(self):
        """取消编辑"""
        self._end_edit()

    def _end_edit(self):
        """结束编辑"""
        self.is_editing = False

        # 清除预览
        if self.controller:
            self.controller.clear_tool_preview()
            if hasattr(self.controller, 'canvas') and self.controller.canvas:
                self.controller.canvas.update()

        if self.controller and hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit("文字编辑完成")

    def cancel(self):
        """取消操作"""
        super().cancel()
        if self.is_editing:
            self._cancel_edit()

    def key_press(self, event):
        """键盘按下事件"""
        if not self.is_editing:
            return False

        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._commit_text()
            return True
        elif event.key() == Qt.Key.Key_Escape:
            self._cancel_edit()
            return True
        elif event.key() == Qt.Key.Key_Backspace:
            if self.preview_text:
                self.preview_text = self.preview_text[:-1]
                self._update_preview()
            return True
        else:
            text = event.text()
            if text and text.isprintable():
                self.preview_text += text
                self._update_preview()
                return True

        return False