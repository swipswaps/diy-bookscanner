#!/usr/bin/python

# bookscanner.py
#
# Copyright 2013 Ben Steinberg <benjamin_steinberg@harvard.edu>
# Harvard Library, Office for Scholarly Communication

# derived from
# https://raw.github.com/markvdb/diybookscanner/master/misc/test_keypedal.sh
# by Mark Van den Borre <mark@markvdb.be>

# TODO: what happens if cameras shut down? now checking in inner loop --
#       does set_ndfilter() work?
#       error-checking after calls to Popen?  raise exceptions?
#       what should this do when it gets a signal from the OS?  now handling Ctrl-C in outer loop.
#       set the outer loop to shut down the pi after some amount of inactivity?


from time import time, sleep
import sys
from datetime import datetime
import subprocess
import os
import re
import usb # 1.0, cloned from git://github.com/walac/pyusb.git -- Debian has 0.4.x
import termios
import fcntl
import termcolor
import contextlib
import math
import exif_date
import glob


PTPCAM =        '/usr/bin/ptpcam'
SHOTS =         0

SHORTPAUSE =    0.5
PAUSE =         3
LONGPAUSE =     5

DLFACTOR =      1.5 # multiplier for download time
SCANDIRPREFIX = '/home/pi/public_html/bookscan_'
CANON =         1193 # decimal from hex value from lsusb or http://www.pcidatabase.com/vendors.php
BRAND =         CANON
SHOTPARAMS =    'set_iso_real(100) ; set_av96(384)' # change exposure here


## quiet print
def qprint(string):
    termcolor.cprint(string, 'grey', attrs=['bold'])

## bright print
def bprint(string):
    termcolor.cprint(string, 'white', attrs=['bold'])

## error print
def eprint(string):
    termcolor.cprint(string, 'red')


## from http://stackoverflow.com/a/7259460/117088
## which is from http://love-python.blogspot.com/2010/03/getch-in-python-get-single-character.html
def getch():
  fd = sys.stdin.fileno()

  oldterm = termios.tcgetattr(fd)
  newattr = termios.tcgetattr(fd)
  newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
  termios.tcsetattr(fd, termios.TCSANOW, newattr)

  oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
  fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

  try:
    while 1:
      try:
        c = sys.stdin.read(1)
        break
      except IOError: pass
  finally:
    termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
    fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)
  return c


def restart_cams():
    qprint("Shutting down cameras to ensure stability...")
    for cam in LEFTCAM, RIGHTCAM:
        qprint("Shutting down " + cam + "...")
        cmdoutput(PTPCAM + " --dev=" + cam + " --chdk='lua shut_down()'")

def restart_program():
    # from http://www.daniweb.com/software-development/python/code/260268/restart-your-python-program
    python = sys.executable
    os.execl(python, python, * sys.argv)

def cmdoutput(cmd):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return out.rstrip()

