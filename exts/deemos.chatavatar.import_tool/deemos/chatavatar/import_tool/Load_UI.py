import os
from typing import Union
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import QMessageBox
import UI_RESOURCES
from ChatAvatarPack.pack import Pack as CAPack
from ChatAvatarPack import defs as CADefs
import webbrowser

class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()
    def __init__(self, parent=None):
        super(ClickableLabel, self).__init__(parent)

    def mousePressEvent(self, event):
        self.clicked.emit()

class HoverLabel(QtWidgets.QLabel):
    __default_enter = (lambda self:None)
    __default_leave = (lambda self:None)
    def __init__(self, setEnter=(lambda self:None), setLeave=(lambda self:None), parent=None):
        super(HoverLabel, self).__init__(parent)
        self.__my_setEnter = setEnter
        self.__my_setLeave = setLeave
        # self.setAlignment(QtCore.Qt.AlignCenter)
    
    def resetHover(self):
        self.__my_setEnter = HoverLabel.__default_enter
        self.__my_setLeave = HoverLabel.__default_leave

    def setEnter(self, enter_func):
        self.__my_setEnter = enter_func
    
    def setLeave(self, leave_func):
        self.__my_setLeave = leave_func

    def enterEvent(self, event):
        self.__my_setEnter(self)

    def leaveEvent(self, event):
        self.__my_setLeave(self)

