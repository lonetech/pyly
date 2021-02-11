import json
from array import array
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.properties import StringProperty
from kivy.core.image import Texture
from kivy.graphics import *
from kivy.graphics.transformation import Matrix
from itertools import chain, izip, repeat

# Math for finding the MLA lens position of a pixel:
# Known factors: sensor pixel pitch, array rotation, pitch, scaling and offset
# Want to go from sensor coordinates to coordinates of microlens and offset
# from microlens center
# First step: let mlaY point 60 degrees away from mlaX.
# mlaX=(mlapitch/pixelpitch*cos(rotation), mlapitch/pixelpitch*sin(rotation))
# mlaY=rot(60,mlaX)
# Add a third axis, mlaZ, which is rot(120,mlaX). This permits more easily
# finding the closest ML center; the fractional part in two axis should be
# less than half the lens pitch. 

dot_shader="""$HEADER$

// Vertex shader for plotting(!) points from the image
//uniform int line;
uniform ivec2 texsize;

void main(void) {
  frag_color = vec4(1,0,1,1);
  vec2 pos = vPosition + texsize*color.xy;
  tex_coord0 = pos;
  gl_Position = projection_mat * modelview_mat * vec4(pos, 0.0, 1.0);
}
"""

bayer_shader="""
$HEADER$

uniform sampler2D bayer;
uniform ivec2 texsize;
uniform float gamma;
uniform vec3 red, green, blue;

void main(void) {
    float i=texture2D(texture0,tex_coord0/texsize);
    ivec2 subp=mod(ivec2(tex_coord0),2);
    vec4 factors = texture2D(bayer,tex_coord0/2+0.5);
    i = (i-factors[1])*2*factors[2];	// sensor range fit
//    i *= 2*factors[3];	// gain
//    i = pow(i,gamma);
    gl_FragColor=vec4(0.0,0.0,0.0,1.0);
    switch (int(4*factors[0])) {
      case 0: gl_FragColor.rgb = red*i; break;
      case 1: gl_FragColor.rgb = green*i; break;
      case 2: gl_FragColor.rgb = blue*i; break;
    }
    gl_FragColor.rgb *= 2*factors[3];	// gain
    gl_FragColor = pow(gl_FragColor,gamma);
}
"""

