# drawing_tools.py - 绘图工具类
from PyQt6.QtCore import Qt, QPointF, QTimer
from PyQt6.QtGui import QColor, QPen, QPainter, QBrush, QImage, QPixmap, QCursor
import math
from base_tool import BaseTool


class BrushTool(BaseTool):
    """画笔工具"""
    def __init__(self, controller):
        super().__init__(controller)
        self.last_point = None
        self.brush_size = 10
        self.brush_opacity = 100
        self.brush_color = QColor("black")
        self.brush_hardness = 0.5
    
    def mouse_press(self, event, image_pos):
        """鼠标按下事件"""
        super().mouse_press(event, image_pos)

        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.drawing = True
            self.start_pos = image_pos
            self.last_point = image_pos
            self.draw_batch_started = True

            # 获取当前画笔属性
            self._update_brush_properties()

            # 开始绘制
            self._draw_point(image_pos)
    
    def mouse_move(self, event, image_pos):
        """鼠标移动事件"""
        super().mouse_move(event, image_pos)
        
        if self.drawing and self.last_point:
            self._draw_line(self.last_point, image_pos)
            self.last_point = image_pos
    
    def mouse_release(self, event, image_pos):
        """鼠标释放事件"""
        super().mouse_release(event, image_pos)
        
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.drawing = False
            self.draw_batch_started = False
            self.last_point = None
    
    def _update_brush_properties(self):
        """更新画笔属性"""
        if self.controller:
            self.brush_size = self.controller.get_current_size()
            self.brush_opacity = self.controller.get_current_opacity()
            
            # 获取绘制颜色
            color = self._get_drawing_color()
            if color:
                self.brush_color = color
    
    def _draw_point(self, point):
        """绘制单个点"""
        if not self.controller:
            return

        def draw_func(painter):
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 检查是否透明色
            if self.brush_color.alpha() == 0:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                pen = QPen(QColor(0, 0, 0, 0), self.brush_size)
                painter.setOpacity(1.0)
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                pen = QPen(self.brush_color, self.brush_size)
                painter.setOpacity(self.brush_opacity / 100.0)

            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            # 绘制点
            painter.drawPoint(int(point.x()), int(point.y()))

        # 在活动图层绘制
        self.controller.draw_on_active_layer(
            draw_func,
            save_history=self.draw_batch_started,
            is_batch_start=self.draw_batch_started,
            is_batch_end=not self.drawing
        )
        self.draw_batch_started = False
    
    def _draw_line(self, start_point, end_point):
        """绘制线条"""
        if not self.controller:
            return

        def draw_func(painter):
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 检查是否透明色
            if self.brush_color.alpha() == 0:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                pen = QPen(QColor(0, 0, 0, 0), self.brush_size)
                painter.setOpacity(1.0)
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                pen = QPen(self.brush_color, self.brush_size)
                painter.setOpacity(self.brush_opacity / 100.0)

            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            # 绘制线条
            painter.drawLine(
                int(start_point.x()), int(start_point.y()),
                int(end_point.x()), int(end_point.y())
            )

        # 在活动图层绘制
        self.controller.draw_on_active_layer(
            draw_func,
            save_history=False,
            is_batch_start=False,
            is_batch_end=not self.drawing
        )


