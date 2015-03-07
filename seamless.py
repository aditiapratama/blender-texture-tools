# -*- coding: utf-8 -*-

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Image Seamless Operators",
    "category": "Paint",
    "description": "Makes seamless textures out of source data",
    "author": "Tommi Hyppänen",
    "location": "Image Editor > Tool Shelf > Texture Tools",
    "documentation": "http://blenderartists.org/forum/showthread.php?364409-WIP-Seamless-texture-patching-addon",
    "version": (0, 1, 2),
    "blender": (2, 73, 0)
}

import bpy
import numpy

bpy.types.Scene.seamless_samples = bpy.props.IntProperty(name="Samples", default=100, min=1, max=10000)
bpy.types.Scene.seamless_window = bpy.props.IntProperty(name="Window", default=32, min=2, max=128)
bpy.types.Scene.seamless_overlap = bpy.props.IntProperty(name="Overlap", default=8, min=1, max=64)
bpy.types.Scene.seamless_lines = bpy.props.IntProperty(name="Lines", default=2, min=1, max=16)
bpy.types.Scene.seamless_gimpmargin = bpy.props.IntProperty(name="Blending margin", default=200, min=1, max=1000)
bpy.types.Scene.seamless_smoothing = bpy.props.BoolProperty(name="Patch smoothing")
bpy.types.Scene.seamless_generated_name = bpy.props.StringProperty(name="Output image", default="generated")

available_objects = []

def availableObjects(self, context):
    available_objects.clear()
    for im in bpy.data.images:
        name = im.name
        available_objects.append((name, name, name))
    return available_objects

bpy.types.Scene.seamless_input_image = bpy.props.EnumProperty(name="Input image", items=availableObjects)

bpy.types.Scene.seamless_filter_type = bpy.props.EnumProperty(name="Filter type", items=[
    ("BLUR", "Box blur", "", 1),
    ("SHARPEN", "Sharpen", "", 2),
    ("EDGEDETECT", "Edge detect", "", 3),
    ("EMBOSS", "Emboss", "", 4),
    ("GAUSSIAN", "Gaussian blur ro:5", "", 5),
    ("FASTGAUSSIAN", "Fast gaussian (defunct)", "", 6),
    ("SOBEL", "Sobel", "", 7),
    ("NORMALSSIMPLE", "Normal map: simple", "", 8),
    ])
bpy.types.Scene.seamless_filter_size = bpy.props.IntProperty(name="Size", default=1, min=1, max=9)
bpy.types.Scene.seamless_filter_intensity = bpy.props.FloatProperty(name="Intensity", default=1.0, min=0.0, max=3.0)

class GeneralImageOperator(bpy.types.Operator):
    def init_images(self, context):
        self.input_image = context.scene.seamless_input_image
        self.target_image = context.scene.seamless_generated_name
        
        print("Creating images...")
        self.size = bpy.data.images[self.input_image].size
        self.xs = self.size[0]
        self.ys = self.size[1]

        # if target image exists, change the size to fit
        if self.target_image in bpy.data.images:
            bpy.data.images[self.target_image].scale(self.xs, self.ys)
            self.image = bpy.data.images[self.target_image]
        else:
            self.image = bpy.data.images.new(self.target_image, width=self.xs, height=self.ys)

        # copy image data into much more performant numpy arrays
        self.sourcepixels = numpy.array(bpy.data.images[self.input_image].pixels)
        self.sourcepixels = self.sourcepixels.reshape((self.ys,self.xs,4))
        self.pixels = numpy.zeros((self.ys,self.xs,4))
        self.pixels[:,:,3] = 1.0 # alpha is always 1.0 everywhere
        
        print("Start iteration")     
        
    def finish_images(self, context):
        print("Assign data")
        # assign pixels
        self.image.pixels = self.pixels.flatten()    
        if False:
            # save and update image 
            #self.image.update()
            bpy.ops.image.save_dirty()
            self.image.reload()