class RawViewWidget(Widget):
    img=StringProperty(None)
    
    def __init__(self, **kwargs):
        self.canvas = RenderContext(use_parent_projection=True)
        super(RawViewWidget,self).__init__(**kwargs)
        # Load metadata
        mdfile=open(self.img+".2",'rb')	# eventually text
        mdfile.read(4)	# skip the length, to do: don't save it
        self.metadata=json.load(mdfile)
        frame=self.metadata['master']['picture']['frameArray'][0]['frame']
        image=frame['metadata']['image']
        self.size=(image['width'],image['height'])
        mosaic=[l.split(',') for l in image['rawDetails']['mosaic']['tile'].split(':')]
        self.bayer=Texture.create(size=(len(mosaic[0]),len(mosaic)), colorfmt='rgba', bufferfmt='float')
        self.bayer.mag_filter='nearest'
        idx={'r':0,'g':1,'b':2}
        for y,r in enumerate(mosaic):
            for x,col in enumerate(r):
                factors=array('f',(0,0,0,0))
                gain=image['color']['whiteBalanceGain'][col]
                if col[0]=='g':
                    gain*=pow(0.5,1/2.2)
                factors[0]=0.25*idx[col[0]]	# color index
                black=image['rawDetails']['pixelFormat']['black'][col]
                white=image['rawDetails']['pixelFormat']['white'][col]
                factors[1]=16*black/float(0xffff)	# black value (subtract)
                factors[2]=0.5*float(0xffff)/(16*(white-black))	# Linearizing factor
                factors[3]=0.5*gain	# linear gain (no clue if this is right)
                print "%s factors: %r"%(col,factors)
                self.bayer.blit_buffer(pbuffer=factors.tostring(), size=(1,1), colorfmt='rgba',
                                       pos=(x,y), bufferfmt='float')
                if col==image['rawDetails']['mosaic']['upperLeftPixel']:
                    uvpos=(-x,-y)
        self.bayer.uvpos=uvpos
        self.bayer.uvsize=(len(mosaic[0]),len(mosaic))
        self.bayer.wrap='repeat'
        self.texture=Texture.create(size=self.size, colorfmt='luminance', bufferfmt='ushort')
        self.texture.mag_filter='nearest'
        self.texture.uvpos=(0,0)
        self.texture.uvsize=self.size
        try:
            raw16=open(self.img+".raw16")
            pixels=raw16.read()
            self.texture.blit_buffer(pbuffer=pixels, size=self.size,
            		             colorfmt='luminance', pos=(0,0), bufferfmt='ushort')
        except IOError, e:
            rawfile=open(self.img+".1","rb")
            raw16=open(self.img+".raw16","wb")
            rawfile.read(4)
            blitline=array('H', [0]*image['width'])
            for y in range(image['height']):
                # TODO: don't hardcode 12bit
                dataline=rawfile.read(image['width']*3/2)
                for i in range(0, image['width'], 2):
                    a,b,c=map(ord,dataline[i*3/2:i*3/2+3])
                    blitline[i]=((a<<4)|(b>>4))<<4
                    blitline[i+1]=(((b&0x0f)<<8)|c)<<4
                blitdata=blitline.tostring()
                raw16.write(blitdata)
                self.texture.blit_buffer(pbuffer=blitdata, size=(len(blitline),1),
            		             colorfmt='luminance', pos=(0,y), bufferfmt='ushort')
        ccmRgbToSrgbArray=image['color']['ccmRgbToSrgbArray']
        if True:
            self.canvas['red']=ccmRgbToSrgbArray[0:3]
            self.canvas['green']=ccmRgbToSrgbArray[3:6]
            self.canvas['blue']=ccmRgbToSrgbArray[6:9]
        else:
            self.canvas['red']=(1.0,0.0,0.0)
            self.canvas['green']=(0.0,1.0,0.0)
            self.canvas['blue']=(0.0,0.0,1.0)
        # Bayer filter via fragment shader?
        self.canvas['gamma']=image['color']['gamma']
        self.canvas['bayer']=1 #self.bayer
        self.canvas['texsize']=tuple(self.size)
        self.canvas.shader.fs=bayer_shader
        self.canvas.shader.vs=dot_shader
        #print "Shader success: ", self.canvas.shader.success
         
        self.canvas.add(Color(1, mode='luminance'))
        self.canvas.add(BindTexture(index=1, texture=self.bayer))
        if True:
            pts=list(chain(*((float(x),0.0) for x in range(self.size[0]))))
            points=Point(points=pts,
                         pointsize=0.5, texture=self.texture)
            for line in range(self.size[1]):
                # Abuse the color shader parameter to pass a sensor site offset
                self.canvas.add(Color(0.0,float(line)/self.size[1],0.0,1.0))
                self.canvas.add(points)
        else:
            with self.canvas:
                #self.rect=Rectangle(pos=(-800,-1300), size=self.size, texture=self.texture)
                #Color(0,1,0)
                points=[]
                for line in range(20+0*self.size[1]):
                    xs=range(self.size[0])
                    ys=repeat(line)
                    points.extend(map(float,chain(*izip(xs,ys))))
                while points:
                    Point(points=points[:2**15-2], 
                          pointsize=0.5, texture=self.texture)
                    del points[:2**15-2]

#    def on_pos(self, instance, pos):
#        self.rect.pos=pos

#    def on_fs(self, instance, value):
#        shader=self.canvas.shader
#        old_value=shader.fs
#        shader.fs=value
#        if not shader.success:
#            shader.fs=old_value
#            raise Exception('failed')

class RawView(App):
    img=StringProperty("sha1-dbcc8f19e3e8fc4ebd5d543ad990823427bb77f7")
    def build(self):
        #l=BoxLayout(size=(3280,3280))
        #l=ScrollView(size=(3200,1800))
        rvv=RawViewWidget(img=self.img) #, size_hint=(None,None))
        #l.add_widget(rvv)
        #b=Button(text="Hello")
        #l.add_widget(b)
        return rvv

if __name__=='__main__':
    from sys import argv
    if len(argv)>=2:
        rv=RawView(img=argv[1])
    else:
        rv=RawView()
    rv.run()
