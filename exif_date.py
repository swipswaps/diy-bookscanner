#!/usr/bin/env python

"""A simple utility to restore file creation and modification
dates back to their original values from EXIF.

This script requires exif module to be installed or the exif
command line utility to be in the path.

To function correctly under windows this script needs win32file and
win32con modules. Otherwise it will not be able to restore the creation
date."""

import os, sys, time, re, glob
from datetime import datetime, timedelta

try:
  import win32file, win32con
  __use_win_32 = True
except:
  __use_win_32 = False

__path_to_exif = 'exif'

TEN_MINUTES = timedelta(minutes=10)

__description = """Restores file's creation and modification dates back to the original
value from EXIF.
usage: exif_date.py [File name mask]"""

def getExifCreationDate(path):
  """Gets the earliest date from the file's EXIF header, returns time tuple"""
  timeStamp = None
  try:
    import exif
    pf = exif.parse(path)
    originalTime = pf.get('DateTimeOriginal')
    if (originalTime):
      timeStamp = datetime.strptime(originalTime, '%Y:%m:%d %H:%M:%S')
  except:
    pass

  #sometimes exif lib failes to retrieve data
  if (not timeStamp):
    response = os.popen(__path_to_exif + ' -x "%s"' % path, 'r')
    lines = response.read()
    matches = re.findall('<Date_and_Time.+?>(.*?)</Date_and_Time.+?>', lines)
    if (len(matches)):
      timeStamp = min(*[datetime.strptime(x, '%Y:%m:%d %H:%M:%S') for x in matches])
  return timeStamp

def getFileDates(path):
  """Returns a dictionary of file creation (ctime), modification (mtime), exif (exif) dates"""
  dates = {}
  dates['exif'] = getExifCreationDate(path)
  dates['mtime'] = datetime.utcfromtimestamp(os.path.getmtime(path))
  dates['ctime'] = datetime.utcfromtimestamp(os.path.getctime(path))
  return dates

def setFileDates(fileName, dates):
  """Sets file modification and creation dates to the specified value"""
  if __use_win_32:
    filehandle = win32file.CreateFile(fileName, win32file.GENERIC_WRITE, 0, None, win32con.OPEN_EXISTING, 0, None)
    win32file.SetFileTime(filehandle, *(dates['exif'],)*3)
    filehandle.close()
  else:
    os.utime(fileName, (time.mktime(dates['exif'].utctimetuple()),)*2)

def fixFileDate(fileName):
  """Reads file's EXIF header, gets the earliest date and sets it to the file"""
  dates = getFileDates(fileName)
  if (dates['exif']):
    cmp_time = lambda x, y: x - y > TEN_MINUTES
    diff = [cmp_time(dates[x], dates['exif']) for x in ('mtime', 'ctime')]
    if(sum(diff)):
      setFileDates(fileName, dates)
    return dates, diff
  else:
    return dates, None

def usage():
  print __description

def main(args):
  if (not len(args)):
    usage()
    return - 1
  processedFiles = []
  for fileNameMask in args:
    if "*" in fileNameMask or "?" in fileNameMask:
      print "Looking for files with mask " + fileNameMask
    for fileName in filter(lambda x: x not in processedFiles, glob.glob(fileNameMask)):
      processedFiles.append(fileName)
      try:
        dates, diff = fixFileDate(fileName)
      except Exception, e:
        print e
        diff = None
      print fileName + ' - ',
      if (not diff):
        print 'SKIP, NO EXIF'
      else:
        if (sum(diff) != 0):
            print 'SET TO "%s" (updated M:%d, C:%d)' % (dates['exif'].strftime('%Y:%m:%d %H:%M:%S'), diff[0], diff[1])
        else:
          print 'OK'
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
