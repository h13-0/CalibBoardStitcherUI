from enum import Enum
from typing import Callable

import cv2.typing
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QImage, QPixmap

from CalibBoardStitcher.CalibResult import MatchedPoint
from QtUI.Widgets.SubImagePixmapItem import SubImagePixmapItem

class SubImageStatus(Enum):
    HIDE = 0                        # 隐藏图像
    SHOW_ORIGINAL_LOCKED = 1        # 显示不可移动的原始图像
    SHOW_ORIGINAL_MOVABLE = 2       # 显示可移动的原始图像
    SHOW_TRANSFORMED_LOCKED = 3     # 显示不可移动的仿射后图像
    SHOW_TRANSFORMED_MOVABLE = 4    # 显示可移动的仿射后图像

class SubImage:
    def __init__(self, img_id: str, img_path: str, pos: tuple=(0, 0)):
        """
        子图像对象，管理UI中的子图像

        :param img_id: 图像id
        :param img_path: 图像文件路径
        :param pos: 子图像坐标
        """
        self.img_id = img_id
        self.img_path = img_path
        q_image = QImage(img_path)
        thumbnail = q_image.scaled(
            100, 100,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.thumbnail_pixmap = QPixmap.fromImage(thumbnail)

        self._original_draggable_pixmap_item = SubImagePixmapItem(img_id, QPixmap(q_image))
        self._original_draggable_pixmap_item.set_double_clicked_callback(self._double_clicked)
        self._original_draggable_pixmap_item.set_matched_point_changed_callback(self._matched_point_changed)

        self._transformed_draggable_pixmap_item = SubImagePixmapItem(img_id, QPixmap())
        self._transformed_draggable_pixmap_item.set_double_clicked_callback(self._double_clicked)
        self._transformed_draggable_pixmap_item.set_matched_point_changed_callback(self._matched_point_changed)

        self.enabled = False
        self._pos = pos
        self.status = SubImageStatus.SHOW_ORIGINAL_LOCKED
        self._double_clicked_callback = None
        self._matched_point_changed_callback = None

    def get_original_pixmap_item(self) -> SubImagePixmapItem:
        """
        获取原始图像对应的PixmapItem
        """
        return self._original_draggable_pixmap_item

    def get_transformed_pixmap_item(self) -> SubImagePixmapItem:
        """
        获取变换后的PixmapItem
        """
        return self._transformed_draggable_pixmap_item

    def update_transformed_img(self, img: cv2.typing.MatLike):
        """
        将子图像更新为校准变换后的图像
        :param img: 变换后的子图像，需要为BGRA四通道
        """
        h, w = img.shape[0:2]
        self._transformed_draggable_pixmap_item.setPixmap(
            QPixmap.fromImage(QImage(img, w, h, w * 4, QImage.Format.Format_ARGB32))
        )


    def set_pos(self, pos: tuple[float, float]):
        """
        设置控件在mainGraphicsView中显示的位置

        :param pos:
        """
        self._pos = pos
        if self._original_draggable_pixmap_item is not None:
            self._original_draggable_pixmap_item.setPos(QPointF(pos[0], pos[1]))
        if self._transformed_draggable_pixmap_item is not None:
            self._transformed_draggable_pixmap_item.setPos(QPointF(pos[0], pos[1]))

    def set_selected_callback(self, callback):
        """
        设置SubImage的选中回调函数

        :param callback: 回调函数
        """
        self._double_clicked_callback = callback

    def get_matched_points(self) -> list[MatchedPoint]:
        """
        获取子图像匹配点

        :param img_id: 子图像ID
        """
        return self._original_draggable_pixmap_item.get_matched_points()

    def set_matched_point_changed_callback(self, callback: Callable[[str, list[MatchedPoint]], None]):
        """
        设置匹配点变化的回调函数

        :param callback: def callback(img_id: str, matched_points: list[MatchedPoint]) -> None
        """
        self._matched_point_changed_callback = callback

    def switch_to(self, status: SubImageStatus):
        """
        切换子图像对象的状态
        :param status: 要切换到的状态
        """
        if status == SubImageStatus.HIDE:
            self._original_draggable_pixmap_item.setVisible(False)
            self._transformed_draggable_pixmap_item.setVisible(False)
        elif status == SubImageStatus.SHOW_ORIGINAL_LOCKED:
            # 设置子图可见性
            self._original_draggable_pixmap_item.setVisible(True)
            self._transformed_draggable_pixmap_item.setVisible(False)
            # 设置原始图像及其MatchedPoints锁定状态
            self._original_draggable_pixmap_item.lock()
        elif status == SubImageStatus.SHOW_ORIGINAL_MOVABLE:
            self._original_draggable_pixmap_item.setVisible(True)
            self._transformed_draggable_pixmap_item.setVisible(False)
            self._original_draggable_pixmap_item.unlock()
        elif status == SubImageStatus.SHOW_TRANSFORMED_LOCKED:
            self._original_draggable_pixmap_item.setVisible(False)
            self._transformed_draggable_pixmap_item.setVisible(True)
            self._transformed_draggable_pixmap_item.lock()
        elif status == SubImageStatus.SHOW_TRANSFORMED_MOVABLE:
            self._original_draggable_pixmap_item.setVisible(False)
            self._transformed_draggable_pixmap_item.setVisible(True)
            self._transformed_draggable_pixmap_item.unlock()
        self.status = status

    def get_status(self) -> SubImageStatus:
        return self.status

    def _double_clicked(self):
        if self._double_clicked_callback is not None:
            self._double_clicked_callback()

    def _matched_point_changed(self, img_id: str, matched_points: list[MatchedPoint]) -> None:
        """
        匹配点变化回调函数
        """
        if self._matched_point_changed_callback is not None:
            self._matched_point_changed_callback(img_id, matched_points)
