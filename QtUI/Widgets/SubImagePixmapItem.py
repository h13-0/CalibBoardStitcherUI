from typing import Callable

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene

from CalibBoardStitcher.CalibResult import MatchedPoint
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

        for matched_point in matched_points:
            widget = MatchedPointWidget(
                calib_board=calib_board,
                calib_board_pos=QPointF(matched_point.cb_point[0], matched_point.cb_point[1]),
                sub_img=self,
                sub_img_pos=QPointF(matched_point.img_point[0], matched_point.img_point[1]),
                scene=scene
            )
            widget.set_changed_callback(self._matched_point_changed)
            self._matched_point_widgets.append(
                widget
            )

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

    def _matched_point_changed(self):
        if self._matched_point_changed_callback is not None:
            self._matched_point_changed_callback(self.img_id, self.get_matched_points())