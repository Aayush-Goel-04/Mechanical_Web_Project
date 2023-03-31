import sys
# sys.path.insert(0, '/var/www/ME')
# sys.path.insert(0, '/var/www/ME/flaskapp')

sys.path.insert(0, "C:/Users/HP/myprojects/mechweb")
sys.path.insert(0, "C:/Users/HP/myprojects/mechweb/flaskapp")

import mail_queue

mailQueue = mail_queue.MAIL_QUEUE()
mailQueue.process_queue()
