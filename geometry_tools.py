# geometry_tools.py - 几何形状工具
from PyQt6.QtCore import Qt, QPointF, QRect, QPoint
from PyQt6.QtGui import QColor, QPen, QPainter, QBrush, QPainterPath, QImage, QPixmap
import math
from base_tool import BaseTool


class ShapeDrawingTool(BaseTool):
    """几何形状绘制工具基类"""
    def mouse_press(self, event, image_pos):
        super().mouse_press(event, image_pos)
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.start_pos = QPointF(image_pos.x(), image_pos.y())
            self.end_pos = self.start_pos
            self.drawing = True
            self._draw_preview()

    def mouse_move(self, event, image_pos):
        super().mouse_move(event, image_pos)
        if self.drawing and event.buttons():
            self.end_pos = QPointF(image_pos.x(), image_pos.y())
            if self.tool_state['is_shift_pressed']:
                x, y = self._apply_constraint(
                    self.start_pos.x(), self.start_pos.y(),
                    self.end_pos.x(), self.end_pos.y(),
                    self._get_constraint_type()
                )
                self.end_pos = QPointF(x, y)
            self._draw_preview()

    def mouse_release(self, event, image_pos):
        super().mouse_release(event, image_pos)
        if self.drawing:
            self.drawing = False
            self._commit()
            if hasattr(self.controller, 'temp_pixmap'):
                self.controller.temp_pixmap = None
                if self.controller.canvas:
                    self.controller.canvas.update()
            self.reset_states()

    def key_press(self, event):
        """处理按键事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True
        return False

    def _get_constraint_type(self):
        return 'square'

    def _should_fill(self):
        return self.tool_state['is_ctrl_pressed']

    def _draw_preview(self):
        """绘制预览"""
        if not self.controller or not self.controller.current_image:
            return

        if not self.start_pos or not self.end_pos:
            return

        # 清除之前的预览
        if hasattr(self.controller, 'temp_pixmap'):
            self.controller.temp_pixmap = None

        canvas_size = self.controller.current_image.size()
        if canvas_size.width() <= 0 or canvas_size.height() <= 0:
            return

        # 创建临时图像
        temp_image = QImage(canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
        if temp_image.isNull():
            return

        temp_image.fill(QColor(0, 0, 0, 0))

        # 创建 QPainter
        painter = QPainter()
        if not painter.begin(temp_image):
            return

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            size = self.controller.get_current_size()
            user_opacity = self.controller.get_current_opacity() / 100.0
            preview_opacity = user_opacity * 0.5

            border_color = self._get_drawing_color()
            fill_color = self.controller.get_current_bg_color() if self.tool_state['mouse_button'] == 'left' else self.controller.get_current_fg_color()

            # 处理透明色：透明色表示擦除
            if fill_color.alpha() == 0:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
                painter.setOpacity(1.0)
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.setBrush(QBrush(fill_color))
                painter.setOpacity(preview_opacity)

            if self._should_fill():
                painter.setPen(Qt.PenStyle.NoPen)
                self._draw_shape(painter)

                if size > 0:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    if border_color.alpha() == 0:
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                        painter.setPen(QPen(QColor(0, 0, 0, 0), size))
                        painter.setOpacity(1.0)
                    else:
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                        pen = QPen(border_color, size)
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                        painter.setPen(pen)
                        painter.setOpacity(preview_opacity)
                    self._draw_shape(painter)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                if border_color.alpha() == 0:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                    painter.setPen(QPen(QColor(0, 0, 0, 0), size))
                    painter.setOpacity(1.0)
                else:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                    pen = QPen(border_color, size)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    painter.setOpacity(preview_opacity)
                self._draw_shape(painter)
        finally:
            painter.end()

        self.controller.temp_pixmap = QPixmap.fromImage(temp_image)
        if self.controller.canvas:
            self.controller.canvas.update()

    def _draw_shape(self, painter):
        """由子类实现具体的形状绘制"""
        pass

    def _commit(self):
        def draw_shape(painter):
            size = self.controller.get_current_size()
            user_opacity = self.controller.get_current_opacity() / 100.0

            border_color = self._get_drawing_color()
            fill_color = self.controller.get_current_bg_color() if self.tool_state['mouse_button'] == 'left' else self.controller.get_current_fg_color()

            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if self._should_fill():
                # 处理填充颜色
                if fill_color.alpha() == 0:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                    painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
                    painter.setOpacity(1.0)
                else:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                    painter.setBrush(QBrush(fill_color))
                    painter.setOpacity(user_opacity)

                painter.setPen(Qt.PenStyle.NoPen)
                self._draw_shape(painter)

                if size > 0:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    if border_color.alpha() == 0:
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                        painter.setPen(QPen(QColor(0, 0, 0, 0), size))
                        painter.setOpacity(1.0)
                    else:
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                        pen = QPen(border_color, size)
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                        painter.setPen(pen)
                        painter.setOpacity(user_opacity)
                    self._draw_shape(painter)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                if border_color.alpha() == 0:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                    painter.setPen(QPen(QColor(0, 0, 0, 0), size))
                    painter.setOpacity(1.0)
                else:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                    pen = QPen(border_color, size)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(pen)
                    painter.setOpacity(user_opacity)
                self._draw_shape(painter)

        save_history = True
        self.controller.draw_on_active_layer(draw_shape, save_history)


class LineTool(ShapeDrawingTool):
    """直线工具"""
    def _get_constraint_type(self):
        return 'line'

    def _draw_shape(self, painter):
        if self.start_pos and self.end_pos:
            painter.drawLine(int(self.start_pos.x()), int(self.start_pos.y()),
                           int(self.end_pos.x()), int(self.end_pos.y()))


class RectangleTool(ShapeDrawingTool):
    """矩形工具"""
    def _draw_shape(self, painter):
        if self.start_pos and self.end_pos:
            x1 = int(min(self.start_pos.x(), self.end_pos.x()))
            y1 = int(min(self.start_pos.y(), self.end_pos.y()))
            x2 = int(max(self.start_pos.x(), self.end_pos.x()))
            y2 = int(max(self.start_pos.y(), self.end_pos.y()))

            # 防止零尺寸
            if x2 - x1 < 1 or y2 - y1 < 1:
                return

            painter.drawRect(x1, y1, x2 - x1, y2 - y1)


class EllipseTool(ShapeDrawingTool):
    """椭圆工具"""
    def _draw_shape(self, painter):
        if self.start_pos and self.end_pos:
            x1 = int(min(self.start_pos.x(), self.end_pos.x()))
            y1 = int(min(self.start_pos.y(), self.end_pos.y()))
            x2 = int(max(self.start_pos.x(), self.end_pos.x()))
            y2 = int(max(self.start_pos.y(), self.end_pos.y()))

            # 防止零尺寸
            if x2 - x1 < 1 or y2 - y1 < 1:
                return

            painter.drawEllipse(x1, y1, x2 - x1, y2 - y1)


class StarTool(ShapeDrawingTool):
    """五角星工具"""
    def _draw_shape(self, painter):
        if self.start_pos and self.end_pos:
            x1, y1 = self.start_pos.x(), self.start_pos.y()
            x2, y2 = self.end_pos.x(), self.end_pos.y()

            # 防止零尺寸
            if abs(x2 - x1) < 1 or abs(y2 - y1) < 1:
                return

            center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
            outer_rx = abs(x2 - x1) / 2
            outer_ry = abs(y2 - y1) / 2
            inner_rx = max(outer_rx * 0.38, 1)  # 确保不为0
            inner_ry = max(outer_ry * 0.38, 1)  # 确保不为0

            points = []
            for i in range(10):
                angle = math.pi / 2 + i * math.pi / 5
                if i % 2 == 0:
                    px = center_x + outer_rx * math.cos(angle)
                    py = center_y - outer_ry * math.sin(angle)
                else:
                    px = center_x + inner_rx * math.cos(angle)
                    py = center_y - inner_ry * math.sin(angle)
                points.append(QPoint(int(px), int(py)))

            if len(points) >= 10:
                # 使用QPainterPath来绘制多边形，避免QPolygon兼容性问题
                path = QPainterPath()
                if points:
                    path.moveTo(points[0].x(), points[0].y())
                    for point in points[1:]:
                        path.lineTo(point.x(), point.y())
                    path.closeSubpath()
                painter.drawPath(path)


class PolygonTool(ShapeDrawingTool):
    """正多边形工具"""
    def __init__(self, controller):
        super().__init__(controller)
        self.polygon_sides = 5

    def _draw_shape(self, painter):
        if self.start_pos and self.end_pos:
            x1, y1 = self.start_pos.x(), self.start_pos.y()
            x2, y2 = self.end_pos.x(), self.end_pos.y()

            # 防止零尺寸
            if abs(x2 - x1) < 1 or abs(y2 - y1) < 1:
                return

            # 确保多边形边数有效
            sides = max(3, min(self.polygon_sides, 20))  # 限制在3-20边之间

            center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
            radius_x = abs(x2 - x1) / 2
            radius_y = abs(y2 - y1) / 2

            points = []
            for i in range(sides):
                angle_deg = 90 + i * (360 / sides)
                angle_rad = math.radians(angle_deg)
                px = center_x + radius_x * math.cos(angle_rad)
                py = center_y + radius_y * math.sin(angle_rad)
                points.append(QPoint(int(px), int(py)))

            if len(points) >= 3:
                # 使用QPainterPath来绘制多边形，避免QPolygon兼容性问题
                path = QPainterPath()
                if points:
                    path.moveTo(points[0].x(), points[0].y())
                    for point in points[1:]:
                        path.lineTo(point.x(), point.y())
                    path.closeSubpath()
                painter.drawPath(path)


class RoundedRectTool(ShapeDrawingTool):
    """圆角矩形工具"""
    def _draw_shape(self, painter):
        if self.start_pos and self.end_pos:
            x1 = int(min(self.start_pos.x(), self.end_pos.x()))
            y1 = int(min(self.start_pos.y(), self.end_pos.y()))
            x2 = int(max(self.start_pos.x(), self.end_pos.x()))
            y2 = int(max(self.start_pos.y(), self.end_pos.y()))

            # 防止零尺寸
            if x2 - x1 < 1 or y2 - y1 < 1:
                return

            radius = min(abs(x2 - x1), abs(y2 - y1)) // 4
            painter.drawRoundedRect(x1, y1, x2 - x1, y2 - y1, radius, radius)


class CurveTool(BaseTool):
    """曲线工具 - 使用Catmull-Rom样条"""
    def __init__(self, controller):
        super().__init__(controller)
        self.control_points = []
        self.is_drawing = False
        self.drawing_color = None
        self.is_closed = False
        self.initial_button = None

    def mouse_press(self, event, image_pos):
        super().mouse_press(event, image_pos)
        x, y = int(image_pos.x()), int(image_pos.y())

        if event.button() == Qt.MouseButton.RightButton:
            if self.is_drawing:
                self._commit_curve()
            else:
                self.initial_button = 'right'
                self.drawing_color = self.controller.get_current_bg_color()
                self.control_points = [(x, y)]
                self.is_drawing = True
                self.is_closed = False
            return

        if not self.is_drawing:
            if event.button() == Qt.MouseButton.LeftButton:
                self.initial_button = 'left'
                self.drawing_color = self.controller.get_current_fg_color()
            else:
                return

            self.control_points = [(x, y)]
            self.is_drawing = True
            self.is_closed = False
        else:
            if event.button() == Qt.MouseButton.LeftButton:
                self.control_points.append((x, y))

        self._update_preview()

    def key_press(self, event):
        """处理按键事件"""
        if not self.is_drawing:
            return False

        if event.key() == Qt.Key.Key_C:
            self.is_closed = not self.is_closed
            self._update_preview()
            if self.controller and hasattr(self.controller, 'status_updated'):
                self.controller.status_updated.emit(f"曲线{'已封闭' if self.is_closed else '已开放'}")
            return True
        elif event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return:
            self._commit_curve()
            return True
        elif event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True

        return False

    def _catmull_rom_spline(self, points, closed=False, num_points=20):
        """生成Catmull-Rom样条曲线"""
        if len(points) < 2:
            return []

        result = []
        n = len(points)

        if closed:
            pts = [(points[-1][0], points[-1][1])] + points + [(points[0][0], points[0][1]), (points[1][0], points[1][1])]
        else:
            pts = [(points[0][0], points[0][1])] + points + [(points[-1][0], points[-1][1])]

        for i in range(1 if closed else 1, n + (1 if closed else 0)):
            p0 = pts[i-1]
            p1 = pts[i]
            p2 = pts[i+1]
            p3 = pts[i+2]

            for t in range(num_points + 1):
                t_norm = t / num_points
                t2 = t_norm * t_norm
                t3 = t2 * t_norm

                x = 0.5 * ((2 * p1[0]) +
                           (-p0[0] + p2[0]) * t_norm +
                           (2*p0[0] - 5*p1[0] + 4*p2[0] - p3[0]) * t2 +
                           (-p0[0] + 3*p1[0] - 3*p2[0] + p3[0]) * t3)

                y = 0.5 * ((2 * p1[1]) +
                           (-p0[1] + p2[1]) * t_norm +
                           (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1]) * t2 +
                           (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1]) * t3)

                result.append((int(x), int(y)))

        return result

    def _update_preview(self):
        """更新预览"""
        if not self.controller or not self.controller.current_image:
            return

        if len(self.control_points) < 2:
            return

        # 清除之前的预览
        if hasattr(self.controller, 'temp_pixmap'):
            self.controller.temp_pixmap = None

        canvas_size = self.controller.current_image.size()
        if canvas_size.width() <= 0 or canvas_size.height() <= 0:
            return

        # 创建临时图像
        temp_image = QImage(canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
        if temp_image.isNull():
            return

        temp_image.fill(QColor(0, 0, 0, 0))

        # 创建 QPainter
        painter = QPainter()
        if not painter.begin(temp_image):
            return

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            size = self.controller.get_current_size()
            user_opacity = self.controller.get_current_opacity() / 100.0
            preview_opacity = user_opacity * 0.5

            color = self.drawing_color if self.drawing_color else self.controller.get_current_fg_color()

            if color.alpha() == 0:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.setPen(QPen(QColor(0, 0, 0, 0), size))
                painter.setOpacity(1.0)
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                pen = QPen(color, size)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setOpacity(preview_opacity)

            # 绘制控制点
            for point in self.control_points:
                painter.drawEllipse(QPointF(point[0], point[1]), 2, 2)

            # 绘制曲线
            if len(self.control_points) >= 2:
                spline_points = self._catmull_rom_spline(self.control_points, self.is_closed)

                if spline_points:
                    for i in range(len(spline_points) - 1):
                        p1 = spline_points[i]
                        p2 = spline_points[i + 1]
                        painter.drawLine(p1[0], p1[1], p2[0], p2[1])
        finally:
            painter.end()

        self.controller.temp_pixmap = QPixmap.fromImage(temp_image)

        if self.controller.canvas:
            self.controller.canvas.update()

    def _commit_curve(self):
        """提交曲线"""
        if len(self.control_points) < 2:
            self.cancel()
            return

        def draw_curve(painter):
            size = self.controller.get_current_size()
            user_opacity = self.controller.get_current_opacity() / 100.0
            color = self.drawing_color if self.drawing_color else self.controller.get_current_fg_color()

            if color.alpha() == 0:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.setPen(QPen(QColor(0, 0, 0, 0), size))
                painter.setOpacity(1.0)
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                pen = QPen(color, size)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setOpacity(user_opacity)

            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if len(self.control_points) >= 2:
                spline_points = self._catmull_rom_spline(self.control_points, self.is_closed)

                if spline_points:
                    for i in range(len(spline_points) - 1):
                        p1 = spline_points[i]
                        p2 = spline_points[i + 1]
                        painter.drawLine(p1[0], p1[1], p2[0], p2[1])

        save_history = True
        self.controller.draw_on_active_layer(draw_curve, save_history)

        self.control_points = []
        self.is_drawing = False
        self.drawing_color = None
        self.is_closed = False

        if hasattr(self.controller, 'temp_pixmap'):
            self.controller.temp_pixmap = None
            if self.controller.canvas:
                self.controller.canvas.update()

        if self.controller and hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit("曲线绘制完成")

    def cancel(self):
        """取消绘制"""
        super().cancel()
        self.control_points = []
        self.is_drawing = False
        self.drawing_color = None
        self.is_closed = False