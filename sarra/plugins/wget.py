#!/usr/bin/python3
"""
This plugin launches the UNIX 'wget' command with appropriate arguments to perform a file transfer.
Sample usage:

  do_download wget

One should invoke the more efficient binary downloader only when it makes sense to do so in place
of the built-in python interpreted downloader, typically for larger files. By default, the threshold
is 10M (ten megabytes.) The wget_threshold option can be used to change it. 

Options
-------

While the internal downloader is bound to the 'http' protocol, if a file larger than the threshold 
is advertised, on_message routine replaces the URL scheme 'http' with 'download'.  That change
causes the do_download plugin to be invoked for that file.  'http' is the default, but the 
initial url is 'sftp', then the wget_protocol option should be set. 

  wget_threshold 6M
  wget_protocol  'sftp'

Means that the do_download routine will be called for sftp url's representing files larger than 
six megabytes.  While the wget command is used by default, it can be overridden with the 
wget_command option.

  wget_command /usr/bin/wget -p 

Instead of invoking wget, it will invoke the wget -p command. To the command will be 
See end of file for performance considerations.

Caveats:

     This downloader invokes wget with only the remote url.
     no options about local file naming are implemented.

     If you have python >= 3.5, replace 'subprocess.call' by subprocess.run, and the stout and stderr will 
     do the right thing. For 'call' also need to change result == 0 to result.returncode == 0 .

"""

import os,stat,time
import calendar

class WGET(object): 

   import urllib.parse

   def __init__(self,parent):

      parent.declare_option( 'wget_command' )
      parent.declare_option( 'wget_threshold' )
      parent.declare_option( 'wget_protocol' )


   def on_start(self,parent):

      if not hasattr(parent,'wget_command'):
         parent.download_wget_command= [ '/usr/bin/wget' ]

      if not hasattr( parent, "wget_threshold" ):
             parent.wget_threshold = [ "10M" ]

      if not hasattr( parent, "wget_protocol" ):
             parent.wget_protocol = [ "http" ]
          

   def on_message(self,parent):

      logger = parent.logger
      msg    = parent.msg

      if type(parent.wget_threshold) is list:
          parent.wget_threshold = parent.chunksize_from_str( parent.wget_threshold[0] )

      if msg.headers['sum'][0] == 'L' or msg.headers['sum'][0] == 'R' : return True

      parts = msg.partstr.split(',')
      if parts[0] == '1':
          sz=int(parts[1])
      else:
          sz=int(parts[1])*int(parts[2])

      logger.debug("wget sz: %d, threshold: %d download: %s to %s, " % ( \
          sz, parent.wget_threshold, parent.msg.urlstr, msg.new_file ) )
      if sz >= parent.wget_threshold :
          for p in parent.wget_protocol :
              parent.msg.urlstr = msg.urlstr.replace(p,"download")

          parent.msg.url = urllib.parse.urlparse(msg.urlstr)
          logger.info("wget triggering alternate method for: %s to %s, " % (parent.msg.urlstr, msg.new_file))

      return True


   def do_download(self,parent):
      logger = parent.logger
      msg    = parent.msg

      import subprocess

      msg.urlstr = msg.urlstr.replace("download:","http:")
      os.chdir( msg.new_dir )
      cmd = parent.download_wget_command[0].split() + [ msg.urlstr ]
      #logger.debug("download_wget in %s invoking: %s " % ( msg.new_dir, cmd ) )
      result =  subprocess.call( cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
      
      if result == 0:  # Success!
         if parent.reportback:
            logger.info("Downloaded: %s " % ( msg.new_dir + os.sep + msg.new_file ) )
            msg.report_publish(201,'Downloaded')
         return True
         
      if parent.reportback:
         msg.report_publish(499,'wget download failed')
      return False 



wget = WGET(self)
self.do_download = wget.do_download

"""
  APPLICATION NOTES:

    - The built-in downloading logic is pretty good in almost all cases. It is rarely adviseable to use
      this functionality from a performance perspective.

    - Ideal use case:  LAN/Short-haul link with very high bandwidth, where lare peak i/o rates are achievable
      given adequate disk and network connections, such as a high speed LAN. Even there, it should only
      be used for larger files.  

    - Where there is a large tree with many small files, it is very likely that the built-in downloader
      is more efficient than forking any other downloader because, in addition to saving the fork/exec/reap
      overhead, the built-in downloader preserves connections to be used for multiple downloads, so 
      connection establishement, log-in etc.. is not needed for every file. It is actually going
      to be about as efficient as possible for the small file case, as those overheads dominate
      the transfer time.
 
    - As a file gets bigger, the transfer time will eventually dominate the setup-time, and at that
      point, it can make sense to switch to a forking download. Experience with actual configurations
      is needed to pick a good threshold for that. Default of 10M is a reasonable first guess.

    - The native downloader does partitioning of files for passage through multiple pumps and is preferable
      for that case to avoid the 'capybara through an anaconda' syndrome. In cases 'dataless' transfers.
      Where the data does not traverse any pump, this is not a consideration.
     
    - For most long-haul use cases, the bounding constraint is the bandwidth on the link so again
      the built-in downloader is likely close to optimal. Partitioning of the file enables portions of it
      to be delivered and for post-processing tasks, such as anti-virus to overlap with the file transfer.
      when using alternate schemes wihout partitioning, one must await until the complet file has arrived.

"""