# 创建自定义窗口类
class CustomWindow(QtWidgets.QMainWindow):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance:
            cls._instance.close()
            del cls._instance
        cls._instance = super(CustomWindow, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, op_handler, unpack_location, parent=None):
        super(CustomWindow, self).__init__(parent)

        assert unpack_location in {"temp", "local"}
        self.unpack_location = unpack_location
        self.load_pixmaps()

        self.op_handler = op_handler

        # Pack state variables
        self.pack: Union(None, CAPack) = None
        self.selected_resolution: Union(None, CADefs.TextureResolution) = None
        self.selected_topology: Union(None, CADefs.Topology) = None
        self.selected_components: CADefs.AdditionalElements = CADefs.AdditionalElements.Nothing

        self.create_window()
        # Button signals
        self.buttonGroup_resolution.buttonClicked.connect(self.resolution_select)
        self.buttonGroup_topology.buttonClicked.connect(self.topology_select)
        self.pushButton_Import.clicked.connect(self.import_press)
        self.pushButton_back.clicked.connect(self.back_press)
        self.pushButton_Confirm.clicked.connect(self.confirm_press)
        self.set_button_enabled("RESET")

    def load_pixmaps(self):
        # Load All images as QIcon
        ## Fixed elements
        self.fixed_element_pixmaps = {
            key: QtGui.QPixmap(value)
            for key, value in UI_RESOURCES.FIXED_ELEMENTS_ABSOLUTE_PATHS.items()
        }
        ### Only buttons need icon
        self.fixed_element_icon = {}
        for i in ["Confirm", "Import", "Back"]:
            icon = self.fixed_element_icon[i] = QtGui.QIcon()
            icon.addPixmap(self.fixed_element_pixmaps[i])
        ## Select buttons
        self.selection_buttons_pixmaps = {
            key_1: {
                key_2: QtGui.QPixmap(value_2)
                for key_2, value_2 in value_1.items()
            } for key_1, value_1 in UI_RESOURCES.SELECTION_BUTTONS_ABSOLUTE_PATHS.items()
        }
        self.selection_buttons_icons = {}
        for i in self.selection_buttons_pixmaps:
            icon = self.selection_buttons_icons[i] = QtGui.QIcon()
            pixmaps = self.selection_buttons_pixmaps[i]
            icon.addPixmap(pixmaps["AVAILABLE"])
            icon.addPixmap(pixmaps["UNAVAILABLE"], QtGui.QIcon.Mode.Disabled)
            icon.addPixmap(pixmaps["SELECTED"], QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.On)

    def create_window(self):
        self.setWindowTitle("ChatAvatar Import Tool")
        # self.setGeometry(100, 100, 1179, 727)
        self.setFixedSize(1179, 727)

        self.set_background_image()

        self.logo_label = ClickableLabel(self)
        self.logo_label.setGeometry(40, 50, 612, 64)

        self.logopixmap = self.fixed_element_pixmaps["Title"]
        self.logo_label.setPixmap(self.logopixmap)
        self.logo_label.setScaledContents(True)
        self.logo_label.setToolTip("Click here to visit ChatAvater.")
        self.logo_label.setCursor(QtCore.Qt.PointingHandCursor)
        self.logo_label.clicked.connect(lambda: webbrowser.open_new("https://hyperhuman.top"))

        self.image_label = QtWidgets.QLabel(self)
        self.image_label.setGeometry(880, 200, 270, 360)

        self.text_label = HoverLabel(parent=self)
        self.text_label.setGeometry(880, 200, 270, 360)
        self.text_label.setFont(QtGui.QFont("SimHei", 12))
        self.text_label.setStyleSheet(
            "color: white; background: transparent; text-align: center;"
            "letter-spacing: -1px; "
            "border-radius: 25px;"
        )
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(QtCore.Qt.AlignCenter)


        #region Selection buttons
        self.pushButton_4K = QtWidgets.QPushButton(self)
        self.pushButton_4K.setCheckable(True)
        self.pushButton_4K.setGeometry(QtCore.QRect(650, 250, 180, 55))
        self.pushButton_4K.setIcon(self.selection_buttons_icons["FOURK"])
        self.pushButton_4K.setIconSize(QtCore.QSize(180, 55))
        self.pushButton_4K.setStyleSheet("background: transparent; border: none")

        self.pushButton_2K = QtWidgets.QPushButton(self)
        self.pushButton_2K.setCheckable(True)
        self.pushButton_2K.setGeometry(QtCore.QRect(470, 250, 180, 55))
        self.pushButton_2K.setIcon(self.selection_buttons_icons["TWOK"])
        self.pushButton_2K.setIconSize(QtCore.QSize(180, 55))
        self.pushButton_2K.setStyleSheet("background: transparent; border: none")

        self.pushButton_default = QtWidgets.QPushButton(self)
        self.pushButton_default.setCheckable(True)
        self.pushButton_default.setGeometry(QtCore.QRect(470, 400, 180, 55))
        self.pushButton_default.setIcon(self.selection_buttons_icons["DEFAULT"])
        self.pushButton_default.setIconSize(QtCore.QSize(180, 55))
        self.pushButton_default.setStyleSheet("background: transparent; border: none")

        self.pushButton_MH = QtWidgets.QPushButton(self)
        self.pushButton_MH.setCheckable(True)
        self.pushButton_MH.setGeometry(QtCore.QRect(650, 400, 180, 55))
        self.pushButton_MH.setIcon(self.selection_buttons_icons["METAHUMAN"])
        self.pushButton_MH.setIconSize(QtCore.QSize(180, 55))
        self.pushButton_MH.setStyleSheet("background: transparent; border: none")

        self.pushButton_Rigged = QtWidgets.QPushButton(self)
        self.pushButton_Rigged.setCheckable(True)
        self.pushButton_Rigged.setGeometry(QtCore.QRect(470, 540, 180, 55))
        self.pushButton_Rigged.setIcon(self.selection_buttons_icons["RIGGED"])
        self.pushButton_Rigged.setIconSize(QtCore.QSize(180, 55))
        self.pushButton_Rigged.setStyleSheet("background: transparent; border: none")

        self.pushButton_eye = QtWidgets.QPushButton(self)
        self.pushButton_eye.setCheckable(True)
        self.pushButton_eye.setGeometry(QtCore.QRect(650, 540, 180, 55))
        self.pushButton_eye.setIcon(self.selection_buttons_icons["EYE"])
        self.pushButton_eye.setIconSize(QtCore.QSize(180, 55))
        self.pushButton_eye.setStyleSheet("background: transparent; border: none")

        self.pushButton_BS = QtWidgets.QPushButton(self)
        self.pushButton_BS.setCheckable(True)
        self.pushButton_BS.setGeometry(QtCore.QRect(470, 610, 180, 55))
        self.pushButton_BS.setIcon(self.selection_buttons_icons["BLEND"])
        self.pushButton_BS.setIconSize(QtCore.QSize(180, 55))
        self.pushButton_BS.setStyleSheet("background: transparent; border: none")

        self.pushButton_BackTex = QtWidgets.QPushButton(self)
        self.pushButton_BackTex.setCheckable(True)
        self.pushButton_BackTex.setGeometry(QtCore.QRect(650, 610, 180, 55))
        self.pushButton_BackTex.setIcon(self.selection_buttons_icons["TEX"])
        self.pushButton_BackTex.setIconSize(QtCore.QSize(180, 55))
        self.pushButton_BackTex.setStyleSheet("background: transparent; border: none")
        #endregion

        #region Fixed button
        self.pushButton_Confirm = QtWidgets.QPushButton(self)
        self.pushButton_Confirm.setGeometry(QtCore.QRect(800, 610, 430, 55))
        self.pushButton_Confirm.setIcon(self.fixed_element_icon["Confirm"])
        self.pushButton_Confirm.setIconSize(QtCore.QSize(430, 55))
        self.pushButton_Confirm.setStyleSheet("background: transparent; border: none")

        self.pushButton_Import = QtWidgets.QPushButton(self)
        self.pushButton_Import.setGeometry(QtCore.QRect(60, 200, 223, 89))
        self.pushButton_Import.setIcon(self.fixed_element_icon["Import"])
        self.pushButton_Import.setIconSize(QtCore.QSize(223, 89))
        self.pushButton_Import.setStyleSheet("background: transparent; border: none")

        self.pushButton_back = QtWidgets.QPushButton(self)
        self.pushButton_back.setGeometry(QtCore.QRect(320, 230, 53, 20))
        self.pushButton_back.setIcon(self.fixed_element_icon["Back"])
        self.pushButton_back.setIconSize(QtCore.QSize(53, 20))
        self.pushButton_back.setStyleSheet("background: transparent; border: none")
        #endregion
        
        ## Selection group
        self.buttonGroup_resolution = QtWidgets.QButtonGroup()
        self.buttonGroup_resolution.setExclusive(True)
        self.buttonGroup_resolution.addButton(self.pushButton_2K)
        self.buttonGroup_resolution.addButton(self.pushButton_4K)

        self.buttonGroup_topology = QtWidgets.QButtonGroup()
        self.buttonGroup_topology.setExclusive(True)
        self.buttonGroup_topology.addButton(self.pushButton_default)
        self.buttonGroup_topology.addButton(self.pushButton_MH)

        self.buttonGroup_parts = QtWidgets.QButtonGroup()
        self.buttonGroup_parts.setExclusive(False)
        self.buttonGroup_parts.addButton(self.pushButton_Rigged)
        self.buttonGroup_parts.addButton(self.pushButton_eye)
        self.buttonGroup_parts.addButton(self.pushButton_BS)
        self.buttonGroup_parts.addButton(self.pushButton_BackTex)
    
    @staticmethod
    def deselect_button_group(button_group: QtWidgets.QButtonGroup):
        if button_group.exclusive():
            button_group.setExclusive(False)
            checked = button_group.checkedButton()
            if checked:
                checked.setChecked(False)
            button_group.setExclusive(True)
        else:
            for button in button_group.buttons():
                button.setChecked(False)

    def set_all_disabled(self):
        for button_group in [
            self.buttonGroup_resolution,
            self.buttonGroup_topology,
            self.buttonGroup_parts,
        ]:
            self.deselect_button_group(button_group)
            for button in button_group.buttons():
                button.setEnabled(False)
        return
    
    def set_resolution_enabled(self):
        self.pushButton_2K.setEnabled(
            any(pack.resolution == CADefs.TextureResolution.TwoK for pack in self.pack.available_packs)
        )
        self.pushButton_4K.setEnabled(
            any(pack.resolution == CADefs.TextureResolution.FourK for pack in self.pack.available_packs)
        )

    def set_topology_enabled(self):
        self.pushButton_default.setEnabled(any(
            pack.resolution == self.selected_resolution and pack.topology == CADefs.Topology.Default
            for pack in self.pack.available_packs
        ))
        self.pushButton_MH.setEnabled(any(
            pack.resolution == self.selected_resolution and pack.topology == CADefs.Topology.MetaHuman
            for pack in self.pack.available_packs
        ))
    
    def set_parts_enabled(self):
        if self.selected_topology == CADefs.Topology.Default:
            if self.pack.additional_elements & CADefs.AdditionalElements.BackHeadTex:
                self.pushButton_BackTex.setEnabled(True)
            if self.pack.additional_elements & CADefs.AdditionalElements.BlendShapes:
                self.pushButton_BS.setEnabled(True)
            if self.pack.additional_elements & CADefs.AdditionalElements.Components:
                self.pushButton_eye.setEnabled(True)
            if self.pack.additional_elements & CADefs.AdditionalElements.RiggedBody:
                self.pushButton_Rigged.setEnabled(True)
        else:
            self.deselect_button_group(self.buttonGroup_parts)
            for button in self.buttonGroup_parts.buttons():
                button.setEnabled(False)

    def set_button_enabled(self, trigger_event: str):
        """Determine all buttons' enabled state."""
        assert trigger_event in {"RESET", "IMPORT", "SELECT_RES", "SELECT_TOP"}
        if trigger_event == "RESET":
            self.deselect_button_group(self.buttonGroup_resolution)
            self.deselect_button_group(self.buttonGroup_topology)
            self.deselect_button_group(self.buttonGroup_parts)
            self.set_all_disabled()
            self.pushButton_Confirm.setEnabled(False)
            return
        if trigger_event == "IMPORT":
            self.set_button_enabled("RESET")
            self.set_resolution_enabled()
            self.pushButton_Confirm.setEnabled(False)
            return
        if trigger_event == "SELECT_RES":
            self.set_topology_enabled()
            if not self.selected_topology:
                self.deselect_button_group(self.buttonGroup_topology)
                self.deselect_button_group(self.buttonGroup_parts)
                self.set_parts_enabled()
                self.pushButton_Confirm.setEnabled(False)
            return
        if trigger_event == "SELECT_TOP":
            self.set_parts_enabled()
            self.pushButton_Confirm.setEnabled(True)
                
    def set_resolution(self, target: "type(None) | CADefs.TextureResolution"):
        self.selected_resolution = target
        if CADefs.PackInfo(self.selected_resolution, self.selected_topology) not in self.pack.available_packs:
            self.set_topology(None)

    def set_topology(self, target: "type(None) | CADefs.Topology"):
        self.selected_topology = target
        if self.selected_topology != CADefs.Topology.Default:
            self.selected_components = CADefs.AdditionalElements.Nothing

    def resolution_select(self, button):
        if button is self.pushButton_2K and self.selected_resolution != CADefs.TextureResolution.TwoK:
            self.set_resolution(CADefs.TextureResolution.TwoK)
            self.set_button_enabled("SELECT_RES")
        elif button is self.pushButton_4K and self.selected_resolution != CADefs.TextureResolution.FourK:
            self.set_resolution(CADefs.TextureResolution.FourK)
            self.set_button_enabled("SELECT_RES")
        else:
            self.set_resolution(None)
            self.set_button_enabled("IMPORT")
        

    def topology_select(self, button):
        if button is self.pushButton_default and self.selected_topology != CADefs.Topology.Default:
            self.set_topology(CADefs.Topology.Default)
            self.set_button_enabled("SELECT_TOP")
        elif button is self.pushButton_MH and self.selected_topology != CADefs.Topology.MetaHuman:
            self.set_topology(CADefs.Topology.MetaHuman)
            self.set_button_enabled("SELECT_TOP")
        else:
            self.set_topology(None)
            self.set_button_enabled("SELECT_RES")

    def set_background_image(self):
        bglabel = QtWidgets.QLabel(self)
        bg_pixmap = self.fixed_element_pixmaps["Background"]
        bglabel.setPixmap(bg_pixmap)
        bglabel.setGeometry(0, 0, self.width(), self.height())
        bglabel.setScaledContents(True)
        bglabel.show()

    def rounded_pixmap(self, pixmap, radius):
        mask = QtGui.QPixmap(pixmap.size())
        mask.fill(QtGui.QColor("transparent"))
        painter = QtGui.QPainter(mask)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QBrush(QtGui.QColor("black")))
        painter.drawRoundedRect(mask.rect(), radius, radius)
        painter.end()

        rounded_pixmap = QtGui.QPixmap(pixmap.size())
        rounded_pixmap.fill(QtGui.QColor("transparent"))
        painter = QtGui.QPainter(rounded_pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
        painter.drawPixmap(rounded_pixmap.rect(), pixmap)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_DestinationIn)
        painter.drawPixmap(rounded_pixmap.rect(), mask)
        painter.end()

        return rounded_pixmap

    def import_press(self):
        zip_file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose Package", "", "Zip Files (*.zip)")
        if not zip_file_path:
            return
        try:
            self.pack = CAPack(os.path.join(zip_file_path), self.unpack_location)
        except CADefs.InvalidPack:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("ChatAvatar Import Tool")
            msg_box.setText(
                "Wrong pack imported! Consider visiting <a href='https://hyperhuman.top'>ChatAvatar</a> to generate a ChatAvatar Package."
            )
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()
            return

        round_radius = 25 # px in original image
        self.view_image_path = self.pack.preview_image_path
        self.viewpixmap = QtGui.QPixmap(self.view_image_path)
        rounded_pixmap = self.rounded_pixmap(self.viewpixmap, round_radius)
        self.image_label.setPixmap(rounded_pixmap)
        self.image_label.setScaledContents(True)

        if self.pack.prompt_txt:
            border_radius_str = "border-radius: {:0.05f}px;".format(round_radius / self.viewpixmap.size().width() * self.image_label.size().width())
            def enter_event(_self):
                _self.setText(self.pack.prompt_txt)
                _self.setStyleSheet(
                    "color: white; text-align: center;" # White text, center alignment
                    + "letter-spacing: -1px;"
                    + "background: rgba(127, 127, 127, 127);"
                    + border_radius_str                 # border radius
                )
            def leave_event(_self):
                _self.clear()
                _self.setStyleSheet(f"background: transparent;")

            self.text_label.setEnter(enter_event)
            self.text_label.setLeave(leave_event)
        self.set_button_enabled("IMPORT")

    def back_press(self):
        self.pack = None
        self.selected_resolution = None
        self.selected_topology = None
        self.selected_components = CADefs.AdditionalElements.Nothing
        self.image_label.clear()
        self.text_label.clear()
        self.text_label.resetHover()
        self.set_button_enabled("RESET")

    def confirm_press(self):
        selected_pack = CADefs.PackInfo(self.selected_resolution, self.selected_topology)

        selected_additional = \
            (CADefs.AdditionalElements.RiggedBody  if self.pushButton_Rigged.isChecked()  else CADefs.AdditionalElements.Nothing) | \
            (CADefs.AdditionalElements.Components  if self.pushButton_eye.isChecked()     else CADefs.AdditionalElements.Nothing) | \
            (CADefs.AdditionalElements.BlendShapes if self.pushButton_BS.isChecked()      else CADefs.AdditionalElements.Nothing) | \
            (CADefs.AdditionalElements.BackHeadTex if self.pushButton_BackTex.isChecked() else CADefs.AdditionalElements.Nothing)
        basic_paths = self.pack.pack_file_paths(selected_pack)
        if self.selected_topology == CADefs.Topology.MetaHuman:
            additional_paths = {}
            model_path = basic_paths["model"]
            obj_name = "head_lod0_mesh"
        elif self.selected_topology == CADefs.Topology.Default:
            additional_paths = self.pack.additional_elements_paths()
            if CADefs.AdditionalElements.RiggedBody & selected_additional:
                model_path = additional_paths[CADefs.AdditionalElements.RiggedBody]
                obj_name = "template_fullbody"
            
            elif CADefs.AdditionalElements.Components & selected_additional:
                model_path = additional_paths[CADefs.AdditionalElements.Components]
                if CADefs.AdditionalElements.BlendShapes & self.pack.additional_elements:
                    obj_name = "tmppu_8s3mi"
                else:
                    obj_name = "Mesh"
            
            elif CADefs.AdditionalElements.BlendShapes & selected_additional:
                model_path = additional_paths[CADefs.AdditionalElements.BlendShapes]
                obj_name = "input_model"

            else:
                model_path = basic_paths["model"]
                obj_name = "Mesh"

        texture_paths = {
            key: basic_paths[key] for key in ["texture_diffuse", "texture_specular", "texture_normal"]
        }

        self.op_handler.pre_import(
            self,
            model_path,
            obj_name,
            texture_paths,
            selected_pack,
            selected_additional,
            self.pack.additional_elements,
            self.pack.pack_name,
            additional_paths,
        )

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.op_handler.import_pack(
            model_path,
            obj_name,
            texture_paths,
            selected_pack,
            selected_additional,
            self.pack.additional_elements,
            self.pack.pack_name,
            additional_paths
        )
        QtWidgets.QApplication.restoreOverrideCursor()
        
        self.op_handler.post_import(
            self,
            model_path,
            obj_name,
            texture_paths,
            selected_pack,
            selected_additional,
            self.pack.additional_elements,
            self.pack.pack_name,
            additional_paths,
        )