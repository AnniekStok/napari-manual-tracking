
import os
import trackpy
import napari

import pandas   as pd
import numpy    as np

from typing                 import List, Tuple
from tifffile               import imwrite
from skimage.io             import imread

from superqt                import QLabeledRangeSlider, QLabeledDoubleRangeSlider
from qtpy.QtWidgets         import QTabWidget, QMessageBox, QDoubleSpinBox, QComboBox, QGroupBox, QLabel, QHBoxLayout, QVBoxLayout, QPushButton, QWidget, QFileDialog, QLineEdit, QSpinBox
from qtpy                   import QtCore
from napari.qt              import QtToolTipLabel

class CustomRangeSliderWidget(QWidget):
    """implements superqt RangeSlider widget to select a range of values based on a table"""

    def __init__(self, df, property, dtype, tip):
        super().__init__()

        slider_layout = QVBoxLayout()
        if dtype == "float":
            self.range_slider = QLabeledDoubleRangeSlider(QtCore.Qt.Horizontal)
            self.min = round(df[property].min(), 2)
            self.max = round(df[property].max(), 2)
            self.span = self.max - self.min
            stepsize = round(self.span / 100, 2)
            self.range_slider.setRange(self.min, self.max)

        else:
            self.range_slider = QLabeledRangeSlider(QtCore.Qt.Horizontal)
            self.min = int(df[property].min())
            self.max = int(df[property].max())
            self.span = self.max - self.min
            stepsize = int(self.span / 100)
            self.range_slider.setRange(self.min, self.max)
       
        self.range_slider.setSingleStep(stepsize)
        self.range_slider.setTickInterval(stepsize)
        self.range_slider.setValue((self.min, self.max))
        self.label = QtToolTipLabel(property)
        self.label.setToolTip(tip)
        self.label.setToolTipDuration(500)
        slider_layout.addWidget(self.label)
        slider_layout.addWidget(self.range_slider)

        self.setLayout(slider_layout)

