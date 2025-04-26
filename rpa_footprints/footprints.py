### NOTES
### - noticed the gimbal yaw was zero for all photos in a mavic 3 mini mission but the flight yaw seemed corrected - check if this is consistent with other DJI EXIF tags or check
###   whether we have to add the Flight Yaw to the Gimbal Yaw to get the actual yaw of the camera

'''
Code to generate image footprints from individual drone images using their EXIF metadata.
Based off code given by Houska in forum: https://gis.stackexchange.com/questions/384756/georeference-single-drone-image-from-exif-data
There is an existing Python repositry for generating footprints and georeferencing invidivual images which is more robust than this: https://github.com/spifftek70/Drone-Footprints

Assumptions:
    - Flat terrain
    - Height above takeoff is equivalent to height above ground level (otherwise height can be manually set)

Limitations:
    - Only works on flat terrain - you would otherwise require an accurate DTM (Digital Terrain Model) to adjust the footprint to what is actually visible on non-flat ground (not coded)
    - Accuracy of footprints severely decreases with oblique photos (non-nadir photos which aren't point directly downwards)
    - Footprints are set to an arbitrary max size for photos which sample the horizon as the size would otherwise be ginourmous and affected by the Earth's curvature
'''
import csv
import subprocess
import geopandas as gpd
import geojson
import math
import os
import pytz
import re
import utm
from datetime import datetime
from shapely.geometry import Polygon, mapping
from timezonefinder import TimezoneFinder
from mpl_toolkits.mplot3d import Axes3D

# Permissable image extensions for footprint generation
img_extensions = ['jpg', 'jpeg', 'tif', 'tiff', 'iiq']

# List of sensor dimensions (in millimetres) for drones using their intrustment EXIF tags - sensor dimensions are not recorded in EXIF data
sensor_dimensions_list = {'m3e': [17.3, 13],
                          'ZenmuseP1': [35.9, 24],
                          'iXM-GS120': [0,0],
                          'FC3682': [9.7, 7.3]                     
        }

# Find the EXIF tool location
try:
    exiftool_exe = os.path.join(os.path.dirname(os.path.dirname(__file__)),'external', 'exiftool_13_16_64', 'exiftool.exe')
except:
     raise ValueError('Could not located EXIF tool path in the plugin folder. Unable to proceed.')

# Extract EXIF tags for a folder of images to an output csv
def extract_exif_csv(input_folder: str, output_exif_csv: str):
    '''
    Description: Function to generate an exif csv from an input folder by calling the Phil Harvey exif tool from cmd line.
    
    Parameters:
        - input_folder : Path to the input folder
        - output_exif_csv : Path to the output csv
    '''
    # Generate the command string
    cmd = exiftool_exe + ' -csv ' + '"' + input_folder + '"' + ' > ' + '"' + output_exif_csv + '"'
    # Run the command and capture the result (result.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    # Raise error if no images found
    if result.stderr == 'No matching files\n':
        raise ValueError('Could not find any recognised image types in the input folder.')
    return result.stderr

# Extract metadata from input exif csv to a dictionary
def create_exif_dict(input_exif_csv: str):
    '''
    Description: Function to generate convert exif csv into a list with each row as a dictionary with all the data for the image. This contains
    every bit of information associated with the image (not just the required metadata for the populating the names).
    Parameters:
        - input_exif_csv : Path to the exif csv generate using extract_exif_csv
    Notes:
        - You can extract a single dictionary from this by subsetting the result of this e.g. dict_single = exif_dict[0] - the first entry
    '''
    # Initialize an empty list
    data_dict = []
    # Open the CSV
    with open(input_exif_csv, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)  # This will read the CSV into dictionaries
        # Loop through each row and add it as a dictionary to the data_dict list
        for row in reader:
            data_dict.append(row)
    return data_dict

# Extract utc time using lat + lon (only used if utc time not found in exif data)
tf = TimezoneFinder()
def get_utc(lat: float, lon: float, local_time_str: str, tf):
    ''' tf is TimezoneFinder() - this is done outside this function as it slow to do it for every image in a loop '''
    # Find the timezone at the given location
    timezone_str = tf.timezone_at(lat=lat, lng=lon)
    if timezone_str is None:
        raise ValueError("Could not determine the timezone for the given location.")
    local_time = datetime.strptime(local_time_str, "%Y:%m:%d %H:%M:%S")
    # Localize the time to the timezone
    local_tz = pytz.timezone(timezone_str)
    localized_time = local_tz.localize(local_time)
    # Convert to UTC
    utc_time = localized_time.astimezone(pytz.utc)
    return utc_time

