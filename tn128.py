# Thumbnails are 128x128, 16 bits per pixel.
# Guessed YUYV, aka interleaved YUV 4:2:2.

from array import array
from PIL import Image

def decode_tn128(data):
    # My download may have added an extra byte.
    if len(data)%2:
        assert data[-1]==0
        data = data[:-1]
        w,h=128,128

    img = Image.new('YCbCr', (w,h))
    for y in range(h):
        for x in range(0,w,2):
            cb = data[(y*w+x)*2+1]
            cr = data[(y*w+x)*2+3]
            cy = data[(y*w+x)*2]
            img.putpixel((x,y), (cy,cb,cr))
            cy = data[(y*w+x)*2+2]
            img.putpixel((x+1,y), (cy,cb,cr))
    return img

if __name__ == '__main__':
    from sys import argv
    for name in argv[1:]:
        data = open(name, 'rb').read()
        img = decode_tn128(data)
        img.show()

