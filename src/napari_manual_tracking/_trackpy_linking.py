
import os
import trackpy
import tifffile
import napari
from napari.utils import Colormap

import pandas   as pd
import numpy    as np

from typing                import List, Tuple
from skimage               import measure
from skimage.io            import imread

from qtpy.QtWidgets        import QMessageBox, QDoubleSpinBox, QComboBox, QGroupBox, QLabel, QHBoxLayout, QVBoxLayout, QPushButton, QWidget, QFileDialog, QLineEdit, QSpinBox

class TrackpyLinker(QWidget):
    """Widget for running linking with trackpy on a directory containing label images.
    
    """
    
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer
        self.inputdir = ""
        self.outputdir = ""

        self.untracked_labels = None
        self.tracked_labels = None     
        self.tracks = None

        # Add input and output directory. 
        settings_layout = QVBoxLayout()

        databox = QGroupBox('Data directories')
        databox_layout = QVBoxLayout()

        input_layout = QHBoxLayout()
        self.inputdirbtn = QPushButton('Select label directory')
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

        # Add trackpy linking configuration. 
        trackpy_settings = QGroupBox("Trackpy linking configuration")
        trackpy_settings_layout = QVBoxLayout()

        self.search_range_spinbox_x = QDoubleSpinBox()
        self.search_range_spinbox_x.setMaximum(500)
        self.search_range_spinbox_x.setValue(20)
        self.search_range_spinbox_y = QDoubleSpinBox()
        self.search_range_spinbox_y.setMaximum(500)
        self.search_range_spinbox_y.setValue(20)
        self.search_range_spinbox_z = QDoubleSpinBox()
        self.search_range_spinbox_z.setMaximum(500)      
        self.search_range_spinbox_z.setValue(20)

        self.memory_spinbox = QSpinBox()
        self.memory_spinbox.setMaximum(500)

        self.neighbor_strategy_combo = QComboBox()
        self.neighbor_strategy_combo.addItem('KDTree')
        self.neighbor_strategy_combo.addItem('BTree')

        self.link_strategy_combo = QComboBox()
        self.link_strategy_combo.addItem('recursive')
        self.link_strategy_combo.addItem('nonrecursive')
        self.link_strategy_combo.addItem('numba')
        self.link_strategy_combo.addItem('hybrid')
        self.link_strategy_combo.addItem('drop')
        self.link_strategy_combo.addItem('auto')

        self.link_trackpy_btn = QPushButton('Link labels')
        self.link_trackpy_btn.clicked.connect(self._run)
        self.link_trackpy_btn.setEnabled(False)
        
        trackpy_settings_layout.addWidget(QLabel('Search range x-axis'))
        trackpy_settings_layout.addWidget(self.search_range_spinbox_x)
        trackpy_settings_layout.addWidget(QLabel('Search range y-axis'))
        trackpy_settings_layout.addWidget(self.search_range_spinbox_y)
        trackpy_settings_layout.addWidget(QLabel('Search range z-axis'))
        trackpy_settings_layout.addWidget(self.search_range_spinbox_z)
        trackpy_settings_layout.addWidget(QLabel('Memory'))
        trackpy_settings_layout.addWidget(self.memory_spinbox)
        trackpy_settings_layout.addWidget(QLabel('Neighbor strategy'))
        trackpy_settings_layout.addWidget(self.neighbor_strategy_combo)
        trackpy_settings_layout.addWidget(QLabel('Link strategy'))
        trackpy_settings_layout.addWidget(self.link_strategy_combo)
        trackpy_settings_layout.addWidget(self.link_trackpy_btn)

        trackpy_settings.setLayout(trackpy_settings_layout)
        settings_layout.addWidget(trackpy_settings)

        self.setLayout(settings_layout)

    def _update_inputdir(self) -> None:
        """Update the input directory when the user modifies the text in the QLineEdit widget"""
        
        self.inputdir = str(self.input_path.text())
        if len(self.inputdir) > 0 and os.path.exists(self.inputdir) and len(self.outputdir) > 0 and os.path.exists(self.outputdir):
            self.link_trackpy_btn.setEnabled(True)
    
    def _update_outputdir(self) -> None:
        """Update the output directory when the user modifies the text in the QLineEdit widget"""
        
        self.outputdir = str(self.output_path.text())
        if len(self.inputdir) > 0 and os.path.exists(self.inputdir) and len(self.outputdir) > 0 and os.path.exists(self.outputdir):
                self.link_trackpy_btn.setEnabled(True)

    def _on_get_label_dir(self) -> None:
        """Open a dialog to choose a label directory"""

        path = QFileDialog.getExistingDirectory(self, 'Select folder with segmentation data to track')
        if path:
            self.input_path.setText(path)      
            self.inputdir = str(self.input_path.text())            
            if len(self.inputdir) > 0 and os.path.exists(self.inputdir) and len(self.outputdir) > 0 and os.path.exists(self.outputdir):
                self.link_trackpy_btn.setEnabled(True)
    
    def _on_get_output_dir(self) -> None:
        """Open a dialog to choose a label directory"""

        path = QFileDialog.getExistingDirectory(self, 'Select output folder')
        if path:
            self.output_path.setText(path)
            self.outputdir = str(self.output_path.text())
            if len(self.inputdir) > 0 and os.path.exists(self.inputdir) and len(self.outputdir) > 0 and os.path.exists(self.outputdir):
                self.link_trackpy_btn.setEnabled(True)
    
    def _measure_properties(self, files:List[str]) -> Tuple[napari.layers.Labels, pd.DataFrame]:
        """Open each file and measure properties, concatenate results and return as labels layer and pandas dataframe."""
           
        dfs = []
        stack = []
        for i, f in enumerate(files): 
            labels = imread(os.path.join(self.inputdir, f))
            props = measure.regionprops_table(labels, properties = ['label', 'centroid'])
            df = pd.DataFrame(props)
            df['frame'] = i
            dfs.append(df)
            stack.append(labels)
        
        locations = pd.concat(dfs, ignore_index = True)
        locations = locations.rename(columns={"centroid-0": "z", "centroid-1": "y", "centroid-2": "x"})

        if self.untracked_labels is not None and self.untracked_labels in self.viewer.layers:
            self.viewer.layers.remove(self.untracked_labels)

        return self.viewer.add_labels(np.stack(stack, axis = 0), name = "Untracked labels"), locations

    def _link_trackpy(self, locations:pd.DataFrame) -> pd.DataFrame:
        """Perform linking with trackpy of the label coordinates in the table"""

        search_range = (self.search_range_spinbox_z.value(), self.search_range_spinbox_y.value(), self.search_range_spinbox_x.value())
        memory = self.memory_spinbox.value()
        neighbor_strategy = self.neighbor_strategy_combo.currentText()
        link_strategy = self.link_strategy_combo.currentText()
        
        try:
            links = trackpy.link(locations, search_range = search_range, memory = memory, neighbor_strategy = neighbor_strategy, link_strategy = link_strategy)
            links['particle'] = links['particle'] + 2 # add plus 2 because label 0 is reserved for background and 1 will be reserved for non specified labels in some contexts
            return links

        except Exception as e:
            print('trackpy could not track labels. This is the error:', e)
            msg = QMessageBox()
            msg.setWindowTitle("Trackpy error")
            msg.setText("Trackpy could not link labels. \nIf you have many small fragmented labels, try to clean them up first. \nReducing the search range may help to limit track options.")
            msg.setIcon(QMessageBox.Information)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            return None

    def _compute_tracked_labels(self, untracked_labels:np.ndarray, links:pd.DataFrame) -> napari.layers.Labels:
        """Relabel the label image based on the links dataframe to give the same object the same label"""
        
        tracked_labels = np.copy(untracked_labels)
        for _, row in links.iterrows():
            frame = int(row['frame'])
            label = row['label']
            particle = row['particle']
            tracked_labels[frame][untracked_labels[frame] == label] = particle
          
        return self.viewer.add_labels(tracked_labels, name = 'Tracked labels')

    def _create_napari_label_colormap(self, tracked_labels: napari.layers.Labels, name: str) -> napari.utils.Colormap:
        """Create a colormap that for the label colors in the napari Labels layer"""

        labels = []
        colors = []
        for label in np.unique(tracked_labels.data):
            if label != 0:
                labels.append(label)
                colors.append(tracked_labels.get_color(label))
                    
        n_labels = len(labels)
        controls = np.arange(n_labels + 1) / n_labels  # Ensure controls are evenly spaced

        # Create a Colormap with discrete mapping using RGBA colors
        colormap = Colormap(colors=colors, controls=controls, name=name, interpolation='zero')

        # This is a bit weird, but I only managed to make the colormap available if it has been applied to a layer at least once. 
        # Directly applying it to the tracks layer is not possible, since it takes a str argument and not a napari.utils.Colormap. 
        # So adding a an image layer that uses the colormap serves only to make the colormap available in the viewer, I have not found a better solution yet...
        temp = self.viewer.add_image(np.random.choice(labels, size=(100, 100)), colormap = colormap, name = 'temp')
        self.viewer.layers.remove(temp)    

        return colormap          

    def _save_results(self, tracked_labels:napari.layers.Labels, links: pd.DataFrame) -> None: 
            """Save the tracking results as labels images (one per time point) and save the table with the time points and labels"""

            # Save the new segmentation data to the output directory. 
            filename = os.path.basename(self.inputdir)
            for i in range(tracked_labels.data.shape[0]):
                stack = tracked_labels.data[i]
                tifffile.imwrite(os.path.join(self.outputdir, (filename + "_TP" + str(i).zfill(4) + '.tif')), np.array(stack, dtype = 'uint16'))

            # Save the links dataframe to the output directory
            links = links[['frame', 'particle']] # Only keep frame and particle columns, since label properties may be updated in the ManualDivisionTracker widget.
            links = links.rename(columns = {'frame': 'time_point', 'particle': 'label'})
            links['parent'] = -1 # add a parent value of -1 (needed for ManualDivisionTracker)
            links.to_csv(os.path.join(self.outputdir, 'LabelAnnotations.csv'), index = False)

    def _run(self) -> None:
        """Run trackpy to link the data in the table"""

        # Load all the data
        files = sorted([f for f in os.listdir(self.inputdir) if '.tif' in f])
        if not len(files) > 0:
            msg = QMessageBox()
            msg.setWindowTitle("No tif files to track")
            msg.setText("No tif files were found in this directory. Please add label files as 3D tif images, 1 per time point.")
            msg.setIcon(QMessageBox.Information)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
        else:
            # measure label locations with skimage.measure.regionprops
            self.untracked_labels, locations = self._measure_properties(files)
            links = self._link_trackpy(locations)
            if links is not None:
                # Relabel the untracked labels following the links in trackpy.
                if self.tracked_labels is not None and self.tracked_labels in self.viewer.layers: 
                    self.viewer.layers.remove(self.tracked_labels)
                self.tracked_labels = self._compute_tracked_labels(self.untracked_labels.data, links)

                # Extract the coordinates of the particle tracks to add them as a tracks layer.
                coordinates_df = links[['particle', 'frame', 'z', 'y', 'x']]
                coordinates_array = coordinates_df.to_numpy()
                coordinates = coordinates_array.reshape(-1, 5)

                # Create a 'labels' colormap to match the colors of the tracks to the colors of the labels. 
                colormap = self._create_napari_label_colormap(self.tracked_labels, name="LabelColors")
               
                # Add the tracks layer and choose the colormap
                # properties = {'label': coordinates[:, 0]}
                # tracks = self.viewer.add_tracks(coordinates, properties=properties, colormaps_dict = {'label': colormap}) #somehow this did not work as expected, the colormap is not visible.
                if self.tracks is not None and self.tracks in self.viewer.layers:
                    self.viewer.layers.remove(self.tracks)
                self.tracks = self.viewer.add_tracks(coordinates, colormap="LabelColors") # this does work if the colormap has been added to the viewer before. 
                
                self.viewer.dims.ndisplay = 3

                # Save the results.
                self._save_results(self.tracked_labels, links)