def detect_cams():
    qprint("detecting cameras...")
    global LEFTCAM, RIGHTCAM, LEFTCAMLONG, RIGHTCAMLONG, GPHOTOCAM1, GPHOTOCAM2
    #CAMS = cmdoutput("gphoto2 --auto-detect|grep usb| wc -l")
    CAMS = camera_count(BRAND)
    if CAMS == 2:
        GPHOTOCAM1 = cmdoutput("gphoto2 --auto-detect|grep usb|sed -e 's/.*Camera *//g'|head -n1")
        GPHOTOCAM2 = cmdoutput("gphoto2 --auto-detect|grep usb|sed -e 's/.*Camera *//g'|tail -n1")
        qprint(GPHOTOCAM1 + " is gphotocam1")
        qprint(GPHOTOCAM2 + " is gphotocam2")

        GPHOTOCAM1ORIENTATION=cmdoutput("gphoto2 --port " + GPHOTOCAM1 + " --get-config /main/settings/ownername|grep Current|sed -e's/.*\ //'")
        GPHOTOCAM2ORIENTATION=cmdoutput("gphoto2 --port " + GPHOTOCAM2 + " --get-config /main/settings/ownername|grep Current|sed -e's/.*\ //'")
        qprint("gphotocam1 orientation is " + GPHOTOCAM1ORIENTATION)
        qprint("gphotocam2 orientation is " + GPHOTOCAM2ORIENTATION)

        CAM1=cmdoutput("echo " + GPHOTOCAM1 + "|sed -e 's/.*,//g'")
        CAM2=cmdoutput("echo " + GPHOTOCAM2 + "|sed -e 's/.*,//g'")
        qprint("Detected 2 camera devices: " + GPHOTOCAM1 + " and " + GPHOTOCAM2)
    else:
        eprint("Number of camera devices does not equal 2. Giving up.")
        qprint("CAMERAS OFF.")
        qprint("RESTARTING...")
        sleep(PAUSE)
        restart_program()

    if GPHOTOCAM1ORIENTATION == "left":
        LEFTCAM=cmdoutput("echo " + GPHOTOCAM1 + "|sed -e 's/.*,//g'")
        LEFTCAMLONG=GPHOTOCAM1
    elif GPHOTOCAM1ORIENTATION == "right":
        RIGHTCAM=cmdoutput("echo " + GPHOTOCAM1 + "|sed -e 's/.*,//g'")
        RIGHTCAMLONG=GPHOTOCAM1
    else:
        qprint("OWNER NAME NOT SET.")
        qprint("RESTARTING...")
        sleep(PAUSE)
        eprint(GPHOTOCAM1 + " owner name is neither set to left or right. Please configure that before continuing.")
        restart_program()

    if GPHOTOCAM2ORIENTATION == "left":
        LEFTCAM=cmdoutput("echo " + GPHOTOCAM2 + "|sed -e 's/.*,//g'")
        LEFTCAMLONG=GPHOTOCAM2
    elif GPHOTOCAM2ORIENTATION == "right":
        RIGHTCAM=cmdoutput("echo " + GPHOTOCAM2 + "| sed -e 's/.*,//g'")
        RIGHTCAMLONG=GPHOTOCAM2
    else:
        qprint("OWNER NAME NOT SET.d")
        qprint("RESTARTING...")
        sleep(PAUSE)
        eprint(GPHOTOCAM1 + " owner name is neither set to left or right. Please configure that before continuing.")
        restart_program()

def delete_from_cams():
    for cam in [LEFTCAM, "left"], [RIGHTCAM, "right"]:
        bprint("deleting existing images from SD card on " + cam[1])
        cmdoutput(PTPCAM + " --dev=" + cam[0] + " -D; true")

def switch_to_record_mode():
    qprint("Switching cameras to record mode...")
    qprint("LEFTCAM is " + LEFTCAM + " and RIGHTCAM is " + RIGHTCAM)
    for cam in LEFTCAM, RIGHTCAM:
        qprint("Switching camera " + cam + " to record mode...")
        cmdoutput(PTPCAM + " --dev=" + cam + " --chdk='mode 1'")
    sleep(PAUSE)

def set_zoom():
    # TODO: make less naive about zoom setting (check before and after setting, ...)
    qprint("Setting zoom...")
    for cam in LEFTCAM, RIGHTCAM:
        qprint("Setting camera " + cam + " zoom to 3...")
        # lua set_zoom() makes one camera shut down, looks like, so we're clicking:
        cmdoutput(PTPCAM + " --dev=" + cam + " --chdk='lua while(get_zoom()<=3) do click(\"zoom_in\") end'")
        sleep(PAUSE)
        cmdoutput(PTPCAM + " --dev=" + cam + " --chdk='lua while(get_zoom()>3) do click(\"zoom_out\") end'")
        sleep(PAUSE)
    sleep(PAUSE)

def flash_off():
    qprint("Switching flash off...")
    for cam in LEFTCAM, RIGHTCAM:
        cmdoutput(PTPCAM + " --dev=" + cam + " --chdk='lua while(get_flash_mode()<2) do click(\"right\") end'")
        sleep(SHORTPAUSE)

