from __future__ import annotations
from PyQt5.QtWidgets import QHBoxLayout
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
    def __init__(self, viewer: "napari.Viewer"):
        super().__init__()
        self.viewer = viewer
        self._add_text_layer()
        self.setLayout(QGridLayout())
        self.layout().setAlignment(QtCore.Qt.AlignTop)
        
        # set color edit
        self._color_edit = QColorSwatchEdit(self, 
                                            initial_color=_INITIAL_TEXT_COLOR, 
                                            tooltip="Select text color")
        
        @self._color_edit.color_changed.connect
        def _(color: np.ndarray):
            self.layer.text.color = color
        self.layout().addWidget(self._color_edit)
        
        # set spin box
        self._spinbox = QSpinBox(self)
        self._spinbox.setRange(_MIN_FONT_SIZE, _MAX_FONT_SIZE)
        self._spinbox.setValue(_INITIAL_FONT_SIZE)
        
        @self._spinbox.valueChanged.connect
        def _(e):
            size = self._spinbox.value()
            self.layer.text.size = size
        
        frame = QWidget(self)
        frame.setLayout(QHBoxLayout())
        frame.layout().addWidget(QLabel("font size", frame))
        frame.layout().addWidget(self._spinbox)
        self.layout().addWidget(frame)
        
    def _add_text_layer(self):
        layer = Shapes(ndim=2,
                       shape_type="rectangle",
                       name="Text Layer",
                       properties={_TEXT_SYMBOL: np.array([""], dtype="<U32")},
                       blending = "additive",
                       edge_width=2.0,
                       face_color=[0, 0, 0, 0],
                       edge_color=[0, 0, 0, 0],
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
            screen_coords = _world_to_screen_coords(center, self.viewer)
            self._enter_editing_mode(i, screen_coords)
            
        @layer.bind_key("Alt-A", overwrite=True)
        def select_all(layer: Shapes):
            layer.selected_data = set(np.arange(layer.nshapes))
            layer._set_highlight()
        
        @layer.bind_key("Enter", overwrite=True)
        def add(layer: Shapes):
            if layer.nshapes == 0:
                next_data = np.array([[0, 0],
                                      [0, _MIN_SHAPE_X_SIZE],
                                      [_MIN_SHAPE_Y_SIZE, _MIN_SHAPE_X_SIZE],
                                      [_MIN_SHAPE_Y_SIZE, 0]])
            elif layer.nshapes == 1:
                next_data = layer.data[-1].copy()
                next_data[:, -2] += _MIN_SHAPE_Y_SIZE
                next_data[:, -1] += _MIN_SHAPE_X_SIZE
            else:
                next_data = 2 * layer.data[-1] - layer.data[-2]
                
            layer.add_rectangles(next_data)
            center = np.mean(next_data, axis=0)
            screen_coords = _world_to_screen_coords(center, self.viewer)
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
            if layer.mode.startswith("add_"):
                layer.data = layer.data[:-1]
            self.layer.current_properties = {_TEXT_SYMBOL: np.array([""], dtype="<U32")}
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
            if layer.mode not in ("add_rectangle", "add_ellipse"):
                return
            x0, y0 = _get_xy(self.viewer)
            yield
            while e.type == "mouse_move":
                # Nothing happens while dragging
                yield
            x1, y1 = _get_xy(self.viewer)
            
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
        
        if position is not None:
            x, y = position
        else:
            x, y = _get_xy(self.viewer)
        
        # Create a line edit widget and set geometry
        line = QLineEdit(self.viewer.window._qt_window)
        self.line = line
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
            self.line = None
            line.deleteLater()
        
        return None
    
def _get_xy(viewer: "napari.Viewer"):
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

def _world_to_screen_coords(coords, viewer: "napari.Viewer"):
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