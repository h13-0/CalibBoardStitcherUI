from typing import Callable

from PyQt6.QtCore import QRectF, QPointF, QLineF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QWidget, QGraphicsLineItem, QGraphicsScene


class CrosshairItem(QGraphicsItem):
    def __init__(self, pos: QPointF, parent=None):
        self._item_change_callback = None
        self._item_changed_callback = None
        self._hover_changed_callback = None
        self._item_changed = False
        super().__init__(parent)
        # 忽略视图变化
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.size = 20
        self.setPos(pos)

        # 鼠标悬停功能
        self.setAcceptHoverEvents(True)
        self._focused = False
        self.default_pen = QPen(QColor(255, 0, 0), 1)
        self.hover_pen = QPen(QColor(0, 255, 0), 1)

        # 启用事件监听
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # 键盘事件监听
        self._is_alt_pressing = False

    def boundingRect(self):
        # 定义项的边界矩形
        return QRectF(-self.size, -self.size, 2 * self.size, 2 * self.size)

    def paint(self, painter: QPainter, option, widget=None):
        # 绘制固定大小的十字
        if self._focused:
            painter.setPen(self.hover_pen)
        else:
            painter.setPen(self.default_pen)

        # 水平线
        painter.drawLine(-self.size, 0, self.size, 0)
        # 垂直线
        painter.drawLine(0, -self.size, 0, self.size)

    def set_item_change_callback(self, callback: Callable):
        """
        设置坐标变化回调函数

        :param callback: 回调函数
        """
        self._item_change_callback = callback

    def set_item_changed_callback(self, callback: Callable):
        """
        设置坐标变化结束回调函数

        :param callback: 回调函数
        """
        self._item_changed_callback = callback

    def set_hover_changed_callback(self, callback: Callable[[bool], None]):
        """
        设置鼠标悬停事件接受函数

        :param callback: def hover_changed(hover: bool) -> None
        """
        self._hover_changed_callback = callback

    def set_focus_status(self, focused: bool):
        """
        手动设置当前的focus状态

        :param focused: bool
        """
        self._focused = focused
        self.update()

    def itemChange(self, change, value):
        if(change == QGraphicsItem.GraphicsItemChange.ItemPositionChange or
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged):
            # 检测alt键是否按下
            if self._is_alt_pressing:
                # 启用坐标自动吸附
                pos_x = round(value.x())
                pos_y = round(value.y())
            # 坐标正在变化事件
            if self._item_change_callback is not None:
                self._item_change_callback()
            self._item_changed = True
            if self._is_alt_pressing:
                return QPointF(pos_x, pos_y)
        return super().itemChange(change, value)

    def keyPressEvent(self, event):
        key = event.key()
        if self._focused and key == Qt.Key.Key_Alt:
            self._is_alt_pressing = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Alt:
            self._is_alt_pressing = False
        super().keyReleaseEvent(event)

    def mouseReleaseEvent(self, event):
        """
        鼠标释放事件

        :param event:
        """
        # 坐标变化结束
        if self._item_changed and self._item_changed_callback is not None:
            self._item_changed_callback()
            self._item_changed = False
        super().mouseReleaseEvent(event)

    def lock(self):
        """
        锁定十字准星，使其不可拖动
        """
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def unlock(self):
        """
        解锁十字准星，允许拖动
        """
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def hoverEnterEvent(self, event):
        if not self._focused and self._item_changed_callback is not None:
            self._hover_changed_callback(True)
        self._focused = True
        view = self.scene().views()[0]
        view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if self._focused and self._item_changed_callback is not None:
            self._hover_changed_callback(False)
        self._focused = False
        self._is_alt_pressing = False
        self.update()
        super().hoverLeaveEvent(event)


class MatchedPointWidget(QWidget):
    def __init__(self,
            calib_board: QGraphicsPixmapItem, calib_board_pos: QPointF,
            sub_img: QGraphicsPixmapItem, sub_img_pos: QPointF,
            scene: QGraphicsScene
        ):
        self._changed_callback = None
        super().__init__()
        self.cb_point = CrosshairItem(
            pos=calib_board_pos,
            parent=calib_board
        )
        self.sub_img_point = CrosshairItem(
            pos=sub_img_pos,
            parent=sub_img
        )
        self._scene = scene

        line_pen = QPen(QColor(0, 153, 204), 5)
        line_pen.setCosmetic(True)
        self.line = QGraphicsLineItem()
        self.line.setVisible(False)
        self.line.setPen(line_pen)
        self.line.setOpacity(0.75)
        self.update_line_pos()
        self._scene.addItem(self.line)

        self.cb_point.set_item_change_callback(self.update_line_pos)
        self.cb_point.set_item_changed_callback(self._point_changed)
        self.cb_point.set_hover_changed_callback(self._hover_changed)
        self.cb_point.setVisible(False)

        self.sub_img_point.set_item_change_callback(self.update_line_pos)
        self.sub_img_point.set_item_changed_callback(self._point_changed)
        self.sub_img_point.set_hover_changed_callback(self._hover_changed)
        self.sub_img_point.setVisible(False)


    def get_cb_point(self) -> tuple[float, float]:
        """
        获取标定板上匹配点坐标
        :return: tuple(x, y)
        """
        pos = self.cb_point.pos()
        return pos.x(), pos.y()

    def get_img_point(self) -> tuple[float, float]:
        """
        获取子图像上匹配点坐标
        :return: tuple(x, y)
        """
        pos = self.sub_img_point.pos()
        return pos.x(), pos.y()

    def set_changed_callback(self, callback: callable):
        """
        设置匹配点发生变化时的回调函数

        :param callback: 回调函数
        """
        self._changed_callback = callback

    def _point_changed(self):
        """
        匹配点变化的回调函数
        """
        # 先更新UI
        self.update_line_pos()
        if self._changed_callback is not None:
            self._changed_callback()

    def _hover_changed(self, hover: bool) -> None:
        """
        鼠标悬停事件回调函数
        """
        self.cb_point.set_focus_status(hover)
        self.sub_img_point.set_focus_status(hover)

    def update_line_pos(self):
        """
        更新线段坐标
        """
        pos1 = self.sub_img_point.mapToScene(self.sub_img_point.boundingRect().center())
        pos2 = self.cb_point.mapToScene(self.cb_point.boundingRect().center())
        self.line.setLine(QLineF(pos1, pos2))

    def lock(self):
        """
        锁定匹配点对，使其不可更改
        """
        self.cb_point.lock()
        self.sub_img_point.lock()

    def unlock(self):
        """
        解锁匹配点对
        """
        self.cb_point.unlock()
        self.sub_img_point.unlock()

    def set_visible(self, visible: bool):
        """
        设置可见性
        :param visible: 可见性
        """
        self.cb_point.setVisible(visible)
        self.sub_img_point.setVisible(visible)
        self.line.setVisible(visible)
        self._scene.update()

    def remove(self):
        """
        删除该节点
        """
        self._scene.removeItem(self.line)
        self.cb_point.setParentItem(None)
        self.sub_img_point.setParentItem(None)
        self.line = None
        self.cb_point = None
        self.sub_img_point = None
