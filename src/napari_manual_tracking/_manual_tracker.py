import os
import tifffile
import warnings
import napari

import pandas           as pd
import numpy            as np

from typing             import List
from skimage                                import measure
from skimage.io         import imread
from matplotlib.colors  import to_rgba
from napari.utils       import DirectLabelColormap

from pathlib            import Path as PathL
from qtpy.QtCore        import Signal, Qt
from qtpy.QtGui         import QColor
from qtpy.QtWidgets     import QTableWidget, QAbstractItemView, QMessageBox, QTableWidgetItem, QScrollArea, QGroupBox, QLabel, QTabWidget, QHBoxLayout, QVBoxLayout, QPushButton, QWidget, QFileDialog, QLineEdit, QSpinBox

from .utilities._plot_widget                      import PlotWidget

icon_root = PathL(__file__).parent / "utilities/icons"

class TableWidget(QTableWidget):
    """QTable widget with functions for updating the table with a pandas dataframe, and sending a signal upon update.
    
    """
    
    table_changed = Signal(pd.DataFrame)

    def __init__(self, df:pd.DataFrame):
        super().__init__()
        self.df = df
        self.initUI()
       
    def initUI(self):
        """Initialize an empty table with columns 'label' and 'parent'"""
        
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(['label', 'parent'])
        self.itemChanged.connect(self.table_cell_changed)
        self.active = False
        self.setMinimumWidth(250)

    def _enable_editing(self) -> None:
        """Enable editing of the table widget"""

        self.setEditTriggers(QAbstractItemView.AllEditTriggers)
    
    def _disable_editing(self) -> None:
        """Disable editing of the table widget"""

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
    
    def _color_table(self, colors) -> None:
        """Apply the colors of the napari label image to the table"""

        for i in range(self.rowCount()):
            label = int(self.item(i, 0).text())
            if label > 0: 
                label_color = colors[label]
                scaled_color = (int(label_color[0] * 255), int(label_color[1] * 255), int(label_color[2] * 255))              
                for j in range(self.columnCount()):
                    self.item(i, j).setBackground(QColor(*scaled_color))

    def _populate_table(self, df:pd.DataFrame, cmap: napari.utils.Colormap):
        """Update the table with a pandas dataframe, overwriting the old associated dataframe."""

        self.itemChanged.disconnect(self.table_cell_changed)
        self.df = df
        n_rows, n_cols = df.shape
        self.setRowCount(n_rows)
        self.setColumnCount(n_cols)
        for i in range(n_rows):
            for j in range(n_cols):
                item = QTableWidgetItem(str(df.iat[i, j]))
                # Set the ItemIsEditable flag only for the second column
                if j == 1:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)

                self.setItem(i, j, item)

        label_colors = {}
        for label in self.df['label'].unique():
            if label > 0:
                label_colors[label] = cmap.map(label)

        self._color_table(label_colors)
        self.itemChanged.connect(self.table_cell_changed)   

    def table_cell_changed(self, item:QTableWidgetItem):
        """Update the dataframe with manually entered values, and send out a signal with the updated dataframe"""
        
        row = item.row()
        col = item.column()
        new_value = item.text()
        try:
            new_value = int(new_value)
            self.df.iat[row, col] = new_value
        except ValueError:
            print('Please enter numerical values!')
        self.table_changed.emit(self.df)

