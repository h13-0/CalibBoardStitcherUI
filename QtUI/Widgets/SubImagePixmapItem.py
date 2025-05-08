from typing import Callable

from PyQt6.QtCore import Qt, QPointF, QPoint
from PyQt6.QtGui import QAction, QPen, QColor
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QMenu

from CalibBoardStitcher.CalibResult import MatchedPoint
from PyQt6.uic.Compiler.qtproxies import QtWidgets

from QtUI.Widgets.MatchedPointWidget import MatchedPointWidget


class SubImagePixmapItem(QGraphicsPixmapItem):
    def __init__(self, img_id: str, pixmap: QGraphicsPixmapItem, pos: tuple[float, float]=(0, 0)):
        super().__init__(pixmap)
        self.img_id = img_id
        self.setPos(pos[0], pos[1])
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self._double_clicked_callback = None
        self._matched_point_widgets = []
        self._matched_point_changed_callback = None
        self._menu_options = {}
        self._menu_pos = (0, 0)

        self._focus_able = False
        self._is_focused = False

    def lock(self):
        """
        锁定对象，禁止拖动
        """
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable, False)
        for matched_point in self._matched_point_widgets:
            matched_point.lock()
            matched_point.set_visible(False)


    def unlock(self):
        """
        取消锁定对象，允许拖动
        """
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        for matched_point in self._matched_point_widgets:
            matched_point.unlock()
            matched_point.set_visible(True)

    def set_focus_able(self, focus_able: bool):
        """
        设置是否响应鼠标悬停(focus)事件
        """
        self._focus_able = focus_able

    def set_double_clicked_callback(self, callback: callable):
        """
        设置双击事件回调

        :param callback: 回调函数
        """
        self._double_clicked_callback = callback

    def set_matched_point_changed_callback(self, callback: Callable[[str, list[MatchedPoint]], None]):
        """
        设置匹配点变化的回调函数

        :param callback: def callback(img_id: str, matched_points: list[MatchedPoint]) -> None
        """
        self._matched_point_changed_callback = callback

    def set_matched_points(self,
            calib_board: QGraphicsPixmapItem,
            matched_points: list[MatchedPoint],
            scene: QGraphicsScene,
        ):
        """
        设置子图像的匹配点对，作为控件，本函数仅能在主线程中调用。

        :param calib_board: 标定板的PixmapItem对象
        :param matched_points: 匹配点列表
        :param scene: 子图像和标定板图像所处于的QGraphicsScene
        """
        # 清空原匹配点列表
        for widget in self._matched_point_widgets:
            widget.remove()
        self._matched_point_widgets = []
        for matched_point in matched_points:
            widget = MatchedPointWidget(
                calib_board=calib_board,
                calib_board_pos=QPointF(matched_point.cb_point[0], matched_point.cb_point[1]),
                sub_img=self,
                sub_img_pos=QPointF(matched_point.img_point[0], matched_point.img_point[1]),
                scene=scene
            )
            widget.set_changed_callback(self._matched_point_changed)
            self._matched_point_widgets.append(widget)

    def get_matched_points(self) -> list[MatchedPoint]:
        """
        获取当前图像中的匹配点信息
        """
        matched_points = []
        for matched_point in self._matched_point_widgets:
            matched_points.append(
                MatchedPoint(
                    img_id=self.img_id,
                    cb_point=[matched_point.cb_point.pos().x(), matched_point.cb_point.pos().y()],
                    img_point=[matched_point.sub_img_point.pos().x(), matched_point.sub_img_point.pos().y()],
                )
            )
        return matched_points

    def mouseDoubleClickEvent(self, event):
        if self._double_clicked_callback is not None:
            self._double_clicked_callback()
        event.accept()

    def itemChange(self, change, value):
        if change == QGraphicsPixmapItem.GraphicsItemChange.ItemPositionHasChanged:
            for matched_point in self._matched_point_widgets:
                matched_point.update_line_pos()
        return super().itemChange(change, value)

    def add_menu_options(self, option: str, callback: Callable[[tuple[float, float]], None]):
        """
        为当前PixmapItem添加右键菜单

        :param option: 菜单选项名
        :param callback: 回调函数，原型为：def callback(pos: tuple[float, float]) -> None
        """
        self._menu_options[option] = callback

    def contextMenuEvent(self, event):
        """
        右键菜单事件

        :param event:
        :return:
        """
        if len(self._menu_options) > 0:
            menu = QMenu()
            if isinstance(event.pos(), QPointF):
                self._menu_pos = event.pos()

                for option in self._menu_options.keys():
                    action = QAction(text=option)
                    action.triggered.connect(lambda : self._menu_options[option]((self._menu_pos.x(), self._menu_pos.y())))
                    menu.addAction(action)

                # 在鼠标位置显示菜单
                menu.exec(event.screenPos())
                event.accept()  # 标记事件已处理

    def hoverEnterEvent(self, event):
        if self._focus_able:
            self._is_focused = True
            self.setOpacity(0.5)
        else:
            self._is_focused = False
            self.setOpacity(1)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_focused = False
        self.setOpacity(1)
        super().hoverLeaveEvent(event)

    def paint(self, painter, option, widget=None):
        # 绘制原始图像
        super().paint(painter, option, widget)

        if self._is_focused:
            # 绘制边框
            painter.save()
            pen = QPen(QColor(0, 153, 204), 5)
            pen.setCosmetic(True)
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)  # 边框拐角锐利
            painter.setPen(pen)
            # 获取图像的实际显示区域（考虑缩放和偏移）
            rect = self.boundingRect()
            painter.drawRect(rect)
            painter.restore()

    def _matched_point_changed(self):
        if self._matched_point_changed_callback is not None:
            self._matched_point_changed_callback(self.img_id, self.get_matched_points())