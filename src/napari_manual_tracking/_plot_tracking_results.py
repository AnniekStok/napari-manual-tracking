import os
import napari.viewer

import pandas                       as pd
import numpy                        as np

from typing                             import Tuple, List
from skimage.io                         import imread
from qtpy.QtWidgets                     import QMessageBox, QGroupBox, QCheckBox, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QFileDialog, QLineEdit, QTabWidget

from .utilities._checkboxWidget               import featuresCheckboxWidget
from .utilities._voxel_dimension_widget       import VoxelDimensionWidget
from .utilities._measure_props                import calculate_extended_props
from .utilities._plot_widget                  import PlotWidget
from .utilities._table_widget                 import ColoredTableWidget

class MeasureLabelTracks(QWidget):
    """Measure the label properties in tracked 3D labels"""

    def __init__(self, napari_viewer:napari.viewer.Viewer):

        super().__init__()
        self.viewer = napari_viewer
        self.viewer.layers.clear() # ensure the viewer is clean
        self.labeldir = ''
        self.measurements_widget = None
        self.labels = None

        # Select label working directory.
        label_box = QGroupBox('Label working directory')
        label_box_layout = QHBoxLayout()
        labeldirbtn = QPushButton('Select directory')
        self.label_path = QLineEdit()
        self.label_path.textChanged.connect(self._update_label_dir)
        label_box_layout.addWidget(labeldirbtn)
        label_box_layout.addWidget(self.label_path)
        labeldirbtn.clicked.connect(self._on_get_label_dir)
        label_box.setLayout(label_box_layout)

        # Create widget to enter the voxel dimensions.
        self.voxel_dimension_widget = VoxelDimensionWidget()

        # Create widget to select the features to be measured.
        self.features = featuresCheckboxWidget()

        # Measure only tracked cells, or all cells? 
        self.measure_tracked = QCheckBox("Tracked cells only")

        # Create push button for user to start measuring.
        self.measure_btn = QPushButton('Measure features')
        self.measure_btn.clicked.connect(self._run_feature_measurements)
        self.measure_btn.setEnabled(False) # button is disabled until valid label directory has been specified

        # Create widget combining widgets together
        settings_widget = QWidget()
        settings_layout = QVBoxLayout()
        settings_layout.addWidget(label_box) 
        settings_layout.addWidget(self.voxel_dimension_widget) 
        settings_layout.addWidget(self.features.checkbox_box)
        settings_layout.addWidget(self.measure_tracked)
        settings_layout.addWidget(self.measure_btn)
        settings_widget.setLayout(settings_layout)
        settings_widget.setMaximumHeight(700)

        # Create a QTabWidget so that Settings and Measurement results will be on separate tabs. 
        self.tab_widget = QTabWidget(self)
        self.tab_widget.addTab(settings_widget, "Settings")

        # Put the tab_widget in the main layout and apply it to the QWidget. 
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.tab_widget)
        self.setLayout(self.main_layout)      

    def _on_get_label_dir(self) -> None:
        """Lets the user set the label directory"""
        
        path = QFileDialog.getExistingDirectory(self, 'Select label Folder')
        if path:
            self.label_path.setText(path)
            self.labeldir = path
        
        # If the given path is valid, enable the measure_btn.    
        if os.path.exists(self.labeldir):
            self.measure_btn.setEnabled(True)

    def _update_label_dir(self) -> None:
        """Updates the label directory in case the user edits the label_path QLineEdit"""

        self.labeldir = str(self.label_path.text())
        # If the given path is valid, enable the measure_btn.    
        if os.path.exists(self.labeldir):
            self.measure_btn.setEnabled(True)
     
    def _load_labels(self) -> np.ndarray:
        """Load the original label image, and create a new labels layer with tracked labels only"""
        
        # Create a new labels layer holding the concatenated 4D array of label images.
        stack = []
        for f in self.files:
            img = imread(os.path.join(self.labeldir, f))
            stack.append(img)
        
        return np.stack(stack, axis = 0)
    
    def _load_tracked_labels(self) -> napari.layers.Labels:
        """Filter labels based on tracked labels."""

        self.labels_to_measure = np.unique(list(self.plot_df[self.plot_df['parent'] > -1]['label'].values))
        mask = np.isin(self.labels_data, self.labels_to_measure)
        tracked_labels = self.labels_data * mask

        return self.viewer.add_labels(tracked_labels, name = "Tracked labels")

    def _measure_properties(self, voxel_dimensions: Tuple[float, float, float], features: List[str]) -> pd.DataFrame:
        """Measure the features using extended version of skimage.measure.regionprops"""

        # Always include the centroid in the measurements since the table widget will make use of it
        features.append('non_calibrated_centroid')

        dfs = []
        for i in range(self.labels.data.shape[0]):
            d = self.labels.data[i]
            df = calculate_extended_props(d, properties = features, voxel_size = voxel_dimensions)
            df['time_point'] = i
            dfs.append(pd.DataFrame(df)) 
       
        measurements = pd.concat(dfs)

        # merge with the original data to also obtain the time_point and parent columns     
        if self.measure_tracked.isChecked():
            measurements = pd.merge(measurements, self.plot_df, on = ['label', 'time_point'], how = 'left')       
            # ensure that there are no NaN rows due to mismatches in the LabelAnnotation table (if it was edited outside napari for example)        
            measurements = measurements.dropna(subset=['parent'])
            measurements['parent'] = measurements['parent'].astype(int)

        # ensure that labels and parents are integers
        measurements['label'] = measurements['label'].astype(int)
        measurements['x'] = measurements['x'].astype(int)
        measurements['y'] = measurements['y'].astype(int)
        measurements['z'] = measurements['z'].astype(int)

        return measurements

    def _run_feature_measurements(self) -> None:
        """Measures the requested features and visualizes measurements in table and plot widget. """
        
        # Check whether the file LabelAnnotations.csv is present
        if not os.path.exists(os.path.join(self.labeldir, "LabelAnnotations.csv")):
            msg = QMessageBox()
            msg.setWindowTitle("No label annotation file found")
            msg.setText("The given label directory does not contain label tracks in a file called LabelAnnotations.csv. Please use the Manual Tracker widget to create one or add the file manually.")
            msg.setIcon(QMessageBox.Information)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        
        else:
            self.files = sorted([f for f in os.listdir(self.labeldir) if '.tif' in f and not f.startswith('.')])

            # Check if the label directory contains tif images. 
            if len(self.files) == 0:
                msg = QMessageBox()
                msg.setWindowTitle("No label files found")
                msg.setText("The given label directory does not contain any .tif label images.")
                msg.setIcon(QMessageBox.Information)
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec_()

            else: 
                # Load the data, create a labels layer
                if self.labels is not None: 
                    self.viewer.layers.remove(self.labels)

                if self.measure_tracked.isChecked(): 
                    # only the tracked labels will be loaded and measured
                    self.labels_data = self._load_labels()
                    self.plot_df = pd.read_csv(os.path.join(self.labeldir, 'LabelAnnotations.csv'))
                    self.labels = self._load_tracked_labels()
                
                else: 
                    # all labels are measured
                    self.labels = self.viewer.add_labels(self._load_labels())

                # Get the voxel dimensions entered by the user.
                voxel_dimensions = (self.voxel_dimension_widget.z_spin.value(), self.voxel_dimension_widget.y_spin.value(), self.voxel_dimension_widget.x_spin.value())

                # Collect the features to be measured.
                features_to_measure = [f for f in self.features.checkbox_state.keys() if self.features.checkbox_state[f]]

                # Measure the features.
                measurements = self._measure_properties(voxel_dimensions=voxel_dimensions, features=features_to_measure)

                if hasattr(self.labels, "properties"):
                    self.labels.properties = measurements
                if hasattr(self.labels, "features"):
                    self.labels.features = measurements
                table = ColoredTableWidget(self.labels, self.viewer)
                plot_widget = PlotWidget(measurements, self.labels)
                                  
                # Add table and plot widgets in a new tab.
                table._set_label_colors_to_rows()

                if self.measurements_widget is not None: 
                    self.tab_widget.removeTab(1)
                    
                self.measurements_widget = QWidget()
                measurements_layout = QVBoxLayout()
                measurements_layout.addWidget(table)
                measurements_layout.addWidget(plot_widget)
                self.measurements_widget.setLayout(measurements_layout)
                self.measurements_widget.setMinimumWidth(700)
                self.tab_widget.addTab(self.measurements_widget, "Measurements")
                self.tab_widget.setCurrentIndex(1) 