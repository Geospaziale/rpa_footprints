from qgis.PyQt.QtWidgets import QFileDialog, QDialog, QMessageBox
from .plugin_dialog_base import Ui_MyPluginDialog

class MyPluginDialog(QDialog, Ui_MyPluginDialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # Initially hide advanced options
        self.advancedOptionsGroup.setVisible(False)

        # Connect the button to toggle the visibility of advanced options
        self.btnToggleAdvancedOptions.clicked.connect(self.toggle_advanced_options)

        # Connect the browse buttons to their respective folder selectors
        self.btnInputFolder.clicked.connect(self.select_input_folder)
        self.btnOutputFolder.clicked.connect(self.select_output_folder)
        self.runButton.clicked.connect(self.run_plugin)

    def toggle_advanced_options(self):
        """ Toggle visibility of advanced options """
        is_visible = self.advancedOptionsGroup.isVisible()
        if is_visible:
            self.advancedOptionsGroup.setVisible(False)
            self.btnToggleAdvancedOptions.setText("Show Advanced Options")
        else:
            self.advancedOptionsGroup.setVisible(True)
            self.btnToggleAdvancedOptions.setText("Hide Advanced Options")

    def select_input_folder(self):
        """ Open file dialog to select input folder """
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.inputFolderLine.setText(folder)

    def select_output_folder(self):
        """ Open file dialog to select output folder """
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.outputFolderLine.setText(folder)

    def run_plugin(self):
        """ Run the plugin after user inputs are validated """
        # Get the input values from the UI fields
        input_folder = self.inputFolderLine.text()
        output_folder = self.outputFolderLine.text()

        # Validate that the required fields (Input and Output folders) are filled
        if not input_folder or not output_folder:
            QMessageBox.warning(self, "Missing Required Fields", "Input and Output folders are required.")
            return

        # Optional fields (set to None if not provided)
        height = self.heightLine.text() or None
        if height:
            height = float(height)
        sensor_width = self.sensorWidthLine.text() or None
        sensor_height = self.sensorHeightLine.text() or None
        sens_dim = None
        if sensor_width and sensor_height:
            sens_dim = [float(sensor_width), float(sensor_height)]
        pitch = self.gimbalPitchLine.text() or None
        if pitch:
            pitch = float(pitch)
            if pitch >= 0 or pitch < -90:
                QMessageBox.information(self, "Invalid parameter", f"Selected pitch of '{pitch}' is invalid. The input gimbal pitch must be between 0 and -90 degrees.")
                raise ValueError(f"Selected pitch of '{pitch}' is invalid. The input gimbal pitch must be between 0 and -90 degrees.")
        
        # Generate footprints for the input folder
        from .rpa_footprints import footprints
        footprints.generate_footprints(input_folder=input_folder, 
                                       output_folder=output_folder, 
                                       height=height, 
                                       pitch=pitch, 
                                       sens_dim=sens_dim, 
                                       keep_only_merged=True)

        # Here, you would add the logic to process the data based on the input fields
        # For now, let's just simulate processing with a success message
        QMessageBox.information(self, "Footprints generated", f"Footprints have been generated and saved to: {output_folder}")