class TrackpyDetector(QWidget):
    """Widget for running detection with trackpy on a directory containing intensity images
    
    """
    
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer
        self.viewer.layers.clear() # ensure the viewer is clean
        self.inputdir = ""
        self.outputdir = ""

        self.intensity_layer = None
        self.points = None
        self.sliders_widget = None

        # Add input and output directory. 
        settings_layout = QVBoxLayout()

        databox = QGroupBox('Data directories')
        databox_layout = QVBoxLayout()

        input_layout = QHBoxLayout()
        self.inputdirbtn = QPushButton('Select intensity directory')
        self.inputdirbtn.clicked.connect(self._on_get_label_dir)
        self.input_path = QLineEdit()
        self.input_path.textChanged.connect(self._update_inputdir)
        input_layout.addWidget(self.inputdirbtn)
        input_layout.addWidget(self.input_path)

        output_layout = QHBoxLayout()
        self.outputdirbtn = QPushButton('Select output directory')
        self.outputdirbtn.clicked.connect(self._on_get_output_dir)
        self.output_path = QLineEdit()
        self.output_path.textChanged.connect(self._update_outputdir)
        output_layout.addWidget(self.outputdirbtn)
        output_layout.addWidget(self.output_path)

        databox_layout.addLayout(input_layout)
        databox_layout.addLayout(output_layout)
        
        settings_layout.addWidget(databox)
        databox.setLayout(databox_layout)

        # Add trackpy detection configuration. 
        trackpy_settings = QGroupBox("Trackpy detection configuration")
        trackpy_settings_layout = QVBoxLayout()

        self.diameter_spinbox_x = QDoubleSpinBox()
        self.diameter_spinbox_x.setMaximum(500)
        self.diameter_spinbox_x.setValue(9)
        self.diameter_spinbox_y = QDoubleSpinBox()
        self.diameter_spinbox_y.setMaximum(500)
        self.diameter_spinbox_y.setValue(9)
        self.diameter_spinbox_z = QDoubleSpinBox()
        self.diameter_spinbox_z.setMaximum(500)      
        self.diameter_spinbox_z.setValue(9)

        self.min_mass_spinbox = QSpinBox()
        self.min_mass_spinbox.setMaximum(10000)

        self.separation_spinbox_x = QDoubleSpinBox()
        self.separation_spinbox_x.setMaximum(500)
        self.separation_spinbox_x.setValue(10)
        self.separation_spinbox_y = QDoubleSpinBox()
        self.separation_spinbox_y.setMaximum(500)
        self.separation_spinbox_y.setValue(10)
        self.separation_spinbox_z = QDoubleSpinBox()
        self.separation_spinbox_z.setMaximum(500)      
        self.separation_spinbox_z.setValue(10)

        self.detect_trackpy_btn = QPushButton('Detect objects')
        self.detect_trackpy_btn.clicked.connect(self._run)
        self.detect_trackpy_btn.setEnabled(False)
        
        trackpy_settings_layout.addWidget(QLabel('Diameter x'))
        trackpy_settings_layout.addWidget(self.diameter_spinbox_x)
        trackpy_settings_layout.addWidget(QLabel('Diameter y'))
        trackpy_settings_layout.addWidget(self.diameter_spinbox_y)
        trackpy_settings_layout.addWidget(QLabel('Diameter z'))
        trackpy_settings_layout.addWidget(self.diameter_spinbox_z)
        
        trackpy_settings_layout.addWidget(QLabel('Separation x'))
        trackpy_settings_layout.addWidget(self.separation_spinbox_x)
        trackpy_settings_layout.addWidget(QLabel('Separation y'))
        trackpy_settings_layout.addWidget(self.separation_spinbox_y)
        trackpy_settings_layout.addWidget(QLabel('Separation z'))
        trackpy_settings_layout.addWidget(self.separation_spinbox_z)
        trackpy_settings_layout.addWidget(self.detect_trackpy_btn)

        trackpy_settings.setLayout(trackpy_settings_layout)
        settings_layout.addWidget(trackpy_settings)
        settings_widget = QWidget()
        settings_widget.setLayout(settings_layout)
        settings_widget.setMaximumHeight(600)

        # Create a tab widget 
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(settings_widget, "Trackpy Configuration")

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)
          
    def _update_inputdir(self) -> None:
        """Update the input directory when the user modifies the text in the QLineEdit widget"""
        
        self.inputdir = str(self.input_path.text())
        if len(self.inputdir) > 0 and os.path.exists(self.inputdir) and len(self.outputdir) > 0 and os.path.exists(self.outputdir):
            self.detect_trackpy_btn.setEnabled(True)
    
    def _update_outputdir(self) -> None:
        """Update the output directory when the user modifies the text in the QLineEdit widget"""
        
        self.outputdir = str(self.output_path.text())
        if len(self.inputdir) > 0 and os.path.exists(self.inputdir) and len(self.outputdir) > 0 and os.path.exists(self.outputdir):
                self.detect_trackpy_btn.setEnabled(True)

    def _on_get_label_dir(self) -> None:
        """Open a dialog to choose a label directory"""

        path = QFileDialog.getExistingDirectory(self, 'Select folder with segmentation data to track')
        if path:
            self.input_path.setText(path)      
            self.inputdir = str(self.input_path.text())            
            if len(self.inputdir) > 0 and os.path.exists(self.inputdir) and len(self.outputdir) > 0 and os.path.exists(self.outputdir):
                self.detect_trackpy_btn.setEnabled(True)
    
    def _on_get_output_dir(self) -> None:
        """Open a dialog to choose a label directory"""

        path = QFileDialog.getExistingDirectory(self, 'Select output folder')
        if path:
            self.output_path.setText(path)
            self.outputdir = str(self.output_path.text())
            if len(self.inputdir) > 0 and os.path.exists(self.inputdir) and len(self.outputdir) > 0 and os.path.exists(self.outputdir):
                self.detect_trackpy_btn.setEnabled(True)
     
    def create_label_image(self, df:pd.DataFrame, output_shape:Tuple[int]) -> np.ndarray:
        """Create a label image of given shape based on the point detections in the given dataframe df"""

        label_image = np.zeros(output_shape, dtype=np.uint16)

        for _, row in df.iterrows():
            time_point = int(row['time_point'])
            z = int(row['z'])
            y = int(row['y'])
            x = int(row['x'])

            label_image[time_point, z-1:z+1, y-1:y+1, x-1:x+1] = row['label']

        return label_image
    
    def _detect_trackpy(self, files: List[str]) -> Tuple[napari.layers.Image, pd.DataFrame]:
        """Load the image data, and run trackpy.locate to detect objects"""

        dfs = []
        imgs = []
        for i, f in enumerate(files):
            img = imread(os.path.join(self.inputdir, f))
            diameter = (self.diameter_spinbox_z.value(), self.diameter_spinbox_y.value(), self.diameter_spinbox_x.value())
            separation = (self.separation_spinbox_z.value(), self.separation_spinbox_y.value(), self.separation_spinbox_x.value())

            d = trackpy.locate(img, diameter=diameter, separation=separation)
            d['time_point'] = i            
            dfs.append(d)
            imgs.append(img)
        
        object_df = pd.concat(dfs)
        object_df['label'] = object_df.index + 2 # We need labels with a value >1 (0 is reserved for background and 1 will be reserved for non-tracked objects in later steps)
        self.filtered_df = object_df.copy()

        intensity_layer = self.viewer.add_image(np.stack(imgs, axis=0), name=os.path.basename(self.inputdir))
        return intensity_layer, object_df

    def _create_point_layer(self, df:pd.DataFrame) -> napari.layers.Points:
        """Create a point layer from pandas dataframe"""
        
        coordinates_df = df[['time_point', 'z', 'y', 'x']]
        coordinates_array = coordinates_df.to_numpy()
        coordinates = coordinates_array.reshape(-1, 4)
        self.viewer.dims.ndisplay = 3

        return self.viewer.add_points(coordinates, name="Detected objects", face_color="red", opacity=0.5)

    def _filter_objects(self, df:pd.DataFrame):
        """Filter the data in the points layer based on the slider settings"""

        masks = []
        for slider in self.sliders:
            # Create a mask for for each of the slider settings.
            property = slider.label.text()
            value = slider.range_slider._slider.value()
            mask = (df[property] >= value[0]) & (df[property] <= value[1])
            masks.append(mask)
        
        # Combine all masks.
        combined_mask = pd.Series(True, index=df.index)
        for mask in masks:
            combined_mask &= mask

        # Select the rows that satisfy all the criteria.
        self.filtered_df = df[combined_mask]

        # Update the points.
        coordinates_df = self.filtered_df[['time_point', 'z', 'y', 'x']]
        coordinates_array = coordinates_df.to_numpy()
        coordinates = coordinates_array.reshape(-1, 4)

        self.points.data = coordinates

    def _enlarge_slider_label(self, slider_widget) -> None:
        """Not so pretty fix to overwrite label sizes that somehow are too small in napari with the default qtrangeslider settings"""
       
        for slider_label in slider_widget.range_slider._handle_labels:
                slider_label.setFixedSize(QtCore.QSize(80, 21))

    def _create_label_image(self, df: pd.DataFrame, output_shape:Tuple[int, int, int]) -> np.ndarray:
        """Create a label image based on a given shape and a dataframe listing the objects"""

        label_image = np.zeros(output_shape, dtype=np.uint16)

        for _, row in df.iterrows():
            time_point = int(row['time_point'])
            z = int(row['z'])
            y = int(row['y'])
            x = int(row['x'])

            label_image[time_point, z-1:z+1, y-1:y+1, x-1:x+1] = row['label']

        return label_image

    def _save_results(self) -> None:
        """Save the object dataframe based on the currently selected points, and convert points to labels image"""

        self.filtered_df.to_csv(os.path.join(self.outputdir, 'DetectedObjects.csv'), index = False)

        label_image = self._create_label_image(self.filtered_df, self.intensity_layer.data.shape)
        for i in range(label_image.shape[0]):
            l = label_image[i]
            imwrite(os.path.join(self.outputdir, (os.path.basename(self.outputdir) + "_labels_TP" + str(i).zfill(4) + '.tif')), np.array(l, dtype = 'uint16'))

    def _add_sliders_widget(self, df:pd.DataFrame) -> None:
        """Add a new tab with slider widgets for the properties 'mass', 'signal', and 'size' to filter the detected objects"""

        if self.sliders_widget is not None: 
            self.tab_widget.removeTab(1)

        self.sliders_widget = QWidget()
        sliders_layout = QVBoxLayout()
        filter_properties = [
            {'name': 'mass', 'type': 'int', 'tip': 'Total brightness'}, 
            {'name': 'signal', 'type': 'int', 'tip': 'Indicator of signal contrast'}, 
            {'name': 'size', 'type': 'float', 'tip': 'Radius-of-gyration of brightness'}
            ]

        # Create a range slider widget for each of the properties. 
        self.sliders = []
        for prop in filter_properties:
            if prop['name'] not in df.columns and prop['name'] == 'size':
                prop['name'] = 'size_x'               
            slider_widget = CustomRangeSliderWidget(df, property=prop['name'], dtype=prop['type'], tip=prop['tip'])
            slider_widget.range_slider.setEdgeLabelMode(0)
            for slider_label in slider_widget.range_slider._handle_labels:
                slider_label.setFixedSize(QtCore.QSize(80, 21))
            slider_widget.range_slider.layout().setContentsMargins(30, 0, 30, 0)
            sliders_layout.addWidget(slider_widget)
            
            # Connect filtering of object to change in value of the range slider.
            slider_widget.range_slider._slider.valueChanged.connect(lambda: self._filter_objects(df=df))
            slider_widget.range_slider._slider.valueChanged.connect(lambda: self._enlarge_slider_label(slider_widget))
            slider_widget.range_slider._slider.rangeChanged.connect(lambda: self._filter_objects(df=df))
            slider_widget.range_slider._slider.rangeChanged.connect(lambda: self._enlarge_slider_label(slider_widget))

            self.sliders.append(slider_widget)

        # Request saving of filtered result.
        save_btn = QPushButton('Save selected objects')
        save_btn.clicked.connect(self._save_results)
        sliders_layout.addWidget(save_btn)
        self.sliders_widget.setLayout(sliders_layout)
        self.sliders_widget.setMaximumHeight(500)

        # Add the slider widgets to the tab widget
        self.tab_widget.addTab(self.sliders_widget, 'Selection Criteria')
        self.tab_widget.setCurrentIndex(1)

    def _run(self) -> None:
        """Run trackpy to link the data in the table"""

        # Load all the data
        files = sorted([f for f in os.listdir(self.inputdir) if '.tif' in f])
        if not len(files) > 0:
            msg = QMessageBox()
            msg.setWindowTitle('No tif files to track')
            msg.setText('No tif files were found in this directory. Please add intensity images as 3D tif images, 1 per time point.')
            msg.setIcon(QMessageBox.Information)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        else:
            if self.intensity_layer is not None and self.intensity_layer in self.viewer.layers:
                self.viewer.layers.remove(self.intensity_layer)
            self.intensity_layer, object_df = self._detect_trackpy(files) # Run trackpy to detect objects
            if self.points is not None:
                self.viewer.layers.remove(self.points)
            self.points = self._create_point_layer(object_df) # Create a points layer to show detected objects
            self._add_sliders_widget(object_df) # Add new widget for filtering the objects. 