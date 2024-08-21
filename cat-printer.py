import socket
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageChops
import PIL.ImageOps
from time import sleep
import struct
import argparse

printerMACAddress = 'XX:XX:XX:XX:XX:XX'
printerWidth = 384
port = 2


def initilizePrinter(soc):
    soc.send(b"\x1b\x40")
    
def getPrinterStatus(soc):
    soc.send(b"\x1e\x47\x03")
    return soc.recv(38) 
    
def getPrinterSerialNumber(soc):
    soc.send(b"\x1D\x67\x39")
    return soc.recv(21)
    
def getPrinterProductInfo(soc):
    soc.send(b"\x1d\x67\x69")
    return soc.recv(16)
    
def sendStartPrintSequence(soc):
    soc.send(b"\x1d\x49\xf0\x19")   
  
def sendEndPrintSequence(soc):
    soc.send(b"\x0a\x0a\x0a\x0a")
    
    
def trimImage(im):
    bg = PIL.Image.new(im.mode, im.size, (255,255,255))
    diff = PIL.ImageChops.difference(im, bg)
    diff = PIL.ImageChops.add(diff, diff, 2.0)
    bbox = diff.getbbox()
    if bbox:
        return im.crop((bbox[0],bbox[1],bbox[2],bbox[3]+10)) # don't cut off the end of the image

def create_text(text, font_name="Lucon.ttf", font_size=12):
    img = PIL.Image.new('RGB', (printerWidth, 5000), color = (255, 255, 255))
    font = PIL.ImageFont.truetype(font_name, int(font_size))
    
    d = PIL.ImageDraw.Draw(img)
    lines = []
    for line in text.splitlines():
        lines.append(get_wrapped_text(line, font, printerWidth))
    lines = "\n".join(lines)
    d.text((0,0), lines, fill=(0,0,0), font=font)
    return trimImage(img)

def get_wrapped_text(text: str, font: PIL.ImageFont.ImageFont,
                     line_length: int):
    lines = ['']
    for word in text.split():
        line = f'{lines[-1]} {word}'.strip()
        if font.getlength(line) <= line_length:
            lines[-1] = line
        else:
            lines.append(word)
    return '\n'.join(lines)


def printImage(soc, im):
    if im.width > printerWidth:
        # image is wider than printer resolution; scale it down proportionately
        height = int(im.height * (printerWidth / im.width))
        im = im.resize((printerWidth, height))
        
    if im.width < printerWidth:
        # image is narrower than printer resolution; pad it out with white pixels
        padded_image = PIL.Image.new("1", (printerWidth, im.height), 1)
        padded_image.paste(im)
        im = padded_image
        
    
    im = im.rotate(180) #print it so it looks right when spewing out of the mouth
    
    # if image is not 1-bit, convert it
    if im.mode != '1':
        im = im.convert('1')
        
        
    # if image width is not a multiple of 8 pixels, fix that
    if im.size[0] % 8:
        im2 = im.new('1', (im.size[0] + 8 - im.size[0] % 8, 
                        im.size[1]), 'white')
        im2.paste(im, (0, 0))
        im = im2
        
        
        
    # Invert image, via greyscale for compatibility
    #  (no, I don't know why I need to do this)
    im = PIL.ImageOps.invert(im.convert('L'))
    # ... and now convert back to single bit
    im = im.convert('1')

    buf = b''.join((bytearray(b'\x1d\x76\x30\x00'), 
                                          struct.pack('2B', int(im.size[0] / 8 % 256), 
                                                      int(im.size[0] / 8 / 256)), 
                                                      struct.pack('2B', int(im.size[1] % 256), 
                                                                  int(im.size[1] / 256)), 
                                                                  im.tobytes()))
    initilizePrinter(soc)  
    sleep(.5)    
    sendStartPrintSequence(soc)
    sleep(.5)
    soc.send(buf)
    sleep(.5)
    sendEndPrintSequence(soc)
    sleep(.5)


s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
s.connect((printerMACAddress,port))

print("Connecting to printer...")

parser = argparse.ArgumentParser('YHK Cat Printer. Choose either --text or --image')
parser.add_argument("--text", '-t', help="text to print", required=False)
parser.add_argument("-i", "--image", help="image to print")
parser.add_argument("-f", "--font", help="font to use", default="Lucon.ttf")
parser.add_argument("-s", "--size", help="font size", default=12)
args = parser.parse_args()
if not args.text and not args.image or (args.image and args.text):
    parser.print_help()
    exit()
if args.image:
    img = PIL.Image.open(args.image)
else:
    img = create_text(args.text, font_size=args.size)

printImage(s,img)
s.close()
