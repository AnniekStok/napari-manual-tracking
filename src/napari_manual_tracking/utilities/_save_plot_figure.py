from matplotlib import rcParams
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from PyQt5 import QtWidgets
import os

class CustomNavigationToolbar(NavigationToolbar2QT):
    def save_figure(self, *args):
        # Save the current figure appearance settings

        filetypes = self.canvas.get_supported_filetypes_grouped()
        sorted_filetypes = sorted(filetypes.items())
        default_filetype = self.canvas.get_default_filetype()

        startpath = os.path.expanduser(rcParams['savefig.directory'])
        start = os.path.join(startpath, self.canvas.get_default_filename())
        filters = []
        selectedFilter = None
        for name, exts in sorted_filetypes:
            exts_list = " ".join(['*.%s' % ext for ext in exts])
            filter = f'{name} ({exts_list})'
            if default_filetype in exts:
                selectedFilter = filter
            filters.append(filter)
        filters = ';;'.join(filters)

        fname, filter = QtWidgets.QFileDialog.getSaveFileName(
            self.canvas.parent(), "Choose a filename to save to", start,
            filters, selectedFilter)
        if fname:
            # Save dir for next time, unless empty str (i.e., use cwd).
            if startpath != "":
                rcParams['savefig.directory'] = os.path.dirname(fname)
            try:
                # Modify the appearance settings of existing axes
                current_axes = self.canvas.figure.gca()
                self.canvas.figure.patch.set_facecolor("white")
                current_axes.set_facecolor("white")
                current_axes.xaxis.label.set_color('black') 
                current_axes.yaxis.label.set_color('black') 
                current_axes.tick_params(axis = 'x', colors='black')
                print('current color for y axis labels', current_axes.yaxis.get_label().get_text())
                if current_axes.yaxis.get_label().get_text() != "Cell":
                    current_axes.tick_params(axis = 'y', colors='black')
                current_axes.spines["bottom"].set_color("black")
                current_axes.spines["top"].set_color("black")
                current_axes.spines["right"].set_color("black")
                current_axes.spines["left"].set_color("black")
                orig_size = self.canvas.figure.get_size_inches()
                self.canvas.figure.set_size_inches((9,4.5))

                # self.canvas.figure.set_size_inches(rcParams['figure.figsize'])
                self.canvas.figure.savefig(fname)

                # set back to original colors:
                self.canvas.figure.patch.set_facecolor("#262930")
                current_axes.set_facecolor("#262930")
                current_axes.xaxis.label.set_color('white') 
                current_axes.yaxis.label.set_color('white') 
                current_axes.tick_params(axis = 'x', colors='white')
                if current_axes.yaxis.get_label().get_text() != "Cell":
                    current_axes.tick_params(axis = 'y', colors='white')
                current_axes.yaxis.label.set_color('white') 
                current_axes.spines["bottom"].set_color("white")
                current_axes.spines["top"].set_color("white")
                current_axes.spines["right"].set_color("white")
                current_axes.spines["left"].set_color("white")
                self.canvas.figure.set_size_inches(orig_size)
            
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error saving file", str(e),
                    QtWidgets.QMessageBox.StandardButton.Ok,
                    QtWidgets.QMessageBox.StandardButton.NoButton)