def convolution(ssp, intens, sfil):    
    # source, intensity, convolution matrix    
    tpx = numpy.zeros(ssp.shape, dtype=float)
    tpx[:,:,3] = 1.0
    ystep = int(4*ssp.shape[1])
    norms = 0
    for y in range(sfil.shape[0]):
        for x in range(sfil.shape[1]):
            tpx += numpy.roll(ssp, (x-int(sfil.shape[1]/2))*4 + (y-int(sfil.shape[0]/2))*ystep) * sfil[y,x]
            norms += sfil[y,x]
    if norms > 0:
        tpx /= norms
    return ssp + (tpx-ssp) * intens

def normalize(arr):
    # vec *= 1/len(vec)
    m = 1.0/numpy.sqrt(arr[:,:,0]**2 + arr[:,:,1]**2 + arr[:,:,2]**2)
    arr[...,0] *= m
    arr[...,1] *= m
    arr[...,2] *= m
    return arr
    #np.apply_along_axis(np.linalg.norm, 1, vectors)

class ConvolutionsOperator(GeneralImageOperator):
    """Image filter operator"""
    bl_idname = "uv.gimp_convolutions"
    bl_label = "Convolution filters"

    def filter_blur(self, s, intensity):
        self.pixels =  convolution(self.sourcepixels, intensity, numpy.ones((1+s*2, 1+s*2), dtype=float))

    def filter_sharpen(self, s, intensity): 
        self.pixels =  convolution(self.sourcepixels, intensity, numpy.array( \
            [[  -1,  -1,  -1],
             [  -1,   9,  -1],
             [  -1,  -1,  -1]]))

    def filter_edgedetect(self, s, intensity):
        self.pixels =  convolution(self.sourcepixels, intensity, numpy.array( \
            [[   0,   1,   0],
             [   1,  -4,   1],
             [   0,   1,   0]]))

    def filter_emboss(self, s, intensity):
        self.pixels =  convolution(self.sourcepixels, intensity, numpy.array( \
            [[  -2,   1,   0],
             [  -1,   1,   1],
             [   0,   1,   2]]))

    def filter_gaussian(self, s, intensity):
        fil = numpy.ones((1+s*2, 1+s*2), dtype=float)
        a = 1.0/numpy.sqrt(2*numpy.pi)
        xs = int(fil.shape[1]/2)
        ys = int(fil.shape[0]/2)
        ro = 5.0 ** 2
        for y in range(0, fil.shape[0]):
            for x in range(0, fil.shape[1]):
                fil[y,x] =  (1.0/numpy.sqrt(2*numpy.pi*ro)) * (2.71828 ** (-((x-xs)**2 + (y-ys)**2)/(2*ro)))
        self.pixels = convolution(self.sourcepixels, intensity, fil)

    def filter_fast_gaussian(self, s, intensity):
        self.pixels = convolution(self.sourcepixels, intensity, numpy.ones((1+s*2, 1+s*2), dtype=float))

    def filter_normals_simple(self, s, intensity):
        gx = numpy.array( \
            [[  -1,   0,   1],
             [  -2,   0,   2],
             [  -1,   0,   1]])

        gy = numpy.array( \
            [[   1,   2,   1],
             [   0,   0,   0],
             [  -1,  -2,  -1]])

        gradx = convolution(self.sourcepixels, 1.0, gx)
        gradx[:,:,2] = (gradx[:,:,0] + gradx[:,:,1] + gradx[:,:,2])*intensity/3
        gradx[:,:,1] = 0
        gradx[:,:,0] = -1

        grady = convolution(self.sourcepixels, 1.0, gy)
        grady[:,:,2] = (grady[:,:,0] + grady[:,:,1] + grady[:,:,2])*intensity/3
        grady[:,:,1] = -1
        grady[:,:,0] = 0

        vectors = normalize(numpy.cross(gradx[:,:,:3], grady[:,:,:3]))

        self.pixels[:,:,0] = vectors[:,:,0] + 0.5
        self.pixels[:,:,1] = vectors[:,:,1] + 0.5
        self.pixels[:,:,2] = vectors[:,:,2]
        self.pixels[:,:,3] = 1.0

    def filter_sobel(self, s, intensity):
        gx = numpy.array( \
            [[  -1,   0,   1],
             [  -2,   0,   2],
             [  -1,   0,   1]])

        gy = numpy.array( \
            [[   1,   2,   1],
             [   0,   0,   0],
             [  -1,  -2,  -1]])

        self.pixels = convolution(self.sourcepixels, 1.0, gx) 
        self.pixels = convolution(self.pixels, 1.0, gy) 
        self.pixels = self.pixels * intensity
        self.pixels[:,:,3] = 1.0

    def filter_unsharp(self, s, intensity): 
        self.pixels = convolution(self.sourcepixels, intensity, numpy.array( \
            [[   1,   4,   6,   4,   1],
             [   4,  16,  24,  16,   4],
             [   6,  24,-476,  24,   6],
             [   4,  16,  24,  16,   4],
             [   1,   4,   6,   4,   1]]))

    def calculate(self, context):     
        self.selected_filter(context.scene.seamless_filter_size, context.scene.seamless_filter_intensity)

    def execute(self, context):
        self.selected_filter = {
            "BLUR":self.filter_blur,
            "EDGEDETECT":self.filter_edgedetect,
            "SHARPEN":self.filter_sharpen,
            "GAUSSIAN":self.filter_gaussian,
            "FASTGAUSSIAN":self.filter_fast_gaussian,
            "SOBEL":self.filter_sobel,
            "NORMALSSIMPLE":self.filter_normals_simple,
            "EMBOSS":self.filter_emboss } \
            [context.scene.seamless_filter_type]
        self.init_images(context)
        self.calculate(context)
        self.finish_images(context)
                
        return {'FINISHED'}  

