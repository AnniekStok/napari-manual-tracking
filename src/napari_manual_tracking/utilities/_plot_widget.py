import os
from pathlib                            import Path 
from typing                              import List

import napari.layers

import matplotlib.pyplot                as plt
import pandas                           as pd
from typing import Literal

from matplotlib.colors                  import to_rgb
from matplotlib.backends.backend_qt5agg import FigureCanvas, NavigationToolbar2QT
from qtpy.QtWidgets                     import QHBoxLayout, QVBoxLayout, QWidget, QComboBox, QLabel, QRadioButton, QButtonGroup, QGroupBox
from qtpy.QtGui                         import QIcon

ICON_ROOT = Path(__file__).parent / "icons"

class PlotWidget(QWidget):
    """Customized plotting widget class.

    Intended for interactive plotting of features in a pandas dataframe (props) belonging to a labels layer (labels).
    """

    def __init__(self, props: pd.DataFrame, labels: napari.layers.Labels):
        super().__init__()

        self.labels = labels
        self.props = props
        self.cmap = self.labels.colormap

        # Main plot.
        self.fig = plt.figure(constrained_layout=True)
        self.plot_canvas = FigureCanvas(self.fig)
        self.ax = self.plot_canvas.figure.subplots()
        self.toolbar = NavigationToolbar2QT(self.plot_canvas)

        # Specify plot customizations.
        self.fig.patch.set_facecolor("#262930")
        self.ax.tick_params(colors='white')
        self.ax.set_facecolor("#262930")
        self.ax.xaxis.label.set_color('white') 
        self.ax.yaxis.label.set_color('white') 
        self.ax.spines["bottom"].set_color("white")
        self.ax.spines["top"].set_color("white")
        self.ax.spines["right"].set_color("white")
        self.ax.spines["left"].set_color("white")
        for action_name in self.toolbar._actions:
            action=self.toolbar._actions[action_name]
            icon_path = os.path.join(ICON_ROOT, action_name + ".png")
            action.setIcon(QIcon(icon_path))

        # Create a dropdown window for selecting what to plot on the axes.
        x_axis_layout = QHBoxLayout()
        self.x_combo = QComboBox()
        self.x_combo.addItems([item for item in self.props.columns if item not in ('index', 'label', 'parent')])
        self.x_combo.setCurrentText('time_point')
        x_axis_layout.addWidget(QLabel('x-axis'))
        x_axis_layout.addWidget(self.x_combo)

        y_axis_layout = QHBoxLayout()
        self.y_combo = QComboBox()
        self.y_combo.addItems([item for item in self.props.columns if item not in ('index', 'label', 'parent')])
        self.y_combo.setCurrentText('cell')
        y_axis_layout.addWidget(QLabel('y-axis'))
        y_axis_layout.addWidget(self.y_combo)

        self.x_combo.currentIndexChanged.connect(self._update_plot)
        self.y_combo.currentIndexChanged.connect(self._update_plot)

        color_group_layout = QHBoxLayout()
        self.group_combo = QComboBox()
        self.group_combo.addItems([item for item in self.props.columns if item not in ('index', 'parent')])
        self.group_combo.setCurrentText('label')

        self.group_combo.currentIndexChanged.connect(self._update_plot)
        color_group_layout.addWidget(QLabel('Group color'))
        color_group_layout.addWidget(self.group_combo)

        dropdown_layout = QVBoxLayout()
        dropdown_layout.addLayout(x_axis_layout)
        dropdown_layout.addLayout(y_axis_layout)
        dropdown_layout.addLayout(color_group_layout)

        dropdown_groupbox = QGroupBox('Choose Axes')
        dropdown_groupbox.setLayout(dropdown_layout)
        dropdown_groupbox.setMaximumHeight(110)

        # Add radio buttons for three display modes: 'show all cells', 'show tracked cells', 'show lineage'
        button_group = QButtonGroup()

        self.show_all_radio = QRadioButton('All cells')
        self.show_all_radio.setChecked(True)  # Set the default option
        button_group.addButton(self.show_all_radio)
        self.show_tracked_radio = QRadioButton('Tracked cells')
        button_group.addButton(self.show_tracked_radio)
        self.show_lineage_radio = QRadioButton('Lineage')
        button_group.addButton(self.show_lineage_radio)
        self.show_loose_radio = QRadioButton('Loose ends')
        button_group.addButton(self.show_loose_radio)

        self.show_all_radio.clicked.connect(self._update_plot)
        self.show_tracked_radio.clicked.connect(self._update_plot)
        self.show_lineage_radio.clicked.connect(self._update_plot)
        self.show_loose_radio.clicked.connect(self._update_plot)
        self.show_all_radio.clicked.connect(self._update_plot_option)
        self.show_tracked_radio.clicked.connect(self._update_plot_option)
        self.show_lineage_radio.clicked.connect(self._update_plot_option)
        self.show_loose_radio.clicked.connect(self._update_plot_option)
    
        radiobutton_layout = QVBoxLayout()
        radiobutton_layout.addWidget(self.show_all_radio)
        radiobutton_layout.addWidget(self.show_tracked_radio)
        radiobutton_layout.addWidget(self.show_lineage_radio)
        radiobutton_layout.addWidget(self.show_loose_radio)

        radiobutton_groupbox = QGroupBox("Display")
        radiobutton_groupbox.setLayout(radiobutton_layout)
        radiobutton_groupbox.setMaximumHeight(170)

        # combine radio buttons and dropdown
        option_layout = QVBoxLayout()
        option_layout.addWidget(radiobutton_groupbox)
        option_layout.addWidget(dropdown_groupbox)

        # Create and apply a vertical layout for the toolbar and canvas.
        plotting_layout = QVBoxLayout()
        plotting_layout.addWidget(self.toolbar)
        plotting_layout.addWidget(self.plot_canvas)

        # combine all layouts
        plot_option_layout = QHBoxLayout()
        plot_option_layout.addLayout(option_layout)
        plot_option_layout.addLayout(plotting_layout)

        self.setLayout(plot_option_layout)
                   
        # Update the plot in case the user uses the "Show Selected Label" option in the labels menu.
        self.labels.events.show_selected_label.connect(self._update_plot_option)
        self.labels.events.show_selected_label.connect(self._update_plot)

    def _get_lineage_data(self, mode: Literal['all', 'tracked', 'lineage', 'selected', 'loose'] = 'all') -> pd.DataFrame:
        """Generate a new pandas dataframe containing the data to be plotted, depending on the 'mode', and with a new column for the colors and the y-axis order."""

        parent_labels = self.props[['label', 'parent']].copy().drop_duplicates()

        if mode == 'all':
            y_axis_order = sorted(self.props['label'].unique())

        if mode == 'selected':
            y_axis_order = [self.labels.selected_label]
        
        if mode == 'loose':
            starting_points = parent_labels.loc[parent_labels['parent'] == -1, 'label']
            y_axis_order = sorted([s for s in starting_points])
        
        if mode == 'tracked':
            # plot all the tracked lineages starting with a parent = 0 label. 
            starting_points = parent_labels.loc[parent_labels['parent'] == 0, 'label'] # find all the labels that have a parent = 0 to find the origins of the tracks
            y_axis_order = self._determine_label_plot_order(parent_labels, starting_points) 
        
        if mode == 'lineage':
            current_label = self.labels.selected_label
            try: 
                parent = parent_labels.loc[parent_labels['label'] == current_label, 'parent'].iloc[0]
                print(parent)
            except IndexError:
                print('this label does not exist in parent labels')
                return pd.DataFrame({'time_point': pd.Series(dtype = 'int'), 'label': pd.Series(dtype = 'int'), 'parent': pd.Series(dtype = 'int'), 'cell': pd.Series(dtype = 'str'), 'y_axis_order': pd.Series(dtype = 'int'), 'label_color': pd.Series(dtype = 'object')})
            
            # first work up the tree to find the earliest ancestor
            if parent == -1:
                print('this label has not been tracked yet and therefore does not belong to a lineage')
                return pd.DataFrame({'time_point': pd.Series(dtype = 'int'), 'label': pd.Series(dtype = 'int'), 'parent': pd.Series(dtype = 'int'), 'cell': pd.Series(dtype = 'str'), 'y_axis_order': pd.Series(dtype = 'int'), 'label_color': pd.Series(dtype = 'object')})
            elif parent == 0:
                y_axis_order = self._determine_label_plot_order(parent_labels, [current_label])      
            else: 
                print('searching parents...')
                while parent > 0:
                    new_parent = parent_labels.loc[parent_labels['label'] == parent, 'parent'].iloc[0]
                    print('new parent', new_parent)
                    if (new_parent == 0) or (new_parent == -1) :
                        break
                    else:
                        parent = new_parent
                y_axis_order = self._determine_label_plot_order(parent_labels, [parent])      
      
        plotting_data = self.props[self.props['label'].isin(y_axis_order)].copy() # keep only the labels that are in the y_axis_order.
        plotting_data['y_axis_order'] = plotting_data['label'].apply(lambda label: y_axis_order.index(label))
        plotting_data.loc[:, 'cell'] = plotting_data.apply(lambda row: 'Cell ' + str(int(row.label)).zfill(5), axis = 1)
        plotting_data.loc[:, 'label_color'] = plotting_data.apply(lambda row: to_rgb(self.cmap.map(row.label)), axis = 1)
        plotting_data = plotting_data.sort_values(by = 'y_axis_order', axis = 0)

        return plotting_data

    def _determine_label_plot_order(self, parent_labels: pd.DataFrame, starting_points: List[int]) -> List[int]:
        """Determines the y-axis order of the tree plot, from the starting points downward"""
        
        y_axis_order = [s for s in starting_points]

        # Find the children of each of the starting points, and work down the tree.
        while len(starting_points) > 0:
            children_list = []
            for l in starting_points:
                children = list(parent_labels.loc[parent_labels['parent'] == l, 'label'])
                for i, c in enumerate(children):
                    [children_list.append(c)]
                    y_axis_order.insert(y_axis_order.index(l) + i, c)
            starting_points = children_list

        return y_axis_order
    
    def _update_plot_option(self) -> None: 
        """conditionally specify whether to bind or not to bind to selected_label event"""
        if self.labels.show_selected_label or self.show_lineage_radio.isChecked(): 
            print('turn on listening to selected label')
            self.labels.events.selected_label.connect(self._update_plot)
        else: 
            print('turn off listening to selected label')
            self.labels.events.selected_label.disconnect(self._update_plot)

    def _update_plot(self) -> None:
        """Update the plot by plotting the features selected by the user. 

        In the case the 'label' column is selected as group, apply the same colors as in the labels layer to the scatter points.
        In the case time is on the x-axis and the 'label' column is selected as group, connect data points with a line. 
        In the case the user has clicked the 'Show selected label' option and the group is set to 'label', plot only the points belonging to that label. 
        In the case any other feature than 'label' is selected for the group, apply a continuous colormap instead.      
        """

        print('call to update plot!')
        x_axis_property = self.x_combo.currentText()
        y_axis_property = self.y_combo.currentText()
        group = self.group_combo.currentText()

        # Clear data points, and reset the axis scaling and labels.
        for artist in self.ax.lines + self.ax.collections:
            artist.remove()
        self.ax.set_xlabel(x_axis_property)
        self.ax.set_ylabel(y_axis_property)
        self.ax.relim()  # Recalculate limits for the current data
        self.ax.autoscale_view()  # Update the view to include the new limits
           
        # Subset the dataframe in the case the user wants to see the selected label or the tracked labels only
        if self.labels.show_selected_label:
            print('show the selected label')
            plotting_data = self._get_lineage_data(mode = 'selected')
        elif self.show_loose_radio.isChecked():
            print('show loose ends only!')
            plotting_data = self._get_lineage_data(mode = 'loose')
        elif self.show_tracked_radio.isChecked(): 
            print('show the tracked labels only!')
            plotting_data = self._get_lineage_data(mode = 'tracked')
        elif self.show_lineage_radio.isChecked(): 
            plotting_data = self._get_lineage_data(mode = 'lineage')
            print('show lineage only!')
        else:
            plotting_data = self._get_lineage_data(mode = 'all')
        
        if group == 'label':
            # In case time is plotted on the x-axis, it makes sense to connect data points with a line, and order the data points based on parent-child relationships
            if x_axis_property == "time_point" and y_axis_property == "cell" and 'parent' in plotting_data:
                                
                unique_labels = plotting_data['label'].unique()

                # Generate a 'tree' plot to show the hierarchy in the labels.
                self.ax.clear()
                self.ax.set_yticks(plotting_data['y_axis_order'])
                self.ax.set_yticklabels(plotting_data['cell'], fontsize = 8)

                # Connect the points for each label
                for label in unique_labels:
                    label_data = plotting_data[plotting_data['label'] == label]
                    color = label_data['label_color'].iloc[0]  # Get the color corresponding to the label
                    self.ax.plot(label_data['time_point'], label_data['y_axis_order'], linestyle='-', marker='o', color=color, label=label)

                # Apply the same label colors also to the y axis labels
                for ytick, color in zip(self.ax.get_yticklabels(), plotting_data['label_color']):
                    ytick.set_color(color)

                self.ax.set_ylabel('Cell')
                self.ax.set_xlabel("Time Point")
                self.ax.xaxis.label.set_color('white') 
                self.ax.yaxis.label.set_color('white') 
              
            else:   
                # Group by label and assign the corresponding label colors to the data points                     
                self.ax.clear()   
                unique_labels = plotting_data['label'].unique()
                label_colors_dict = {label: to_rgb(self.cmap.map(label)) for label in unique_labels}

                for label in unique_labels:
                    label_data = plotting_data[plotting_data['label'] == label]
                    color = label_colors_dict[label]
                    label_data = label_data.sort_values(by=x_axis_property)
                    self.ax.plot(label_data[x_axis_property], label_data[y_axis_property], linestyle='-', marker='o', color=color, label=label)
                
                self.ax.set_ylabel(y_axis_property)
                self.ax.set_xlabel(x_axis_property)
                self.ax.xaxis.label.set_color('white') 
                self.ax.yaxis.label.set_color('white')                         
   
        else:
            # Plot data points on a continuous colormap.
            self.ax.legend().remove()
            self.ax.scatter(self.props[x_axis_property], self.props[y_axis_property], c=self.props[group], cmap="summer", s = 10)
            self.ax.legend(loc='upper left', bbox_to_anchor=(1, 1), framealpha=0.2, edgecolor='white', labelcolor='w', frameon=True)

            
        self.plot_canvas.draw()