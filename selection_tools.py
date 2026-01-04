# selection_tools.py - 重构的选区工具（完全对标 TextTool 的交互逻辑）
from PyQt6.QtCore import Qt, QPointF, QRect, QPoint, QTimer, QRectF
from PyQt6.QtGui import (QColor, QPen, QPainter, QImage, QBrush, QPixmap, QPolygon, QPolygonF, QPainterPath, QFont, QFontMetrics, QTransform, QCursor)
from PyQt6.QtWidgets import QApplication
import math
import time
from base_tool import BaseTool

class BaseSelectTool(BaseTool):
    """选区工具基类 - 交互逻辑完全对标 TextTool"""
    def __init__(self, controller):
        super().__init__(controller)
        # --- 选区状态 ---
        self.selection_rect = None      # 原始选区矩形 (未变换)
        self.is_floating = False        # 标志位：选区是否处于"浮动"编辑状态
        self.selected_content = None    # 选区捕获的内容 (带Alpha通道)
        self.selection_mask = None      # 选区蒙版，用于确定哪些区域被选中

        # --- 变换控制 (与 TextTool 一致) ---
        self.is_moving = False
        self.is_scaling = False
        self.is_rotating = False
        self.is_resizing = False        # 8方向调整
        self.resize_handle = None
        self.last_mouse_pos = None
        self.original_scale = 1.0
        self.original_angle = 0.0
        self.scale_factor = 1.0
        self.rotation_angle = 0.0

        # --- 控制点 (与 TextTool 一致) ---
        self.handle_size = 12
        self.hot_size = self.handle_size * 2  # 更大的热区
        self.scale_handle_rect = None
        self.rotate_handle_rect = None
        self.transformed_corners = []
        self.rotate_handle_pos = None
        self.resize_handles = {}

        # --- 视觉样式 ---
        self.border_color = QColor(0, 150, 255)
        self.handle_color = QColor(255, 255, 255)
        self.scale_handle_color = QColor(255, 100, 100)
        self.rotate_handle_color = QColor(100, 255, 100)

        # --- 新增：自动销毁标志 ---
        self.destroy_on_other_action = True  # 是否在其他操作时销毁

    def mouse_press(self, event, image_pos):
        """鼠标按下事件"""
        super().mouse_press(event, image_pos)
        x, y = int(image_pos.x()), int(image_pos.y())

        # 如果已有浮动选区
        if self.is_floating:
            # 检查各种手柄
            if self.scale_handle_rect and self.scale_handle_rect.contains(x, y):
                self.is_scaling = True
                self.last_mouse_pos = QPointF(x, y)
                self.original_scale = self.scale_factor
                return

            if self.rotate_handle_rect and self.rotate_handle_rect.contains(x, y):
                self.is_rotating = True
                self.last_mouse_pos = QPointF(x, y)
                self.original_angle = self.rotation_angle
                return

            self.resize_handle = self._get_resize_handle_at(x, y)
            if self.resize_handle:
                self.is_resizing = True
                self.last_mouse_pos = QPointF(x, y)
                self._update_cursor(x, y)
                return

            # 检查是否在选区内
            if self._is_point_in_selection(x, y):
                self.is_moving = True
                self.last_mouse_pos = QPointF(x, y)
                self._set_cursor(Qt.CursorShape.ClosedHandCursor)
                return

            # 点击外部，提交选区（这是唯一自动提交的情况）
            self._commit_selection()
            return

        # 创建新选区 (仅当没有浮动选区时)
        if event.button() == Qt.MouseButton.LeftButton and not self.is_floating:
            self._start_new_selection(x, y)

    def mouse_move(self, event, image_pos):
        """鼠标移动事件"""
        super().mouse_move(event, image_pos)
        x, y = int(image_pos.x()), int(image_pos.y())

        # 更新光标（非操作状态）
        if self.is_floating and not (self.is_moving or self.is_scaling or self.is_rotating or self.is_resizing):
            self._update_cursor(x, y)

        # 处理各种变换
        if self.is_moving and self.last_mouse_pos:
            dx = x - int(self.last_mouse_pos.x())
            dy = y - int(self.last_mouse_pos.y())
            self._move_selection(dx, dy)
            self.last_mouse_pos = QPointF(x, y)
            self._update_selection_preview()

        elif self.is_resizing and self.resize_handle and self.last_mouse_pos:
            dx = x - int(self.last_mouse_pos.x())
            dy = y - int(self.last_mouse_pos.y())
            self._resize_selection(dx, dy)
            self.last_mouse_pos = QPointF(x, y)
            self._update_selection_preview()

        elif self.is_scaling and self.last_mouse_pos:
            self._handle_scaling(x, y)

        elif self.is_rotating and self.last_mouse_pos:
            self._handle_rotation(x, y)

        # 绘制新选区预览
        elif self.drawing:
            self.end_pos = QPointF(x, y)
            if self.tool_state['is_shift_pressed']:
                self._apply_square_constraint()
            self._update_preview()

    def mouse_release(self, event, image_pos):
        """鼠标释放事件"""
        super().mouse_release(event, image_pos)
        if self.is_moving or self.is_scaling or self.is_rotating or self.is_resizing:
            self.is_moving = False
            self.is_scaling = False
            self.is_rotating = False
            self.is_resizing = False
            self.resize_handle = None
            self.last_mouse_pos = None
            self._update_selection_preview()
            self._set_cursor(Qt.CursorShape.ArrowCursor)
            return

        # 完成新选区的创建，进入浮动状态
        if self.drawing:
            self.drawing = False
            self._finalize_selection()

    def key_press(self, event):
        """处理按键事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True

        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if self.is_floating:
                self._commit_selection()
            return True

        # 新增：如果按下其他按键（非Enter/Esc）且有浮动选区，则销毁选区
        if self.is_floating and self.destroy_on_other_action:
            # 检查是否是非操作键（这里排除方向键、修改键等）
            non_operation_keys = [
                Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt,
                Qt.Key.Key_Meta, Qt.Key.Key_CapsLock, Qt.Key.Key_NumLock,
                Qt.Key.Key_ScrollLock,
                Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                Qt.Key.Key_PageUp, Qt.Key.Key_PageDown, Qt.Key.Key_Home, Qt.Key.Key_End
            ]
            if event.key() not in non_operation_keys:
                # 排除我们处理的键
                if event.key() not in (Qt.Key.Key_Escape, Qt.Key.Key_Enter, Qt.Key.Key_Return):
                    self._cancel_selection()
                    # 返回False让其他工具可以处理这个按键
                    return False

        # TODO: 可以在这里添加 Ctrl+C/V/X 等快捷键逻辑
        return False

    def on_tool_changed(self):
        """当工具切换时被控制器调用 - 销毁选区"""
        if self.is_floating and self.destroy_on_other_action:
            self._cancel_selection()

    def on_other_operation(self):
        """当执行其他操作（如菜单操作、工具栏按钮）时被控制器调用 - 销毁选区"""
        if self.is_floating and self.destroy_on_other_action:
            self._cancel_selection()

    def on_menu_action(self):
        """当执行菜单操作时被控制器调用 - 销毁选区"""
        if self.is_floating and self.destroy_on_other_action:
            self._cancel_selection()

    def on_toolbar_button_click(self):
        """当点击工具栏按钮时被控制器调用 - 销毁选区"""
        if self.is_floating and self.destroy_on_other_action:
            self._cancel_selection()

    def set_auto_destroy(self, enabled):
        """设置是否在其他操作时自动销毁选区"""
        self.destroy_on_other_action = enabled

    def _start_new_selection(self, x, y):
        """开始新选区"""
        self.start_pos = QPointF(x, y)
        self.end_pos = self.start_pos
        self.drawing = True
        self._set_cursor(Qt.CursorShape.CrossCursor)
        self._update_preview()

    def _apply_square_constraint(self):
        """应用正方形/圆形约束"""
        if not self.start_pos or not self.end_pos:
            return
        dx = self.end_pos.x() - self.start_pos.x()
        dy = self.end_pos.y() - self.start_pos.y()
        size = max(abs(dx), abs(dy))
        end_x = self.start_pos.x() + (size if dx >= 0 else -size)
        end_y = self.start_pos.y() + (size if dy >= 0 else -size)
        self.end_pos = QPointF(end_x, end_y)

    def _move_selection(self, dx, dy):
        """移动选区"""
        if self.selection_rect:
            self.selection_rect.translate(dx, dy)

    def _resize_selection(self, dx, dy):
        """调整选区大小 (8方向)"""
        if not self.selection_rect or not self.resize_handle:
            return
        rect = self.selection_rect
        if self.resize_handle == 'tl':
            rect.setLeft(rect.left() + dx); rect.setTop(rect.top() + dy)
        elif self.resize_handle == 'tr':
            rect.setRight(rect.right() + dx); rect.setTop(rect.top() + dy)
        elif self.resize_handle == 'bl':
            rect.setLeft(rect.left() + dx); rect.setBottom(rect.bottom() + dy)
        elif self.resize_handle == 'br':
            rect.setRight(rect.right() + dx); rect.setBottom(rect.bottom() + dy)
        elif self.resize_handle == 't':
            rect.setTop(rect.top() + dy)
        elif self.resize_handle == 'b':
            rect.setBottom(rect.bottom() + dy)
        elif self.resize_handle == 'l':
            rect.setLeft(rect.left() + dx)
        elif self.resize_handle == 'r':
            rect.setRight(rect.right() + dx)
        
        rect = rect.normalized()
        rect.setWidth(max(1, rect.width()))
        rect.setHeight(max(1, rect.height()))
        self.selection_rect = rect

    def _handle_scaling(self, x, y):
        """处理基于中心的缩放"""
        if not self.selection_rect:
            return
        center = self.selection_rect.center()
        dist = math.sqrt((x - center.x()) ** 2 + (y - center.y()) ** 2)
        original_dist = math.sqrt((self.last_mouse_pos.x() - center.x()) ** 2 + (self.last_mouse_pos.y() - center.y()) ** 2)
        if original_dist > 0:
            scale_delta = dist / original_dist
            self.scale_factor = self.original_scale * scale_delta
            self.scale_factor = max(0.1, min(self.scale_factor, 10.0))
            self._update_selection_preview()

    def _handle_rotation(self, x, y):
        """处理基于中心的旋转"""
        if not self.selection_rect:
            return
        center = self.selection_rect.center()
        dx1 = self.last_mouse_pos.x() - center.x()
        dy1 = self.last_mouse_pos.y() - center.y()
        dx2 = x - center.x()
        dy2 = y - center.y()
        angle1 = math.degrees(math.atan2(dy1, dx1))
        angle2 = math.degrees(math.atan2(dy2, dx2))
        angle_diff = angle2 - angle1
        self.rotation_angle = (self.original_angle + angle_diff) % 360
        self._update_selection_preview()

    def _update_handles(self):
        """更新所有控制点的位置 (考虑当前变换)"""
        if not self.selection_rect:
            return

        transform = QTransform()
        center = self.selection_rect.center()
        transform.translate(center.x(), center.y())
        transform.rotate(self.rotation_angle)
        transform.scale(self.scale_factor, self.scale_factor)
        transform.translate(-center.x(), -center.y())

        corners = [
            QPointF(self.selection_rect.left(), self.selection_rect.top()),
            QPointF(self.selection_rect.right(), self.selection_rect.top()),
            QPointF(self.selection_rect.left(), self.selection_rect.bottom()),
            QPointF(self.selection_rect.right(), self.selection_rect.bottom())
        ]
        self.transformed_corners = [transform.map(corner) for corner in corners]

        # 缩放手柄 (右下角)
        br_corner = self.transformed_corners[3]
        self.scale_handle_rect = QRect(
            int(br_corner.x() - self.hot_size / 2),
            int(br_corner.y() - self.hot_size / 2),
            self.hot_size, self.hot_size
        )

        # 旋转手柄 (右上角外延)
        tr_corner = self.transformed_corners[1]
        offset = 20 * self.scale_factor
        dx = tr_corner.x() - center.x()
        dy = tr_corner.y() - center.y()
        length = math.sqrt(dx*dx + dy*dy)
        if length > 0:
            rotate_x = tr_corner.x() + (dx / length) * offset
            rotate_y = tr_corner.y() + (dy / length) * offset
        else:
            rotate_x, rotate_y = tr_corner.x() + offset, tr_corner.y() - offset
        
        self.rotate_handle_rect = QRect(
            int(rotate_x - self.hot_size / 2),
            int(rotate_y - self.hot_size / 2),
            self.hot_size, self.hot_size
        )
        self.rotate_handle_pos = QPointF(rotate_x, rotate_y)

        # 8方向调整手柄
        self._update_resize_handles()

    def _update_resize_handles(self):
        """更新8个调整手柄的位置"""
        if len(self.transformed_corners) < 4:
            return
        tl, tr, bl, br = self.transformed_corners
        t_mid = QPointF((tl.x() + tr.x()) / 2, (tl.y() + tr.y()) / 2)
        b_mid = QPointF((bl.x() + br.x()) / 2, (bl.y() + br.y()) / 2)
        l_mid = QPointF((tl.x() + bl.x()) / 2, (tl.y() + bl.y()) / 2)
        r_mid = QPointF((tr.x() + br.x()) / 2, (tr.y() + br.y()) / 2)

        handle_size = self.handle_size
        self.resize_handles = {
            'tl': QRect(int(tl.x() - handle_size/2), int(tl.y() - handle_size/2), handle_size, handle_size),
            'tr': QRect(int(tr.x() - handle_size/2), int(tr.y() - handle_size/2), handle_size, handle_size),
            'bl': QRect(int(bl.x() - handle_size/2), int(bl.y() - handle_size/2), handle_size, handle_size),
            'br': QRect(int(br.x() - handle_size/2), int(br.y() - handle_size/2), handle_size, handle_size),
            't': QRect(int(t_mid.x() - handle_size/2), int(t_mid.y() - handle_size/2), handle_size, handle_size),
            'b': QRect(int(b_mid.x() - handle_size/2), int(b_mid.y() - handle_size/2), handle_size, handle_size),
            'l': QRect(int(l_mid.x() - handle_size/2), int(l_mid.y() - handle_size/2), handle_size, handle_size),
            'r': QRect(int(r_mid.x() - handle_size/2), int(r_mid.y() - handle_size/2), handle_size, handle_size),
        }

    def _get_resize_handle_at(self, x, y):
        """获取鼠标所在位置的调整手柄"""
        if not self.resize_handles:
            return None
        hot_expand = 10
        for name, rect in self.resize_handles.items():
            if rect.adjusted(-hot_expand, -hot_expand, hot_expand, hot_expand).contains(x, y):
                return name
        return None

    def _update_preview(self):
        """更新绘制新选区时的预览 (虚线框)"""
        if not self.controller or not self.controller.current_image or not self.start_pos or not self.end_pos:
            return

        canvas_size = self.controller.current_image.size()
        temp_image = QImage(canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
        temp_image.fill(QColor(0, 0, 0, 0))

        painter = QPainter(temp_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.border_color, 2, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 4])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        x1 = int(min(self.start_pos.x(), self.end_pos.x()))
        y1 = int(min(self.start_pos.y(), self.end_pos.y()))
        x2 = int(max(self.start_pos.x(), self.end_pos.x()))
        y2 = int(max(self.start_pos.y(), self.end_pos.y()))
        self._draw_selection_preview(painter, x1, y1, x2 - x1, y2 - y1)

        self._draw_hint(painter, "拖动创建选区，Shift=正方形/圆形")
        painter.end()

        self.controller.temp_pixmap = QPixmap.fromImage(temp_image)
        if self.controller.canvas:
            self.controller.canvas.update()

    def _finalize_selection(self):
        """完成选区创建，进入浮动编辑状态"""
        if not self.start_pos or not self.end_pos:
            return

        x1 = int(min(self.start_pos.x(), self.end_pos.x()))
        y1 = int(min(self.start_pos.y(), self.end_pos.y()))
        x2 = int(max(self.start_pos.x(), self.end_pos.x()))
        y2 = int(max(self.start_pos.y(), self.end_pos.y()))

        if x2 - x1 > 1 and y2 - y1 > 1:
            self.selection_rect = QRect(x1, y1, x2 - x1, y2 - y1)
            self.is_floating = True
            self.scale_factor = 1.0
            self.rotation_angle = 0.0
            self._capture_selection()  # 关键：捕获带Alpha的内容
            self._update_selection_preview()
            if self.controller and hasattr(self.controller, 'status_updated'):
                self.controller.status_updated.emit(
                    f"选区就绪: {self.selection_rect.width()}x{self.selection_rect.height()} | "
                    "拖动=移动, 角点=调整, 右下=缩放, 右上=旋转, Enter=提交, 画布外单击=提交, 其他操作=取消"
                )
        else:
            self.cancel()

    def _capture_selection(self):
        """捕获选区内容，并生成正确的Alpha蒙版"""
        if not self.selection_rect or not self.controller or not self.controller.layers:
            return

        active_layer = self.controller.layers[self.controller.active_layer_index]
        layer_image = active_layer['image']

        # 1. 创建选区蒙版 (子类可重写此方法实现不同形状)
        self.selection_mask = self._create_selection_mask()
        if self.selection_mask is None:
            return

        # 2. 创建一个新的ARGB图像来存储选区内容
        self.selected_content = QImage(self.selection_rect.size(), QImage.Format.Format_ARGB32)
        self.selected_content.fill(QColor(0, 0, 0, 0))  # 填充完全透明
        
        # 3. 使用QPainter将原始内容和蒙版合并
        painter = QPainter(self.selected_content)
        
        # 先绘制原始内容
        source_rect = QRect(0, 0, self.selection_rect.width(), self.selection_rect.height())
        painter.drawImage(source_rect, layer_image, self.selection_rect)
        
        # 然后应用蒙版作为alpha通道
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, self.selection_mask)
        
        painter.end()

    def _create_selection_mask(self):
        """创建矩形选区的蒙版 (白色区域表示选中)"""
        if not self.selection_rect:
            return None
        mask = QImage(self.selection_rect.size(), QImage.Format.Format_ARGB32)
        mask.fill(QColor(0, 0, 0, 0))  # 先填充透明
        painter = QPainter(mask)
        painter.fillRect(mask.rect(), QColor(255, 255, 255, 255))  # 再填充白色不透明
        painter.end()
        return mask

    def _update_selection_preview(self):
        """更新浮动选区的预览 (显示在 temp_pixmap 上)"""
        if not self.controller or not self.controller.current_image or not self.is_floating:
            return

        canvas_size = self.controller.current_image.size()
        temp_image = QImage(canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
        temp_image.fill(QColor(0, 0, 0, 0))

        painter = QPainter(temp_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 绘制变换后的选区内容
        if self.selected_content and not self.selected_content.isNull():
            self._draw_transformed_content(painter)

        # 绘制选区框架和手柄
        self._draw_selection_frame(painter)

        self._draw_hint(painter, "🔵移动 🔴缩放 🟢旋转 ⚪调整 Enter=提交 画布外单击=提交 其他操作=取消")
        painter.end()

        self.controller.temp_pixmap = QPixmap.fromImage(temp_image)
        if self.controller.canvas:
            self.controller.canvas.update()

    def _draw_transformed_content(self, painter):
        """绘制经过缩放和旋转的选区内容"""
        if not self.selected_content or not self.selection_rect:
            return

        center = self.selection_rect.center()
        painter.save()
        painter.translate(center.x(), center.y())
        painter.rotate(self.rotation_angle)
        painter.scale(self.scale_factor, self.scale_factor)
        painter.translate(-center.x(), -center.y())

        # 使用 SmoothTransformation 保证质量
        scaled_content = self.selected_content.scaled(
            self.selection_rect.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawImage(self.selection_rect.topLeft(), scaled_content)
        painter.restore()

    def _draw_selection_frame(self, painter):
        """绘制选区的边框、手柄和中心点"""
        if not self.selection_rect:
            return

        self._update_handles()

        # 绘制变换后的边框
        pen = QPen(self.border_color, 2, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 4])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.save()
        center = self.selection_rect.center()
        painter.translate(center.x(), center.y())
        painter.rotate(self.rotation_angle)
        painter.scale(self.scale_factor, self.scale_factor)
        painter.translate(-center.x(), -center.y())
        # 绘制实际选区形状（矩形、椭圆或多边形）
        self._draw_selection_frame_shape(painter)
        painter.restore()

        # 绘制8个调整手柄（基于transformed_corners）
        painter.setBrush(QBrush(self.handle_color))
        painter.setPen(QPen(self.border_color, 1))
        for handle_rect in self.resize_handles.values():
            painter.drawRect(handle_rect)

        # 绘制缩放手柄 (右下角)
        br_corner = self.transformed_corners[3]
        painter.setBrush(QBrush(self.scale_handle_color))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        handle_rect = QRect(
            int(br_corner.x() - self.handle_size / 2),
            int(br_corner.y() - self.handle_size / 2),
            self.handle_size, self.handle_size
        )
        painter.drawRect(handle_rect)
        painter.drawLine(handle_rect.topLeft(), handle_rect.bottomRight())
        painter.drawLine(handle_rect.topRight(), handle_rect.bottomLeft())

        # 绘制旋转手柄 (右上角外延)
        tr_corner = self.transformed_corners[1]
        rotate_pos = self.rotate_handle_pos
        # 连接线
        painter.setPen(QPen(self.rotate_handle_color, 1, Qt.PenStyle.DotLine))
        painter.drawLine(int(tr_corner.x()), int(tr_corner.y()), int(rotate_pos.x()), int(rotate_pos.y()))
        # 手柄本身
        painter.setBrush(QBrush(self.rotate_handle_color))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawEllipse(
            int(rotate_pos.x() - self.handle_size / 2),
            int(rotate_pos.y() - self.handle_size / 2),
            self.handle_size, self.handle_size
        )
        # 旋转图标
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        arc_rect = QRect(int(rotate_pos.x() - 4), int(rotate_pos.y() - 4), 8, 8)
        painter.drawArc(arc_rect, 30 * 16, 300 * 16)

        # 绘制中心点
        center = self.selection_rect.center()
        transform = QTransform()
        transform.translate(center.x(), center.y())
        transform.rotate(self.rotation_angle)
        transform.scale(self.scale_factor, self.scale_factor)
        transform.translate(-center.x(), -center.y())
        transformed_center = transform.map(center)

        painter.setPen(QPen(QColor(255, 255, 0), 1))
        painter.setBrush(QBrush(QColor(255, 255, 0)))
        cross_size = 8
        painter.drawLine(int(transformed_center.x() - cross_size), int(transformed_center.y()), int(transformed_center.x() + cross_size), int(transformed_center.y()))
        painter.drawLine(int(transformed_center.x()), int(transformed_center.y() - cross_size), int(transformed_center.x()), int(transformed_center.y() + cross_size))
        painter.drawEllipse(int(transformed_center.x() - 3), int(transformed_center.y() - 3), 6, 6)

    def _draw_hint(self, painter, hint_text):
        """在画布左上角绘制操作提示"""
        painter.save()
        font = QFont("Arial", 10)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        padding = 10
        text_width = metrics.horizontalAdvance(hint_text)
        text_height = metrics.height()
        hint_rect = QRect(10, 10, text_width + padding * 2, text_height + padding * 2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.drawRoundedRect(hint_rect, 5, 5)

        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(hint_rect.left() + padding, hint_rect.top() + padding + text_height - 2, hint_text)
        painter.restore()

    def _draw_selection_preview(self, painter, x, y, w, h):
        """绘制初始选区预览 (由子类实现不同形状)"""
        painter.drawRect(x, y, w, h)

    def _draw_selection_frame_shape(self, painter):
        """绘制选区形状（矩形、椭圆等）"""
        # 默认绘制矩形
        painter.drawRect(self.selection_rect)

    def _is_point_in_selection(self, x, y):
        """判断点是否在(变换后的)选区内"""
        if not self.selection_rect:
            return False

        transform = QTransform()
        center = self.selection_rect.center()
        transform.translate(center.x(), center.y())
        transform.rotate(self.rotation_angle)
        transform.scale(self.scale_factor, self.scale_factor)
        transform.translate(-center.x(), -center.y())

        polygon = QPolygonF(QRectF(self.selection_rect))
        transformed = transform.map(polygon)
        return transformed.containsPoint(QPointF(x, y), Qt.FillRule.OddEvenFill)

    def _update_cursor(self, x, y):
        """根据鼠标位置更新光标"""
        if not self.controller or not self.controller.canvas:
            return

        if self.scale_handle_rect and self.scale_handle_rect.contains(x, y):
            self.controller.canvas.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        elif self.rotate_handle_rect and self.rotate_handle_rect.contains(x, y):
            self.controller.canvas.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        elif (handle := self._get_resize_handle_at(x, y)):
            cursor_map = {
                'tl': Qt.CursorShape.SizeFDiagCursor, 'tr': Qt.CursorShape.SizeBDiagCursor,
                'bl': Qt.CursorShape.SizeBDiagCursor, 'br': Qt.CursorShape.SizeFDiagCursor,
                't': Qt.CursorShape.SizeVerCursor, 'b': Qt.CursorShape.SizeVerCursor,
                'l': Qt.CursorShape.SizeHorCursor, 'r': Qt.CursorShape.SizeHorCursor,
            }
            self.controller.canvas.setCursor(QCursor(cursor_map.get(handle, Qt.CursorShape.ArrowCursor)))
        elif self._is_point_in_selection(x, y):
            self.controller.canvas.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.controller.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _set_cursor(self, cursor):
        """设置光标"""
        if self.controller and self.controller.canvas:
            self.controller.canvas.setCursor(QCursor(cursor))

    def _commit_selection(self):
        """【核心】将变换后的浮动选区提交到原图层"""
        if not self.is_floating or not self.selection_rect or self.selected_content is None:
            return

        # 1. 保存历史记录
        if hasattr(self.controller, 'save_to_history'):
            self.controller.save_to_history()

        # 2. 定义一个绘制函数，用于在活动图层上执行操作
        def draw_transformed_selection(painter):
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 第一步：创建一个临时蒙版图像，用于清除原选区区域
            if self.selection_mask:
                # 应用变换到蒙版
                mask_image = self.selection_mask.scaled(
                    self.selection_rect.size(),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # 使用CompositionMode_DestinationOut清除原选区内容
                # 这会根据蒙版的alpha值来清除相应区域
                painter.save()
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
                center = self.selection_rect.center()
                painter.translate(center.x(), center.y())
                painter.rotate(self.rotation_angle)
                painter.scale(self.scale_factor, self.scale_factor)
                painter.translate(-center.x(), -center.y())
                painter.drawImage(self.selection_rect.topLeft(), mask_image)
                painter.restore()
            
            # 第二步：绘制变换后的新内容
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
            center = self.selection_rect.center()
            painter.save()
            painter.translate(center.x(), center.y())
            painter.rotate(self.rotation_angle)
            painter.scale(self.scale_factor, self.scale_factor)
            painter.translate(-center.x(), -center.y())
            
            scaled_content = self.selected_content.scaled(
                self.selection_rect.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawImage(self.selection_rect.topLeft(), scaled_content)
            painter.restore()

        # 3. 调用控制器方法，将绘制操作应用到活动图层
        self.controller.draw_on_active_layer(draw_transformed_selection, save_history=False)

        # 4. 清理状态，退出浮动模式
        self._cancel_selection()

    def _cancel_selection(self):
        """取消浮动选区，清理状态（不提交）"""
        self.is_floating = False
        self.selection_rect = None
        self.selected_content = None
        self.selection_mask = None
        self.scale_factor = 1.0
        self.rotation_angle = 0.0
        # 清除临时预览
        if self.controller:
            self.controller.temp_pixmap = None
            if self.controller.canvas:
                self.controller.canvas.update()
                self.controller.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        
        # 清理多边形工具的点列表
        if hasattr(self, 'points'):
            self.points.clear()
        if hasattr(self, 'original_points'):
            self.original_points.clear()

        # 发送状态更新
        if self.controller and hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit("选区已取消")

    def cancel(self):
        """对外暴露的取消方法"""
        super().cancel()
        self._cancel_selection()


# ==================== 具体的选区工具实现 ====================
class RectSelectTool(BaseSelectTool):
    """矩形选区工具"""
    def __init__(self, controller):
        super().__init__(controller)

    def _draw_selection_preview(self, painter, x, y, w, h):
        painter.drawRect(x, y, w, h)

    def _draw_selection_frame_shape(self, painter):
        painter.drawRect(self.selection_rect)


class EllipseSelectTool(BaseSelectTool):
    """椭圆选区工具"""
    def __init__(self, controller):
        super().__init__(controller)

    def _draw_selection_preview(self, painter, x, y, w, h):
        painter.drawEllipse(x, y, w, h)

    def _draw_selection_frame_shape(self, painter):
        painter.drawEllipse(self.selection_rect)

    def _create_selection_mask(self):
        """创建椭圆选区的蒙版"""
        if not self.selection_rect:
            return None
        mask = QImage(self.selection_rect.size(), QImage.Format.Format_ARGB32)
        mask.fill(QColor(0, 0, 0, 0))
        painter = QPainter(mask)
        painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(mask.rect())
        painter.end()
        return mask


class ImprovedPolygonSelectTool(BaseSelectTool):
    """多边形选区工具"""
    def __init__(self, controller):
        super().__init__(controller)
        self.points = []  # 固定的点列表
        self.original_points = []  # 保存原始点（相对于选区矩形），用于变换
        self.temp_point = None  # 当前鼠标位置的预览点
        self.is_creating = False   # 是否正在创建多边形
        self.has_first_click = False  # 是否已经进行了第一次点击

    def mouse_press(self, event, image_pos):
        """重写鼠标按下以处理多边形创建"""
        x, y = int(image_pos.x()), int(image_pos.y())
        
        # 如果已有浮动选区，使用基类的编辑逻辑
        if self.is_floating:
            # 检查是否在选区内或手柄上
            in_selection = self._is_point_in_selection(x, y)
            on_scale = self.scale_handle_rect and self.scale_handle_rect.contains(x, y)
            on_rotate = self.rotate_handle_rect and self.rotate_handle_rect.contains(x, y)
            on_resize = self._get_resize_handle_at(x, y) is not None
            
            # 如果在选区外，提交选区
            if not (in_selection or on_scale or on_rotate or on_resize):
                self._commit_selection()
                return
            
            # 否则调用基类的编辑逻辑
            super().mouse_press(event, image_pos)
            return
        
        # 如果没有浮动选区，处理多边形创建
        if event.button() == Qt.MouseButton.LeftButton:
            # 第一次点击就直接开始创建
            if not self.has_first_click:
                # 这是第一次点击，开始创建新多边形
                self.has_first_click = True
                self.is_creating = True
                self.points = [QPointF(x, y)]  # 放置第一个点
                self._set_cursor(Qt.CursorShape.CrossCursor)
                self._update_preview()  # 立即更新预览显示第一个点
                
                # 更新状态提示
                if self.controller and hasattr(self.controller, 'status_updated'):
                    self.controller.status_updated.emit("多边形创建中: 已放置第1个点 - 继续左键添加点，右键完成，Enter完成，Esc取消")
            else:
                # 已经开始了创建，添加新点
                self.points.append(QPointF(x, y))
                self.temp_point = None  # 点击后清除预览
                self._update_preview()

                # 更新状态提示
                if self.controller and hasattr(self.controller, 'status_updated'):
                    self.controller.status_updated.emit(f"多边形创建中: 已放置第{len(self.points)}个点 - 移动鼠标预览，左键添加点，右键完成，Enter完成，Esc取消")
            
        elif event.button() == Qt.MouseButton.RightButton:
            if self.is_creating and len(self.points) >= 3:
                # 右键完成多边形
                self._finalize_selection()
            elif not self.is_creating:
                # 如果没有在创建，则取消
                self.cancel()

    def mouse_move(self, event, image_pos):
        """重写鼠标移动"""
        if self.is_floating:
            # 如果已有浮动选区，使用基类的移动逻辑
            super().mouse_move(event, image_pos)
            return
        
        if self.is_creating and self.has_first_click:
            # 实时更新预览点
            x, y = int(image_pos.x()), int(image_pos.y())
            if not self.temp_point or self.temp_point != QPointF(x, y):
                self.temp_point = QPointF(x, y)
                self._update_preview()

    def mouse_release(self, event, image_pos):
        """重写鼠标释放"""
        # 多边形创建不需要特殊的鼠标释放处理
        if not self.is_floating:
            return
        super().mouse_release(event, image_pos)

    def key_press(self, event):
        """处理按键事件"""
        if event.key() == Qt.Key.Key_Escape:
            if self.is_creating:
                # 在创建过程中按Esc，取消创建
                self.cancel()
                return True
            else:
                # 在浮动状态下按Esc，取消选区
                return super().key_press(event)
        
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if self.is_floating:
                self._commit_selection()
                return True
            elif self.is_creating and len(self.points) >= 3:
                # 在创建过程中按Enter，完成创建
                self._finalize_selection()
                return True
            elif self.is_creating and len(self.points) < 3:
                # 在创建过程中按Enter但点不够，提示用户
                if self.controller and hasattr(self.controller, 'status_updated'):
                    self.controller.status_updated.emit("多边形至少需要3个点才能完成")
                return True
        
        # 其他按键处理
        return super().key_press(event)

    def _finalize_selection(self):
        """完成多边形创建"""
        if len(self.points) < 3:
            if self.controller and hasattr(self.controller, 'status_updated'):
                self.controller.status_updated.emit("多边形至少需要3个点")
            self.cancel()
            return

        # 计算bounding rect
        min_x = min(p.x() for p in self.points)
        min_y = min(p.y() for p in self.points)
        max_x = max(p.x() for p in self.points)
        max_y = max(p.y() for p in self.points)
        self.selection_rect = QRect(int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y))

        # 保存原始点（相对于选区矩形）
        self.original_points = [QPointF(p.x() - self.selection_rect.x(),
                                         p.y() - self.selection_rect.y())
                                for p in self.points]

        self.is_floating = True
        self.is_creating = False  # 完成创建
        self.has_first_click = False  # 重置第一次点击标志
        self.scale_factor = 1.0
        self.rotation_angle = 0.0
        self._capture_selection()
        self._update_selection_preview()

    def _update_preview(self):
        """重写预览更新以适应多边形"""
        if not self.controller or not self.controller.current_image:
            return

        canvas_size = self.controller.current_image.size()
        temp_image = QImage(canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
        temp_image.fill(QColor(0, 0, 0, 0))

        painter = QPainter(temp_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.border_color, 2, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 4])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # 绘制多边形预览
        if self.points and self.is_creating:
            # 绘制固定点
            point_radius = 5
            painter.setBrush(QBrush(self.border_color))
            painter.setPen(QPen(self.border_color, 2))
            for point in self.points:
                painter.drawEllipse(point, point_radius, point_radius)

            # 为第一个点添加特殊标记
            if len(self.points) >= 1:
                painter.setPen(QPen(QColor(255, 0, 0), 2))  # 红色边框
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(self.points[0], point_radius + 2, point_radius + 2)

            # 绘制固定线
            if len(self.points) > 1:
                for i in range(len(self.points) - 1):
                    painter.drawLine(self.points[i], self.points[i + 1])

            # 绘制预览点和线
            if self.temp_point and len(self.points) >= 1:
                painter.setPen(QPen(self.border_color, 2, Qt.PenStyle.DashLine))
                painter.drawLine(self.points[-1], self.temp_point)

                painter.setBrush(QBrush(QColor(255, 0, 0)))
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawEllipse(self.temp_point, point_radius, point_radius)

        point_count = len(self.points)
        hint_text = f"多边形创建中: {point_count}个点 - 移动鼠标预览，左键添加点，右键/Enter完成，Esc取消"
        self._draw_hint(painter, hint_text)
        painter.end()

        self.controller.temp_pixmap = QPixmap.fromImage(temp_image)
        if self.controller.canvas:
            self.controller.canvas.update()

    def _draw_selection_preview(self, painter, x, y, w, h):
        """绘制多边形预览（基类调用）"""
        # 这个方法被基类的 _update_preview 调用，但在多边形工具中我们有自己的预览逻辑
        # 所以这里什么都不做
        pass

    def _draw_selection_frame_shape(self, painter):
        """绘制多边形边框"""
        if self.original_points:
            # 使用原始点加上选区偏移，绘制当前变换后的多边形
            poly = QPolygonF([QPointF(p.x() + self.selection_rect.x(),
                                       p.y() + self.selection_rect.y())
                              for p in self.original_points])
            painter.drawPolygon(poly)

    def _create_selection_mask(self):
        """创建多边形选区的蒙版"""
        if not self.selection_rect or not self.original_points:
            return None

        mask = QImage(self.selection_rect.size(), QImage.Format.Format_ARGB32)
        mask.fill(QColor(0, 0, 0, 0))
        painter = QPainter(mask)
        painter.setBrush(QBrush(QColor(255, 255, 255, 255)))
        painter.setPen(Qt.PenStyle.NoPen)

        painter.drawPolygon(QPolygonF(self.original_points))
        painter.end()
        return mask

    def _is_point_in_selection(self, x, y):
        """检查点是否在变换后的多边形内"""
        if not self.original_points:
            return False

        transform = QTransform()
        center = self.selection_rect.center()
        transform.translate(center.x(), center.y())
        transform.rotate(self.rotation_angle)
        transform.scale(self.scale_factor, self.scale_factor)
        transform.translate(-center.x(), -center.y())

        poly = QPolygonF([QPointF(p.x() + self.selection_rect.x(),
                                   p.y() + self.selection_rect.y())
                          for p in self.original_points])
        transformed_poly = transform.map(poly)
        return transformed_poly.containsPoint(QPointF(x, y), Qt.FillRule.OddEvenFill)

    def _update_selection_preview(self):
        """更新浮动选区的预览"""
        if not self.controller or not self.controller.current_image:
            return
        
        if not self.is_floating and self.is_creating:
            # 如果是创建中的状态，使用自己的预览逻辑
            self._update_preview()
            return
        
        # 否则调用基类的预览逻辑
        super()._update_selection_preview()

    def cancel(self):
        """取消时清理点列表"""
        if self.is_creating:
            # 取消创建过程
            self.is_creating = False
            self.has_first_click = False
            self.points.clear()
            self.original_points.clear()
            # 清除预览
            if self.controller:
                self.controller.temp_pixmap = None
                if self.controller.canvas:
                    self.controller.canvas.update()
                    self.controller.canvas.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            # 发送状态更新
            if self.controller and hasattr(self.controller, 'status_updated'):
                self.controller.status_updated.emit("多边形创建已取消")
        else:
            # 取消浮动选区
            super().cancel()

    def on_tool_changed(self):
        """当工具切换时被控制器调用"""
        # 如果在创建过程中切换工具，取消创建
        if self.is_creating:
            self.cancel()
        # 否则调用基类的销毁逻辑
        elif self.is_floating and self.destroy_on_other_action:
            self._cancel_selection()

    def on_other_operation(self):
        """当执行其他操作时被控制器调用"""
        # 如果在创建过程中执行其他操作，取消创建
        if self.is_creating:
            self.cancel()
        # 否则调用基类的销毁逻辑
        elif self.is_floating and self.destroy_on_other_action:
            self._cancel_selection()

    def on_menu_action(self):
        """当执行菜单操作时被控制器调用"""
        self.on_other_operation()

    def on_toolbar_button_click(self):
        """当点击工具栏按钮时被控制器调用"""
        self.on_other_operation()