class GimpSeamlessOperator(GeneralImageOperator):
    # TODO: the smoothing is not complete, it goes only one way
    """Image seamless generator operator"""
    bl_idname = "uv.gimp_seamless_operator"
    bl_label = "Gimp-style Image Seamless Operator"

    def gimpify(self):
        self.pixels = numpy.copy(self.sourcepixels)
        self.sourcepixels = numpy.roll(self.sourcepixels,self.xs*2+self.xs*4*int(self.ys/2))

        margin = self.seamless_gimpmargin
        if margin>self.xs:
            margin = int(self.xs)

        sxs = int(self.xs/2)
        sys = int(self.ys/2)

        # create the blending interpolation line
        #pix = numpy.zeros((margin,4), dtype=float)
        #for i in range(margin):
        #    pix[i,:] = [(margin-i)/margin, (margin-i)/margin, (margin-i)/margin, 1.0]

        # imask = numpy.zeros(self.pixels.shape, dtype=float)

        # generate 1 of the four corners of the blending mask
        # for i in range(0, int(self.ys/2)):
        #     x = int(self.xs/2-i*self.xs/self.ys)
        #     t = int( margin * (numpy.cos((i+1)/360)+1.2) )
        #     if t<3:
        #         t = 3
        #     length = numpy.maximum(t/2-x, 0)
        #     x0 = numpy.maximum(x-t/2, 0) 
        #     imask[i,0:x0+1] = [1.0, 1.0, 1.0, 1.0]
        #     x1 = x - (t-1)/2

        #     if length >= t or x1 + length < 0 or t < 0 or length < 0 or x1 < 0:
        #         continue
        #     imask[i,x1+length:x1+t] = pix[length:t]
        imask = numpy.zeros((self.pixels.shape[0], self.pixels.shape[1]), dtype=float) 
        for i in range(0, sys):
            x = int(sxs - i*self.xs/self.ys)
            t = int(margin*(  (1-(1-numpy.sin(i*numpy.pi/sys))**1) )/2)
            if t <= 1:
                t = 1
            x0 = x - t/2
            if x0 >= 0:
                imask[i,0:x0] = 1.0
                imask[i,x0:x0+t] = numpy.arange(1.0, 0.0, -1/t)[0:t]
            else:
                x1 = x+t/2
                if x1>0:
                    imask[i,0:x1] = numpy.arange(1.0, 0.0, -1/x1)[0:x1]

        # NO PREMATURE OPTIMIZATION

        #t = int(margin*numpy.sin(i*numpy.pi/(self.ys/2))/2)

        # fac = 1.0
        # xpatch = numpy.arange(1.0, 0.0, -1/sxs)[0:sxs] ** fac
        # ypatch = numpy.arange(1.0, 0.0, -1/sys)[0:sys] ** fac
        # image A: x + y > 1.0 (numpy.where(imask[0:sys,i]+ypatch>1.0, 1.0, 0.0))
        # image B: x * y
        # grey center line: imask[0:sys,i] = (imask[0:sys,i]**0.5) * (ypatch**0.5)
        # for i in range(0, sys):
        #     imask[i,0:sxs] = xpatch
        # for i in range(0, sxs):
        #     imask[0:sys,i] = (imask[0:sys,i]**2) * (ypatch**2)

        # def lerpp(length, endval):
        #     return numpy.arange(1.0, endval, -(1.0-endval)/length)

        # def lerppn(length, endval):
        #     return numpy.arange(endval, 1.0, endval/length)

        # for y in range(0,sys):
        #     xl = int(y*self.xs/self.ys)
        #     nxl = int(1.0-y*self.xs/self.ys)
        #     if xl <= 0 or y == 0 or nxl <= 0:
        #         continue

        #     blk = lerpp(xl, 1.0-y/sys)
        #     imask[y,0:blk.shape[0]] = blk

        #     blk = lerppn(nxl, y/sys)
            #imask[y,sxs-blk.shape[0]:sxs] = blk

        # copy the data into the three remaining corners
        imask[0:self.ys/2+1, self.xs/2:self.xs-1] = numpy.fliplr(imask[0:self.ys/2+1, 0:self.xs/2-1])
        imask[-self.ys/2:self.ys, 0:self.xs/2] = numpy.flipud(imask[0:self.ys/2, 0:self.xs/2])
        imask[-self.ys/2:self.ys, self.xs/2:self.xs-1] = numpy.flipud(imask[0:self.ys/2, self.xs/2:self.xs-1])
        imask[self.ys/2,:] = imask[self.ys/2-1,:] # center line

        # apply mask
        amask = numpy.zeros(self.pixels.shape, dtype=float)
        amask[:,:,0] = imask 
        amask[:,:,1] = imask
        amask[:,:,2] = imask
        amask[:,:,3] = 1.0

        self.pixels = amask * self.sourcepixels + (numpy.ones(amask.shape) - amask) * self.pixels

        #self.pixels = amask

    def execute(self, context):
        self.init_images(context)
        self.seamless_gimpmargin = context.scene.seamless_gimpmargin
        self.gimpify()
        self.finish_images(context)
                
        return {'FINISHED'}  