def download_from_cams():
    totalfilesize = 0
    for pair in [LEFTCAM, "left"], [RIGHTCAM, "right"]:
        qprint("Calculating images from " + pair[1] + "...")
        cmd = PTPCAM + " --dev=" + pair[0] + " -L"
        rawlist = cmdoutput(cmd)
        filelist = rawlist.strip().split('\n')[3:]
        filecount = len(filelist)
        filesize = 0
        for b in filelist:
            filesize = filesize + int(b.split()[1])
        qprint("I see %d images totalling %d megabytes on %s" % (filecount, int(math.ceil(float(filesize) / 1024.0 / 1024.0)), pair[1]))
        totalfilesize = totalfilesize + filesize

    needfree = int(math.ceil(float(totalfilesize) / 1024.0 / 1024.0))
    bprint("INSERT USB STICK WITH AT LEAST %d MEGABYTES FREE" % needfree)
    usbstick = ''
    while usbstick == '':
        qprint("checking in five seconds")
        sleep(5)
        with contextlib.closing(open('/etc/mtab')) as fp:
            for m in fp:
                fs_spec, fs_file, fs_vfstype, fs_mntops, fs_freq, fs_passno = m.split()
                if fs_spec.startswith('/') and fs_file.startswith('/media'):
                    try:
                        r = os.statvfs(fs_file)
                    except:
                        eprint("This USB stick seems to be having problems, please try another one")
                    else:
                        qprint("Block size: %s, blocks: %s, avail: %s" % (str(r.f_bsize), str(r.f_blocks), str(r.f_bavail)))
                        block_usage_pct = 0.0
                        if float(r.f_blocks) > 0:
                            block_usage_pct = 100.0 - (float(r.f_bavail) / float(r.f_blocks) * 100)
                        inode_usage_pct = 0.0
                        if float(r.f_files) > 0:
                            inode_usage_pct = 100.0 - (float(r.f_favail) / float(r.f_files) * 100)
                        qprint("%s\t%s\t\t%d%%\t%d%%" % (fs_spec, fs_file, block_usage_pct, inode_usage_pct))
                        usbfree = int(math.floor(float(r.f_bsize) * float(r.f_bavail) / 1024.0 / 1024.0))
                        qprint("Megabytes free: %d" % usbfree)
                        if usbfree < needfree:
                            eprint("This USB stick doesn't have enough free space, please try another one")
                        else:
                            usbstick = fs_file
    qprint("Mounted USB stick")
    SCANDIRPREFIX = usbstick
    TIMESTAMP=datetime.now().strftime("%Y%m%d-%H%M")
    qprint("Making directory %s/atxhs-bookscan-%s" % (SCANDIRPREFIX, TIMESTAMP))
    # gphoto2 processes end with -1 unexpected result even though everything seems to be fine -> hack: true gives exit status 0
    # ptpcam downloads with bad file creation date and permissions....
    for side in "left", "right":
        os.makedirs("%s/atxhs-bookscan-%s/%s" % (SCANDIRPREFIX, TIMESTAMP, side))
        os.chown("%s/atxhs-bookscan-%s/%s" % (SCANDIRPREFIX, TIMESTAMP, side), 1000, 1000)
        os.chmod("%s/atxhs-bookscan-%s/%s" % (SCANDIRPREFIX, TIMESTAMP, side), 0755)
    os.chown("%s/atxhs-bookscan-%s" % (SCANDIRPREFIX, TIMESTAMP), 1000, 1000)
    os.chmod("%s/atxhs-bookscan-%s" % (SCANDIRPREFIX, TIMESTAMP), 0755)

    # previous attempts used gphoto, then ptpcam en masse; then tried listing
    # then downloading one at a time with ptpcam; now back to bulk, but waiting
    # an amount of time proportional to the number of files
    for pair in [LEFTCAM, "left"], [RIGHTCAM, "right"]:
        bprint("Downloading images from " + pair[1] + "...")
        os.chdir("%s/atxhs-bookscan-%s/%s" % (SCANDIRPREFIX, TIMESTAMP, pair[1]))
        cmdoutput(PTPCAM + " --dev=" + pair[0] + " -G ; true")

    # timestamp are not set correctly on the files we get from the camera....
    counter = 0
    qprint("Adjusting timestamps")
    for side in "left", "right":
        os.chdir("%s/atxhs-bookscan-%s/%s" % (SCANDIRPREFIX, TIMESTAMP, side))
        processedFiles = []
        for fileName in filter(lambda x: x not in processedFiles, glob.glob('*.*')):
            processedFiles.append(fileName)
            try:
                dates, diff = exif_date.fixFileDate(fileName)
            except Exception, e:
                qprint(str(e))
            else:
                counter += 1
    qprint("Adjusted " + str(counter) + " files")
    qprint("syncing filesystems")
    cmdoutput("sync")
    bprint("It is now safe to remove your USB stick")


