import sys
# sys.path.insert(0, '/var/www/ME')
# sys.path.insert(0, '/var/www/ME/flaskapp')

sys.path.insert(0, "C:/Users/HP/myprojects/mechweb")
sys.path.insert(0, "C:/Users/HP/myprojects/mechweb/flaskapp")

import os, filelock, pickle, settings
import mail_handler

class MAIL_QUEUE(object):
  
  #-----------------------------------------------------------------------------
  def __init__(self):
    self._path_root = settings.DATA_DIR
    self._path_data = "%s/" % (settings.MAIL_DIR)
    self._lock = "%s/%s" % (self._path_data, "lock_failed_emails")
    self._filename_failed = "failed_emails.pickle"
    self._mail_handler = mail_handler.MAIL_HANDLER()

  #-----------------------------------------------------------------------------
  def add_mails_to_queue(self, entries):
    
    self._queue = []
    if os.path.exists("%s/%s" % (self._path_data, self._filename_failed)):
      with filelock.FileLock(self._lock):
        with open("%s/%s" % (self._path_data, self._filename_failed), "rb") as f:
          self._queue = pickle.load(f)

    for entry in entries:
        newentry = {'subject' : entry['subject'], \
                    'content'  : entry['content'], \
                    'to' : entry['to']}
        self._queue.append(newentry)
    
    with filelock.FileLock(self._lock):
      with open("%s/%s" % (self._path_data, self._filename_failed), "wb") as f:
        pickle.dump(self._queue, f)
        f.close()
    
    return

  #-----------------------------------------------------------------------------
  def process_queue(self):

    self._queue = []
    if os.path.exists("%s/%s" % (self._path_data, self._filename_failed)):
      with filelock.FileLock(self._lock):
        with open("%s/%s" % (self._path_data, self._filename_failed), "rb") as f:
          self._queue = pickle.load(f)

    
    _queue = []
    total = len(self._queue)
    for entry in self._queue:
      if self._mail_handler.send_email(entry):
        continue
      _queue.append(entry)  
    failed = len(_queue)

    with filelock.FileLock(self._lock):
      with open("%s/%s" % (self._path_data, self._filename_failed), "wb") as f:
        pickle.dump(_queue, f)
    
    status = {'total' : total, 'failed' : failed}
    
    return status