# Convert a DMS (degrees, minutes, seconds) string to decimal degress
def dms_to_decimal(dms_str: str):
       # Extract deg, mins and secs using re
        deg_match = re.search(r'([\d.]+)\s*deg', dms_str, re.IGNORECASE)
        min_match = re.search(r'([\d.]+)\s*\'', dms_str)
        sec_match = re.search(r'([\d.]+)\s*\"', dms_str)
        dir_match = re.search(r'[NSWE]', dms_str)
        if not deg_match or not min_match or not sec_match or not dir_match:
            raise ValueError(f"Invalid DMS format: {dms_str}")
        degrees = float(deg_match.group(1))
        minutes = float(min_match.group(1))
        seconds = float(sec_match.group(1))
        direction = dir_match.group(0).upper()  # Get N/S/E/W
        #Convert to decimal degrees
        decimal = degrees + (minutes / 60) + (seconds / 3600)
        # S and W should be -ve
        if direction in ['S', 'W']:
            decimal = -decimal
        return decimal

# Simple function to calculate GSD in cm
def calculate_gsd(height: float, pitch: float, focal_length: float, sens_dim: list, img_dim: list):
    ONA = math.radians(float(90 + pitch)) # off-nadir angle in radians
    distance = height / math.cos(ONA)
    gsd = round(100*(distance * sens_dim[0]) / (focal_length * img_dim[0]),3)
    if gsd > 9999 or gsd <= 0:
        gsd = 'NA' # set large gsd's to infinity (when sampling the horizon at high off-nadir angles)
    return gsd

