call %USERPROFILE%\anaconda3\Scripts\activate.bat %USERPROFILE%\anaconda3
call conda activate h13_stitcher
python -m PyQt6.uic.pyuic CalibBoardStitcher.ui -o Ui_CalibBoardStitcher.py