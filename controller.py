# controller.py - 完整修复版（含透明色支持和选区工具功能）
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QPointF, QTimer, QRect
from PyQt6.QtGui import QColor, QPixmap, QPainter, QImage, QTransform, QPen
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QListWidgetItem, QApplication, QInputDialog
from image_processor import ImageProcessor
from tool_system import ToolManager
from PIL import Image, ImageOps, ImageEnhance
import os
from collections import deque


class Controller(QObject):
    """控制器 - 修复图像调整问题，支持透明色和选区工具"""
    
    status_updated = pyqtSignal(str)
    
    # 常量
    DEFAULT_WIDTH = 800
    DEFAULT_HEIGHT = 600
    DEFAULT_BG_COLOR = QColor(0, 0, 0, 0)
    MAX_HISTORY = 20
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.image_processor = ImageProcessor()
        self.tool_manager = ToolManager(self)
        
        # 图像状态
        self.current_image = None
        self.image_path = None
        self.is_modified = False
        
        # 图层管理
        self.layers = []
        self.active_layer_index = -1
        
        # 工具状态
        self.current_tool = 'brush'
        self.temp_pixmap = None
        self.canvas = None
        
        # 选区状态
        self.selection_rect = None
        self.selection_content = None
        self.is_selection_active = False
        self.selection_transform = None  # 保存选区变换状态
        
        # 历史记录
        self.undo_stack = deque(maxlen=self.MAX_HISTORY)
        self.redo_stack = deque(maxlen=self.MAX_HISTORY)
        self.is_recording = True
        
        # 性能优化
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._delayed_update)
        self._update_timer.setSingleShot(True)
        self._pending_update = False
        
        # 调整状态
        self._original_images = {}  # 保存各图层的原始图像
        self._adjustment_values = {}  # 保存调整值
        self._current_adjustment_type = None  # 当前正在进行的调整类型
        
        # 操作状态
        self._current_operation_saved = False
        
        # 文字工具状态
        self.text_editing = False
        self.current_text_data = None
        
        # 透明色支持
        self.transparent_color = QColor(0, 0, 0, 0)
        
        # 临时预览位置
        self.temp_preview_position = None
    
    def connect_signals(self):
        """连接信号"""
        if not hasattr(self.main_window, 'tool_panel'):
            return
        
        self.main_window.tool_panel.tool_selected.connect(self.on_tool_selected)
        
        if hasattr(self.main_window, 'property_panel'):
            panel = self.main_window.property_panel
            
            # 连接属性面板信号
            panel.size_changed.connect(self.on_size_changed)
            panel.opacity_changed.connect(self.on_opacity_changed)
            panel.foreground_color_changed.connect(self.on_fg_color_changed)
            panel.background_color_changed.connect(self.on_bg_color_changed)
            panel.brightness_changed.connect(self.on_brightness_changed)
            panel.contrast_changed.connect(self.on_contrast_changed)
            panel.saturation_changed.connect(self.on_saturation_changed)
        
        if hasattr(self.main_window, 'layer_panel'):
            panel = self.main_window.layer_panel
            
            # 连接图层面板信号
            panel.layer_added.connect(self.on_layer_added)
            panel.layer_removed.connect(self.on_layer_removed)
            panel.layer_toggled.connect(self.on_layer_toggled)
            panel.layer_selected.connect(self.on_layer_selected)
    
    # ===================== 图层管理 =====================
    
    def create_layer(self, name="图层", fill_color=None, image=None):
        """创建图层"""
        if not self.current_image:
            # 如果没有当前图像，创建默认大小的图像
            width = self.DEFAULT_WIDTH
            height = self.DEFAULT_HEIGHT
        else:
            width = self.current_image.width()
            height = self.current_image.height()
        
        if image:
            layer_image = image.copy()
        else:
            layer_image = QImage(width, height, QImage.Format.Format_ARGB32)
            color = fill_color or self.get_current_bg_color()
            layer_image.fill(color)
        
        return {
            'name': name,
            'image': layer_image,
            'visible': True,
            'opacity': 100,
            'locked': False
        }
    
    def add_layer(self, name="图层", fill_color=None, image=None):
        """添加图层"""
        self.save_to_history()
        
        layer = self.create_layer(name, fill_color, image)
        if not layer:
            return None
        
        self.layers.append(layer)
        self.active_layer_index = len(self.layers) - 1
        
        self.schedule_update()
        self._update_layer_panel_ui()
        
        return layer
    
    def remove_layer(self, index):
        """删除图层"""
        if not (0 <= index < len(self.layers)):
            return False
        
        if len(self.layers) <= 1:
            self.status_updated.emit("无法删除最后一个图层")
            return False
        
        if index == 0:
            self.status_updated.emit("无法删除背景图层")
            return False
        
        self.save_to_history()
        self.layers.pop(index)
        
        # 更新活动图层索引
        if self.active_layer_index >= len(self.layers):
            self.active_layer_index = len(self.layers) - 1
        elif index < self.active_layer_index:
            self.active_layer_index -= 1
        
        self.schedule_update()
        self._update_layer_panel_ui()
        
        return True
    
    def toggle_layer_visibility(self, index, visible):
        """切换图层可见性"""
        if 0 <= index < len(self.layers):
            if self.layers[index]['visible'] != visible:
                self.save_to_history()
                self.layers[index]['visible'] = visible
                self.schedule_update()
    
    def select_layer(self, index):
        """选择图层"""
        if 0 <= index < len(self.layers):
            self.active_layer_index = index
            self.status_updated.emit(f"选中图层: {self.layers[index]['name']}")
    
    def move_layer(self, from_idx, to_idx):
        """移动图层"""
        if not (0 <= from_idx < len(self.layers) and 0 <= to_idx < len(self.layers)):
            return False
        
        if from_idx == to_idx or from_idx == 0 or to_idx == 0:
            return False
        
        self.save_to_history()
        
        layer = self.layers.pop(from_idx)
        self.layers.insert(to_idx, layer)
        
        # 更新活动图层索引
        if self.active_layer_index == from_idx:
            self.active_layer_index = to_idx
        elif from_idx < self.active_layer_index <= to_idx:
            self.active_layer_index -= 1
        elif to_idx <= self.active_layer_index < from_idx:
            self.active_layer_index += 1
        
        self.schedule_update()
        self._update_layer_panel_ui()
        
        return True
    
    def move_layer_up(self, index):
        """上移图层"""
        if index > 1:
            return self.move_layer(index, index - 1)
        return False
    
    def move_layer_down(self, index):
        """下移图层"""
        if index < len(self.layers) - 1:
            return self.move_layer(index, index + 1)
        return False
    
    def update_composite_image(self):
        """更新合成图像"""
        if not self.layers:
            return
        
        first = self.layers[0]
        width = first['image'].width()
        height = first['image'].height()
        
        composite = QImage(width, height, QImage.Format.Format_ARGB32)
        composite.fill(QColor(0, 0, 0, 0))
        
        painter = QPainter(composite)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        for layer in self.layers:
            if layer['visible']:
                opacity = layer.get('opacity', 100) / 100.0
                painter.setOpacity(opacity)
                painter.drawImage(0, 0, layer['image'])
        
        painter.end()
        self.current_image = composite
        
        self._force_canvas_update()
    
    def _force_canvas_update(self):
        """强制画布更新"""
        if not self.canvas:
            return
        
        if hasattr(self.canvas, 'pixmap'):
            self.canvas.pixmap = None
        
        try:
            self.canvas.update()
        except RuntimeError:
            self.canvas = None
    
    def schedule_update(self):
        """调度延迟更新"""
        self._pending_update = True
        if not self._update_timer.isActive():
            self._update_timer.start(16)  # 约60fps
    
    def _delayed_update(self):
        """延迟更新执行"""
        if self._pending_update:
            self._pending_update = False
            self.update_composite_image()
    
    def draw_on_active_layer(self, painter_func, save_history=True, is_batch_start=False, is_batch_end=False):
        """在活动图层绘制 - 修复:支持批处理参数"""
        if self.active_layer_index < 0 or self.active_layer_index >= len(self.layers):
            return
        
        # 检查图层是否锁定
        if self.layers[self.active_layer_index].get('locked', False):
            self.status_updated.emit("图层已锁定，无法绘制")
            return
        
        # 只有在批处理开始时或非批处理模式下才保存历史
        if save_history and (is_batch_start or (not is_batch_start and not is_batch_end)):
            # 检查是否已经为当前操作保存过历史
            if not hasattr(self, '_current_operation_saved') or not self._current_operation_saved:
                self.save_to_history()
                self._current_operation_saved = True
        
        active_layer = self.layers[self.active_layer_index]
        temp_image = active_layer['image'].copy()
        
        painter = QPainter(temp_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter_func(painter)
        painter.end()
        
        active_layer['image'] = temp_image
        self.schedule_update()
        self.is_modified = True
        
        # 如果是批处理结束,重置操作保存标志
        if is_batch_end:
            self._current_operation_saved = False
    
    # ===================== 工具相关 =====================
    
    def on_tool_selected(self, tool_id: str):
        """工具选择"""
        self.current_tool = tool_id
        
        if self.tool_manager:
            self.tool_manager.set_active_tool(tool_id)
        
        # 取消任何正在进行的操作
        if hasattr(self, 'temp_pixmap'):
            self.temp_pixmap = None
            if self.canvas:
                self.canvas.update()
        
        # 取消选区
        if tool_id not in ['rect_select', 'ellipse_select', 'polygon_select']:
            self.clear_selection()
        
        # 工具提示信息
        hints = {
            'brush': "画笔工具 (B键)",
            'eraser': "橡皮擦工具 (E键)",
            'airbrush': "喷枪工具 (A键)",
            'fill': "填充工具 (F键)",
            'line': "直线工具 (L键)",
            'rectangle': "矩形工具 (R键, Shift: 正方形, Ctrl: 填充)",
            'ellipse': "椭圆工具 (O键, Shift: 圆形, Ctrl: 填充)",
            'star': "多角星工具 (S键)",
            'polygon': "多边形工具 (P键)",
            'rounded_rect': "圆角矩形工具 (U键)",
            'text': "文字工具 (T键, 左键创建, 双击编辑, 右键提交)",
            'picker': "取色工具 (I键, 左键前景色, 右键背景色)",
            'rect_select': "矩形选区工具 (M键, Enter提交, Esc取消)",
            'ellipse_select': "椭圆选区工具",
            'polygon_select': "多边形选区工具",
            'curve': "曲线工具 (V键, C键切换封闭/开放, 右键结束)",
        }
        
        hint = hints.get(tool_id, f"已切换到: {tool_id}")
        self.status_updated.emit(hint)
    
    def on_canvas_mouse_press(self, event, image_pos):
        """鼠标按下"""
        # 检查是否是文字工具且在编辑状态
        if self.current_tool == 'text':
            tool = self.tool_manager.get_tool('text')
            if tool and hasattr(tool, 'is_editing') and tool.is_editing:
                # 检查是否点击在文字框外 - 使用TextTool自己的方法
                if hasattr(tool, '_is_click_outside_preview') and tool._is_click_outside_preview(image_pos):
                    # 提交文字
                    tool._commit_text()
                    return
        
        # 检查是否是选区工具且在选区外点击
        if self.current_tool in ['rect_select', 'ellipse_select', 'polygon_select']:
            tool = self.tool_manager.get_tool(self.current_tool)
            if tool and hasattr(tool, 'is_active') and tool.is_active:
                # 检查是否点击在选区外
                if tool.selection_rect and not tool.selection_rect.contains(int(image_pos.x()), int(image_pos.y())):
                    # 提交选区
                    tool._commit_selection()
                    return
        
        # 原有逻辑
        if self.current_tool and self.tool_manager:
            tool = self.tool_manager.get_tool(self.current_tool)
            if tool:
                tool.mouse_press(event, image_pos)
    
    def on_canvas_mouse_move(self, event, image_pos):
        """鼠标移动"""
        if self.current_tool and self.tool_manager:
            tool = self.tool_manager.get_tool(self.current_tool)
            if tool:
                tool.mouse_move(event, image_pos)
    
    def on_canvas_mouse_release(self, event, image_pos):
        """鼠标释放 - 重置操作保存标志"""
        if self.current_tool and self.tool_manager:
            tool = self.tool_manager.get_tool(self.current_tool)
            if tool:
                tool.mouse_release(event, image_pos)
        
        # 鼠标释放时重置操作保存标志
        if hasattr(self, '_current_operation_saved'):
            self._current_operation_saved = False
    
    def on_key_press(self, event):
        """处理按键事件"""
        if self.current_tool and self.tool_manager:
            tool = self.tool_manager.get_tool(self.current_tool)
            if tool and hasattr(tool, 'key_press'):
                return tool.key_press(event)
        return False
    
    # ===================== 图像处理 =====================
    
    def apply_filter(self, filter_name: str):
        """应用滤镜"""
        if not self.layers or self.active_layer_index < 0:
            self.status_updated.emit("没有可应用的图层")
            return
        
        self.save_to_history()
        
        try:
            active_layer = self.layers[self.active_layer_index]
            
            # 保存原始图像
            if self.active_layer_index not in self._original_images:
                self._original_images[self.active_layer_index] = active_layer['image'].copy()
            
            pil_image = self._qimage_to_pil(active_layer['image'])
            
            # 滤镜映射表
            filters = {
                "高斯模糊": self.image_processor.apply_gaussian_blur,
                "运动模糊": self.image_processor.apply_motion_blur,
                "锐化": self.image_processor.apply_sharpen,
                "浮雕": self.image_processor.apply_emboss,
                "马赛克": self.image_processor.apply_mosaic,
            }
            
            method = filters.get(filter_name)
            if not method:
                self.status_updated.emit(f"未知滤镜: {filter_name}")
                return
            
            pil_image = method(pil_image)
            active_layer['image'] = self._pil_to_qimage(pil_image)
            
            self.schedule_update()
            self.is_modified = True
            self.status_updated.emit(f"已应用滤镜: {filter_name}")
            
        except Exception as e:
            self.status_updated.emit(f"应用滤镜失败: {str(e)}")
    
    def _apply_adjustment(self, adj_type, value):
        """应用调整 - 完全修复"""
        if not self.layers or self.active_layer_index < 0:
            return
        
        # 如果是新的调整类型,保存历史
        if adj_type != self._current_adjustment_type:
            self.save_to_history()
            self._current_adjustment_type = adj_type
            
            # 保存原始图像(如果还没有保存)
            if self.active_layer_index not in self._original_images:
                active_layer = self.layers[self.active_layer_index]
                self._original_images[self.active_layer_index] = active_layer['image'].copy()
        
        # 保存调整值
        self._adjustment_values[adj_type] = value
        
        # 从原始图像开始应用所有调整
        active_layer = self.layers[self.active_layer_index]
        
        # 如果有保存的原始图像,从它开始
        if self.active_layer_index in self._original_images:
            pil_image = self._qimage_to_pil(self._original_images[self.active_layer_index])
        else:
            pil_image = self._qimage_to_pil(active_layer['image'])
        
        # 按顺序应用所有调整
        if 'brightness' in self._adjustment_values:
            brightness_value = self._adjustment_values['brightness']
            if brightness_value != 0:
                enhancer = ImageEnhance.Brightness(pil_image)
                factor = 1.0 + brightness_value / 100.0
                pil_image = enhancer.enhance(factor)
        
        if 'contrast' in self._adjustment_values:
            contrast_value = self._adjustment_values['contrast']
            if contrast_value != 0:
                enhancer = ImageEnhance.Contrast(pil_image)
                factor = 1.0 + contrast_value / 100.0
                pil_image = enhancer.enhance(factor)
        
        if 'saturation' in self._adjustment_values:
            saturation_value = self._adjustment_values['saturation']
            if saturation_value != 0:
                enhancer = ImageEnhance.Color(pil_image)
                factor = 1.0 + saturation_value / 100.0
                pil_image = enhancer.enhance(factor)
        
        # 更新图层图像
        active_layer['image'] = self._pil_to_qimage(pil_image)
        self.schedule_update()
        self.is_modified = True
    
    def on_brightness_changed(self, value: int):
        self._apply_adjustment('brightness', value)
    
    def on_contrast_changed(self, value: int):
        self._apply_adjustment('contrast', value)
    
    def on_saturation_changed(self, value: int):
        self._apply_adjustment('saturation', value)
    
    def reset_adjustments(self):
        """重置所有调整"""
        if not self.layers or self.active_layer_index < 0:
            return
        
        # 如果没有保存原始图像,直接返回
        if self.active_layer_index not in self._original_images:
            self.status_updated.emit("没有可重置的调整")
            return
        
        self.save_to_history()
        
        active_layer = self.layers[self.active_layer_index]
        
        # 恢复原始图像 - 创建新的QImage实例
        active_layer['image'] = QImage(self._original_images[self.active_layer_index])
        
        # 清除调整状态
        self._adjustment_values.clear()
        self._current_adjustment_type = None
        del self._original_images[self.active_layer_index]
        
        self.schedule_update()
        self.is_modified = True
        self.status_updated.emit("已重置所有调整")
    
    # ===================== 图像转换 =====================
    
    def _qimage_to_pil(self, qimage: QImage):
        """QImage转PIL"""
        if qimage.isNull():
            return Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        
        if qimage.format() != QImage.Format.Format_ARGB32:
            qimage = qimage.convertToFormat(QImage.Format.Format_ARGB32)
        
        width = qimage.width()
        height = qimage.height()
        bytes_per_line = qimage.bytesPerLine()
        
        ptr = qimage.bits()
        if ptr is None:
            return Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        ptr.setsize(bytes_per_line * height)
        buffer = bytes(ptr.asarray())
        return Image.frombytes('RGBA', (width, height), buffer, 'raw', 'BGRA', bytes_per_line, 1)
    
    def _pil_to_qimage(self, pil_image):
        """PIL转QImage"""
        if pil_image is None:
            return QImage(1, 1, QImage.Format.Format_ARGB32)
        
        if pil_image.mode != 'RGBA':
            pil_image = pil_image.convert('RGBA')
        
        width, height = pil_image.size
        data = pil_image.tobytes('raw', 'BGRA')
        qimage = QImage(data, width, height, QImage.Format.Format_ARGB32)
        return qimage.copy()
    
    def _ensure_rgba(self, pil_image):
        """确保RGBA模式"""
        if pil_image is None:
            return Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        
        if pil_image.mode in ['P', 'L', 'RGB']:
            return pil_image.convert('RGBA')
        return pil_image
    
    # ===================== 文件操作 =====================
    
    def new_file(self):
        """新建文件"""
        # 检查当前文档是否需要保存
        if self.is_modified:
            reply = QMessageBox.question(
                self.main_window, '保存更改',
                "当前图像已修改,是否保存?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_file()
                if self.is_modified:  # 保存失败
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        self.clear_history()
        
        width, height = self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT
        pil_image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        self.current_image = self._pil_to_qimage(pil_image)
        self.image_path = None
        self.is_modified = False
        
        # 清除选区
        self.clear_selection()
        
        self.initialize_layers()
        
        if self.canvas and hasattr(self.canvas, 'fit_to_window'):
            self.canvas.fit_to_window()
        
        self.status_updated.emit(f"新建 {width}x{height} 画布")
    
    def initialize_layers(self):
        """初始化图层"""
        self.layers.clear()
        self.active_layer_index = -1
        
        if not self.current_image:
            return
        
        # 创建背景图层
        bg = self.create_layer("背景", self.DEFAULT_BG_COLOR)
        if bg:
            self.layers.append(bg)
        
        # 创建默认图层
        layer1 = self.create_layer("图层 1", self.get_current_bg_color())
        if layer1:
            self.layers.append(layer1)
            self.active_layer_index = len(self.layers) - 1
        
        self.schedule_update()
        self._update_layer_panel_ui()
        self.status_updated.emit("图层初始化完成")
    
    def open_file(self):
        """打开文件"""
        # 检查当前文档是否需要保存
        if self.is_modified:
            reply = QMessageBox.question(
                self.main_window, '保存更改',
                "当前图像已修改,是否保存?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_file()
                if self.is_modified:  # 保存失败
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        self.clear_history()
        
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window, "打开图像", "", 
            "图像文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            pil_image = Image.open(file_path)
            
            # 处理EXIF方向
            try:
                pil_image = ImageOps.exif_transpose(pil_image)
            except:
                pass
            
            pil_image = self._ensure_rgba(pil_image)
            self.current_image = self._pil_to_qimage(pil_image)
            self.image_path = file_path
            self.is_modified = False
            
            # 清除选区
            self.clear_selection()
            
            # 初始化图层
            self.layers.clear()
            self.active_layer_index = -1
            
            # 背景图层
            bg = self.create_layer("背景", self.DEFAULT_BG_COLOR)
            if bg:
                self.layers.append(bg)
            
            # 图像图层
            name = os.path.basename(file_path)[:20]
            img_layer = self.create_layer(f"图像: {name}", image=self.current_image)
            if img_layer:
                self.layers.append(img_layer)
                self.active_layer_index = len(self.layers) - 1
            
            self.schedule_update()
            self._update_layer_panel_ui()
            
            # 更新画布
            if self.canvas:
                if hasattr(self.canvas, 'fit_to_window'):
                    self.canvas.fit_to_window()
                self.canvas.update()
            
            self.status_updated.emit(f"已打开: {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self.main_window, "错误", f"打开失败: {str(e)}")
    
    def save_file(self):
        """保存文件"""
        if not self.current_image:
            return
        
        if not self.image_path:
            self.save_file_as()
            return
        
        try:
            # 保存当前视图（包括所有图层）
            composite = self._qimage_to_pil(self.current_image)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(self.image_path)), exist_ok=True)
            
            composite.save(self.image_path)
            self.is_modified = False
            self.status_updated.emit(f"已保存: {self.image_path}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "错误", f"保存失败: {str(e)}")
    
    def save_file_as(self):
        """另存为"""
        if not self.current_image:
            return
        
        # 获取默认文件名
        default_name = "未命名.png"
        if self.image_path:
            default_name = os.path.basename(self.image_path)
        
        path, selected_filter = QFileDialog.getSaveFileName(
            self.main_window, "另存为", default_name,
            "PNG 文件 (*.png);;JPG 文件 (*.jpg);;BMP 文件 (*.bmp);;所有文件 (*.*)"
        )
        
        if not path:
            return
        
        # 确保文件扩展名
        if not path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            if 'JPG' in selected_filter:
                path += '.jpg'
            elif 'BMP' in selected_filter:
                path += '.bmp'
            else:
                path += '.png'
        
        try:
            composite = self._qimage_to_pil(self.current_image)
            
            # 格式转换
            if path.lower().endswith(('.jpg', '.jpeg')):
                if composite.mode == 'RGBA':
                    # 创建白色背景
                    background = Image.new('RGB', composite.size, (255, 255, 255))
                    background.paste(composite, mask=composite.split()[3] if composite.mode == 'RGBA' else None)
                    composite = background
            
            elif path.lower().endswith('.bmp'):
                if composite.mode == 'RGBA':
                    composite = composite.convert('RGB')
            
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            composite.save(path)
            
            self.image_path = path
            self.is_modified = False
            self.status_updated.emit(f"已保存为: {path}")
            
        except Exception as e:
            QMessageBox.critical(self.main_window, "错误", f"保存失败: {str(e)}")
    
    # ===================== 历史记录 =====================
    
    def save_to_history(self):
        """✅ 修复核心：保存完整快照，不比较状态"""
        if not self.is_recording or not self.layers:
            return
        
        # ✅ 修复：删除状态比较逻辑，确保每次操作都保存到历史
        state = []
        for layer in self.layers:
            state.append({
                'name': layer['name'],
                'image': layer['image'].copy(),  # 关键：确保独立副本
                'visible': layer['visible'],
                'opacity': layer['opacity'],
                'locked': layer.get('locked', False)
            })
        
        # 保存调整状态
        adjustments = {
            'original_images': {idx: img.copy() for idx, img in self._original_images.items()},
            'adjustment_values': dict(self._adjustment_values),
            'current_adjustment_type': self._current_adjustment_type
        }
        
        self.undo_stack.append({
            'layers': state,
            'active': self.active_layer_index,
            'adjustments': adjustments
        })
        
        self.redo_stack.clear()
        self._update_undo_redo_buttons()
    
    def undo(self):
        """撤销 - 修复调整的撤销"""
        if not self.undo_stack:
            self.status_updated.emit("没有可撤销的操作")
            return
        
        # 保存当前状态到重做栈
        current = []
        for layer in self.layers:
            current.append({
                'name': layer['name'],
                'image': layer['image'].copy(),
                'visible': layer['visible'],
                'opacity': layer['opacity'],
                'locked': layer.get('locked', False)
            })
        
        # 保存调整状态
        current_adjustments = {
            'original_images': {idx: img.copy() for idx, img in self._original_images.items()},
            'adjustment_values': dict(self._adjustment_values),
            'current_adjustment_type': self._current_adjustment_type
        }
        
        self.redo_stack.append({
            'layers': current,
            'active': self.active_layer_index,
            'adjustments': current_adjustments
        })
        
        # 恢复历史状态
        data = self.undo_stack.pop()
        self._restore_history(data)
        
        self.is_modified = True
        self.status_updated.emit(f"撤销 (剩余: {len(self.undo_stack)})")
        self._update_undo_redo_buttons()
        self._update_layer_panel_ui()
    
    def redo(self):
        """重做 - 修复调整的重做"""
        if not self.redo_stack:
            self.status_updated.emit("没有可重做的操作")
            return
        
        # 保存当前状态到撤销栈
        current = []
        for layer in self.layers:
            current.append({
                'name': layer['name'],
                'image': layer['image'].copy(),
                'visible': layer['visible'],
                'opacity': layer['opacity'],
                'locked': layer.get('locked', False)
            })
        
        # 保存调整状态
        current_adjustments = {
            'original_images': {idx: img.copy() for idx, img in self._original_images.items()},
            'adjustment_values': dict(self._adjustment_values),
            'current_adjustment_type': self._current_adjustment_type
        }
        
        self.undo_stack.append({
            'layers': current,
            'active': self.active_layer_index,
            'adjustments': current_adjustments
        })
        
        # 恢复重做状态
        data = self.redo_stack.pop()
        self._restore_history(data)
        
        self.is_modified = True
        self.status_updated.emit(f"重做 (剩余: {len(self.redo_stack)})")
        self._update_undo_redo_buttons()
        self._update_layer_panel_ui()
    
    def _restore_history(self, data):
        """✅ 修复核心：重建所有对象，避免引用污染"""
        self.is_recording = False
        
        self.layers.clear()
        for state in data['layers']:
            layer = {
                'name': state['name'],
                'image': QImage(state['image']),  # ✅ 修复：创建新的QImage实例
                'visible': state['visible'],
                'opacity': state['opacity'],
                'locked': state.get('locked', False)
            }
            self.layers.append(layer)
        
        self.active_layer_index = data['active']
        
        # 恢复调整状态
        if 'adjustments' in data:
            adj_data = data['adjustments']
            # ✅ 修复：创建新的QImage实例
            self._original_images = {idx: QImage(img) for idx, img in adj_data.get('original_images', {}).items()}
            self._adjustment_values = dict(adj_data.get('adjustment_values', {}))
            self._current_adjustment_type = adj_data.get('current_adjustment_type')
        else:
            # 清除调整状态
            self._original_images.clear()
            self._adjustment_values.clear()
            self._current_adjustment_type = None
        
        # 清除临时预览
        if hasattr(self, 'temp_pixmap'):
            self.temp_pixmap = None
        
        # 清除选区
        self.clear_selection()
        
        self._update_layer_panel_ui()
        self.schedule_update()
        
        self.is_recording = True
    
    def _update_undo_redo_buttons(self):
        """更新撤销/重做按钮状态"""
        if not self.main_window:
            return
        
        # 在主窗口工具栏中查找并更新按钮状态
        if hasattr(self.main_window, 'top_toolbar'):
            for action in self.main_window.top_toolbar.actions():
                if action.text() == "撤销":
                    action.setEnabled(len(self.undo_stack) > 0)
                elif action.text() == "重做":
                    action.setEnabled(len(self.redo_stack) > 0)
    
    def clear_history(self):
        """清空历史"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._original_images.clear()
        self._adjustment_values.clear()
        self._current_adjustment_type = None
        self._update_undo_redo_buttons()
    
    # ===================== 选区操作 =====================
    
    def copy_selection(self):
        """复制选区"""
        if not self.is_selection_active or not self.selection_rect:
            self.status_updated.emit("没有选中区域")
            return False
        
        if self.current_tool and self.tool_manager:
            tool = self.tool_manager.get_tool(self.current_tool)
            if tool and hasattr(tool, 'copy_selection'):
                return tool.copy_selection()
        
        # 通用复制逻辑
        if self.selection_content:
            # 将选区内容复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setImage(self.selection_content)
            self.status_updated.emit("选区内容已复制到剪贴板")
            return True
        
        return False
    
    def cut_selection(self):
        """剪切选区"""
        if not self.is_selection_active or not self.selection_rect:
            self.status_updated.emit("没有选中区域")
            return False
        
        if self.current_tool and self.tool_manager:
            tool = self.tool_manager.get_tool(self.current_tool)
            if tool and hasattr(tool, 'cut_selection'):
                return tool.cut_selection()
        
        # 通用剪切逻辑
        if self.selection_content:
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setImage(self.selection_content)
            
            # 从图层中删除选区内容
            self.delete_selection()
            
            self.status_updated.emit("选区内容已剪切到剪贴板")
            return True
        
        return False
    
    def paste_selection(self):
        """粘贴选区"""
        # 首先检查剪贴板
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        
        if image.isNull():
            # 如果没有图像，尝试工具粘贴
            if self.current_tool and self.tool_manager:
                tool = self.tool_manager.get_tool(self.current_tool)
                if tool and hasattr(tool, 'paste_selection'):
                    return tool.paste_selection()
            
            self.status_updated.emit("剪贴板中没有图像内容")
            return False
        
        # 如果有图像，创建新的图层来粘贴
        self.save_to_history()
        
        # 创建新图层
        new_layer = self.add_layer("粘贴", image=image)
        if new_layer:
            self.status_updated.emit("已从剪贴板粘贴图像")
            return True
        
        return False
    
    def delete_selection(self):
        """删除选区"""
        if not self.is_selection_active or not self.selection_rect:
            self.status_updated.emit("没有选中区域")
            return False
        
        if self.current_tool and self.tool_manager:
            tool = self.tool_manager.get_tool(self.current_tool)
            if tool and hasattr(tool, 'delete_selection'):
                return tool.delete_selection()
        
        # 通用删除逻辑
        if self.active_layer_index >= 0 and self.active_layer_index < len(self.layers):
            self.save_to_history()
            
            active_layer = self.layers[self.active_layer_index]
            image = active_layer['image']
            
            # 创建临时图像
            temp_image = image.copy()
            painter = QPainter(temp_image)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self.selection_rect, QColor(0, 0, 0, 0))
            painter.end()
            
            active_layer['image'] = temp_image
            self.schedule_update()
            self.is_modified = True
            
            # 清除选区
            self.clear_selection()
            
            self.status_updated.emit("选区内容已删除")
            return True
        
        return False
    
    def select_all(self):
        """全选"""
        if not self.current_image:
            self.status_updated.emit("没有图像")
            return
        
        self.selection_rect = QRect(0, 0, self.current_image.width(), self.current_image.height())
        self.is_selection_active = True
        
        # 获取选区内容
        self.selection_content = self.current_image.copy(self.selection_rect)
        
        self.status_updated.emit(f"全选: {self.selection_rect.width()}x{self.selection_rect.height()}")
    
    def clear_selection(self):
        """清除选区"""
        self.selection_rect = None
        self.selection_content = None
        self.is_selection_active = False
        self.selection_transform = None
        
        # 清除临时预览
        if hasattr(self, 'temp_pixmap'):
            self.temp_pixmap = None
            if self.canvas:
                self.canvas.update()
        
        self.status_updated.emit("选区已清除")
    
    def commit_selection(self):
        """提交选区"""
        if not self.is_selection_active or not self.selection_rect:
            self.status_updated.emit("没有选中区域")
            return
        
        # 这里可以添加选区提交后的处理逻辑
        # 例如：将选区内容应用到新图层
        
        self.clear_selection()
        self.status_updated.emit("选区已提交")
    
    def cut(self):
        """剪切(快捷键)"""
        return self.cut_selection()
    
    def copy(self):
        """复制(快捷键)"""
        return self.copy_selection()
    
    def paste(self):
        """粘贴(快捷键)"""
        return self.paste_selection()
    
    def delete_selection_shortcut(self):
        """删除选区(快捷键)"""
        return self.delete_selection()
    
    # ===================== 视图操作 =====================
    
    def zoom_in(self):
        """放大"""
        if self.canvas:
            self.canvas.scale_factor *= 1.1
            self.canvas.update()
            
            # 更新主窗口缩放标签
            if self.main_window and hasattr(self.main_window, 'update_zoom_label'):
                self.main_window.update_zoom_label(self.canvas.scale_factor)
    
    def zoom_out(self):
        """缩小"""
        if self.canvas:
            self.canvas.scale_factor /= 1.1
            self.canvas.scale_factor = max(self.canvas.scale_factor, 0.1)
            self.canvas.update()
            
            # 更新主窗口缩放标签
            if self.main_window and hasattr(self.main_window, 'update_zoom_label'):
                self.main_window.update_zoom_label(self.canvas.scale_factor)
    
    def reset_zoom(self):
        """重置缩放"""
        if self.canvas:
            self.canvas.fit_to_window()
            
            # 更新主窗口缩放标签
            if self.main_window and hasattr(self.main_window, 'update_zoom_label'):
                self.main_window.update_zoom_label(self.canvas.scale_factor)
    
    # ===================== 辅助方法 =====================
    
    def get_current_size(self) -> int:
        """获取当前画笔大小"""
        if hasattr(self.main_window, 'property_panel'):
            return self.main_window.property_panel.size_slider.value()
        return 10
    
    def get_current_opacity(self) -> int:
        """获取当前不透明度"""
        if hasattr(self.main_window, 'property_panel'):
            return self.main_window.property_panel.opacity_slider.value()
        return 100
    
    def get_current_fg_color(self) -> QColor:
        """获取当前前景色"""
        if hasattr(self.main_window, 'property_panel'):
            return self.main_window.property_panel.fg_button.color
        return QColor("black")
    
    def get_current_bg_color(self) -> QColor:
        """获取当前背景色"""
        if hasattr(self.main_window, 'property_panel'):
            return self.main_window.property_panel.bg_button.color
        return QColor("white")
    
    def get_transparent_color(self) -> QColor:
        """获取透明色"""
        return self.transparent_color
    
    # ===================== 事件处理 =====================
    
    def on_layer_added(self, name: str):
        """图层添加事件"""
        if self.current_image:
            new_layer = self.add_layer(name, self.get_current_bg_color())
            if new_layer:
                self._update_layer_panel_ui()
    
    def on_layer_removed(self, index: int):
        """图层删除事件"""
        if self.remove_layer(index):
            self._update_layer_panel_ui()
    
    def on_layer_toggled(self, index: int, visible: bool):
        """图层可见性切换事件"""
        self.toggle_layer_visibility(index, visible)
    
    def on_layer_selected(self, index: int):
        """图层选择事件"""
        self.select_layer(index)
    
    def on_size_changed(self, value: int):
        """画笔大小改变事件"""
        # 可以在这里添加额外处理
        pass
    
    def on_opacity_changed(self, value: int):
        """不透明度改变事件"""
        # 可以在这里添加额外处理
        pass
    
    def on_fg_color_changed(self, color: QColor):
        """前景色改变事件"""
        # 可以在这里添加额外处理
        if hasattr(self.main_window, 'property_panel'):
            self.main_window.property_panel.fg_button.set_color(color)
    
    def on_bg_color_changed(self, color: QColor):
        """背景色改变事件"""
        # 可以在这里添加额外处理
        if hasattr(self.main_window, 'property_panel'):
            self.main_window.property_panel.bg_button.set_color(color)
    
    # ===================== UI更新 =====================
    
    def _update_layer_panel_ui(self):
        """更新图层面板UI"""
        if not hasattr(self.main_window, 'layer_panel'):
            return
        
        panel = self.main_window.layer_panel
        
        if hasattr(panel, 'update_layer_list'):
            panel.update_layer_list(self.layers, self.active_layer_index)
        else:
            # 回退方法
            panel.layer_list.clear()
            
            for i, layer in enumerate(self.layers):
                item = QListWidgetItem(layer['name'])
                item.setCheckState(Qt.CheckState.Checked if layer['visible'] else Qt.CheckState.Unchecked)
                
                # 背景图层不能取消选中
                if i == 0:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                
                panel.layer_list.addItem(item)
            
            if self.active_layer_index >= 0:
                panel.layer_list.setCurrentRow(self.active_layer_index)
            
            # 更新按钮状态
            if hasattr(panel, '_update_buttons'):
                panel._update_buttons(self.active_layer_index)
    
    # ===================== 文字工具相关 =====================
    
    def add_text(self, text, font, color, scale=1.0, rotation=0.0, position=None):
        """添加文字到画布"""
        if not text or not self.layers or self.active_layer_index < 0:
            return

        self.save_to_history()

        def draw_text(painter):
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

            # 保存当前状态
            painter.save()

            # 如果指定了位置，移动到该位置
            if position:
                painter.translate(position.x(), position.y())

            # 应用旋转
            if rotation != 0:
                painter.rotate(rotation)

            # 应用缩放
            if scale != 1.0:
                painter.scale(scale, scale)

            # 设置字体和颜色
            painter.setFont(font)

            # 处理透明色
            if hasattr(color, 'alpha') and color.alpha() == 0:
                # 对于透明色，绘制文字轮廓
                painter.setPen(QPen(QColor(0, 0, 0, 100), 1))
            else:
                painter.setPen(color)

            # 绘制文字
            painter.drawText(0, 0, text)

            # 恢复状态
            painter.restore()

        save_history = True
        self.draw_on_active_layer(draw_text, save_history)

        self.status_updated.emit(f"已添加文字: {text[:20]}...")
    
    # ===================== 其他功能 =====================
    
    def print_document(self):
        """打印文档"""
        self.status_updated.emit("打印功能暂未实现")
    
    def print_preview(self):
        """打印预览"""
        self.status_updated.emit("打印预览功能暂未实现")
    
    def about(self):
        """关于对话框"""
        QMessageBox.information(self.main_window, "关于", 
            "笨笨画图 - 旗舰版 v3.0 (重构优化版)\n\n"
            "功能特色:\n"
            "• 完整的图层管理系统\n"
            "• 支持透明色和Alpha通道\n"
            "• 多种绘图工具（画笔、形状、文字等）\n"
            "• 选区工具支持旋转缩放\n"
            "• 图像调整（亮度、对比度、饱和度）\n"
            "• 滤镜效果\n"
            "• 撤销/重做历史记录\n\n"
            "作者: 笨笨\n"
            "版本: 3.0.0")
    
    def exit_app(self):
        """退出应用"""
        if self.main_window:
            self.main_window.close()
    
    def check_save_before_close(self):
        """关闭前检查保存"""
        if not self.is_modified:
            return True
        
        reply = QMessageBox.question(
            self.main_window, '保存更改',
            "当前图像已修改,是否保存?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | 
            QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.save_file()
            return True
        elif reply == QMessageBox.StandardButton.Cancel:
            return False
        
        return True
    
    # ===================== 透明色处理 =====================
    
    def apply_transparent_color(self, is_background=False):
        """应用透明色"""
        transparent_color = QColor(0, 0, 0, 0)
        
        if is_background:
            self.on_bg_color_changed(transparent_color)
        else:
            self.on_fg_color_changed(transparent_color)
        
        self.status_updated.emit(f"已设置{'背景' if is_background else '前景'}色为透明")
    
    # ===================== 工具状态管理 =====================
    
    def cancel_current_operation(self):
        """取消当前操作"""
        # 清除临时预览
        if hasattr(self, 'temp_pixmap'):
            self.temp_pixmap = None
            if self.canvas:
                self.canvas.update()
        
        # 取消当前工具操作
        if self.current_tool and self.tool_manager:
            tool = self.tool_manager.get_tool(self.current_tool)
            if tool and hasattr(tool, 'cancel'):
                tool.cancel()
        
        # 清除选区
        self.clear_selection()
        
        self.status_updated.emit("当前操作已取消")
    
    def update_tool_preview(self, pixmap, position=None):
        """更新工具预览 - 支持位置参数"""
        self.temp_pixmap = pixmap
        self.temp_preview_position = position  # 保存预览位置
        if self.canvas:
            self.canvas.update()
    
    def clear_tool_preview(self):
        """清除工具预览"""
        self.temp_pixmap = None
        if self.canvas:
            self.canvas.update()