class EraserTool(BaseTool):
    """橡皮擦工具"""
    def __init__(self, controller):
        super().__init__(controller)
        self.last_point = None
        self.eraser_size = 20
        self.eraser_opacity = 100
    
    def mouse_press(self, event, image_pos):
        """鼠标按下事件"""
        super().mouse_press(event, image_pos)
        
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.drawing = True
            self.start_pos = image_pos
            self.last_point = image_pos
            self.draw_batch_started = True
            
            # 获取当前橡皮擦属性
            self._update_eraser_properties()
            
            # 开始擦除
            self._erase_point(image_pos)
    
    def mouse_move(self, event, image_pos):
        """鼠标移动事件"""
        super().mouse_move(event, image_pos)
        
        if self.drawing and self.last_point:
            self._erase_line(self.last_point, image_pos)
            self.last_point = image_pos
    
    def mouse_release(self, event, image_pos):
        """鼠标释放事件"""
        super().mouse_release(event, image_pos)
        
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.drawing = False
            self.draw_batch_started = False
            self.last_point = None
    
    def _update_eraser_properties(self):
        """更新橡皮擦属性"""
        if self.controller:
            self.eraser_size = self.controller.get_current_size()
            self.eraser_opacity = self.controller.get_current_opacity()
    
    def _erase_point(self, point):
        """擦除单个点"""
        if not self.controller:
            return
        
        def erase_func(painter):
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 如果是右键，执行颜色替换擦除
            if self.tool_state['mouse_button'] == 'right' or self.tool_state['is_right_button_during_drag']:
                target_color = self.controller.get_current_fg_color()
                replace_color = self.controller.get_current_bg_color()
                self._replace_color_at_point(painter, point.x(), point.y(), self.eraser_size, target_color, replace_color)
            else:
                # 左键：透明擦除
                # 使用清除模式
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                
                # 设置橡皮擦画笔
                pen = QPen(QColor(0, 0, 0, 0), self.eraser_size)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                
                # 擦除点
                painter.setOpacity(self.eraser_opacity / 100.0)
                painter.drawPoint(int(point.x()), int(point.y()))
        
        # 在活动图层擦除
        self.controller.draw_on_active_layer(
            erase_func,
            save_history=self.draw_batch_started,
            is_batch_start=self.draw_batch_started,
            is_batch_end=not self.drawing
        )
        self.draw_batch_started = False
    
    def _erase_line(self, start_point, end_point):
        """擦除线条"""
        if not self.controller:
            return
        
        def erase_func(painter):
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # 如果是右键，执行颜色替换擦除
            if self.tool_state['mouse_button'] == 'right' or self.tool_state['is_right_button_during_drag']:
                target_color = self.controller.get_current_fg_color()
                replace_color = self.controller.get_current_bg_color()
                self._replace_color_along_line(painter, start_point, end_point, self.eraser_size, target_color, replace_color)
            else:
                # 左键：透明擦除
                # 使用清除模式
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                
                # 设置橡皮擦画笔
                pen = QPen(QColor(0, 0, 0, 0), self.eraser_size)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                
                # 擦除线条
                painter.setOpacity(self.eraser_opacity / 100.0)
                painter.drawLine(
                    int(start_point.x()), int(start_point.y()),
                    int(end_point.x()), int(end_point.y())
                )
        
        # 在活动图层擦除
        self.controller.draw_on_active_layer(
            erase_func,
            save_history=False,
            is_batch_start=False,
            is_batch_end=not self.drawing
        )

    def _replace_color_at_point(self, painter, x, y, size, target_color, replace_color):
        """在单点替换颜色"""
        radius = size // 2
        draw_device = painter.device()
        if not isinstance(draw_device, QImage):
            return
        
        image = draw_device
        for px in range(max(0, int(x - radius)), min(image.width(), int(x + radius) + 1)):
            for py in range(max(0, int(y - radius)), min(image.height(), int(y + radius) + 1)):
                distance = math.sqrt((px - x)**2 + (py - y)**2)
                if distance <= radius:
                    color = QColor(image.pixel(px, py))
                    if self._is_color_close(color, target_color):
                        painter.setPen(QPen(replace_color, 1))
                        painter.drawPoint(px, py)

    def _replace_color_along_line(self, painter, start_point, end_point, size, target_color, replace_color):
        """沿直线替换颜色"""
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0:
            return
        
        steps = max(2, int(length))
        radius = size // 2
        draw_device = painter.device()
        
        if not isinstance(draw_device, QImage):
            return
        
        image = draw_device
        for i in range(steps + 1):
            t = i / steps
            x = start_point.x() + dx * t
            y = start_point.y() + dy * t
            
            for px in range(max(0, int(x - radius)), min(image.width(), int(x + radius) + 1)):
                for py in range(max(0, int(y - radius)), min(image.height(), int(y + radius) + 1)):
                    distance = math.sqrt((px - x)**2 + (py - y)**2)
                    if distance <= radius:
                        color = QColor(image.pixel(px, py))
                        if self._is_color_close(color, target_color):
                            painter.setPen(QPen(replace_color, 1))
                            painter.drawPoint(px, py)

    def _is_color_close(self, color1, color2, tolerance=50):
        """判断颜色是否相近"""
        r_diff = abs(color1.red() - color2.red())
        g_diff = abs(color1.green() - color2.green())
        b_diff = abs(color1.blue() - color2.blue())
        a_diff = abs(color1.alpha() - color2.alpha())
        total_diff = r_diff + g_diff + b_diff + a_diff
        return total_diff <= tolerance