class SeamlessOperator(GeneralImageOperator):
    """Image seamless texture patcher operator"""
    bl_idname = "uv.seamless_operator"
    bl_label = "Image Seamless Operator"

    maxSSD = 100000000

    def SSD(self,b1,b2):
        if b1.shape == b2.shape:
            return numpy.sum(((b1-b2)*[0.2989, 0.5870, 0.1140, 0.0])**2)
        else:
            return self.maxSSD
        
    def sobel(self):
        pass
        
    def stitch(self,x,y):
        dimage = self.pixels
        simage = self.sourcepixels

        winx = self.seamless_window
        winy = self.seamless_window
        
        if winx + x > self.xs or winy + y > self.ys:
            return
            
        sxs = self.xs - winx
        sys = self.ys - winy
        
        bestx,besty = self.seamless_window,self.seamless_window
        bestresult = self.maxSSD
        b1 = dimage[y:y+winy, x:x+winx,:]
        
        # only test for pixels where the alpha is not zero
        # alpha 0.0 signifies no data, the area to be filled by patching
        # alpha 1.0 is the source data plus the already written patches
        indices = numpy.where(b1[:,:,3]>0)
        
        # random sample through the entire source data to find the best match
        for i in range(self.seamless_samples):
            temx = numpy.random.randint(sxs)
            temy = numpy.random.randint(sys)
            b2 = simage[temy:temy+winy,temx:temx+winx,:]
            result = self.SSD(b1[indices], b2[indices])
            if result < bestresult:
                bestresult = result
                bestx, besty = temx, temy
                
        batch = numpy.copy(simage[besty:besty+winy,bestx:bestx+winx,:])
                
        if self.seamless_smoothing and winx == self.seamless_window and winy == self.seamless_window: 
            # image edge patches can't have a mask because they are irregular shapes
            mask = numpy.ones((winx, winy))
            for i in range(int(self.seamless_overlap/2)):
                val = float(i)/float(self.seamless_overlap/2)
                mask[i,:] *= val
                mask[winy-i-1,:] *= val
                mask[:,i] *= val
                mask[:,winx-i-1] *= val            
            
            mask[numpy.where(b1[:,:,3]<0.5)] = 1.0
            #mask[indices] = 1.0
            batch[:,:,0] = dimage[y:y+winy, x:x+winx,0]*(1.0-mask) + batch[:,:,0]*mask
            batch[:,:,1] = dimage[y:y+winy, x:x+winx,1]*(1.0-mask) + batch[:,:,1]*mask
            batch[:,:,2] = dimage[y:y+winy, x:x+winx,2]*(1.0-mask) + batch[:,:,2]*mask
            batch[:,:,3] = 1.0

        # copy the new patch to the image
        dimage[y:y+winy, x:x+winx,:] = batch
        
    def patch_iterate(self):
        # offset both x and y half the size of the image (put edges on center)
        self.pixels = numpy.roll(self.sourcepixels,self.xs*2+self.xs*4*int(self.ys/2))

        step = self.seamless_window-self.seamless_overlap
        margin = step * self.seamless_lines - self.seamless_overlap
        
        # erase the data from the are we are about to fill with patches
        self.pixels[int(self.ys/2-margin/2):int(self.ys/2+margin/2),:,:] = [0.0,0.0,0.0,0.0]
        self.pixels[:,int(self.xs/2)-margin/2:int(self.xs/2)+margin/2,:] = [0.0,0.0,0.0,0.0]
        
        xmax = int(self.xs-1)
        ymax = int(self.ys-1)
        
        # reconstruct the missing area with patching
        xstart = int(self.xs/2)-margin/2-self.seamless_overlap
        ystart = int(self.ys/2)-margin/2-self.seamless_overlap

        for _ in range(1):
            #horizontal
            for x in range(0, xmax, step):
                for y in range(0, self.seamless_lines):
                    self.stitch(x,y*step+ystart)

            #vertical
            for y in range(0, ymax, step):
                for x in range(0, self.seamless_lines):
                    self.stitch(x*step+xstart,y)       
                    
        # fill in the last edge cases
        self.pixels = numpy.roll(self.pixels,self.xs*2) # half x offset
        for y in range(0, self.seamless_lines):
            self.stitch(int(self.xs/2)-step,y*step+ystart)
        self.pixels = numpy.roll(self.pixels,self.xs*2) # half x offset
        self.pixels = numpy.roll(self.pixels,self.xs*4*int(self.ys/2)) # half y offset
        for x in range(0, self.seamless_lines):
            self.stitch(x*step+xstart,int(self.ys/2)-step)  
        self.pixels = numpy.roll(self.pixels,self.xs*4*int(self.ys/2)) # half y offset

    def execute(self, context):
        self.init_images(context)

        self.seamless_samples = bpy.context.scene.seamless_samples
        self.seamless_window = bpy.context.scene.seamless_window
        self.seamless_overlap = bpy.context.scene.seamless_overlap
        self.seamless_lines = bpy.context.scene.seamless_lines
        self.seamless_smoothing = bpy.context.scene.seamless_smoothing

        self.patch_iterate()
        self.finish_images(context)
                
        return {'FINISHED'}    
    
