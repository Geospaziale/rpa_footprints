from qgis.PyQt.QtWidgets import QFileDialog, QDialog, QMessageBox
from .plugin_dialog_base import Ui_RPA_Footprints
from .rpa_footprints import footprints
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
import json
import os
import numpy as np

class MyPluginDialog(QDialog, Ui_RPA_Footprints):
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
        self.runButton.clicked.connect(self.generate_footprints)
        self.btninput_geojson.clicked.connect(self.select_input_geojson)
        self.btnplot3danimation.clicked.connect(self.plot_geojson_footprints)

        # Track the values in the visualise tab as they are changed
        self.height_slider.valueChanged.connect(self.update_footprint_plot)
        self.pitch_slider.valueChanged.connect(self.update_footprint_plot)
        self.yaw_slider.valueChanged.connect(self.update_footprint_plot)
        self.focallength_slider.valueChanged.connect(self.update_footprint_plot)
        self.sensor_width.textChanged.connect(self.update_footprint_plot)
        self.sensor_height.textChanged.connect(self.update_footprint_plot)
        self.image_width.textChanged.connect(self.update_footprint_plot)
        self.image_height.textChanged.connect(self.update_footprint_plot)

        # setup the geojson 3D plot
        self.plot_3d_fig = plt.figure()
        self.plot_3d = Canvas(self.plot_3d_fig)
        self.plotlayout_3d_2.addWidget(self.plot_3d)
        self.plot_ax_3d = self.plot_3d.figure.add_subplot(111, projection = '3d')
        self.plot_ax_3d.set_xlabel("X")
        self.plot_ax_3d.set_ylabel("Y")
        self.plot_ax_3d.set_zlabel("Z")
        self.plot_ax_3d.view_init(elev=30, azim=45)

        # Setup the simuluation plot
        #3D 
        self.canvas_3d = Canvas(Figure(figsize=(4, 4)))
        self.plotlayout_3d.addWidget(self.canvas_3d)
        self.ax_3d = self.canvas_3d.figure.add_subplot(111, projection = '3d')
        self.update_footprint_plot()


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

    def select_input_geojson(self):
        """ Open file dialog to select input geojson """
        options = QFileDialog.Options()
        filter = "GeoJSON Files (*.geojson)"
        file_name, _ = QFileDialog.getOpenFileName(self, "Open GeoJSON File", "", filter, options=options)
        if file_name:
            self.input_geojsonLine.setText(file_name)

    def update_footprint_plot(self):
        
        # Extract parameters from input values
        lat, lon = -35, 149 # default img location values for the plot
        easting, northing = 682516.0936188, 6125129.365233506 # corresponding projected coords for the img location
        height = self.height_slider.value()
        self.height_label.setText(f"Height (m): {height}")
        pitch = self.pitch_slider.value()
        self.pitch_label.setText(f"Pitch (°): {pitch}")
        yaw = self.yaw_slider.value()
        self.yaw_label.setText(f"Yaw (°): {yaw}")
        focal_length = self.focallength_slider.value()/10
        self.focal_length_label.setText(f"Focal length (mm): {focal_length}")
        sens_width = self.sensor_width.text()
        sens_height = self.sensor_height.text()
        img_width = self.image_width.text()
        img_height = self.image_height.text()
        if sens_width:
            try:
                sens_width = float(self.sensor_width.text())
            except:
                QMessageBox.information(self, "Invalid parameter", f"Sensor width must be a number")
        if sens_height:
            try:
                sens_height = float(self.sensor_height.text())
            except:
                QMessageBox.information(self, "Invalid parameter", f"Sensor height must be a number")
        if img_width:
            try:
                img_width = int(self.image_width.text())
            except:
                QMessageBox.information(self, "Invalid parameter", f"Image width must be a number")
        if img_height:
            try:
                img_height = int(self.image_height.text())
            except:
                QMessageBox.information(self, "Invalid parameter", f"Image height must be a number")
        try:
            gsd = footprints.calculate_gsd(height, pitch, focal_length, [sens_width, sens_height], [img_width, img_height])
        except:
            gsd = 'NA'
        self.gsd_label.setText(f"GSD (cm) = {gsd}")

        # Extract the footprints coords in UTM
        try:
            coords = footprints.img_footprint_coords(lat, 
                                                 lon, 
                                                 height, 
                                                 pitch, 
                                                 yaw, 
                                                 focal_length, 
                                                 [sens_width, sens_height], 
                                                 [img_width, img_height], 
                                                 return_all = True)
            coords_utm = coords['projected']
        except:
            coords_utm = None
        
        # Calculate area of footprint
        try:
            area = round(footprints.polygon_area(coords_utm),2)
        except:
            area = 'NA'
        self.area_label.setText(f"Area (m²) = {area}")

        # Update the 3D plot
        self.ax_3d.clear()
        self.ax_3d.set_title("Image footprint")
        try:
            # Extract the x and y coords seperately
            x = [coords_utm[0][0], coords_utm[1][0], coords_utm[2][0], coords_utm[3][0], coords_utm[0][0]]
            y = [coords_utm[0][1], coords_utm[1][1], coords_utm[2][1], coords_utm[3][1], coords_utm[0][1]]
            # normalise coords by the min x and min y
            x_min, y_min = min(x), min(y)
            x_norm = [value - x_min for value in x]
            y_norm = [value - y_min for value in y]
            img_x_norm, img_y_norm = easting - x_min, northing - y_min
            # Plot the image footprint at z = 0
            vertices = [list(zip(x_norm[:4], y_norm[:4], [0,0,0,0]))]
            poly = Poly3DCollection(vertices, color='blue', alpha=0.5, linewidths=2, edgecolors='r')
            self.ax_3d.add_collection3d(poly) # add filled footprint to plot
            self.ax_3d.scatter(img_x_norm, img_y_norm, height, c='red', marker='x', s=100) # image location at z = height
            # Plot lines from img location to each footprint corner
            for cx, cy, cz in vertices[0]: # cx = corner x coord etc
                self.ax_3d.plot([img_x_norm, cx], [img_y_norm, cy], [height, cz], color='black', linewidth=2)
            self.ax_3d.set_xlabel("X")
            self.ax_3d.set_ylabel("Y")
            self.ax_3d.set_zlabel("Z")
            self.ax_3d.view_init(elev=30, azim=45)
            self.canvas_3d.draw()
        except:
            self.ax_3d.text(0, 0, 0, "Error in footprint calculation", fontsize=12)
        self.canvas_3d.draw()

    def plot_geojson_footprints(self):
        self.plot_ax_3d.clear()
        
        # Open the GeoJSON and read the features
        file_path = self.input_geojsonLine.text()
        if not file_path and not '.geojson' in file_path:
            None
        else:    
            with open(file_path) as f:
                gj = json.load(f)
            features = gj['features']
            total = len(features) # total amount of features (footprints)

            # Loop through each feature extract the coords we need
            all_footprint_coords = []
            all_img_coords = []
            all_line_coords = []
            for feature in features:
                properties = feature['properties']
                coords_2d = properties['Coords_UTM']
                coords_3d = [[x, y, 0] for x, y in coords_2d] # coords in 3D at Z = 0
                img_x, img_y = properties['UTM Easting'], properties['UTM Northing'] # sensor location
                height = properties['Height']
                img_coords = [img_x, img_y, height]
                lines = [] # build a list of the lines to each corner
                for x,y,z in coords_3d:
                    lines.append([[img_x, x], [img_y, y], [height, z]])
                all_footprint_coords.append(coords_3d)
                all_img_coords.append(img_coords)
                all_line_coords.append(lines)

            # Create an array of all coords and set axis limits based on them
            all_footprint_coords_array = [np.array(footprint) for footprint in all_footprint_coords]

            # Set axis limits based on all polygons and img locations
            all_points = np.vstack(all_footprint_coords_array + all_img_coords)
            self.plot_ax_3d.set_xlim(np.min(all_points[:, 0]) - 10, np.max(all_points[:, 0]) + 10)
            self.plot_ax_3d.set_ylim(np.min(all_points[:, 1]) - 10, np.max(all_points[:, 1]) + 10)
            self.plot_ax_3d.set_zlim(np.min(all_points[:, 2]) - 10, np.max(all_points[:, 2]) + 10)

            # Store added collections so they persist
            footprint_frames = []
            img_pos_frames = []
            line_frames = []
            def init():
                return []
            def update(frame):
                if frame < len(all_footprint_coords_array):
                    # Remove previous footprints
                    for footprint in footprint_frames:
                        try:
                            footprint.remove()
                        except:
                            None
                    # Make previos img locations lighter
                    for img_frame in img_pos_frames:
                        img_frame.set_sizes([20])
                        img_frame.set_alpha(0.4)
                    # Make previous lines invisible
                    for line_frame in line_frames:
                        try:
                            line_frame[0].remove()
                        except:
                            None
                    
                    # Extract the things to plot
                    footprint = all_footprint_coords_array[frame]
                    img_coords = all_img_coords[frame]
                    lines_coords = all_line_coords[frame]
                    # Plot the footprint 
                    poly = Poly3DCollection([footprint], color='blue', alpha=0.5, linewidths=3, edgecolors = 'r')
                    self.plot_ax_3d.add_collection3d(poly) # plot the footprint
                    footprint_frames.append(poly)
                    # Plot the sensor position (img_coords)
                    img_plot = self.plot_ax_3d.scatter(img_coords[0], img_coords[1], img_coords[2], c='red', marker='x', s=60) # image location at z = height
                    img_pos_frames.append(img_plot)
                    # Plot the lines to the corner of each footprint
                    for line in lines_coords:
                        line_plot = self.plot_ax_3d.plot(line[0], line[1], line[2], color='black', linewidth=1)
                        line_frames.append(line_plot)
                    
                return footprint_frames, line_frames, img_pos_frames

            ani = FuncAnimation(self.plot_3d_fig, update, frames=total, init_func=init, blit=False, repeat=False)
            self.plot_3d_fig.show()
            self.plot_3d.draw()

    def generate_footprints(self):
        """ Run the plugin after user inputs are validated """
        # Initialise progress bar as 0%
        self.progressBar.setProperty("value", 0)
        
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
        footprints.generate_footprints(input_folder=input_folder, 
                                       output_folder=output_folder, 
                                       height=height, 
                                       pitch=pitch, 
                                       sens_dim=sens_dim, 
                                       keep_only_merged=self.checkbox_merge.isChecked(),
                                       progress_bar=self.progressBar)

        # Here, you would add the logic to process the data based on the input fields
        # For now, let's just simulate processing with a success message
        QMessageBox.information(self, "Footprints generated", f"Footprints have been generated and saved to: {output_folder}")
