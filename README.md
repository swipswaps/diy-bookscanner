diy-bookscanner
===============
This repo contains, at the moment, the [main script](bookscanner.py) and some additional code for running a [DIY bookscanner](http://www.diybookscanner.org/) using a [Raspberry Pi](http://www.raspberrypi.org/).  The script, bookscanner.py, is derived from Ben Steinberg's [bookscanner.py](https://github.com/bensteinberg/diy-bookscanner/blob/master/bookscanner.py), which is in turn derived from Mark Van den Borre's [test_keypedal.sh](https://github.com/markvdb/diybookscanner/blob/master/misc/test_keypedal.sh).  As I haven't yet rewritten everything from scratch, this code is released under the Affero GPL.  

Like test_keypedal.sh, this script uses [gphoto](http://www.gphoto.org/) and [a fork of libptp2](https://github.com/jrabbit/libptp-chdk) to communicate with the cameras, in this case a pair of Canon A2200 point-and-shoots.  It also relies on the [Canon Hack Development Kit (CHDK)](http://chdk.wikia.com/), enhanced firmware for selected Canon cameras.  Note that you may (will?) have to compile ptpcam, as the libptp2 you have installed is not likely to include the CHDK code.

Unlike Ben's version, the user interface for this system consists of a standard DVI or HDMI display plugged into the Raspberry Pi for output, and a standard USB keyboard for input.  Files remain on the cameras' SD cards until the user triggers a transfer to a (user-provided) USB stick.

Other details
-------------
The triggering script, bookscanner.py, is part of a larger system, including

* an init script, so that bookscanner.py will run as a daemon on boot
* a network connection (ethernet or wireless) to set dates and times correctly

A wired ethernet connection is recommended over a USB wifi adapter.

When using an original Raspberry Pi (which has only two USB ports) use a powered USB hub: the user's USB stick (to download photos to) is plugged directly into one USB port on the Pi itself, and the keyboard and two cameras are plugged into the powered hub.  (We experienced a lot of problems with the USB stick being plugged into the hub.)

When using a Raspberry Pi B+ or Model 2 B+ (four USB ports), the USB hub is not necessary; plug the two cameras, keyboard, and user's USB stick directly into the Pi.

We provided a USB extension cable for users to plug their USB stick into.

Post-processing
---------------
Post-processing is left as an exercise to the reader.

In practice
-----------
Instructions and photos of the system in practice can be found here: http://atxhackerspace.org/wiki/Book_Scanner