class TextureToolsPanel(bpy.types.Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'TOOLS'
    bl_label = "Seamless Patching"
    bl_category = "Texture Tools"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.prop(context.scene, "seamless_input_image")

        row = layout.row()
        row.prop(context.scene, "seamless_generated_name")

        row = layout.row()
        row.label("Patched:")

        row = layout.row()
        row.prop(context.scene, "seamless_samples")
        row.prop(context.scene, "seamless_window")

        row = layout.row()
        row.prop(context.scene, "seamless_overlap")
        row.prop(context.scene, "seamless_lines")
        
        row = layout.row()
        row.prop(context.scene, "seamless_smoothing")

        row = layout.row()
        row.operator(SeamlessOperator.bl_idname, text="Make seamless (patches)")

        row = layout.row()
        row.label("Fast and simple:")
                
        row = layout.row()
        row.prop(context.scene, "seamless_gimpmargin")
        
        row = layout.row()
        row.operator(GimpSeamlessOperator.bl_idname, text="Make seamless (fast)")

class TextureToolsFiltersPanel(bpy.types.Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'TOOLS'
    bl_label = "Image Filters"
    bl_category = "Texture Tools"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(context.scene, "seamless_filter_type")

        row = layout.row()
        row.prop(context.scene, "seamless_filter_size")
        row.prop(context.scene, "seamless_filter_intensity")

        row = layout.row()
        row.operator(ConvolutionsOperator.bl_idname, text="Filter")

def register():
    bpy.utils.register_class(SeamlessOperator)
    bpy.utils.register_class(GimpSeamlessOperator)
    bpy.utils.register_class(ConvolutionsOperator)    
    bpy.utils.register_class(TextureToolsPanel)
    bpy.utils.register_class(TextureToolsFiltersPanel)

def unregister():
    bpy.utils.unregister_class(SeamlessOperator)
    bpy.utils.unregister_class(GimpSeamlessOperator)
    bpy.utils.unregister_class(ConvolutionsOperator)
    bpy.utils.unregister_class(TextureToolsPanel)
    bpy.utils.unregister_class(TextureToolsFiltersPanel)

if __name__ == "__main__":
    register()

# ~~~ DOCUMENTATION ~~~
    # space > Reload Scripts ... to clean up UI crap

    # stuff I want done:

    # Progress bar

    # after generation, update texture for materials

    # ??? drag & drop from google images

    # Normal/diffuse/height/cavitymap extraction from bitmap data
    # convolution filters

    #--------------------------

    # drag & drop
    # import urllib
    # urllib.urlretrieve ("http://www.example.com/songs/mp3.mp3", "mp3.mp3")

    # import urllib2
    # mp3file = urllib2.urlopen("http://www.example.com/songs/mp3.mp3")
    # output = open('test.mp3','wb')
    # output.write(mp3file.read())
    # output.close()

    # -------- FUTURE TOOLS:
    # Invert
    # Lighting Lighting_balance
    # Normalize
    # Grayscale
    # Offset by half

    # Dilate
    # Erode


    # [22:14] == Ambient [5b9f2a1e@gateway/web/freenode/ip.91.159.42.30] has joined #blenderpython
    # [22:15] <Ambient> I'm changing image data inside a script, then when I want it to update to the image editor and the 3d view, I do: bpy.ops.image.save_dirty(); self.image.reload()
    # [22:15] <Ambient> while this works, are there some unforeseen consequences I should be worried of?
    # [22:16] <Ambient> image pixel data that is
    # [23:24] <Ambient> also is there a way to update the image to the 3d view and the image editor without actually saving the image to the disk?
    # [23:30] <purplefrog> Ambient: that's a good question.  i1.update() does not accomplish the mission.
    # [23:30] <Ambient> yes, I already tried that
    # [23:32] <purplefrog> I'm not finding anything on the areas[].spaces[] that looks like it should work either.
    # [23:33] <purplefrog> Although C.screen.areas[6].spaces[0].image = i1 accomplishes the mission, although it does seem mighty clumsy to iterate through all the areas looking for a space.type=='IMAGE_EDITOR' and re-setting it if it matches the problem image.
    # [23:34] == JuxTApoze has changed nick to Oblique-Angl
    # [23:35] <Ambient> i also have to update everything the object is linked to
    # [23:35] <Ambient> the image that is
    # [23:35] <purplefrog> And to affect the 3d view you'd probably be messing with the preview layer (like set_UV_editor_texture() in http://web.purplefrog.com/~thoth/blender/python-cookbook/meshFromBathymetry.html
