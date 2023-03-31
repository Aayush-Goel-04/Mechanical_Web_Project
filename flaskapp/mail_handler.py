
import sys
# sys.path.insert(0, '/var/www/ME')
# sys.path.insert(0, '/var/www/ME/flaskapp')

sys.path.insert(0, "C:/Users/HP/myprojects/mechweb")
sys.path.insert(0, "C:/Users/HP/myprojects/mechweb/flaskapp")


import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import settings


class MAIL_HANDLER(object):
  

    def __init__(self):
        self._server_password = settings.server_password
        self._server_email = settings.server_email
        self._sender_email = settings.sender_email
        self.server = settings.mail_server
        self.port  = settings.mail_port
        if settings.debug != True:
            self.__set_connection()

    #-----------------------------------------------------------------------------
    def __set_connection(self):
          
        context = ssl.create_default_context()
        server = smtplib.SMTP(self.server, self.port)
        server.starttls(context=context)
        server.login(self._server_email, self._server_password)
        self._server = server


    #-----------------------------------------------------------------------------
    def send_email(self, entry):
        
        with open("/var/www/ME/mail_log", "a+") as f:
            f.write("%s \n %s \n %s \n\n\n" % (entry['subject'], entry['content'], entry['to']))

        subject = entry['subject']
        content = entry['content']
        to_ = entry['to']
        
        #message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = "Mech @ IITB <%s>" % (self._sender_email)
        msg['To'] = to_
        
        part = MIMEText(content, "html")
        msg.attach(part)

        try:
          receiver_emails  =  [to_] + []
          self._server.sendmail(self._sender_email, receiver_emails, msg.as_string())
          return True
        
        except:
          return False

