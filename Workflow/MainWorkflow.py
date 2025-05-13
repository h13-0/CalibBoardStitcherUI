import logging
import math
import os.path
import threading
import multiprocessing
import time

import cv2
import numpy

from CalibBoardStitcher.Generator import BoardGenerator
from CalibBoardStitcher.CalibResult import CalibResult, MatchedPoint
from QtUI.CalibBoardStitcherUI import CalibBoardStitcherUI, ButtonClickedEvent, CalibDataSource
from QtUI.SubImage import SubImageStatus

from CalibBoardStitcher.Stitcher import Stitcher
from CalibBoardStitcher.Elements import CalibBoardObj

class ImageInfo:
    def __init__(self, path: str):
        self.path = path
        self._shape = None

    @property
    def shape(self):
        if self._shape is None:
            self._shape = cv2.imread(self.path).shape
        return self._shape


class MainWorkflow:
    def __init__(self, ui:CalibBoardStitcherUI, stop_event:threading.Event):
        self._ui = ui
        self._stop_event = stop_event
        self._main_thread = None
        self._stitcher = None

        # 任务锁
        self._task_mutex = threading.Lock()
        self._task_name = ""

        # 标定板拼接对象
        self._board_obj = None
        self._board_generator = BoardGenerator()
        self._board_img = None

        # 子图像序列
        self._sub_image_infos = {}

        # 配置UI回调函数
        self._ui.set_add_new_matched_point_callback(self._add_new_matched_point)

    def _gen_calib_board_img_task(self):
        """
        生成标定板图像的task
        """
        self._ui.set_progress_bar_value(0)

        board_obj = CalibBoardObj(
            row_count=self._ui.get_row_count(),
            col_count=self._ui.get_col_count(),
            qr_pixel_size=self._ui.get_qr_pixel_size(),
            qr_border=self._ui.get_qr_border()
        )

        self._board_img = self._board_generator.gen_img(
            board_obj,
            progress_callback=lambda v: self._ui.set_progress_bar_value(int(v))
        )
        self._ui.set_progress_bar_value(100)
        self._ui.set_calib_board_img(self._board_img)

    def _update_transformed_sub_image(self):
        pass

    def _load_sub_image_seq_task(self, folder: str):
        """
        从指定路径加载子图像序列的task

        :param folder: 文件夹路径
        """
        self._ui.set_progress_bar_value(0)
        self._sub_image_infos = {}

        if folder is None or not os.path.isdir(folder):
            logging.error("No folder selected.")
            return
        logging.info("Loading sub image sequence from folder {}.".format(folder))

        file_list = os.listdir(folder)
        file_num = len(file_list)
        for i in range(file_num):
            file_name = file_list[i]
            file_path = os.path.join(folder, file_name)
            try:
                self._ui.add_sub_image(file_name, file_path)
                self._ui.set_sub_image_status(file_name, SubImageStatus.HIDE)
                self._ui.set_progress_bar_value(int((i + 1) / file_num * 100))
                self._sub_image_infos[file_name] = ImageInfo(file_path)
            except Exception as e:
                logging.error(f"load image: {file_path} failed with msg: {str(e)}")
            if self._stop_event.is_set():
                break
        self._ui.set_progress_bar_value(100)

    def _detect_and_load_qr(self):
        """
        执行自动关键点匹配
        """
        self._ui.set_progress_bar_value(0)

        calib_result = None
        board_obj = None
        img_nums = len(self._sub_image_infos)

        # 尝试寻找图像中的二维码，并获取配置信息
        for img_info in self._sub_image_infos.values():
            img = cv2.imread(img_info.path)
            if self._stitcher is None:
                self._stitcher = Stitcher.from_qr_img(img)
                if self._stitcher:
                    calib_result = CalibResult(board_obj=self._stitcher.board_obj)
                    board_obj = calib_result.get_calib_board_obj()
                    break

        # 执行标定算法
        i = 0
        for img_info in self._sub_image_infos.values():
            img_id = os.path.basename(img_info.path)
            img = cv2.imread(img_info.path)

            start = time.perf_counter()
            matched_points = self._stitcher.match(img, img_id)  # 0.1655s
            end = time.perf_counter()
            logging.info("stitcher.match() spend: {}".format(end - start))

            for matched_point in matched_points:
                logging.info(matched_point)
                calib_result.add_matched_point(matched_point)

            # 找到匹配点对，进行拼接
            if len(matched_points) > 0:
                start = time.perf_counter()
                transformed, box = self._stitcher.stitch_full_gen_wrapped_partial(img, matched_points)
                end = time.perf_counter()
                logging.info("stitcher.stitch_full_gen_wrapped_partial() spend: {}".format(end - start))

                self._ui.update_transformed_sub_img(img_id, transformed)
                self._ui.set_sub_image_pos(img_id, (box.lt[0], box.lt[1]))
                self._ui.set_sub_image_matched_points(img_id, matched_points)
                self._ui.set_sub_image_status(img_id, SubImageStatus.SHOW_TRANSFORMED_LOCKED)
                self._ui.set_matched_points_changed_callback(self._matched_point_changed)

                self._ui.set_progress_bar_value(int((i + 1) / img_nums * 100))
            i += 1
        else:
            self._ui.set_progress_bar_value(0)
            logging.error(f"No QrCode found in total {img_nums} images.")

    def _load_calib_data(self, source: CalibDataSource):
        """
        从指定数据源导入数据

        :param source: 数据源
        """
        if source == CalibDataSource.DETECT_QR_CODE:
            self._detect_and_load_qr()
        elif source == CalibDataSource.IMPORT_FROM_FILE:
            file_path = self._ui.select_existing_file_path("选择标定结果文件")
            try:
                calib_result = CalibResult.load_from_file(file_path)
                self._stitcher = Stitcher.from_json_file(file_path)
                img_ids = calib_result.get_matched_img_id()
                img_nums = len(img_ids)
                i = 0
                for img_id in img_ids:
                    if img_id in self._sub_image_infos:
                        matched_points = calib_result.get_matched_points(img_id)
                        if len(matched_points) >= 3:
                            img = cv2.imread(self._sub_image_infos[img_id].path)
                            start = time.perf_counter()
                            transformed, box = self._stitcher.stitch_full_gen_wrapped_partial(img, matched_points)
                            end = time.perf_counter()
                            logging.info("stitcher.stitch_full_gen_wrapped_partial() spend: {}".format(end - start))

                            self._ui.update_transformed_sub_img(img_id, transformed)
                            self._ui.set_sub_image_pos(img_id, (box.lt[0], box.lt[1]))
                            self._ui.set_sub_image_matched_points(img_id, matched_points)
                            self._ui.set_sub_image_status(img_id, SubImageStatus.SHOW_TRANSFORMED_LOCKED)
                            self._ui.set_matched_points_changed_callback(self._matched_point_changed)

                            self._ui.set_progress_bar_value(int((i + 1) / img_nums * 100))
                        i += 1
            except Exception as e:
                logging.error(f"Load from file {file_path} failed with msg: {str(e)}")


    def _matched_point_changed(self, img_id: str, matched_points: list[MatchedPoint]) -> None:
        """
        匹配点变化时的回调函数

        :param img_id: 图像id
        :param matched_points: 新的匹配点
        """
        # 更新子图仿射图像
        img = cv2.imread(self._sub_image_infos[img_id].path)

        if len(matched_points) >= 3:
            start = time.perf_counter()
            transformed, box = self._stitcher.stitch_full_gen_wrapped_partial(img, matched_points)
            end = time.perf_counter()
            logging.info("stitcher.stitch_full_gen_wrapped_partial() spend: {}".format(end - start))

            self._ui.update_transformed_sub_img(img_id, transformed)
            self._ui.set_sub_image_pos(img_id, (box.lt[0], box.lt[1]))
        else:
            pass


    def _add_new_matched_point(self, img_id: str, pos: tuple[float, float]) -> None:
        """
        添加新的匹配点的回调函数

        :param img_id: 子图像ID
        """
        matched_points = self._ui.get_sub_image_matched_points(img_id)
        if len(matched_points) > 0:
            cb_pos = (0, 0)
            for point in matched_points:
                cb_pos = (
                    cb_pos[0] + point.cb_point[0],
                    cb_pos[1] + point.cb_point[1]
                )
            matched_point_nums = len(matched_points)
            cb_pos = (cb_pos[0] / matched_point_nums, cb_pos[1] / matched_point_nums)
        else:
            cb_pos = (0, 0)
        new_matched_point = MatchedPoint(
            img_id,
            cb_pos,
            pos
        )
        matched_points.append(new_matched_point)
        self._ui.set_sub_image_matched_points(img_id, matched_points)

    def _save_matched_points(self, save_path: str):
        """
        保存匹配点到文件

        :param save_path: 保存路径
        """
        if(self._stitcher is not None and
            save_path is not None and
            len(save_path) > 0
        ):
            calib_result = CalibResult(board_obj=self._stitcher.board_obj)
            for img_id in self._sub_image_infos.keys():
                matched_points = self._ui.get_sub_image_matched_points(img_id)
                for matched in matched_points:
                    calib_result.add_matched_point(matched)
            try:
                calib_result.save(save_path)
            except Exception as e:
                logging.error(e)

    def stitch_and_save_img(self):
        """
        拼接并保存图像
        """
        if self._stitcher is None:
            logging.warning("No stitch parameters configured, unable to stitch images.")
            return

        # 1. 将当前结果注册到CalibResult
        calib_result = CalibResult(board_obj=self._stitcher.board_obj)
        for img_id in self._sub_image_infos.keys():
            matched_points = self._ui.get_sub_image_matched_points(img_id)
            if len(matched_points) >= 3:
                for matched_point in matched_points:
                    calib_result.add_matched_point(matched_point)
        img_ids = calib_result.get_matched_img_id()
        if len(img_ids) == 0:
            logging.error(f"Insufficient matching points (n>3), stitching stopped.")
            return

        # 2. 计算比例常数、标准大图大小等
        scale = calib_result.calc_mean_sub_img_scale()
        ## 2.1 计算子图像能覆盖到的范围
        for i in range(len(img_ids)):
            matched_points = self._ui.get_sub_image_matched_points(img_ids[i])
            box = self._stitcher.stitch_full_calc_wrapped_partial_box(
                img_size=self._sub_image_infos[img_ids[i]].shape[0:2], matched_points=matched_points, scale=scale,
            )
            if i == 0:
                l = math.floor(box.left)
                t = math.floor(box.top)
                r = math.ceil(box.right)
                b = math.ceil(box.bottom)
            else:
                l = min(l, math.floor(box.left))
                t = min(t, math.floor(box.top))
                r = max(r, math.floor(box.right))
                b = max(b, math.ceil(box.bottom))
        ## 2.2 实例化大图
        base_w, base_h = r - l, b - t
        base_img = numpy.zeros(shape=(base_w, base_h, 3), dtype=numpy.uint8)

        # 3. 执行拼接
        for i in range(len(img_ids)):
            # 3.1 仿射变换
            wrapped_partial, box = self._stitcher.stitch_full_gen_wrapped_partial(
                partial_img=cv2.imread(self._sub_image_infos[img_ids[i]].path),
                matched_points=calib_result.get_matched_points(img_id=img_ids[i]),
                scale=scale,
            )
            # 3.2 计算ROI区域
            box_l = math.floor(box.left) - l
            box_r = math.ceil(box.right) - l
            box_t = math.floor(box.top) - t
            box_b = math.ceil(box.bottom) - t
            roi_l = min(max(box_l, 0), base_w - 1)
            roi_r = min(box_r, base_w - 1)
            roi_t = min(max(box_t, 0), base_h - 1)
            roi_b = min(box_b, base_h - 1)

            # 3.3 拼回大图
            base_img_roi = base_img[roi_t:roi_b + 1, roi_l:roi_r + 1]
            wrapped_partial_roi = wrapped_partial[roi_t - box_t:roi_b - box_t + 1, roi_l - box_l:roi_r - box_l + 1, 0:3]
            wrapped_mask_roi = wrapped_partial[roi_t - box_t:roi_b - box_t + 1, roi_l - box_l:roi_r - box_l + 1, 3]
            wrapped_mask_roi_bool = wrapped_mask_roi == 255
            base_img_roi[wrapped_mask_roi_bool] = wrapped_partial_roi[wrapped_mask_roi_bool]

            # 3.4 更新进度条
            self._ui.set_progress_bar_value(int((i + 1) / len(img_ids) * 100))

        # 4. 执行保存操作
        save_path = self._ui.select_save_file_path("选择图像保存路径", filter=".jpg")
        if len(save_path):
            try:
                cv2.imwrite(save_path, base_img)
            except Exception as e:
                logging.error(f"save image failed: {e}")

    def _do_task(self, task):
        task()
        self._task_mutex.release()

    def _try_load_task(self, task, task_name: str, wait: bool=False) -> bool:
        succ = False
        if self._task_mutex.acquire(blocking=wait):
            self._task_name = task_name
            thread = threading.Thread(target=self._do_task, args=(task, ))
            thread.daemon = True
            thread.start()
            succ = True
        if not succ:
            logging.warning("Task: {} is running".format(self._task_name))
        return succ

    def _main(self):
        """
        当前工作流的主逻辑，不应当在主线程中使用
        """
        self._ui.set_btn_clicked_callback(
            ButtonClickedEvent.GEN_AND_SAVE_CALIB_BOARD_BTN_CLICKED,
            lambda : self._try_load_task(
                self._gen_calib_board_img_task,
                task_name="Generate CalibBoard image task"
            ),
        )
        self._ui.set_btn_clicked_callback(
            ButtonClickedEvent.LOAD_SUB_IMG_SEQ_BTN_CLICKED,
            lambda : self._try_load_task(
                lambda : self._load_sub_image_seq_task(
                    folder=self._ui.select_existing_folder_path("选择子图像序列文件夹")
                ),
                task_name="Load sub image sequence task"
            ),
        )
        self._ui.set_btn_clicked_callback(
            ButtonClickedEvent.IMPORT_CALIB_RESULT_BTN_CLICKED,
            lambda : self._try_load_task(
                lambda : self._load_calib_data(
                    source=self._ui.get_selected_calib_source()
                ),
                task_name="Save calibration result task"
            )
        )

        self._ui.set_btn_clicked_callback(
            ButtonClickedEvent.GEN_CALIB_BOARD_BTN_CLICKED,
            lambda : self._try_load_task(
                lambda : self._gen_calib_board_img_task()
            )
        )
        self._ui.set_btn_clicked_callback(
            ButtonClickedEvent.SAVE_CALIB_RESULT_BUTTON,
            lambda : self._try_load_task(
                lambda : self._save_matched_points(
                    save_path=self._ui.select_save_file_path("选择保存路径", filter=".json")
                ),
                task_name="Save calibration result task"
            )
        )

        self._ui.set_btn_clicked_callback(
            ButtonClickedEvent.GEN_STITCHED_IMG_BTN_CLICKED,
            lambda : self._try_load_task(
                lambda : self.stitch_and_save_img(),
                task_name="Stitch and save img"
            )
        )

        while not self._stop_event.is_set():
            pass


    def run(self, block:bool = False):
        """
        启动工作流
        :param block: 是否在当前线程工作, 配合UI使用时应当为 `False`
        """
        if block:
            self._main()
        else:
            self._main_thread = threading.Thread(target = self._main)
            self._main_thread.start()