class AirbrushTool(BaseTool):
    """喷枪工具"""
    def __init__(self, controller):
        super().__init__(controller)
        self.last_point = None
        self.spray_size = 20
        self.spray_opacity = 50
        self.spray_density = 50
        self.spray_timer = QTimer()
        self.spray_timer.timeout.connect(self._spray_paint)
        self.spray_positions = []
    
    def mouse_press(self, event, image_pos):
        """鼠标按下事件"""
        super().mouse_press(event, image_pos)
        
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.drawing = True
            self.start_pos = image_pos
            self.last_point = image_pos
            self.draw_batch_started = True
            
            # 获取当前喷枪属性
            self._update_spray_properties()
            
            # 开始喷涂
            self.spray_positions = [image_pos]
            self.spray_timer.start(50)  # 每50ms喷涂一次
    
    def mouse_move(self, event, image_pos):
        """鼠标移动事件"""
        super().mouse_move(event, image_pos)
        
        if self.drawing:
            self.last_point = image_pos
            self.spray_positions.append(image_pos)
    
    def mouse_release(self, event, image_pos):
        """鼠标释放事件"""
        super().mouse_release(event, image_pos)
        
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.drawing = False
            self.draw_batch_started = False
            self.last_point = None
            self.spray_timer.stop()
            self.spray_positions.clear()
    
    def _update_spray_properties(self):
        """更新喷枪属性"""
        if self.controller:
            self.spray_size = self.controller.get_current_size()
            self.spray_opacity = self.controller.get_current_opacity()
            
            # 获取绘制颜色
            color = self._get_drawing_color()
            if color:
                self.spray_color = color
            else:
                self.spray_color = QColor("black")
    
    def _spray_paint(self):
        """喷涂效果"""
        if not self.drawing or not self.spray_positions or not self.controller:
            return

        def spray_func(painter):
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 检查是否透明色
            if self.spray_color.alpha() == 0:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.setPen(QPen(QColor(0, 0, 0, 0), 1))
                painter.setOpacity(1.0)
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.setPen(QPen(self.spray_color, 1))
                painter.setOpacity(self.spray_opacity / 100.0)

            # 在多个位置喷涂
            for pos in self.spray_positions:
                x = int(pos.x())
                y = int(pos.y())
                radius = self.spray_size // 2

                # 生成随机点进行喷涂
                import random
                density = max(1, self.spray_density // 10)

                for _ in range(density):
                    angle = random.uniform(0, 2 * math.pi)
                    distance = random.uniform(0, radius)
                    spray_x = x + distance * math.cos(angle)
                    spray_y = y + distance * math.sin(angle)

                    # 绘制小点
                    painter.drawPoint(int(spray_x), int(spray_y))

        # 在活动图层喷涂
        self.controller.draw_on_active_layer(
            spray_func,
            save_history=self.draw_batch_started,
            is_batch_start=self.draw_batch_started,
            is_batch_end=False
        )
        self.draw_batch_started = False

        # 清空位置队列
        self.spray_positions.clear()


class FillTool(BaseTool):
    """填充工具"""
    def __init__(self, controller):
        super().__init__(controller)
        self.fill_color = QColor("black")
        self.fill_opacity = 100
        self.tolerance = 10
    
    def mouse_press(self, event, image_pos):
        """鼠标按下事件"""
        super().mouse_press(event, image_pos)
        
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            # 获取填充颜色
            self._update_fill_properties()
            
            # 执行填充
            self._perform_fill(int(image_pos.x()), int(image_pos.y()))
    
    def _update_fill_properties(self):
        """更新填充属性"""
        if self.controller:
            self.fill_opacity = self.controller.get_current_opacity()
            
            # 获取绘制颜色
            color = self._get_drawing_color()
            if color:
                self.fill_color = color
    
    def _perform_fill(self, x, y):
        """执行填充操作"""
        if not self.controller:
            return
        
        # 获取活动图层
        if self.controller.active_layer_index < 0:
            return
        
        active_layer = self.controller.layers[self.controller.active_layer_index]
        layer_image = active_layer['image']
        
        # 获取点击位置的颜色
        target_color = layer_image.pixelColor(x, y)
        if not target_color.isValid():
            return
        
        # 保存历史
        self.controller.save_to_history()
        
        def fill_func(painter):
            # 实现洪水填充算法
            self._flood_fill(painter, x, y, target_color, layer_image)
        
        # 在活动图层填充
        self.controller.draw_on_active_layer(fill_func)
        
        if self.controller and hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit(f"区域填充完成")
    
    def _flood_fill(self, painter, start_x, start_y, target_color, image):
        """洪水填充算法（简化版）"""
        # 获取图像尺寸
        width = image.width()
        height = image.height()

        # 创建访问标记
        visited = [[False] * height for _ in range(width)]

        # 队列用于BFS
        queue = [(start_x, start_y)]
        visited[start_x][start_y] = True

        # 检查是否透明色
        if self.fill_color.alpha() == 0:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setOpacity(1.0)
        else:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setBrush(QBrush(self.fill_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setOpacity(self.fill_opacity / 100.0)

        # BFS遍历相邻像素
        while queue:
            x, y = queue.pop(0)

            # 检查当前像素是否匹配目标颜色（考虑容差）
            pixel_color = image.pixelColor(x, y)
            if self._colors_similar(pixel_color, target_color, self.tolerance):
                # 填充当前像素
                painter.drawRect(x, y, 1, 1)

                # 添加相邻像素到队列
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = x + dx, y + dy

                    if (0 <= nx < width and 0 <= ny < height and
                        not visited[nx][ny]):
                        visited[nx][ny] = True
                        queue.append((nx, ny))
    
    def _colors_similar(self, color1, color2, tolerance):
        """判断两个颜色是否相似"""
        r_diff = abs(color1.red() - color2.red())
        g_diff = abs(color1.green() - color2.green())
        b_diff = abs(color1.blue() - color2.blue())
        a_diff = abs(color1.alpha() - color2.alpha())
        
        return (r_diff <= tolerance and g_diff <= tolerance and 
                b_diff <= tolerance and a_diff <= tolerance)