# Function to extract the approx footprint of an image
''' this function will freak out if it samples the horizon (e.g. at high oblique angles) since it assumes a flat earth '''
def img_footprint_coords(lat: float, lon: float, height: float, pitch: float, yaw: float, focal_length: float, sens_dim: list, img_dim: list, return_utm:bool = False):
    '''
    Description:
        - Estimates the footprint coordinates of a drone image based on drone image and sensor metadata.
    Parameters:
        - lat : latitude in decimal degrees
        - lon : longitude in decimal degrees
        - pitch : gimbal pitch in degrees (90 is straight down)
        - yaw : yaw of the sensor with respect to north (e.g. yaw = 0 means camera is facing grid north)
        - focal_length : focal length of the sensor in millimetres
        - sens_dim : list of the sensor dimensions in width and height e.g. sens_dim = [35.9, 24] < 35.9mm x 24mm (Zenmuse P1)
        - img_dim : list of the image dimensions in pixels e.g. img_dim = [4000, 2250]
    Optionals:
        - return_utm : returns in the coordinates in UTM rather than latitude and longitude (e.g. for plotting). NOTE that it returns in eastings and northings this way (e.g. x,y) rather than lat (y), lon (x)
    Output:
        - coords: list of lists
        Output is in the following format in lat (y), lon (x):
        [[BLy, BLx], [TLy, TLx], [TRy, TRx], [BRy, BRx]]
        where BL is bottom left, TR is top right, etc.
    '''
    
    # Extract required camera parameters
    utm_output = utm.from_latlon(lat, lon)
    CamX, CamY = utm_output[0], utm_output[1]  # Camera coords in projected CRS
    zone, utm_letter = utm_output[2], utm_output[3]
    A = height  # the height AGL (m)
    pitch = math.radians(-pitch)  # pitch in radians
    if pitch == 0:
        pitch = 1  # to deal with camera pointing directly at the horizon (0)
    dir = math.radians(yaw)  # the azimuth in radians
    Cf = focal_length  # camera focal length in mm
    SX = float(sens_dim[0])  # sensor width in mm
    SY = float(sens_dim[1])  # sensor height in mm
    img_width = float(img_dim[0])
    img_height = float(img_dim[1])
    aspect = img_width / img_height  # aspect ratio
    Sd = math.sqrt(SX**2 + SY**2)  # sensor diagonal in mm
    
    # Calculations for field of view
    ratXh = SX / Cf / 2  # ratio of sensor half-width to focal length (at image center)
    ratYh = SY / Cf / 2  # ratio of sensor half-height to focal length (at image center)
    ccf = math.sqrt(1 + (ratYh ** 2))  # "corner correction factor" due to sensor crop
    
    # Half FOV angles in radians at image center
    phiXh = math.atan(ratXh)
    phiYh = math.atan(ratYh)
    
    # Ground distances of the camera projection to the image
    Kc = A / math.tan(pitch + phiYh)  # ground distance at image center
    Kf = A / math.tan(pitch + phiYh)  # ground distance at front of image
    Kb = A / math.tan(pitch - phiYh)  # ground distance at back of image
    
    Rc = math.sqrt(A**2 + Kc**2)  # full distance, hypotenuse of ground distance and altitude triangle
    Rf = math.sqrt(A**2 + Kf**2)
    Rb = math.sqrt(A**2 + Kb**2)
    
    # 1/2 width of frame in ground coordinates, at center, front, back
    Wch = Rc * ratXh  # center width
    Wfh = Rf * ratXh  # front width
    Wbh = Rb * ratXh  # back width
    
    # Ground coordinates of the image corners
    Centre_W, Centre_K = 0, Kc
    BR_K = BL_K = Kf
    TR_K = TL_K = Kb
    BL_W, BR_W = Wfh, -Wfh
    TL_W, TR_W = Wbh, -Wbh

    # Now apply rotation (azimuth) to the coordinates
    centre_x = CamX + (Centre_W * math.cos(dir)) + (Centre_K * math.sin(dir))
    centre_y = CamY - (Centre_W * math.sin(dir)) + (Centre_K * math.cos(dir))
    
    BR_x = CamX + (BR_W * math.cos(dir)) + (BR_K * math.sin(dir))
    BR_y = CamY - (BR_W * math.sin(dir)) + (BR_K * math.cos(dir))
    
    BL_x = CamX + (BL_W * math.cos(dir)) + (BL_K * math.sin(dir))
    BL_y = CamY - (BL_W * math.sin(dir)) + (BL_K * math.cos(dir))
    
    TR_x = CamX + (TR_W * math.cos(dir)) + (TR_K * math.sin(dir))
    TR_y = CamY - (TR_W * math.sin(dir)) + (TR_K * math.cos(dir))
    
    TL_x = CamX + (TL_W * math.cos(dir)) + (TL_K * math.sin(dir))
    TL_y = CamY - (TL_W * math.sin(dir)) + (TL_K * math.cos(dir))
    
    # Convert to latitude/longitude
    coords_x = [BR_x, BL_x, TL_x, TR_x]
    coords_y = [BR_y, BL_y, TL_y, TR_y]
    
    coords_lat = [utm.to_latlon(x, y, zone, utm_letter)[0] for x, y in zip(coords_x, coords_y)]
    coords_lon = [utm.to_latlon(x, y, zone, utm_letter)[1] for x, y in zip(coords_x, coords_y)]
    
    # Create the final coordinates list (BL, TL, TR, BR order)
    if not return_utm: # return in geographic by default
        coords = [[coords_lat[1], coords_lon[1]], 
                [coords_lat[2], coords_lon[2]], 
                [coords_lat[3], coords_lon[3]], 
                [coords_lat[0], coords_lon[0]]]
    else: # return projected UTM coords if return_utm == True
        coords = [[coords_x[1], coords_y[1]], 
                [coords_x[2], coords_y[2]], 
                [coords_x[3], coords_y[3]], 
                [coords_x[0], coords_y[0]]]
        
    return coords

# Calculate the area of a footprint (coords must be in utm projected)
def polygon_area(coords: list):
    n = len(coords)
    area = 0
    # Loop through the coords
    for i in range(n):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % n]  # wrap around
        area += (x1 * y2) - (x2 * y1)
    return abs(area) / 2

# Function to convert coords of footprint to a geojson
'''
Parameters:
    - coords : lat/lon coords in the format [[BLx, BLy], [TLx, TLy], [TRx, TRy], [BRx, BRy]]
    - output_path : path to the output file
Optional:
    - attributes : dictionary containing any metadata you want to add to the geojson as attributes
'''
def footprint_coords_to_geojson(coords: list, output_path: str, attributes:dict = None):
    coords = [[lon, lat] for lat, lon in coords] # swap lat and lon so lon comes first (required in this order for some reason)
    polygon = Polygon(coords)
    feature = geojson.Feature(geometry=polygon, properties=attributes)
    feature_collection = geojson.FeatureCollection([feature], 
                                                   crs={
                                                    "type": "name",
                                                    "properties": {
                                                        "name": "epsg:4326"
                                                    }})
    # Save the GeoJSON to a file
    with open(output_path, 'w') as f:
        geojson.dump(feature_collection, f, indent=2)

