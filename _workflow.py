import sys
from wand.image import Image
import tifffile
import numpy as np
import math
import subprocess as sub
import os

class workflows:
    class NGP_3DEP:
        modTag: str
        bodyName: str
        
        tileOffset = -0.7
        workDir: str
        provider: str
        verNum: int
        coords: str
        date: int
        extension: str
        
        width: int
        height: int
        deformity: float
        offset: float

        def ExtractData(self, mapName):
            data = mapName.split("_")
            self.provider = data[0]
            self.verNum = data[1]
            self.coords = data[2]
            self.date = data[3].split(".")[0]
            self.extension = "."+data[3].split(".")[1]
            
        def ProcessHeightmap(self, fileName):
            range = 0
            FP_data = []
            INT_data = []
            errorValue = -999999 # -999999
            minima = sys.float_info.max
            maxima = -sys.float_info.max


            print("exporting pixels")
            with Image(filename= f"{fileName}.tif[0]") as img:
                self.width = img.width
                self.height = img.height
                range = img.quantum_range
                FP_data = img.export_pixels(0,0,self.width,self.height,"I","quantum")
                
                print("Finding maximium and minimum")
                for pixel in FP_data:
                    if pixel/range > maxima:
                        maxima = pixel/range
                    if pixel/range < minima and not(round(pixel/range) == errorValue):
                        minima = pixel/range

                print(minima)
                print(maxima)

            scaleFactor = 65535/(maxima-minima)

            print("Correcting Pixels")
            for pixel in FP_data:
                if round(pixel/range) == errorValue:
                    INT_data.append(0)
                else:
                    INT_data.append(round((pixel/range-minima)*scaleFactor))
                
                
            image_array = np.array(INT_data, dtype=np.uint16)
            image_array = image_array.reshape((self.height,self.width))

            tifffile.imwrite(f"{fileName}-Corrected.tif", image_array)
            
            print("Converting Heightmap to DDS")
            sub.run(["TopoConv",f"{fileName}-Corrected.tif",f"{self.coords}_Height.dds"])
            self.deformity = maxima-minima
            self.offset = minima+self.tileOffset
            
            print(f"Width: {self.width}")
            print(f"Height: {self.height}")
            print(f"Deformity: {self.deformity}")
            print(f"Offset: {self.offset}")
        
        def ProcessColormap(self, fileName):
            print("Reprojecting Colormap")
            sub.call(f'C:\OSGeo4W\OSGeo4W.bat gdalwarp {fileName}_color.tif {fileName}_color-Corrected.tif -t_srs "+proj=longlat +ellps=WGS84"', shell=True)
            
            print("Resizing Colormap")
            with Image(filename=f"{fileName}_color-Corrected.tif") as img:
                img.resize(self.width, self.height)
                img.save(filename = f"{fileName}_color-Sized.tif")
            
            print("Converting Colormap to DDS")
            sub.run(["nvtt_export", f"{fileName}_color-Sized.tif", "-o", f"{fileName}_Color.dds", "-f 15", "--no-mips"])
        
        def GenerateConfig(self):
            
            Lat = int(self.coords[1:3])
            if self.coords[0] == 's':
                Lat = -1*Lat
            Long = int(self.coords[4:7])
            if self.coords[3] == 'w':
                Long = -1*Long
            order = ""
            if self.modTag == "RealSolarSystem":
                order = "9999996"
            else:
                order = "21"
            
            output = []
            output.append(f"@Kopernicus:AFTER[{self.modTag}]\n")
            output.append("{\n")
            output.append(f"\t@Body[{self.bodyName}]\n")
            output.append("\t{\n")
            output.append("\t\t@PQS\n")
            output.append("\t\t{\n")
            output.append("\t\t\t@Mods\n")
            output.append("\t\t\t{\n")
            output.append("\t\t\t\tBoundedDecal\n")
            output.append("\t\t\t\t{\n")
            output.append(f"\t\t\t\t\theightMap = {self.workDir}/{self.coords}_Height.dds\n")
            output.append(f"\t\t\t\t\tcolorMap  = {self.workDir}/{self.coords}_Color.dds\n")
            output.append(f"\t\t\t\t\toffset = {self.offset}\n")
            output.append(f"\t\t\t\t\tdeformity = {self.deformity}\n")
            output.append(f"\t\t\t\t\tmaxLong = {Long+1}\n")
            output.append(f"\t\t\t\t\tminLong = {Long}\n")
            output.append(f"\t\t\t\t\tmaxLat = {Lat}\n")
            output.append(f"\t\t\t\t\tminLat = {Lat-1}\n")
            output.append(f"\t\t\t\t\torder = {order}\n")
            output.append("\t\t\t\t}\n")
            output.append("\t\t\t}\n")
            output.append("\t\t}\n")
            output.append("\t}\n")
            output.append("}\n")
            
            txt = ""
            for line in output:
                txt += line
            
            with open(file=f"{self.coords}.cfg", mode='w') as file:
                file.write(txt)
        
        def CleanupFiles(self, heightmapName, colormapName):
            os.remove(f"{colormapName}_color-Corrected.tif")
            os.remove(f"{colormapName}_color-Sized.tif")
            os.remove(f"{heightmapName}-Corrected.tif")
            
        def __init__(self, mapName, wd, modTag, bodyName):
            self.modTag = modTag
            self.bodyName = bodyName
            self.workDir = wd
            self.ExtractData(mapName)
            heightmapName = self.provider+"_"+self.verNum+"_"+self.coords+"_"+self.date
            colormapName = self.coords
            
            self.ProcessHeightmap(heightmapName)
            self.ProcessColormap(colormapName)
            self.GenerateConfig()
            self.CleanupFiles(heightmapName, colormapName)
            print(heightmapName)
            print(colormapName)
    
    class NASA_SRTM:
        modTag: str
        bodyName: str
        
        tileOffset = -0.5
        topCoord: int
        bottomCoord: int
        leftCoord: int
        rightCoord: int
        coords: str
        
        width: int
        height: int
        deformity: float
        offset: float
        
        
        def ExtractData(self, mapName):
            data = mapName.split("_")
            print(data)
            
            self.bottomCoord = int(data[0][1:])
            if (data[0][0] == "s"):
                self.bottomCoord *= -1
            
            self.topCoord = self.bottomCoord + 1
            
            self.leftCoord = int(data[1][1:])
            if (data[1][0] == "w"):
                self.leftCoord *= -1
                
            self.rightCoord = self.leftCoord + 1
            
            self.coords = data[0][0]+str(self.topCoord)+data[1]
        
        def ProcessHeightmap(self, fileName):
            print("exporting pixels")
            with Image(filename= f"{fileName}[0]") as img:
                self.width = img.width
                self.height = img.height
                
                self.offset = img.minima-32768+self.tileOffset
                self.deformity = (img.maxima)-(img.minima)
                scaleFactor = 65535/self.deformity
                print(self.offset)
                print(self.deformity)
                print(img.minima)
                print(img.maxima)
                with img.clone() as normalized:
                    normalized.evaluate("subtract", img.minima)
                    normalized.evaluate("multiply", scaleFactor)
                    normalized.save(filename=f"{fileName}-Corrected.tif")
                    
            print("Converting Heightmap to DDS")
            sub.run(["TopoConv",f"{fileName}-Corrected.tif",f"{self.coords}_Height.dds"])
            
        def ProcessColormap(self, fileName):
            print("Reprojecting Colormap")
            sub.call(f'C:\OSGeo4W\OSGeo4W.bat gdalwarp {fileName}_color.tif {fileName}_color-Corrected.tif -t_srs "+proj=longlat +ellps=WGS84"', shell=True)
            
            print("Resizing Colormap")
            with Image(filename=f"{fileName}_color-Corrected.tif") as img:
                img.resize(self.width, self.height)
                img.save(filename = f"{fileName}_color-Sized.tif")
            
            print("Converting Colormap to DDS")
            sub.run(["nvtt_export", f"{fileName}_color-Sized.tif", "-o", f"{fileName}_Color.dds", "-f 15", "--no-mips"])
            
        def GenerateConfig(self):            
            order = ""
            if self.modTag == "RealSolarSystem":
                order = "9999996"
            else:
                order = "21"
            
            output = []
            output.append(f"@Kopernicus:AFTER[{self.modTag}]\n")
            output.append("{\n")
            output.append(f"\t@Body[{self.bodyName}]\n")
            output.append("\t{\n")
            output.append("\t\t@PQS\n")
            output.append("\t\t{\n")
            output.append("\t\t\t@Mods\n")
            output.append("\t\t\t{\n")
            output.append("\t\t\t\tBoundedDecal\n")
            output.append("\t\t\t\t{\n")
            output.append(f"\t\t\t\t\theightMap = {self.workDir}/{self.coords}_Height.dds\n")
            output.append(f"\t\t\t\t\tcolorMap  = {self.workDir}/{self.coords}_Color.dds\n")
            output.append(f"\t\t\t\t\toffset = {self.offset}\n")
            output.append(f"\t\t\t\t\tdeformity = {self.deformity}\n")
            output.append(f"\t\t\t\t\tmaxLong = {self.rightCoord}\n")
            output.append(f"\t\t\t\t\tminLong = {self.leftCoord}\n")
            output.append(f"\t\t\t\t\tmaxLat = {self.topCoord}\n")
            output.append(f"\t\t\t\t\tminLat = {self.bottomCoord}\n")
            output.append(f"\t\t\t\t\torder = {order}\n")
            output.append("\t\t\t\t}\n")
            output.append("\t\t\t}\n")
            output.append("\t\t}\n")
            output.append("\t}\n")
            output.append("}\n")
            
            txt = ""
            for line in output:
                txt += line
            
            with open(file=f"{self.coords}.cfg", mode='w') as file:
                file.write(txt)
        
        def CleanupFiles(self, heightmapName, colormapName):
            os.remove(f"{colormapName}_color-Corrected.tif")
            os.remove(f"{colormapName}_color-Sized.tif")
            os.remove(f"{heightmapName}-Corrected.tif")
            
        def __init__(self, mapName, wd, modTag, bodyName):
            self.modTag = modTag
            self.bodyName = bodyName
            self.workDir = wd
            self.ExtractData(mapName)
            self.ProcessHeightmap(mapName)
            self.ProcessColormap(f"{self.coords}")
            self.GenerateConfig()
            self.CleanupFiles(mapName, self.coords)


