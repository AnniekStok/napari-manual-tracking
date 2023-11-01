from qtpy.QtWidgets import QGroupBox, QVBoxLayout, QCheckBox

class featuresCheckboxWidget():
    def __init__(self):
        # create a dictionary to store the checkbox state for each property
        self.properties = [ 
        {'prop_name': 'voxel_count',        'display_name': 'Voxel count',    'selected': False, 'enabled': True},
        {'prop_name': 'volume',             'display_name': 'Volume',         'selected': False, 'enabled': True},
        {'prop_name': 'sphericity',         'display_name': 'Sphericity',     'selected': False, 'enabled': True},
        {'prop_name': 'axes',               'display_name': 'Axes radii',     'selected': False, 'enabled': True},
        {'prop_name': 'eccentricity',       'display_name': 'Eccentricity',   'selected': False, 'enabled': True}
        ]
        
        self.checkbox_state = {prop['prop_name']: prop['selected'] for prop in self.properties}
        self.checkbox_box = QGroupBox('Select Properties')
        checkbox_layout = QVBoxLayout()

        self.checkboxes = []
        # create checkboxes for each property
        for prop in self.properties:
            checkbox = QCheckBox(prop['display_name'])
            checkbox.setEnabled(prop['enabled'])
            checkbox.setStyleSheet("QCheckBox:disabled { color: grey }")
            checkbox.setChecked(self.checkbox_state[prop['prop_name']])
            checkbox.stateChanged.connect(lambda state, prop=prop: self.checkbox_state.update({prop['prop_name']: state == 2}))
            self.checkboxes.append({'prop_name': prop['prop_name'], 'checkbox': checkbox})
            checkbox_layout.addWidget(checkbox)

        self.checkbox_box.setLayout(checkbox_layout)
