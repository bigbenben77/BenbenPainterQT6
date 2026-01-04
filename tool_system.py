# tool_system.py - 工具管理器主文件
from selection_tools import RectSelectTool, EllipseSelectTool, ImprovedPolygonSelectTool
from drawing_tools import BrushTool, EraserTool, AirbrushTool, FillTool
from geometry_tools import LineTool, RectangleTool, EllipseTool, StarTool, PolygonTool, RoundedRectTool, CurveTool
from other_tools import PickerTool
from text_tool import TextTool

class ToolManager:
    """工具管理器"""
    def __init__(self, controller):
        self.controller = controller
        self.active_tool = None
        self.tools = {}
        
        # 注册工具
        self._register_tools()
    
    def _register_tools(self):
        """注册所有工具"""
        # 选择工具
        self.tools['rect_select'] = RectSelectTool(self.controller)
        self.tools['ellipse_select'] = EllipseSelectTool(self.controller)
        self.tools['polygon_select'] = ImprovedPolygonSelectTool(self.controller)
        
        # 绘画工具
        self.tools['brush'] = BrushTool(self.controller)
        self.tools['eraser'] = EraserTool(self.controller)
        self.tools['airbrush'] = AirbrushTool(self.controller)
        self.tools['fill'] = FillTool(self.controller)
        
        # 几何工具
        self.tools['line'] = LineTool(self.controller)
        self.tools['rectangle'] = RectangleTool(self.controller)
        self.tools['ellipse'] = EllipseTool(self.controller)
        self.tools['star'] = StarTool(self.controller)
        self.tools['polygon'] = PolygonTool(self.controller)
        self.tools['rounded_rect'] = RoundedRectTool(self.controller)
        self.tools['curve'] = CurveTool(self.controller)
        
        # 其他工具
        self.tools['picker'] = PickerTool(self.controller)
        self.tools['text'] = TextTool(self.controller)
    
    def set_active_tool(self, tool_id):
        """设置激活的工具"""
        self.active_tool = tool_id
        if self.controller and hasattr(self.controller, 'status_updated'):
            self.controller.status_updated.emit(f"激活工具: {tool_id}")
    
    def get_tool(self, tool_id):
        """获取指定工具"""
        return self.tools.get(tool_id)