### WRITE SCRIPTS HERE:

# Example NASA SRTM Workflow
# 30 m per pixel, 3601x3601~, 6.19MB colormap, 24.7MB heightmap, 30.2MB per tile
# Heightmap | Bottom Coord | Left Coord
# Colormap  | Top Coord    | Left Coord
#
# workflows.NASA_SRTM(HEIGHTMAP_NAME, TEXTURE_PATH, MOD_TAG, BODY_NAME)
# /// SCRIPT ///
# workflows.NASA_SRTM("n24_w098_1arc_v3.tif", "Sol-Addons/PluginData/03_Earth/Tiles", "RealSolarSystem", Earth)
# 


# Example NGP 3DEP Workflow
# 10m per pixel, 10812x10812~, 55.7MB colormap, 222MB heightmap, 277.7MB per tile
# Heightmap | Top Coord | Left Coord
# Colormap  | Top Coord | Left Coord
# workflows.NASA_SRTM(HEIGHTMAP_NAME, TEXTURE_PATH, MOD_TAG, BODY_NAME)
# /// SCRIPT ///
# workflows.NGP_3DEP("USGS_13_n26w099_20130911.tif", "Sol-Addons/PluginData/03_Earth/Tiles", "RealSolarSystem", Earth)
# 

workflows.NGP_3DEP("USGS_1_n27w100_20240925.tif", "Sol-Addons/PluginData/03_Earth/Tiles", "SolSystem", "Earth")