#! /usr/bin/env python3
#-*-coding:utf-8;-*-
#qpy:2
#qpy:console

import argparse
import datetime

import lytro

def main():
    parser = argparse.ArgumentParser(description='Access a Lytro F01 camera.')
    parser.add_argument('--probe', action='store_true',
                        help='List Lytro F01 device paths found')
    parser.add_argument('--battery', action='store_true',
                        help='Check battery level')
    parser.add_argument('--time', action='store_true',
                        help='Check camera time')
    parser.add_argument('--hardwareinfo', action='store_true',
                        help='Check hardware info')
    parser.add_argument('--listpictures', action='store_true',
                        help='List pictures')
    parser.add_argument('--output', '-o', type=argparse.FileType('wb'),
                        help='Output filename')
    parser.add_argument('--download-file',
                        help='Download file')
    downloadtypes = list(lytro.loadtypes.keys())
    downloadtypes.remove('picture')
    downloadtypes.extend(lytro.picturesubtypes)
    parser.add_argument('--download-type', '-t',
                        choices=downloadtypes, default='file',
                        help='Type of download to perform')
    
    args = parser.parse_args()

    if args.probe:
        list(lytro.probe(verbose=True))
        return

    # Connect to the first found Lytro camera
    dev = lytro.connect()

    if args.battery:
        battery = dev.getbattery()
        print(f"Battery level: {battery}")
    
    if args.time:
        dt = dev.gettime()
        print(f"Camera time: {dt}")

    if args.hardwareinfo:
        info = dev.gethardwareinfo()
        print(info)

    if args.listpictures:
        # TODO: Sane format! This doesn't describe them at all
        for picture in dev.getpicturelist():
            print(picture)
    
    if args.output:
        with args.output as f:
            if args.download_type in lytro.picturesubtypes:
                dt = 'picture'
                subtype = args.download_type
            else:
                dt = args.download_type
                subtype = None
            data = dev.download(dt, args.download_file, subtype=subtype)
            f.write(data)

    return

    # Time set does not yet work.
    if False and dt == datetime.datetime(2010,1,1,0,0,0,0, tzinfo=datetime.timezone.utc):
        print("Camera time not set. Attempting to set.")
        dev.settime()
        dt = dev.gettime()
    picture = pictures[32]
    print(picture.id)
    # Image sections can be accessed via picture or file loads
    # Guess: file access is more reliable because it doesn't have to look up the image ID.
    # FIXME: SG picture download commands fail (and typically crash camera)
    # Need to implement checks that a reply is for the right command, and continue download.
    #thumbnail = dev.download('picture', picture.id, '128')
    for part in ('128', 'TXT', 'RAW'):
        # thumbnail, metadata and raw sensor data. raw.lfp contains these.
        data = dev.download('file', picture.pathname(part))
        if part=='128':
            import tn128
            tn128.decode_tn128(data).show()
        with open(f"{picture.id}.{part}", 'wb') as f:
            f.write(data)

if __name__=='__main__':
    main()
