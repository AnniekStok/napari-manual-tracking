from qtpy.QtWidgets import QGroupBox, QVBoxLayout, QDoubleSpinBox, QLabel, QWidget

class VoxelDimensionWidget(QWidget):
    """Voxel dimension widget
    
    Lets the user specify voxel dimensions using double spin boxes
    """
    
    def __init__(self):  
        super().__init__()  
           
        main_layout = QVBoxLayout()
        voxel_dimension_box = QGroupBox('Voxel dimensions')
        voxel_dimension_layout = QVBoxLayout()

        self.x_spin = QDoubleSpinBox()
        self.y_spin = QDoubleSpinBox()
        self.z_spin = QDoubleSpinBox()

        self.x_spin.setValue(1.0)
        self.y_spin.setValue(1.0)
        self.z_spin.setValue(1.0)

        voxel_dimension_layout.addWidget(QLabel('Z (µm):'))
        voxel_dimension_layout.addWidget(self.z_spin)
        voxel_dimension_layout.addWidget(QLabel('Y (µm):'))
        voxel_dimension_layout.addWidget(self.y_spin)
        voxel_dimension_layout.addWidget(QLabel('X (µm):'))
        voxel_dimension_layout.addWidget(self.x_spin)

        voxel_dimension_box.setLayout(voxel_dimension_layout)
        main_layout.addWidget(voxel_dimension_box)
        self.setLayout(main_layout)