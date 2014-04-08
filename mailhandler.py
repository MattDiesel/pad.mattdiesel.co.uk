import logging
import webapp2
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
import email.utils
import models
import main
from google.appengine.api import mail

class MailHandler(InboundMailHandler):
	def receive(self, mail_message):
		action = email.utils.parseaddr(mail_message.to)[1].split("@")[0]

		if action == "put":
			fr = email.utils.parseaddr(mail_message.sender)[1]

			user = models.Author.getByEmail(fr)

			if user is None or not user.canCreate:
				self.reply_error(mail_message, "User '%s' not authorised to create snippets." % fr)
				return

			title = mail_message.subject
			language = "text"

			if "[" in title:
				spl = title.rsplit("[", 1)
				title = spl[0].strip()
				language = spl[1].strip("]").strip()

			slug = main.slugify(title)

			lang = models.Language.lookup(language)

			if lang is None:
				self.reply_error(mail_message, "Language not recognised.")
				return

			if len(mail_message.attachments) < 1:
				self.reply_error(mail_message, "No files attached!")
				return

			filename = mail_message.attachments[0][0]
			filedata = mail_message.attachments[0][1].decode()

			description = ""
			for contenttype, body in mail_message.bodies('text/plain'):
				description = body.decode()
				break

			sn = models.Snippet(key_name=slug,
				title=title,
				fileName=filename,
				description=description,
				language=lang,
				createdBy=user,
				content=filedata)
			sn.put()

			self.reply_success(mail_message, sn)


	def reply_error(self, mail_message, error_message):
		message = "Unable to add your snippet. " + error_message
		reply(mail_message, message)

	def reply_success(self, mail_message, sn):
		message = "Your snippet was added successfully! You can view your snippet at: http://pad.mattdiesel.co.uk" + sn.url()
		reply(mail_message, message)

def reply(mail_message, new_message):
	sender = "put@pad-matt-diesel.appspotmail.com"
	to = mail_message.sender
	subject = "Re: " + mail_message.subject

	try:
		cc = mail_message.cc
	except AttributeError:
		cc = None

	message = "%s\n\n%s" % (new_message, messageToStr(mail_message))

	mail.send_mail(sender=sender,
		to=to,
		subject=subject,
		body=message)

def messageToStr(mail_message):
	header = "On %s, %s wrote:" % (mail_message.date, mail_message.sender)

	content = ""
	for contenttype, body in mail_message.bodies('text/plain'):
		content = body.decode()
		break

	new_content = '\n> '.join(l.strip() for l in content.split('\n'))

	return header + "\n> " + content



application = webapp2.WSGIApplication([
	MailHandler.mapping(),
], debug=True)