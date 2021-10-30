from PyQt5.QtWidgets import QHBoxLayout, QPushButton
import numpy as np
from qtpy.QtWidgets import QLineEdit, QWidget, QGridLayout, QLabel, QSpinBox
from qtpy import QtGui, QtCore
import napari
from napari._qt.widgets.qt_color_swatch import QColorSwatchEdit
from napari_plugin_engine import napari_hook_implementation

from napari.layers import Shapes

_TEXT_SYMBOL = "t"
_INITIAL_TEXT_COLOR = "white"
_INITIAL_FONT_SIZE = 6
_MIN_FONT_SIZE = 2
_MAX_FONT_SIZE = 48
_MIN_SHAPE_X_SIZE = 16
_MIN_SHAPE_Y_SIZE = 16

class TextLayerOverview(QWidget):
    def __init__(self, viewer: napari.viewer.Viewer):
        super().__init__()
        self.viewer = viewer
        self._add_text_layer()
        self.setLayout(QGridLayout())
        self.layout().setAlignment(QtCore.Qt.AlignTop)
        
        # set color edit
        
        color_edit = QColorSwatchEdit(self, 
                                      initial_color=_INITIAL_TEXT_COLOR, 
                                      tooltip="Select text color")
        
        @color_edit.color_changed.connect
        def _(color: np.ndarray):
            self.layer.text.color = color
        self.layout().addWidget(color_edit)
        
        # set a spin box for font size
        
        frame = QWidget(self)
        frame.setLayout(QHBoxLayout())
        frame.layout().setContentsMargins(0, 0, 0, 0)
        
        self._font_size_spinbox = QSpinBox(frame)
        self._font_size_spinbox.setRange(_MIN_FONT_SIZE, _MAX_FONT_SIZE)
        self._font_size_spinbox.setValue(_INITIAL_FONT_SIZE)
        
        @self._font_size_spinbox.valueChanged.connect
        def _(e):
            size = self._font_size_spinbox.value()
            self.layer.text.size = size
        
        frame.layout().addWidget(QLabel("font size", frame))
        frame.layout().addWidget(self._font_size_spinbox)
        self.layout().addWidget(frame)
        
        # set a spin box for rotation
        
        frame = QWidget(self)
        frame.setLayout(QHBoxLayout())
        frame.layout().setContentsMargins(0, 0, 0, 0)
        
        self._rot_spin_box = QSpinBox(frame)
        self._rot_spin_box.setRange(-180, 180)
        self._rot_spin_box.setValue(0)
        self._rot_spin_box.setSingleStep(5)
        
        @self._rot_spin_box.valueChanged.connect
        def _(e):
            deg = self._rot_spin_box.value()
            self.layer.text.rotation = deg
        
        frame.layout().addWidget(QLabel("text rotation", frame))
        frame.layout().addWidget(self._rot_spin_box)
        self.layout().addWidget(frame)
        
        # set buttons for anchor position, and add it to color edit layout
        
        frame = QWidget(self)
        frame.setLayout(QGridLayout())
        frame.layout().setContentsMargins(0, 0, 0, 0)
        frame.setFixedWidth(frame.height()*2)
        self._button_ul = QPushButton("◤", frame)
        self._button_ur = QPushButton("◥", frame)
        self._button_ll = QPushButton("◣", frame)
        self._button_lr = QPushButton("◢", frame)
        self._button_ct = QPushButton("●", frame)
        
        frame.layout().addWidget(self._button_ul, 0, 0, 2, 2)
        frame.layout().addWidget(self._button_ur, 0, 2, 2, 2)
        frame.layout().addWidget(self._button_ll, 2, 0, 2, 2)
        frame.layout().addWidget(self._button_lr, 2, 2, 2, 2)
        frame.layout().addWidget(self._button_ct, 1, 1, 2, 2)
        
        @self._button_ul.clicked.connect
        def _(e):
            self.layer.text.anchor = "upper_left"
            
        @self._button_ur.clicked.connect
        def _(e):
            self.layer.text.anchor = "upper_right"
            
        @self._button_ll.clicked.connect
        def _(e):
            self.layer.text.anchor = "lower_left"
            
        @self._button_lr.clicked.connect
        def _(e):
            self.layer.text.anchor = "lower_right"
            
        @self._button_ct.clicked.connect
        def _(e):
            self.layer.text.anchor = "center"
        
        frame.setToolTip("Text anchor")
        color_edit.layout().addWidget(frame)
        
    def _add_text_layer(self):
        # Add a new text layer and bind shortcuts.
        layer = Shapes(ndim=2,
                       shape_type="rectangle",
                       name="Text Layer",
                       properties={_TEXT_SYMBOL: np.array([""], dtype="<U32")},
                       blending = "additive",
                       opacity=1,
                       text={"text": "{" + _TEXT_SYMBOL + "}", 
                             "size": _INITIAL_FONT_SIZE,
                             "color": _INITIAL_TEXT_COLOR,
                             "anchor": "center"}
                       )
        layer.mode = "add_rectangle"
        self.layer = layer
        
        @layer.bind_key("F2", overwrite=True)
        def edit_selected(layer: Shapes):
            selected = list(layer.selected_data)
            if layer.nshapes == 0:
                return
            elif len(selected) == 0:
                i = -1
            else:
                i = selected[-1]
            data = layer.data[i]
            center = np.mean(data, axis=0)
            screen_coords = _get_data_coords_in_screen(center, self.viewer)
            self._enter_editing_mode(i, screen_coords)
            
        @layer.bind_key("Enter", overwrite=True)
        def add(layer: Shapes):
            # Add a new shape when Enter is clicked.
            
            # If no shape exists, add a rectangle at (0, 0)
            if layer.nshapes == 0:
                next_data = np.array([[0, 0],
                                      [0, _MIN_SHAPE_X_SIZE],
                                      [_MIN_SHAPE_Y_SIZE, _MIN_SHAPE_X_SIZE],
                                      [_MIN_SHAPE_Y_SIZE, 0]])
                layer.add_rectangles(next_data)
            
            # If one shape exists, add the last shape at almost the same position.
            elif layer.nshapes == 1:
                next_data = layer.data[-1].copy()
                next_data[:, -2] += _MIN_SHAPE_Y_SIZE
                next_data[:, -1] += _MIN_SHAPE_X_SIZE
                layer.add(next_data, shape_type=layer.shape_type[-1])
            
            # If more, add the last shape in the same direction.
            else:
                # TODO: sometimes new_data will be outside the canvas
                dr = np.mean(layer.data[-1], axis=0) - np.mean(layer.data[-2], axis=0)
                next_data = layer.data[-1] + dr
                layer.add(next_data, shape_type=layer.shape_type[-1])
                
            center = np.mean(next_data, axis=0)
            screen_coords = _get_data_coords_in_screen(center, self.viewer)
            self._enter_editing_mode(-1, screen_coords)
                
        @layer.bind_key("Left", overwrite=True)
        def left(layer: Shapes):
            _translate_shape(layer, -1, -1)
            
        @layer.bind_key("Right", overwrite=True)
        def right(layer: Shapes):
            _translate_shape(layer, -1, 1)
            
        @layer.bind_key("Up", overwrite=True)
        def up(layer: Shapes):
            _translate_shape(layer, -2, -1)
            
        @layer.bind_key("Down", overwrite=True)
        def down(layer: Shapes):
            _translate_shape(layer, -2, 1)
        
        @layer.bind_key("Control-Shift-<", overwrite=True)
        def size_down(layer: Shapes):
            layer.text.size = max(_MIN_FONT_SIZE, layer.text.size - 1)
        
        @layer.bind_key("Control-Shift->", overwrite=True)
        def size_up(layer: Shapes):
            layer.text.size = min(_MAX_FONT_SIZE, layer.text.size + 1)
        
        @layer.mouse_double_click_callbacks.append
        def edit(layer: Shapes, event):
            # Enter editing mode with out switching to the selection mode of shapes layer.
            if layer.nshapes > 1 and layer.mode in ("add_rectangle", "add_ellipse", "add_line"):
                # These shapes does not need double click to finish editing.
                layer.data = layer.data[:-1]
                
            i, _ = layer.get_value(
                event.position,
                view_direction=event.view_direction,
                dims_displayed=event.dims_displayed,
                world=True
            )

            if i is None:
                return None
            self._enter_editing_mode(i)
        
        @layer.mouse_drag_callbacks.append
        def _(layer: Shapes, e):
            if layer.mode not in ("add_rectangle", "add_ellipse", "add_line"):
                return
            x0, y0 = _get_mouse_coords_in_screen(self.viewer)
            yield
            while e.type == "mouse_move":
                # Nothing happens while dragging
                yield
            x1, y1 = _get_mouse_coords_in_screen(self.viewer)
            
            # Enlarge shape if it is too small
            data = layer.data
            dx = abs(x1 - x0)
            if dx <= _MIN_SHAPE_X_SIZE:
                center = np.mean(layer.data[-1][:, -1])
                xsmall = center - _MIN_SHAPE_X_SIZE/2
                xlarge = center + _MIN_SHAPE_X_SIZE/2
                data[-1][:, -1] = [xsmall, xlarge, xlarge, xsmall]
            
            dy = abs(y1 - y0)
            if dy <= _MIN_SHAPE_Y_SIZE:
                center = np.mean(layer.data[-1][:, -2])
                ysmall = center - _MIN_SHAPE_Y_SIZE/2
                ylarge = center + _MIN_SHAPE_Y_SIZE/2
                data[-1][:, -2] = [ysmall, ysmall, ylarge, ylarge]
            
            layer.data = data
                        
            # Enter editing mode when clicked
            self._enter_editing_mode(-1, ((x0+x1)/2, (y0+y1)/2))
                
        self.viewer.add_layer(layer)
        return None

    def _enter_editing_mode(self, i: int, position: tuple[int, int] = None):
        # Create a line edit at the position of shape and enter text editing mode.
        self.layer.current_properties = {_TEXT_SYMBOL: np.array([""], dtype="<U32")}
        if position is not None:
            x, y = position
        else:
            x, y = _get_mouse_coords_in_screen(self.viewer)
        
        # Create a line edit widget and set geometry
        line = QLineEdit(self.viewer.window._qt_window)
        edit_geometry = line.geometry()
        edit_geometry.setWidth(140)
        edit_geometry.moveLeft(x)
        edit_geometry.moveTop(y)
        line.setGeometry(edit_geometry)
        f = line.font()
        f.setPointSize(20)
        line.setFont(f)
        line.setText(self.layer.text.values[i])
        line.setHidden(False)
        line.setFocus()
        line.selectAll()
        
        @line.textChanged.connect
        def _():
            old = self.layer.properties.get(_TEXT_SYMBOL, [""]*len(self.layer.data))
            old[i] = line.text().strip()
            self.layer.text.refresh_text({_TEXT_SYMBOL: old})
        
        @line.editingFinished.connect
        def _():
            line.setHidden(True)
            line.deleteLater()
        
        return None
    
def _get_mouse_coords_in_screen(viewer: "napari.Viewer"):
    window_geo = viewer.window._qt_window.geometry()
    pos = QtGui.QCursor().pos()
    x = pos.x() - window_geo.x()
    y = pos.y() - window_geo.y()
    return x, y
    

def _translate_shape(layer: Shapes, ind: int, direction: int):
    data = layer.data
    selected = layer.selected_data
    for i in selected:
        data[i][:, ind] += direction
    layer.data = data
    layer.selected_data = selected
    layer._set_highlight()
    return None

def _get_data_coords_in_screen(coords, viewer: "napari.Viewer"):
    dr = viewer.window._qt_window.centralWidget().geometry()
    w = dr.width()
    h = dr.height()
    canvas_center = np.array([dr.y(), dr.x()]) + np.array([h, w])/2
    crds = canvas_center + (coords - viewer.camera.center[-2:])* viewer.camera.zoom
    return crds.astype(int)[::-1]

@napari_hook_implementation
def napari_experimental_provide_dock_widget():
    widget_options = {
        "name": "napari-text-layer",
        "area": "left",
    }
    return TextLayerOverview, widget_options