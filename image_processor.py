# image_processor.py - 性能优化版（重构）
from PyQt6.QtGui import QImage, QColor, QPainter, QPen, QBrush
from PyQt6.QtCore import Qt, QRect
from PIL import Image, ImageFilter, ImageEnhance
import numpy as np
from functools import lru_cache
import math


class ImageProcessor:
    """图像处理器 - 优化版"""
    
    # 常量
    DEFAULT_RADIUS = 5
    DEFAULT_KERNEL = 9
    DEFAULT_BLOCK = 10
    MAX_KERNEL = 15
    
    @staticmethod
    @lru_cache(maxsize=32)
    def create_new_image(width: int, height: int, bg_color: QColor = None) -> QImage:
        """创建新图像 - 缓存优化"""
        bg_color = bg_color or QColor(Qt.GlobalColor.white)
        
        if not isinstance(bg_color, QColor):
            bg_color = QColor(bg_color)
        
        fmt = QImage.Format.Format_ARGB32 if bg_color.alpha() == 0 else QImage.Format.Format_RGB32
        
        image = QImage(width, height, fmt)
        image.fill(bg_color)
        return image
    
    @staticmethod
    def _enhance_image(image: Image.Image, value: int, enhancer_type: str) -> Image.Image:
        """通用增强方法"""
        if value == 0:
            return image
        
        enhancers = {
            'brightness': ImageEnhance.Brightness,
            'contrast': ImageEnhance.Contrast,
            'saturation': ImageEnhance.Color
        }
        
        cls = enhancers.get(enhancer_type)
        if not cls:
            return image
        
        enhancer = cls(image)
        return enhancer.enhance(1.0 + value / 100.0)
    
    @staticmethod
    def apply_brightness(image: Image.Image, value: int) -> Image.Image:
        """调整亮度"""
        return ImageProcessor._enhance_image(image, value, 'brightness')
    
    @staticmethod
    def apply_contrast(image: Image.Image, value: int) -> Image.Image:
        """调整对比度"""
        return ImageProcessor._enhance_image(image, value, 'contrast')
    
    @staticmethod
    def apply_saturation(image: Image.Image, value: int) -> Image.Image:
        """调整饱和度"""
        return ImageProcessor._enhance_image(image, value, 'saturation')
    
    @staticmethod
    def apply_gaussian_blur(image: Image.Image, radius: int = DEFAULT_RADIUS) -> Image.Image:
        """高斯模糊 - 优化版"""
        try:
            if radius <= 0:
                return image.copy()
            radius = min(radius, 10)
            return image.filter(ImageFilter.GaussianBlur(radius=radius))
        except Exception as e:
            print(f"高斯模糊失败: {e}")
            return image.copy()
    
    @staticmethod
    def apply_motion_blur(image: Image.Image, kernel_size: int = DEFAULT_KERNEL) -> Image.Image:
        """运动模糊 - 优化版"""
        try:
            kernel_size = max(3, min(kernel_size, ImageProcessor.MAX_KERNEL))
            if kernel_size % 2 == 0:
                kernel_size += 1
            
            return ImageProcessor._simple_motion_blur(image, kernel_size)
            
        except Exception as e:
            print(f"运动模糊失败: {e}")
            return image.copy()
    
    @staticmethod
    def _simple_motion_blur(image: Image.Image, kernel_size: int) -> Image.Image:
        """简化的运动模糊"""
        try:
            kernel_size = max(3, min(kernel_size, 15))
            original = image.copy()
            
            work = image.convert('RGBA') if image.mode != 'RGBA' else image.copy()
            blur_radius = kernel_size // 3
            
            result = work
            for _ in range(3):
                result = result.filter(ImageFilter.BoxBlur(blur_radius))
            
            if image.mode == 'RGBA':
                blended = Image.blend(original.convert('RGBA'), result, alpha=0.6)
                return blended.convert(image.mode) if image.mode != 'RGBA' else blended
            else:
                return Image.blend(original, result, alpha=0.6)
            
        except Exception as e:
            print(f"简化运动模糊失败: {e}")
            return image.copy()
    
    @staticmethod
    def apply_sharpen(image: Image.Image) -> Image.Image:
        """锐化"""
        try:
            return image.filter(ImageFilter.SHARPEN)
        except Exception as e:
            print(f"锐化失败: {e}")
            return image.copy()
    
    @staticmethod
    def apply_emboss(image: Image.Image) -> Image.Image:
        """浮雕"""
        try:
            return image.filter(ImageFilter.EMBOSS)
        except Exception as e:
            print(f"浮雕失败: {e}")
            return image.copy()
    
    @staticmethod
    def apply_mosaic(image: Image.Image, block_size: int = DEFAULT_BLOCK) -> Image.Image:
        """马赛克 - numpy优化版"""
        try:
            block_size = max(2, min(block_size, 50))
            
            # 转换为numpy数组加速处理
            arr = np.array(image)
            h, w = arr.shape[:2]
            
            # 分块处理
            for y in range(0, h, block_size):
                for x in range(0, w, block_size):
                    y_end = min(y + block_size, h)
                    x_end = min(x + block_size, w)
                    
                    # 计算块的平均颜色
                    block = arr[y:y_end, x:x_end]
                    avg_color = block.mean(axis=(0, 1)).astype(np.uint8)
                    
                    # 填充块
                    arr[y:y_end, x:x_end] = avg_color
            
            return Image.fromarray(arr, mode=image.mode)
            
        except Exception as e:
            print(f"马赛克失败: {e}")
            return image.copy()
    
    @staticmethod
    def draw_shape_preview(shape_type: str, start_x: int, start_y: int, end_x: int, end_y: int,
                          size: int, color: QColor, opacity: float, filled: bool = False) -> QImage:
        """绘制形状预览 - 通用方法"""
        width = abs(end_x - start_x) + size + 20
        height = abs(end_y - start_y) + size + 20
        
        preview = QImage(width, height, QImage.Format.Format_ARGB32)
        preview.fill(QColor(0, 0, 0, 0))
        
        painter = QPainter(preview)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(opacity)
        
        offset_x = min(start_x, end_x) - 10
        offset_y = min(start_y, end_y) - 10
        
        rel_x = start_x - offset_x
        rel_y = start_y - offset_y
        rel_w = abs(end_x - start_x)
        rel_h = abs(end_y - start_y)
        
        pen = QPen(color, size)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        
        if filled:
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(pen)
        
        # 根据形状类型绘制
        if shape_type == 'line':
            painter.drawLine(rel_x, rel_y, rel_x + rel_w, rel_y + rel_h)
        elif shape_type == 'rectangle':
            painter.drawRect(QRect(rel_x, rel_y, rel_w, rel_h))
        elif shape_type == 'ellipse':
            painter.drawEllipse(QRect(rel_x, rel_y, rel_w, rel_h))
        elif shape_type == 'rounded_rect':
            radius = min(rel_w, rel_h) // 4
            painter.drawRoundedRect(QRect(rel_x, rel_y, rel_w, rel_h), radius, radius)
        
        painter.end()
        return preview
    
    @staticmethod
    def merge_images(source_image: QImage, dest_image: QImage, x: int, y: int) -> QImage:
        """合并图像"""
        result = dest_image.copy()
        painter = QPainter(result)
        painter.drawImage(x, y, source_image)
        painter.end()
        return result