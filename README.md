# rpa_footprints

#### Simple QGIS plugin to generate footprint polygons from drone images.

This plugin allows you to input a folder of drone images collected with a drone or Remotely Piloted Aircraft (RPA) and estimate the approximate footprint area of each image based upon the metadata contained in the EXIF tags of each image. A footprint is essentially a polygon representing the approximate area sampled by an image on the ground. The Phil Harvey ExifTool is used in this plugin to extract EXIF tags for images: https://github.com/exiftool/exiftool. 

Caveats:
- Currently only working for DJI drones, but sensor dimensions have not be added for all sensors. You can manually specify sensor dimensions in the advanced options though.
- This plugin assumes a flat earth, meaning footprints won't be accurate if they are collected on non-flat terrain. The more sophisticated repo from spifftek70 allows you to warp footprints with a terrain model for images on undulating terrain: https://github.com/spifftek70/Drone-Footprints
- The code will attempt to read 

---

## Installation

To install the plugin, download the .zip file of the repo and install it through the QGIS plugin manager. It has several depencies which should be installed when the plugin is loaded for the first time. A copy of the Phil Harvey ExifTool is included within the plugin to handle image metadata extraction.


---

## Usage

### Generate footprints for a folder

The plugin requires you to select and input folder containing all the images, and an output folder where the footprints will be exported to. There are advanced options if you want to manually enter your own parameters. These parameters are applied to EVERY image in the input folder if you use them.

Advanced options:
- Height (m): Height in metres of drone images above the ground level
- Sensor Width (mm): Width of the sensor in millimetres
- Sensow Height (mm): Height of the sensor in millimetres
- Gimbal Pitch (degrees): Pitch of the gimbal. Must be between 0 and -90 degrees. A pitch of -90 degrees meanings the sensor is pointing directly downwards (nadir)

![](images/interface.PNG)

The footprints are exported to geojson files in the output folder, with each footprint having a number of attributes taken from the image metadata.

### Visualise 

For fun, you can use the temporal controller in QGIS to visualise how the images were collected in real time.