class ManualDivisionTracker(QWidget):
    """QWidget for manually correcting the tracks by updating label values in a 4D Labels layer
    
    """
    
    def __init__(self, napari_viewer:napari.viewer.Viewer):
        super().__init__()
        self.viewer = napari_viewer
        self.viewer.layers.clear() # ensure the viewer is clean
        self.parent_labels = pd.DataFrame()
        self.raw_data1_dir = ''
        self.label_dir = ''
        self.tab_widget = QTabWidget(self)
        self.include_raw_data2 = False
        self.running = False
        self.label_df = pd.DataFrame({'time_point': pd.Series(dtype = 'int'), 'label': pd.Series(dtype = 'int'), 'parent': pd.Series(dtype = 'int'), 'cell': pd.Series(dtype = 'str')})

        settings_layout = QVBoxLayout()

        # colormap options 
        self.colormap_options = ['All', 'Tracked', 'Lineage', 'Non-connected cells']
        self.colormap_selection_index = 0

        # Create widgets for user input and settings. 

        # Folder selection.
        raw_data1_box = QGroupBox('Raw data')
        raw_data1_box_layout = QHBoxLayout()
        raw_data1_dirbtn = QPushButton('Select directory')
        self.raw_data1_path = QLineEdit()
        self.raw_data1_path.textChanged.connect(self._update_raw_data1_dir)
        raw_data1_box_layout.addWidget(raw_data1_dirbtn)
        raw_data1_box_layout.addWidget(self.raw_data1_path)
        raw_data1_dirbtn.clicked.connect(self._on_get_raw_data1_dir)
        raw_data1_box.setLayout(raw_data1_box_layout)

        raw_data2_box = QGroupBox('(Optional) second channel raw data')
        raw_data2_box_layout = QHBoxLayout()
        raw_data2_dirbtn = QPushButton('Select directory')
        self.raw_data2_path = QLineEdit()
        self.raw_data2_path.textChanged.connect(self._update_raw_data2_dir)
        raw_data2_box_layout.addWidget(raw_data2_dirbtn)
        raw_data2_box_layout.addWidget(self.raw_data2_path)
        raw_data2_dirbtn.clicked.connect(self._on_get_raw_data2_dir)
        raw_data2_box.setLayout(raw_data2_box_layout)

        labelbox = QGroupBox('Label working directory')
        labelbox_layout = QHBoxLayout()
        label_dirbtn = QPushButton('Select directory')
        self.label_path = QLineEdit()
        self.label_path.textChanged.connect(self._update_label_dir)
        labelbox_layout.addWidget(label_dirbtn)
        labelbox_layout.addWidget(self.label_path)
        label_dirbtn.clicked.connect(self._on_get_label_dir)
        labelbox.setLayout(labelbox_layout)

        settings_layout.addWidget(raw_data1_box)
        settings_layout.addWidget(raw_data2_box)
        settings_layout.addWidget(labelbox)
        
        # Start / stop buttons
        StartStopBox = QGroupBox('Start / Stop editing')
        StartStopBoxLayout = QHBoxLayout()

        self.startbtn = QPushButton("Start")
        self.startbtn.clicked.connect(self._on_start)
        self.startbtn.setEnabled(False)

        self.stopbtn = QPushButton("Stop")
        self.stopbtn.clicked.connect(lambda: self._save(stop = True))
        self.stopbtn.setEnabled(False)

        StartStopBoxLayout.addWidget(self.startbtn)
        StartStopBoxLayout.addWidget(self.stopbtn)

        settings_layout.addWidget(StartStopBox)
        StartStopBox.setLayout(StartStopBoxLayout)

        # Add widget for converting a label to a new value.
        edit_box = QGroupBox('')
        edit_box_layout = QVBoxLayout()

        source_label_layout = QHBoxLayout()
        source_label_label = QLabel("Label 1")
        self.source_label_spin = QSpinBox()
        self.source_label_spin.setMaximum(100000)
        source_label_layout.addWidget(source_label_label)
        source_label_layout.addWidget(self.source_label_spin)
        source_label_widget = QWidget()
        source_label_widget.setLayout(source_label_layout)

        target_label_layout = QHBoxLayout()
        target_label_label = QLabel("Label 2")
        self.target_label_spin = QSpinBox()
        self.target_label_spin.setMaximum(100000)
        target_label_layout.addWidget(target_label_label)
        target_label_layout.addWidget(self.target_label_spin)
        target_label_widget = QWidget()
        target_label_widget.setLayout(target_label_layout)

        convert_layout = QVBoxLayout()
        swap_layout = QVBoxLayout()
        self.edit_frame_btn = QPushButton('Convert label 1 to label 2 (subsequent frames)')
        self.edit_frame_btn.clicked.connect(lambda: self._convert_label(all=False))
        self.edit_frame_btn.setEnabled(False)
        self.edit_all_btn = QPushButton('Convert label 1 to label 2 (all)')
        self.edit_all_btn.clicked.connect(lambda: self._convert_label(all=True))
        self.edit_all_btn.setEnabled(False)
        self.swap_frame_btn = QPushButton('Swap label 1 and 2 (subsequent frames)')
        self.swap_frame_btn.clicked.connect(lambda: self._swap_label(all=False))
        self.swap_frame_btn.setEnabled(False)
        self.swap_all_btn = QPushButton('Swap label 1 and 2 (all)')
        self.swap_all_btn.clicked.connect(lambda: self._swap_label(all=True))
        self.swap_all_btn.setEnabled(False)

        convert_layout.addWidget(self.edit_frame_btn)
        convert_layout.addWidget(self.edit_all_btn)
        swap_layout.addWidget(self.swap_frame_btn)
        swap_layout.addWidget(self.swap_all_btn)

        convert_swap_layout = QHBoxLayout()
        convert_swap_layout.addLayout(convert_layout)
        convert_swap_layout.addLayout(swap_layout)

        edit_box_layout.addWidget(source_label_widget)
        edit_box_layout.addWidget(target_label_widget)
        edit_box_layout.addLayout(convert_swap_layout)
        edit_box.setLayout(edit_box_layout)

        settings_layout.addWidget(edit_box)

        # Add a save button.
        self.savebtn = QPushButton('Save current state')
        self.savebtn.clicked.connect(self._save)
        self.savebtn.setEnabled(False)
        settings_layout.addWidget(self.savebtn)
        
        # Create tab widget that holds the table in the first tab and the settings in the second tab 

        # Create horizontal layout to have multiple viewer widget on the left and table on the right.
        self.multi_view_table_widget = QWidget()
        self.multi_view_table_layout = QVBoxLayout()
    
        # Create an instance of the customized table widget.
        self.table_widget = TableWidget(self)
        self.table_widget._disable_editing()
        self.table_widget.table_changed.connect(self._update_parent_labels)  

        # Add widget to show and edit table.
        table_edit_widget = QWidget()
        table_edit_widget_layout = QVBoxLayout()

        table_edit_widget_layout.addWidget(self.table_widget)
        table_edit_widget.setLayout(table_edit_widget_layout)

        # Add multiview and combined table widget to the layout, apply to the widget, and set it in the first tab of the tab_widget.
        self.multi_view_table_layout.addWidget(table_edit_widget)        
        self.multi_view_table_widget.setLayout(self.multi_view_table_layout)      
        self.tab_widget.addTab(self.multi_view_table_widget, "Table")

        # Combine all settings widgets and create a tab in the tab_widget.
        settings_widgets = QWidget()
        settings_widgets.setLayout(settings_layout)
        scroll_area = QScrollArea() # add a scroll bar to make sure it fits on small screens
        scroll_area.setWidget(settings_widgets)
        settings_widgets.setMaximumHeight(700)
        scroll_area.setWidgetResizable(True)
        self.tab_widget.addTab(scroll_area, "Settings")
        self.tab_widget.setCurrentIndex(1) 

        # add the tab widget as main layout, and apply it to the main widget
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.tab_widget)
        self.setLayout(self.main_layout)

    def _on_get_raw_data1_dir(self) -> None:
        """Sets the path to the main raw data directory (e.g. nuclei)"""

        path = QFileDialog.getExistingDirectory(self, 'Select Raw Data Folder')
        if path:
            self.raw_data1_path.setText(path)
            self.raw_data1_dir = path

            # If valid paths are given for raw data and label data, enable the start button
            if len(self.raw_data1_dir) > 0 and os.path.exists(self.raw_data1_dir) and len(self.label_dir) > 0 and os.path.exists(self.label_dir):
                self.startbtn.setEnabled(True)
            else:
                self.startbtn.setEnabled(False)

    def _on_get_raw_data2_dir(self) -> None:
        """Sets the path to the second (optional) raw data directory (e.g. membrane)"""

        path = QFileDialog.getExistingDirectory(self, 'Select raw_data2 Data Folder')
        if path:
            self.raw_data2_path.setText(path)
            self.raw_data2_dir = path
            self.include_raw_data2 = True

    def _on_get_label_dir(self) -> None:
        """Sets the path to the label data directory"""

        path = QFileDialog.getExistingDirectory(self, 'Select label Folder')
        if path:
            self.label_path.setText(path)
            self.label_dir = path

            # If valid paths are given for raw data and label data, enable the start button
            if len(self.raw_data1_dir) > 0 and os.path.exists(self.raw_data1_dir) and len(self.label_dir) > 0 and os.path.exists(self.label_dir):
                self.startbtn.setEnabled(True)
            else:
                self.startbtn.setEnabled(False)

    def _update_raw_data1_dir(self) -> None:
        """Updates the main raw data directory in the case the user modified the content in the QLineEdit widget."""

        self.raw_data1_dir = str(self.raw_data1_path.text())

        # If valid paths are given for raw data and label data, enable the start button
        if len(self.raw_data1_dir) > 0 and os.path.exists(self.raw_data1_dir) and len(self.label_dir) > 0 and os.path.exists(self.label_dir):
                self.startbtn.setEnabled(True)
        else:
            self.startbtn.setEnabled(False)

    def _update_raw_data2_dir(self) -> None:
        """Updates the path to the second data directory in case the user modified the content in the QLineEdit widget."""

        self.raw_data2_dir = str(self.raw_data2_path.text())     
    
    def _update_label_dir(self) -> None:
        """Updates the path to the label data directory in case the user modified the content in the QLineEdit widget."""

        self.label_dir = str(self.label_path.text())     
        if len(self.raw_data1_dir) > 0 and os.path.exists(self.raw_data1_dir) and len(self.label_dir) > 0 and os.path.exists(self.label_dir):
                self.startbtn.setEnabled(True)
        else:
            self.startbtn.setEnabled(False)

    def _update_parent_labels(self, df:pd.DataFrame) -> None:
        """Update the parent_labels object, the table, and the plot"""

        self.parent_labels = df 
        self.label_df['parent'] = self.label_df['label'].map(self.parent_labels.set_index('label')['parent'])
        self.plot_widget.props = self.label_df       
        self.plot_widget._update_plot()
   
    def _convert_label(self, all:bool) -> None:
        """Change the label value of a particular label to a new value from the current time point onwards (all is False) or for all time points (all is True)."""

        source_label = self.source_label_spin.value()
        target_label = self.target_label_spin.value()
        time_start = int(self.viewer.dims.current_step[0])

        # update self.label_df based on self.parent_labels just in case there are any inconsistencies (dirty fix)
        self.label_df = pd.merge(self.label_df, self.parent_labels[['label', 'parent']], on='label', how='left', suffixes=('', '_new'))
        self.label_df['parent'] = self.label_df['parent_new']
        self.label_df.drop('parent_new', axis=1, inplace=True)

        if target_label == 0:
            # the user wants to remove this label entirely
            if all: 
                self.labels.data[self.labels.data == source_label] = target_label
                self.label_df = self.label_df[self.label_df['label'] != source_label]
            else:
                self.labels.data[time_start:, :, :, :][self.labels.data[time_start:, :, :, :] == source_label] = target_label    
                mask = (self.label_df['label'] != source_label) & (self.label_df['time_point'] <= time_start)        
                self.label_df = self.label_df[mask]
            
            # remove source_label from parent_labels
            self.parent_labels = self.parent_labels[self.parent_labels['label'] != source_label]
            self.table_widget._populate_table(self.parent_labels, self.cmap)    

        else: 
            # Update both the labels layer and the dataframe
            if all:
                self.labels.data[self.labels.data == source_label] = target_label
                self.label_df.loc[self.label_df['label'] == source_label, "label"] = target_label
            else:  
                self.labels.data[time_start:, :, :, :][self.labels.data[time_start:, :, :, :] == source_label] = target_label
                self.label_df.loc[(self.label_df['time_point'] >= time_start) & (self.label_df['label'] == source_label), "label"] = target_label

            # If the new label did not exist yet in the parent_labels dataframe, add it now, and remove any that are no longer in the self.label_df.
            if not target_label in self.parent_labels['label'].values:
                self.parent_labels.loc[len(self.parent_labels.index)] = [target_label, 0]
                self.parent_labels = self.parent_labels[self.parent_labels['label'].isin(self.label_df['label'])]
                self.table_widget._populate_table(self.parent_labels, self.cmap)        

        # update self.label_df based on self.parent_labels just in case there are any inconsistencies (dirty fix)
        self.label_df = pd.merge(self.label_df, self.parent_labels[['label', 'parent']], on='label', how='left', suffixes=('', '_new'))
        self.label_df['parent'] = self.label_df['parent_new']
        self.label_df.drop('parent_new', axis=1, inplace=True)
        
        # Call plot update
        self.plot_widget.props = self.label_df       
        self.plot_widget._update_plot()
    
        # update the labels
        self.labels.data = self.labels.data

    def _swap_label(self, all:bool) -> None:
        """Change the label value of a particular label to a new value from the current time point onwards (all is False) or for all time points (all is True)."""

        source_label = self.source_label_spin.value()
        target_label = self.target_label_spin.value()
        time_start = int(self.viewer.dims.current_step[0])
        
        # If any of the two labels did not yet exist in self.parent_labels, the swap is invalid
        if not (source_label in self.parent_labels['label'].values and target_label in self.parent_labels['label'].values): 
            print('Invalid source or target label!')
            warnings.warn('Invalid source or target label!')
            return

        # update self.label_df based on self.parent_labels just in case there are any inconsistencies (dirty fix)
        self.label_df = pd.merge(self.label_df, self.parent_labels[['label', 'parent']], on='label', how='left', suffixes=('', '_new'))
        self.label_df['parent'] = self.label_df['parent_new']
        self.label_df.drop('parent_new', axis=1, inplace=True)

        # Swap source and target label in the array and in the pandas df
        if all:

            # swap in the array
            mask = (self.labels.data == source_label)
            self.labels.data[self.labels.data == target_label] = source_label
            self.labels.data[mask] = target_label

            # swap in self.label_df
            mask_source = self.label_df['label'] == source_label
            mask_target = self.label_df['label'] == target_label

            self.label_df.loc[mask_target, 'label'] = source_label
            self.label_df.loc[mask_source, 'label'] = target_label

            # Swap 'parent' values
            source_parent = self.parent_labels.loc[self.parent_labels['label'] == source_label, 'parent'].values[0]
            target_parent = self.parent_labels.loc[self.parent_labels['label'] == target_label, 'parent'].values[0]

            self.label_df.loc[mask_target, 'parent'] = source_parent
            self.label_df.loc[mask_source, 'parent'] = target_parent
          
        else:          
            mask = (self.labels.data[time_start:, :, :, :] == source_label)
            self.labels.data[time_start:, :, :, :][self.labels.data[time_start:, :, :, :] == target_label] = source_label
            self.labels.data[time_start:, :, :, :][mask] = target_label

            mask_time_source = (self.label_df['time_point'] >= time_start) & (self.label_df['label'] == source_label)
            mask_time_target = (self.label_df['time_point'] >= time_start) & (self.label_df['label'] == target_label)

            self.label_df.loc[mask_time_target, 'label'] = source_label
            self.label_df.loc[mask_time_source, 'label'] = target_label

            # Swap 'parent' values
            source_parent = self.parent_labels.loc[self.parent_labels['label'] == source_label, 'parent'].values[0]
            target_parent = self.parent_labels.loc[self.parent_labels['label'] == target_label, 'parent'].values[0]

            self.label_df.loc[mask_time_target, 'parent'] = source_parent
            self.label_df.loc[mask_time_source, 'parent'] = target_parent  
        
        self.parent_labels = self.parent_labels[self.parent_labels['label'].isin(self.label_df['label'])]
        self.table_widget._populate_table(self.parent_labels, self.cmap)   

        # Call plot update
        print('updating the plot')
        self.plot_widget.props = self.label_df       
        self.plot_widget._update_plot()

        # update the labels
        self.labels.data = self.labels.data
    
    def _load_image_data(self, directory:str, files:List[str]) -> np.ndarray:
        """Load all tiff files in the specified directory as a numpy.ndarray"""

        imgs = []
        for f in files:
            img = imread(os.path.join(directory, f))
            imgs.append(img)
        
        return np.stack(imgs, axis = 0)

    def _show_empty_dir_message(self, directory:str) -> None:
        """Show a message in case the given directory does not contain tif files"""

        msg = QMessageBox()
        msg.setWindowTitle("Directory does not contain tif files")
        msg.setText(f"The directory {directory} does not contain label tracks in a file called LabelAnnotations.csv. Please use the Manual Tracker widget to create one or add the file manually.")
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
    
    def _update_labels(self, time_point:int, label:int) -> None: 
        """Update the current time point for all labels, and include the new one. Update parent_labels and the plot. Note that the first time the function is called, the data is not yet updated, so the user needs to click twice if a new label is introduced."""

        if label != 1: # label 1 is reserved for non-tracked labels

            # If the label was in parent_labels with value -1, set it to 0 
            if self.parent_labels[self.parent_labels['label'] == label].empty:
                # Add a new row with label = label and parent = 0
                self.parent_labels = pd.concat([self.parent_labels, pd.DataFrame({'label': [label], 'parent': [0]})], ignore_index=True)        
                print('add label to parent labels for ', label)

            elif self.parent_labels.loc[self.parent_labels['label'] == label, 'parent'].values[0] == -1:
                print('changing the -1 value to 0 for parent for label', label)
                self.parent_labels.loc[self.parent_labels['label'] == label, 'parent'] = 0
               
            # Also update all other time points for this label, replacing the parent label
            parent_value = self.parent_labels.loc[self.parent_labels['label'] == label, 'parent'].values[0]
            self.label_df.loc[self.label_df['label'] == label, 'parent'] = parent_value

        # update self.label_df at the current time point
        area_df = pd.DataFrame(measure.regionprops_table(self.labels.data[time_point], properties = ['label', 'area']))
        areas = area_df[area_df['label'] > 1]['area']
        labels = np.unique(area_df[area_df['label'] > 1]['label'])
        time_points = [time_point for _ in labels]
        parents = [self.parent_labels.loc[self.parent_labels['label'] == l, 'parent'].values[0] for l in labels]
        cells = ['Cell ' + str(label).zfill(5) for label in labels]
        d = {'time_point': time_points, 'label': labels, 'parent': parents, 'cell': cells, 'area': areas}
        df = pd.DataFrame(d)
        self.label_df = self.label_df.loc[self.label_df['time_point'] != time_point] # remove all rows for the current time point from the dataframe...
        self.label_df = pd.concat([self.label_df, df]) # ...to concatenate it with the updated data points at the current time point.
        self.plot_widget.props = self.label_df       
        self.plot_widget._update_plot()
        
        # also update the parent labels df, removing any labels that no longer exist in the data. 
        self.parent_labels = self.parent_labels[self.parent_labels['label'].isin(self.label_df['label'])]
        self.table_widget._populate_table(self.parent_labels, self.cmap)
    
    def _on_start(self) -> None:
        """Start the tracking procedure by loading all data and adding mouse callback"""

        self.viewer.layers.clear()
        
        # Load the image data from the provided directories. 
        raw_files = sorted([f for f in os.listdir(self.raw_data1_dir) if '.tif' in f])
        if len(raw_files) > 0:
            self.raw_layer = self.viewer.add_image(self._load_image_data(self.raw_data1_dir, raw_files))
        else:
            self._show_empty_dir_message(self.raw_data1_dir)
            return False
        
        if self.include_raw_data2:
            raw_files2 = sorted([f for f in os.listdir(self.raw_data2_dir) if '.tif' in f])
            if len(raw_files2) > 0:
                 self.raw_data2_layer = self.viewer.add_image(self._load_image_data(self.raw_data2_dir, raw_files2))
            else:
                self._show_empty_dir_message(self.raw_data2_dir)
                return False
        
        self.label_files = sorted([f for f in os.listdir(self.label_dir) if '.tif' in f])
        if len(self.label_files) > 0:
            self.labels = self.viewer.add_labels(self._load_image_data(self.label_dir, self.label_files))
        else:
            # Create empty label files in this directory, so that they can be filled in by the user.
            label_data = []
            for i in range(self.raw_layer.data.shape[0]):
                empty_arr = np.zeros_like(self.raw_layer.data[0])
                tifffile.imwrite(os.path.join(self.label_dir, (os.path.basename(self.label_dir) + "_TP" + str(i).zfill(4) + ".tif")), empty_arr)
                label_data.append(empty_arr)
            self.labels = self.viewer.add_labels(np.stack(label_data, axis = 0), name = os.path.basename(self.label_dir))
            self.label_files = sorted([f for f in os.listdir(self.label_dir) if '.tif' in f])
        
        self.cmap = self.labels.colormap # store the original cycliclabelcolormap

        # Activate / deactivate the buttons.
        self.stopbtn.setEnabled(True)
        self.startbtn.setEnabled(False)
        self.edit_all_btn.setEnabled(True)
        self.edit_frame_btn.setEnabled(True)
        self.swap_all_btn.setEnabled(True)
        self.swap_frame_btn.setEnabled(True)
        self.tab_widget.setCurrentIndex(0)
        self.table_widget._enable_editing()
        self.savebtn.setEnabled(True)
        self.running = True

        # Load or create the label annotation dataframe.
        if os.path.exists(os.path.join(self.label_dir, 'LabelAnnotations.csv')):
            self.label_df = pd.read_csv(os.path.join(self.label_dir, 'LabelAnnotations.csv'))
            self.label_df['parent'] = self.label_df['parent'].astype(int)
            self.label_df['label'] = self.label_df['label'].astype(int)
            self.label_df['cell'] = self.label_df['label'].apply(lambda x: f'Cell {str(x).zfill(5)}')

        else: 
            for i in range(self.labels.data.shape[0]):
                props = measure.regionprops_table(self.labels.data[i], properties = ['label', 'area'])
                props['time_point'] = i
                props['parent'] = -1
                props = pd.DataFrame(props)
                props['cell'] = props.apply(lambda row: 'Cell ' + str(row.label).zfill(5), axis = 1)
                self.label_df = pd.concat([self.label_df, props])
            
        if hasattr(self.labels, "properties"):
            self.labels.properties = self.label_df
        if hasattr(self.labels, "features"):
            self.labels.features = self.label_df

        # Populate the parent_labels table widget.
        existing_labels = self.label_df[['label', 'parent']].drop_duplicates().sort_values(by = 'label', axis = 0)
        label_list = list(existing_labels['label'])
        parent_list = list(existing_labels['parent'])
        self.parent_labels = pd.DataFrame({'label': label_list, 'parent': parent_list})      
        self.table_widget._populate_table(self.parent_labels, self.cmap)

        # Add the plot widget
        self.plot_widget = PlotWidget(self.label_df, self.labels)
        self.viewer.window.add_dock_widget(self.plot_widget,name='Lineage Tree',area='bottom')

        # Add mouse click callback to fill bucket and paint brush events. 
        def labels_updated(event): 
            print('update labels was triggered!')
            tp = int(self.viewer.dims.current_step[0])
            current_label = int(self.labels.selected_label)
            if self.running: 
                self._update_labels(tp, current_label)

        @self.labels.events.labels_update.connect(labels_updated)
        
        # Add custom key binding
        @self.labels.bind_key('s')
        def show_selected_label(event):
            self.labels.colormap = self.cmap
            self.labels.show_selected_label = not self.labels.show_selected_label

        @self.labels.bind_key('a')
        def cycle_label_selection(event):

            self.colormap_selection_index = (self.colormap_selection_index + 1) % len(self.colormap_options)
            self.viewer.text_overlay.text = str(self.colormap_options[self.colormap_selection_index])
            self.viewer.text_overlay.visible = True
            self._update_cmap()

            if self.colormap_options[self.colormap_selection_index] == 'Lineage': 
                self.labels.events.selected_label.connect(self._update_cmap)
            else: 
                self.labels.events.selected_label.disconnect(self._update_cmap) 

    def _update_cmap(self) -> None: 
        """Updates the colormap of the labels, using the current selection (all, tracked, lineage, or loose cells)."""

        self.labels.events.selected_label.disconnect(self._update_cmap)
        self.labels.colormap = self.cmap

        if not self.colormap_options[self.colormap_selection_index] == "All":           
            if self.colormap_options[self.colormap_selection_index] == "Tracked": 
                selection = self.parent_labels.loc[self.parent_labels['parent'] != -1, 'label'] # find all the labels that have a parent != -1
            if self.colormap_options[self.colormap_selection_index] == "Lineage": 
                selection = self._get_lineage(self.labels.selected_label)
            if self.colormap_options[self.colormap_selection_index] == "Non-connected cells": 
                selection = self.parent_labels.loc[self.parent_labels['parent'] == -1, 'label']
            
            self.labels.colormap = self._create_custom_direct_cmap(selection)

            if self.colormap_options[self.colormap_selection_index] == "Lineage": 
                self.labels.events.selected_label.connect(self._update_cmap)      

    def _get_lineage(self, selected_label: int): 
        """Get the entire lineage the current label belongs to"""

        if selected_label in [0, 1]:
            return []
        try: 
            parent = self.parent_labels.loc[self.parent_labels['label'] == selected_label, 'parent'].iloc[0]
        except IndexError:
            print('this label does not exist in parent labels')
            return []

        if parent == -1:
            print('this label has not been tracked yet and therefore does not belong to a lineage')
            return []
        elif parent == 0:
            y_axis_order = self._determine_label_plot_order([selected_label])      
        else: 
            while parent > 0:
                new_parent = self.parent_labels.loc[self.parent_labels['label'] == parent, 'parent'].iloc[0]
                if (new_parent == 0) or (new_parent == -1) :
                    break
                else:
                    parent = new_parent
            y_axis_order = self._determine_label_plot_order([parent])  
        
        return(y_axis_order)

    def _determine_label_plot_order(self, starting_points: List[int]) -> List[int]:
        """Determines the y-axis order of the tree plot, from the starting points downward"""
        
        y_axis_order = [s for s in starting_points]

        # Find the children of each of the starting points, and work down the tree.
        while len(starting_points) > 0:
            children_list = []
            for l in starting_points:
                children = list(self.parent_labels.loc[self.parent_labels['parent'] == l, 'label'])
                for i, c in enumerate(children):
                    [children_list.append(c)]
                    y_axis_order.insert(y_axis_order.index(l) + i, c)
            starting_points = children_list

        return y_axis_order

    def _create_custom_direct_cmap(self, selected_labels: List[int]):
        """Create a custom direct colormap for the selected labels, and set all other other labels to transparent"""
        
        color_dict_rgb = {None: (0.0, 0.0, 0.0, 0.0)}
        for s in selected_labels:
            color_dict_rgb[s] = to_rgba(self.labels.get_color(s))
        print(color_dict_rgb)
        return DirectLabelColormap(color_dict=color_dict_rgb)

    def _save(self, stop=False) -> None:
        """Save the current labels layer and label dataframe"""
        
        if stop:
            self.stopbtn.setEnabled(False)
            self.startbtn.setEnabled(True)
            self.running = False
            self.table_widget._disable_editing()
            self.savebtn.setEnabled(False)

        # Save all label image data.
        for i in range(self.labels.data.shape[0]):
            reconstructed_labels = self.labels.data[i, :, :, :]
            tifffile.imwrite(os.path.join(self.label_dir, self.label_files[i]), reconstructed_labels, bigtiff=True)

        # Merge the dataframe with the information from parent_labels and save dataframe and plot.
        self.parent_labels['parent'] = self.parent_labels['parent'].astype(int)
        result = pd.merge(self.label_df[['time_point', 'label', 'area', 'cell']], self.parent_labels, on = 'label', how = 'left')
        result['parent'] = result['parent'].fillna(-1)
        result.to_csv(os.path.join(self.label_dir, 'LabelAnnotations.csv'), index = False)
