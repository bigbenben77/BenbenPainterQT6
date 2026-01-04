# base_tool.py - 基础工具类
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPen, QPainter, QImage
import math

class BaseTool:
    """基础工具类"""
    def __init__(self, controller):
        self.controller = controller
        self.start_pos = None
        self.end_pos = None
        self.drawing = False
        self.last_point = None
        self.draw_batch_started = False
        
        # 工具状态
        self.tool_state = {
            'mouse_button': None,
            'is_ctrl_pressed': False,
            'is_shift_pressed': False,
            'is_right_button_during_drag': False,
        }
    
    def mouse_press(self, event, image_pos):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.tool_state['mouse_button'] = 'left'
            self.tool_state['is_right_button_during_drag'] = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.tool_state['mouse_button'] = 'right'
            self.tool_state['is_right_button_during_drag'] = True
        
        self.tool_state['is_ctrl_pressed'] = (event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self.tool_state['is_shift_pressed'] = (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.draw_batch_started = False
    
    def mouse_move(self, event, image_pos):
        """鼠标移动事件"""
        if event.buttons() & Qt.MouseButton.RightButton:
            self.tool_state['is_right_button_during_drag'] = True
            self.tool_state['mouse_button'] = 'right'
        elif event.buttons() & Qt.MouseButton.LeftButton:
            self.tool_state['is_right_button_during_drag'] = False
            self.tool_state['mouse_button'] = 'left'
        
        self.tool_state['is_ctrl_pressed'] = (event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self.tool_state['is_shift_pressed'] = (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
    
    def mouse_release(self, event, image_pos):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.tool_state['mouse_button'] = 'left'
        elif event.button() == Qt.MouseButton.RightButton:
            self.tool_state['mouse_button'] = 'right'
        self.tool_state['is_right_button_during_drag'] = False
    
    def key_press(self, event):
        """键盘按下事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True
        return False
    
    def cancel(self):
        """取消当前操作"""
        self.drawing = False
        self.reset_states()
        
        if hasattr(self.controller, 'temp_pixmap'):
            self.controller.temp_pixmap = None
            if self.controller.canvas:
                self.controller.canvas.update()
        
        if self.controller and hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit("操作已取消")
    
    def reset_states(self):
        """重置工具状态"""
        self.tool_state = {
            'mouse_button': None,
            'is_ctrl_pressed': False,
            'is_shift_pressed': False,
            'is_right_button_during_drag': False,
        }
        self.draw_batch_started = False
    
    def _get_drawing_color(self):
        """获取绘制颜色"""
        if self.tool_state['is_right_button_during_drag']:
            return self.controller.get_current_bg_color()
        else:
            button = self.tool_state['mouse_button']
            if button == 'right':
                return self.controller.get_current_bg_color()
            return self.controller.get_current_fg_color()
    
    def _apply_constraint(self, start_x, start_y, end_x, end_y, constraint_type='square'):
        """应用约束(正方形、圆形等)"""
        if not self.tool_state['is_shift_pressed']:
            return end_x, end_y
        
        dx = end_x - start_x
        dy = end_y - start_y
        
        if constraint_type in ['square', 'circle']:
            max_dist = max(abs(dx), abs(dy))
            new_end_x = start_x + (max_dist if dx >= 0 else -max_dist)
            new_end_y = start_y + (max_dist if dy >= 0 else -max_dist)
            return new_end_x, new_end_y
        elif constraint_type == 'line':
            angle_rad = math.atan2(dy, dx)
            angle_deg = math.degrees(angle_rad)
            constrained_angle_deg = round(angle_deg / 45.0) * 45.0
            constrained_angle_rad = math.radians(constrained_angle_deg)
            dist = math.sqrt(dx**2 + dy**2)
            new_end_x = start_x + dist * math.cos(constrained_angle_rad)
            new_end_y = start_y + dist * math.sin(constrained_angle_rad)
            return new_end_x, new_end_y
        
        return end_x, end_y