import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#-----------------------------------------------------------------------------
class SEND_MAIL(object):
  
  def __init__(self):
    self._sender_password = 'password'
    self._sender_email = 'email'
    self.__set_connection() 

  def __set_connection(self):
    port = 465
    context = ssl.create_default_context()
    server = smtplib.SMTP_SSL("smtp.gmail.com", port, context=context)
    server.login(self._sender_email, self._sender_password)
    self._server = server

  def send_email(self, entries):
    for entry in entries:
      #message
      msg = MIMEMultipart('alternative')
      msg['Subject'] = entry['subject']
      msg['From'] = self._sender_email
      msg['To'] = entry['email']
      part = MIMEText(entry['body_'], "html")
      msg.attach(part)

      try:
        receiver_emails  =  [msg['to']] 
        self._server.sendmail(self._sender_email, receiver_emails, msg.as_string())
        return True
      
      except:
        return False