# Merge multiple geojsons together
def merge_geojsons(geojson_list: list, output_geojson_path: str):
    all_features = []
    for path in geojson_list:
        with open(path, 'r') as f:
            # Load the GeoJSON data
            data = geojson.load(f)
            if 'features' in data:
                all_features.extend(data['features'])
    feature_collection = geojson.FeatureCollection(all_features) # create feature collection
    with open(output_geojson_path, 'w') as outfile:
        geojson.dump(feature_collection, outfile, indent=2)

# Main function to generate footprints for an input folder
def generate_footprints(input_folder: str, 
                        output_folder: str, 
                        height: float = None, 
                        pitch: float = None, 
                        sens_dim: list = None, 
                        keep_only_merged:bool = True,
                        progress_bar = None):
    
    # Find all folders in the input folder with images
    folders_list = []
    for dirpath, dirnames, files in os.walk(input_folder):
            parent_dir = os.path.dirname(dirpath)
            # Find folders with jpgs in them (imagery folders to be renamed)
            if os.path.isdir(dirpath):
                img_found = False
                for file in os.listdir(dirpath):
                    file_path = os.path.join(dirpath, file)
                    if file.lower().split('.')[-1] in img_extensions: # determine whether any images are in the folder
                        img_found = True
                    if img_found:
                        break
                if img_found:
                    folders_list.append(dirpath)
    total = len(folders_list) # total number of folders to process
    
    # Loop through each folder an extract footprints
    count = 0 # initialise a count for updating the progress bar
    for folder_path in folders_list:
        folder_name = os.path.basename(folder_path)
        
        # Generate EXIF csv with EXIF Tool
        exif_csv_path = os.path.join(folder_path, 'exif.csv')
        extract_exif_csv(folder_path, exif_csv_path)
        
        # Convert EXIF csv into a dictionary
        exif_dict = create_exif_dict(exif_csv_path)
        os.remove(exif_csv_path) 
        
        # Extract each line of EXIF dictionary, translate required metadata into correct formats and generate footprints
        footprints_list = []
        for exif_dict_single in exif_dict: 
            file_path = os.path.abspath(exif_dict_single['SourceFile'])
            rel_path = os.path.abspath(file_path).split(os.path.abspath(input_folder))[1].split('\\')[1] # rel path of the file in the input folder
            image_name = os.path.basename(file_path) 
            
            ### Required metadata for footprints
            
            # Sensor model - required for getting sensor dimensions
            try:
                model = exif_dict_single['Model']
            except:
                model = 'NA'
            # Lat and lon (decimal degrees)
            try:
                lat_str = exif_dict_single['GPSLatitude'] # will return something like 68 deg 34' 49.69" S
                lon_str = exif_dict_single['GPSLongitude']
                lat = dms_to_decimal(lat_str) # should now be in decimal format e.g. -68.58046944444445
                lon = dms_to_decimal(lon_str)
            except:
                print(f"Could not extract latitude and longitude from EXIF for {file_path}")
                lat = 'NA'
                lon = 'NA'
            # UTM Zone
            try:
                utm_details = utm.from_latlon(lat, lon)
                utm_easting = utm_details[0]
                utm_northing = utm_details[1]
                utm_zone = str(utm_details[2])
            except:
                utm_zone = 'NA'
            # Height (m)
            if not height:
                try:
                    height = float(exif_dict_single['RelativeAltitude']) # this is height above takeoff point in metres, hence not an accurate indicator of height above ground level if terrain is not flat
                except:
                    height = 'NA'
                    print(f"Could not extract height from EXIF for {file_path}")
            # Pitch (degrees)
            if not pitch:
                try:
                    pitch = float(exif_dict_single['GimbalPitchDegree'])
                except:
                    pitch = 'NA'
                    print(f"Could not extract gimbal pitch from EXIF for {file_path}")
            # Yaw (degrees)
            try:
                if exif_dict_single['Model'] in ['FC3682']:
                    yaw = float(exif_dict_single['FlightYawDegree'])
                else:
                    yaw = float(exif_dict_single['GimbalYawDegree'])
            except:
                yaw = 'NA'
                print(f"Could not extract gimbal yaw from EXIF for {file_path}")
            # Focal length (millimetres)
            try:
                focal_length = float(exif_dict_single['FocalLength'].split()[0])
            except:
                focal_length = 'NA'
                print(f"Could not extract focal length from EXIF for {file_path}")
            # Sensor dimensions (millimetres)
            if not sens_dim:  
                try:
                    sens_dim = sensor_dimensions_list[model]
                except:
                    print(f"Could not extract sensor dimensions for sensor dimensions list for: '{file_path}' which has sensor model '{model}'. Try manually specify them with sens_dim = [width, height].")
            # Image dimensions (pixels)
            try:
                img_width = int(exif_dict_single['ExifImageWidth'])
                img_height = int(exif_dict_single['ExifImageHeight'])
                img_dim = [img_width, img_height]
            except:
                print(f'Could not extract image dimensions for: {file_path}')

            ### Useful but non essential metadata

            # Datetime
            try:
                datetime_local = exif_dict_single['DateTimeOriginal']
                datetime_local_str = str(datetime.strptime(datetime_local, "%Y:%m:%d %H:%M:%S"))
            except:
                datetime_local_obj = 'NA'
            try:
                datetime_utc = exif_dict_single['UTCAtExposure']
                datetime_utc_str = str(datetime.strptime(datetime_utc, "%Y:%m:%d %H:%M:%S.%f"))
            except:
                try:
                    datetime_utc_str = str(get_utc(lat, lon, datetime_local, tf))
                except:
                    datetime_utc_str = 'NA'
            # Speed (m/s)
            try:
                try:
                    x_speed = float(exif_dict_single['FlightXSpeed'])
                except:
                    x_speed = float(exif_dict_single['SpeedX'])
                try:
                    y_speed = float(exif_dict_single['FlightYSpeed'])
                except:
                    y_speed = float(exif_dict_single['SpeedY'])
                try:
                    z_speed = float(exif_dict_single['FlightZSpeed'])
                except:
                    z_speed = float(exif_dict_single['SpeedZ'])
                speed = round(math.sqrt((abs(x_speed) ** 2) + (abs(y_speed) ** 2) + (abs(z_speed) ** 2)), 3) # speed in m/s = sqrt(xspeed^2 + yspeed^2)
            except:
                speed = 'NA'
            # Ground sample distance (cm)
            gsd = calculate_gsd(height, pitch, focal_length, sens_dim, img_dim)

            # Create a dictionary with all the required metadata
            metadata = {'File Path': file_path, 'Datetime - local': datetime_local_str, 'Datetime - UTC': datetime_utc_str, 'Latitude': lat, 'Longitude': lon, 'UTM Easting': utm_easting, 
                        'UTM Northing': utm_northing,'UTM Zone': utm_zone, 'Sensor': model, 'Height': height, 'GSD': gsd, 'Speed': speed, 'Pitch': pitch, 'Yaw': yaw, 'Focal Length': focal_length, 'Sensor Dimensions': sens_dim, 'Image Dimensions': img_dim}

            # Generate footprints coords and save to an individual geojson
            coords = img_footprint_coords(lat, lon, height, pitch, yaw, focal_length, sens_dim, img_dim)
            geojson_path = os.path.join(output_folder, rel_path.rsplit('.',1)[0] + '_footprint.geojson')
            footprint_coords_to_geojson(coords, geojson_path, metadata)
            footprints_list.append(geojson_path)

        # Merged footprints in each folder into a single geojson
        if keep_only_merged: 
            output_merged_geojson = os.path.join(os.path.dirname(geojson_path), folder_name + '_footprints_merged.geojson')
            merge_geojsons(footprints_list, output_merged_geojson)
            for root, dirs, files in os.walk(output_folder):
                        for file in files:
                            if '_footprint.geojson' in file:
                                file_path = os.path.join(root, file)
                                os.remove(file_path)
        
        # Update the progress bar if one is inputted
        count += 1
        if progress_bar:
            progress_bar.setProperty("value", 100* count / total)