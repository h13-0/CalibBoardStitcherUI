from typing import Callable

from PyQt6.QtCore import QRectF, QPointF, QLineF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QWidget, QGraphicsLineItem, QGraphicsScene


class CrosshairItem(QGraphicsItem):
    def __init__(self, pos: QPointF, parent=None):
        self._item_change_callback = None
        self._item_changed_callback = None
        self._item_changed = False
        super().__init__(parent)
        # 忽略视图变化
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.size = 20
        self.setPos(pos)

        # 鼠标悬停功能
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.default_pen = QPen(QColor(255, 0, 0), 1)
        self.hover_pen = QPen(QColor(0, 255, 0), 1)

        # 启用事件监听
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def boundingRect(self):
        # 定义项的边界矩形
        return QRectF(-self.size, -self.size, 2 * self.size, 2 * self.size)

    def paint(self, painter: QPainter, option, widget=None):
        # 绘制固定大小的十字
        if self._is_hovered:
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

    def itemChange(self, change, value):
        if(change == QGraphicsItem.GraphicsItemChange.ItemPositionChange or
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged):
            # 坐标正在变化事件
            if self._item_change_callback is not None:
                self._item_change_callback()
            self._item_changed = True

        return super().itemChange(change, value)

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
        self._is_hovered = True
        view = self.scene().views()[0]
        view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
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
        self.line = QGraphicsLineItem()
        self.line.setVisible(False)
        self._update_line_pos()
        self._scene.addItem(self.line)

        self.cb_point.set_item_change_callback(self._update_line_pos)
        self.cb_point.set_item_changed_callback(self._point_changed)
        self.cb_point.setVisible(False)

        self.sub_img_point.set_item_change_callback(self._update_line_pos)
        self.sub_img_point.set_item_changed_callback(self._point_changed)
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
        self._update_line_pos()
        if self._changed_callback is not None:
            self._changed_callback()

    def _update_line_pos(self):
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
