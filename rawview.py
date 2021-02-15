#! /usr/bin/env python3

import numpy as np
from PIL import Image

def load_raw(f, w=3280, h=3280):
    # Metadata: width, height
    # Metadata: pixelPacking
    arr = np.fromfile(f, np.uint8, w*h*3//2).reshape((h,w//2,3)).astype('H')
    # Image is big endian 12 bit 2d array, bayered.
    # This is detailed in the TXT (JSON metadata). 
    # Bayer pattern is r,gr:gb,b but upper left pixel is blue
    # Metadata: mosaic
    b  = (arr[0::2,:,0]<<4 | arr[0::2,:,1]>>4) & 0xfff
    g0 = (arr[0::2,:,1]<<8 | arr[0::2,:,2]   ) & 0xfff
    g1 = (arr[1::2,:,0]<<4 | arr[1::2,:,1]>>4) & 0xfff
    r  = (arr[1::2,:,1]<<8 | arr[1::2,:,2]   ) & 0xfff
    # Subsampled RGB image for now. Just a proof of concept.
    a = np.zeros((h//2,w//2,3))
    a[:,:,:]=168  # black level
    a[:,:,0] = r
    a[:,:,1] = (g0+g1)/2   # Average since we have more green photosites
    a[:,:,2] = b
    # Rescale a to 0..1 levels (Metadata: pixelFormat)
    a = (a-168)/(4095-168)
    a = np.maximum(a, 0)
    # White balance (Metadata: color)
    a[:,:,0] *= 1.015625
    a[:,:,2] *= 1.2578125
    # Gamma (Metadata: color)
    a **= 0.416660010814666748046875
    a = np.minimum(a, 1.0)   # Gain may have pushed values out of range
    
    #print(a.max(), a.min())

    img = Image.frombytes('RGB', (w//2,h//2), (a*255).astype('B').tobytes())
    
    return img

# Rendering thoughts: use scipy or ndsplines for interpolation?
# Can both trace rays to specific depth for focusing, or do full 4D
# interpolation for lightfield conversion. 

if __name__=='__main__':
    from sys import argv
    name = argv[1] if argv[1:] else "../0001.RAW"
    #'sha1-d004cadb9917237bde5145d77d970a4b252de1e9.RAW'
    load_raw(open(name,'rb')).show()
