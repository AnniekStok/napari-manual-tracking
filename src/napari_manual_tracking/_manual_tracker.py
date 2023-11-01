import os
import tifffile
import matplotlib
import napari

import pandas           as pd
import numpy            as np

from typing             import List, Tuple
from skimage.io         import imread
from matplotlib.figure  import Figure
from matplotlib.colors  import to_rgb

from pathlib            import Path as PathL

from qtpy.QtGui         import QIcon
from qtpy.QtCore        import Signal
from qtpy.QtGui         import QColor
from qtpy.QtWidgets     import QTableWidget, QAbstractItemView, QMessageBox, QTableWidgetItem, QScrollArea, QGroupBox, QLabel, QTabWidget, QHBoxLayout, QVBoxLayout, QPushButton, QWidget, QFileDialog, QLineEdit, QSpinBox

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from .utilities.napari_multiple_view_widget       import CrossWidget, MultipleViewerWidget

icon_root = PathL(__file__).parent / "utilities/icons"

class TableWidget(QTableWidget):
    """QTable widget with functions for updating the table with a pandas dataframe, and sending a signal upon update.
    
    """
    
    table_changed = Signal(pd.DataFrame)
    colors_changed = Signal(tuple, int)

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

    def _enable_editing(self) -> None:
        """Enable editing of the table widget"""

        self.setEditTriggers(QAbstractItemView.AllEditTriggers)
    
    def _disable_editing(self) -> None:
        """Disable editing of the table widget"""

        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
    
    def _color_row(self, location, label_color) -> None: 
        """Color a specific row in the table based on the given label color"""

        self.itemChanged.disconnect(self.table_cell_changed)
        scaled_color = (int(label_color[0] * 255), int(label_color[1] * 255), int(label_color[2] * 255))
        for j in range(self.columnCount()):
            self.item(location[0], j).setBackground(QColor(*scaled_color))
        self.itemChanged.connect(self.table_cell_changed)

    def _color_table(self, colors) -> None:
        """Apply the colors of the napari label image to the table"""

        for i in range(self.rowCount()):
            label = int(self.item(i, 0).text())
            if label > 0: 
                label_color = colors[label]
                scaled_color = (int(label_color[0] * 255), int(label_color[1] * 255), int(label_color[2] * 255))              
                for j in range(self.columnCount()):
                    self.item(i, j).setBackground(QColor(*scaled_color))

    def _populate_table(self, df:pd.DataFrame, colors: dict):
        """Update the table with a pandas dataframe, overwriting the old associated dataframe."""

        self.itemChanged.disconnect(self.table_cell_changed)
        self.df = df
        n_rows, n_cols = df.shape
        self.setRowCount(n_rows)
        self.setColumnCount(n_cols)
        for i in range(n_rows):
            for j in range(n_cols):
                item = QTableWidgetItem(str(df.iat[i, j]))
                self.setItem(i, j, item)
        self._color_table(colors)
        self.itemChanged.connect(self.table_cell_changed)
    
    def _delete_row(self):
        """Delete a row in the table widget"""

        self.itemChanged.disconnect(self.table_cell_changed)
        row_to_delete = self.currentRow()
        if row_to_delete >= 0:
            item = self.item(row_to_delete, 0)
            if item.text() != "":
                label = int(item.text())
                self.df = self.df.drop(self.df[self.df['label'] == label].index).reset_index(drop=True)        
                self.table_changed.emit(self.df)
            self.removeRow(row_to_delete)             
        self.itemChanged.connect(self.table_cell_changed)

    def _add_row(self):
        """Add a row to the table widget"""

        self.itemChanged.disconnect(self.table_cell_changed)
        self.df.loc[len(self.df.index)] = [0, 0]
        row_position = self.rowCount()
        self.insertRow(self.rowCount())
        for j in range(self.columnCount()):
            item = QTableWidgetItem("0")  # Create a new QTableWidgetItem for each cell
            self.setItem(row_position, j, item)       
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
            pass       
        self.table_changed.emit(self.df)
        if col == 0:
            self.colors_changed.emit((row, col), new_value)

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
        settings_layout = QVBoxLayout()

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
        source_label_label = QLabel("Label to be converted")
        self.source_label_spin = QSpinBox()
        self.source_label_spin.setMaximum(100000)
        source_label_layout.addWidget(source_label_label)
        source_label_layout.addWidget(self.source_label_spin)
        source_label_widget = QWidget()
        source_label_widget.setLayout(source_label_layout)

        target_label_layout = QHBoxLayout()
        target_label_label = QLabel("Label to convert to")
        self.target_label_spin = QSpinBox()
        self.target_label_spin.setMaximum(100000)
        target_label_layout.addWidget(target_label_label)
        target_label_layout.addWidget(self.target_label_spin)
        target_label_widget = QWidget()
        target_label_widget.setLayout(target_label_layout)

        convert_layout = QHBoxLayout()
        self.edit_frame_btn = QPushButton('Edit subsequent frames')
        self.edit_frame_btn.clicked.connect(lambda: self._convert_label(all=False))
        self.edit_frame_btn.setEnabled(False)
        self.edit_all_btn = QPushButton('Edit all frames')
        self.edit_all_btn.clicked.connect(lambda: self._convert_label(all=True))
        self.edit_all_btn.setEnabled(False)
        convert_layout.addWidget(self.edit_frame_btn)
        convert_layout.addWidget(self.edit_all_btn)
        convert_widget = QWidget()
        convert_widget.setLayout(convert_layout)

        edit_box_layout.addWidget(source_label_widget)
        edit_box_layout.addWidget(target_label_widget)
        edit_box_layout.addWidget(convert_widget)
        edit_box.setLayout(edit_box_layout)

        settings_layout.addWidget(edit_box)

        # Add a save button.
        self.savebtn = QPushButton('Save current state')
        self.savebtn.clicked.connect(self._save)
        self.savebtn.setEnabled(False)
        settings_layout.addWidget(self.savebtn)
        
        # Add the button to show the cross in multiple viewer widget.
        cross_box = QGroupBox('Add cross to multiview')
        cross_box_layout = QHBoxLayout()
        self.cross = CrossWidget(self.viewer)
        cross_box_layout.addWidget(self.cross)
        cross_box.setLayout(cross_box_layout)
        settings_layout.addWidget(cross_box)

        # Create tab widget that holds the multipleviewer + table in the first tab and the settings in the second tab 

        # Create horizontal layout to have multiple viewer widget on the left and table on the right.
        self.multi_view_table_widget = QWidget()
        self.multi_view_table_layout = QHBoxLayout()

        # Add multiview widget.
        self.multiview_widget = MultipleViewerWidget(self.viewer)
     
        # Create an instance of the customized table widget.
        self.table_widget = TableWidget(self)
        self.table_widget._disable_editing()
        self.table_widget.table_changed.connect(self._update_parent_labels)  
        self.table_widget.colors_changed.connect(self._update_table_item_color)  

        # Add widget to show and edit table.
        table_edit_widget = QWidget()
        table_edit_widget_layout = QVBoxLayout()

        table_edit_button_layout = QHBoxLayout()
        self.delete_row_btn = QPushButton('Delete row')
        self.delete_row_btn.clicked.connect(self.table_widget._delete_row)
        self.delete_row_btn.setEnabled(False)
        self.add_row_btn = QPushButton('Add row')
        self.add_row_btn.clicked.connect(self.table_widget._add_row)
        self.add_row_btn.setEnabled(False)
        table_edit_button_layout.addWidget(self.delete_row_btn)
        table_edit_button_layout.addWidget(self.add_row_btn)
        table_edit_widget_layout.addLayout(table_edit_button_layout)

        table_edit_widget_layout.addWidget(self.table_widget)
        table_edit_widget.setLayout(table_edit_widget_layout)

        # Add multiview and combined table widget to the layout, apply to the widget, and set it in the first tab of the tab_widget.
        self.multi_view_table_layout.addWidget(self.multiview_widget)
        self.multi_view_table_layout.addWidget(table_edit_widget)        
        self.multi_view_table_widget.setLayout(self.multi_view_table_layout)      
        self.tab_widget.addTab(self.multi_view_table_widget, "Orthogonal Views")

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

        # Create a dockable plotting canvas at the bottom of the napari window.

        # Add a plot widget.
        self.plot_widget_tree = FigureCanvas(Figure(figsize=(2, 1.5), dpi=150))
        self.ax = self.plot_widget_tree.figure.subplots()
        self.toolbar = NavigationToolbar(self.plot_widget_tree, self)
        for action_name in self.toolbar._actions: # change the icons to white for better visibility on dark napari background
            action = self.toolbar._actions[action_name]
            if len(action_name) > 0:
                icon_path = os.path.join(icon_root, action_name + ".png")
                action.setIcon(QIcon(icon_path))

        # Create a placeholder widget to hold the toolbar and graphics widget.
        graph_container = QWidget()
        graph_container.setMaximumHeight(500)
        graph_container.setLayout(QVBoxLayout())
        graph_container.layout().addWidget(self.toolbar)
        graph_container.layout().addWidget(self.plot_widget_tree)

        self.viewer.window.add_dock_widget(graph_container,name='Lineage Tree',area='bottom')

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
        self._update_plot()
   
    def _determine_label_plot_order(self) -> List[int]:
        """Determines the y-axis order of the tree plot, starting with labels for which the parent==0 (no parent known) at the top of the tree"""
        
        starting_points = self.parent_labels.loc[self.parent_labels['parent'] == 0, 'label']
        starting_points = [s for s in starting_points if s != 0]
        order = [l for l in starting_points if l > 1]

        # Find the children of each of the starting points, and work down the tree.
        while len(starting_points) > 0:
            children_list = []
            for l in starting_points:
                children = list(self.parent_labels.loc[self.parent_labels['parent'] == l, 'label'])
                for i, c in enumerate(children):
                    [children_list.append(c)]
                    order.insert(order.index(l) + i, c)
            starting_points = children_list

        return order

    def _update_plot(self) -> None:
        """Update the tree plot with all the annotated labels"""

        y_axis_order = self._determine_label_plot_order()
        if len(y_axis_order) > 0:
            plot_sub = self.label_df[self.label_df['label'].isin(y_axis_order)].copy() # keep only the labels that are in the y_axis_order, as these are manually added by the user.
            plot_sub.loc[:, 'y_axis_order'] = plot_sub.apply(lambda row: y_axis_order.index(row.label), axis=1)
            plot_sub.loc[:, 'cell'] = plot_sub.apply(lambda row: 'Cell ' + str(row.label).zfill(5), axis = 1)
            plot_sub.loc[:, 'label_color'] = plot_sub.apply(lambda row: matplotlib.colors.to_rgb(self.label_layer.get_color(row.label)), axis = 1)
            plot_sub = plot_sub.sort_values(by = 'y_axis_order', axis = 0)

            # Generate a 'tree' plot to show the hierarchy in the labels.
            self.ax.clear()
            self.ax.set_yticks(plot_sub['y_axis_order'])
            self.ax.set_yticklabels(plot_sub['cell'], fontsize = 8)

            for key, data in plot_sub.groupby('cell'):
                label = list(plot_sub.loc[plot_sub['cell'] == key, 'label'])[0]
                label_color = matplotlib.colors.to_rgb(self.label_layer.get_color(label))
                data.plot(x = 'time_point', y = 'y_axis_order', ax = self.ax, label = key, color = label_color, legend = None, linestyle ='-', marker = 'o')

            # Apply the same label colors also to the y axis labels
            for ytick, color in zip(self.ax.get_yticklabels(), plot_sub['label_color']):
                ytick.set_color(color)
            self.ax.set_ylabel('Cell')
            self.ax.set_xlabel("Time Point")
            self.plot_widget_tree.draw()

    def _get_label_colors(self) -> dict: 
        """Create a dictionary with the rgb colors for each label in self.parent_labels"""

        label_colors = {}
        for label in self.parent_labels['label'].unique():
            if label > 0:
                label_colors[label] = to_rgb(self.label_layer.get_color(label))
        
        return label_colors
    
    def _update_table_item_color(self, location: Tuple, label: int) -> None:
        """Request updating of the colors in the table widget"""

        color = to_rgb(self.label_layer.get_color(label))       
        self.table_widget._color_row(location, color)

    def _convert_label(self, all:bool) -> None:
        """Change the label value of a particular label to a new value from the current time point onwards (all is False) or for all time points (all is True)."""

        source_label = self.source_label_spin.value()
        target_label = self.target_label_spin.value()
        time_start = int(self.viewer.dims.current_step[0])
        
        # Update both the labels layer and the dataframe
        if all:
            self.label_layer.data[self.label_layer.data == source_label] = target_label
            self.label_df.loc[self.label_df['label'] == source_label, "label"] = target_label
        else:  
            self.label_layer.data[time_start:, :, :, :][self.label_layer.data[time_start:, :, :, :] == source_label] = target_label
            self.label_df.loc[(self.label_df['time_point'] >= time_start) & (self.label_df['label'] == source_label), "label"] = target_label

        # If the new label did not exist yet in the parent_labels dataframe, add it now.
        if not target_label in self.parent_labels['label'].values:
            self.parent_labels.loc[len(self.parent_labels.index)] = [target_label, 0]
            label_colors = self._get_label_colors()           
            self.table_widget._populate_table(self.parent_labels, label_colors)

        # Call plot update
        self._update_plot()
    
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
        """Update the current time point for all labels, and include the new one. Update parent_labels and the plot"""

        if label != 1: # label 1 is reserved for non-tracked labels
            labels = np.unique(np.append(np.unique(self.label_layer.data[self.viewer.dims.current_step[0]]), label)) # check which labels are currently present
            labels = [l for l in labels if l > 1]
            time_points = [time_point for l in labels]
            parents = [-1 for _ in labels] # set the parent to -1 as a placeholder only, it will be overwritten with the data from parent_labels upon saving.
            d = {'time_point': time_points, 'label': labels, 'parent': parents}
            df = pd.DataFrame(d)
            self.label_df = self.label_df.loc[self.label_df['time_point'] != time_point] # remove all rows for the current time point from the dataframe...
            self.label_df = pd.concat([self.label_df, df]) # ...to concatenate it with the updated data points at the current time point.

            # If the label was not yet in the dataframe, add it to the parent_labels dataframe with parent=0 (to be updated by the user)
            if not int(label) in self.parent_labels['label'].values:
                self.parent_labels.loc[len(self.parent_labels.index)] = [int(label), 0]
                label_colors = self._get_label_colors()           
                self.table_widget._populate_table(self.parent_labels, label_colors)

            self._update_plot()

    def _on_start(self) -> None:
        """Start the tracking procedure by loading all data and adding mouse callback"""

        self.cross.setChecked(False)
        self.cross.layer = None
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
            self.label_layer = self.viewer.add_labels(self._load_image_data(self.label_dir, self.label_files))
        else:
            # Create empty label files in this directory, so that they can be filled in by the user.
            label_data = []
            for i in range(self.raw_layer.data.shape[0]):
                empty_arr = np.zeros_like(self.raw_layer.data[0])
                tifffile.imwrite(os.path.join(self.label_dir, (os.path.basename(self.label_dir) + "_TP" + str(i).zfill(4) + ".tif")), empty_arr)
                label_data.append(empty_arr)
            self.label_layer = self.viewer.add_labels(np.stack(label_data, axis = 0), name = os.path.basename(self.label_dir))
            self.label_files = sorted([f for f in os.listdir(self.label_dir) if '.tif' in f])
       
        # Activate / deactivate the buttons.
        self.stopbtn.setEnabled(True)
        self.startbtn.setEnabled(False)
        self.edit_all_btn.setEnabled(True)
        self.edit_frame_btn.setEnabled(True)
        self.tab_widget.setCurrentIndex(0)
        self.table_widget._enable_editing()
        self.delete_row_btn.setEnabled(True)
        self.add_row_btn.setEnabled(True)
        self.savebtn.setEnabled(True)
        self.running = True

        # Load or create the label annotation dataframe.
        if os.path.exists(os.path.join(self.label_dir, 'LabelAnnotations.csv')):
            self.label_df = pd.read_csv(os.path.join(self.label_dir, 'LabelAnnotations.csv'))
            self.label_df['parent'] = self.label_df['parent'].astype(int)
            self.label_df['label'] = self.label_df['label'].astype(int)
        else:
            self.label_df = pd.DataFrame({'time_point': pd.Series(dtype = 'int'), 'label': pd.Series(dtype = 'int'), 'parent': pd.Series(dtype = 'int'), 'y_axis_order': pd.Series(dtype = 'int'), 'cell': pd.Series(dtype = 'str')})

        # Populate the parent_labels table widget.
        existing_labels = self.label_df[['label', 'parent']].drop_duplicates().sort_values(by = 'label', axis = 0)
        existing_labels = existing_labels[existing_labels['parent'] != -1]
        label_list = list(existing_labels['label'])
        parent_list = list(existing_labels['parent'])
        self.parent_labels = pd.DataFrame({'label': label_list, 'parent': parent_list})
        label_colors = self._get_label_colors()           
        self.table_widget._populate_table(self.parent_labels, label_colors)

        # If there are still previously existing labels, update the plot now. 
        if not self.label_df.empty:
            self._update_plot()

        # Add mouse click callback to fill bucket and paint brush events. 
        viewer = self.viewer
        @viewer.mouse_drag_callbacks.append
        def canvas_painted(viewer, event):
            if event.type == "mouse_press" and (self.label_layer.mode == "fill" or self.label_layer.mode == "paint"):
                tp = int(viewer.dims.current_step[0])
                current_label = self.label_layer.selected_label
                if self.running: 
                    self._update_labels(tp, current_label)

    def _save(self, stop=False) -> None:
        """Save the current labels layer and label dataframe"""
        
        if stop:
            self.stopbtn.setEnabled(False)
            self.startbtn.setEnabled(True)
            self.running = False
            self.table_widget._disable_editing()
            self.delete_row_btn.setEnabled(False)
            self.add_row_btn.setEnabled(False)
            self.savebtn.setEnabled(False)

        # Save all label image data.
        for i in range(self.label_layer.data.shape[0]):
            reconstructed_labels = self.label_layer.data[i, :, :, :]
            tifffile.imwrite(os.path.join(self.label_dir, self.label_files[i]), reconstructed_labels, bigtiff=True)

        # Merge the dataframe with the information from parent_labels and save dataframe and plot.
        self.parent_labels['parent'] = self.parent_labels['parent'].astype(int)
        result = pd.merge(self.label_df[['time_point', 'label']], self.parent_labels, on = 'label', how = 'left')
        result['parent'] = result['parent'].fillna(-1)
        print(result)
        result.to_csv(os.path.join(self.label_dir, 'LabelAnnotations.csv'), index = False)
        self.plot_widget_tree.figure.savefig(os.path.join(self.label_dir, 'LabelTracks.png'))