def set_iso():
    for cam in LEFTCAM, RIGHTCAM:
        qprint("Setting ISO mode to 1 for camera " + cam)
        cmdoutput(PTPCAM + " --dev=" + cam + " --chdk=\"lua set_iso_real(50)\"")
        sleep(SHORTPAUSE)

def set_ndfilter():
    for cam in LEFTCAM, RIGHTCAM:
        qprint("Disabling neutral density filter for " + cam + " -- see http://chdk.wikia.com/wiki/ND_Filter")
        cmdoutput(PTPCAM + " --dev=" + cam + " --chdk=\"luar set_nd_filter(2)\"")
        sleep(SHORTPAUSE)

def outer_loop():

    global SHOTS
    detect_cams()
    while True:
        bprint("Press   1   to download photos from cameras")
        bprint("Press   2   to delete photos from cameras")
        bprint("Press any other alphanumeric key to take photos")
        try:
            input = getch()
            if input == '1':
                download_from_cams()
            elif input == '2':
                delete_from_cams()
            else:
                restart_cams()   #because I don't trust you
                bprint("Turn the cameras on and press any alphanumeric key")
                getch()
                detect_cams()
                switch_to_record_mode()
                set_zoom()
                flash_off()
                set_iso()
                set_ndfilter()
                SHOTS = 0
                inner_loop()
        except KeyboardInterrupt:
            bprint("GOODBYE")
            sleep(PAUSE)
            qprint("Quitting.")
            sys.exit()

def inner_loop():
    global SHOTS
    print ""
    bprint("Press   ESCAPE   to stop taking photos")
    bprint("Press any other alphanumeric key to take photos")
    qprint("ready")
    start = time()
    firstloop = 1
    while True:
        input = getch()
        if (input == '\x1b'):
            break

        # check that a camera hasn't turned off
        # can we do this more quickly?  it's interfering with the pedal.
        #cmdoutput("lsusb | grep Canon | wc -l") == "2"                                      # 1.16 sec
        #cmdoutput(PTPCAM + " -l | grep 0x | wc -l") == "2"                                  # 0.42 sec
        #cmdoutput("gphoto2 --auto-detect|grep usb|sed -e 's/.*Camera *//g' | wc -l") == "2" # 0.36 sec
        #cmdoutput("gphoto2 --auto-detect | grep Camera | wc -l") == "2"                     # 0.34 sec, still too long
        if camera_count(BRAND) == 2:                                       # 0.58 sec from command line, faster inside the program? yes!
            shoot()
            SHOTS += 1
            qprint(str(SHOTS / 2))
        else:
            eprint("Number of camera devices does not equal 2. Try again.")
            qprint("A CAMERA IS OFF.")
            qprint("RESTARTING...")
            qprint("")
            return

def camera_count(brand):
    counter = 0
    for dev in usb.core.find(find_all=True):
        if dev.idVendor == brand:
            counter += 1
    return counter

def shoot():
    global SHOTS
    qprint("Shooting with cameras " + LEFTCAM + " (left) and " + RIGHTCAM + " (right)")
    for cam in LEFTCAM, RIGHTCAM:
        cmdoutput(PTPCAM + " --dev=" + cam + " --chdk='lua " + SHOTPARAMS + "'")
        cmdoutput(PTPCAM + " --dev=" + cam + " --chdk='luar shoot()'")
    qprint("ready")
    bprint("Press   ESCAPE   to stop taking photos")
    bprint("Press any other alphanumeric key to take photos")
    SHOTS += 1

if __name__ == "__main__":
    outer_loop()
