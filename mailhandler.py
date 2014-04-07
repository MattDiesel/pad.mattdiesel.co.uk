import logging
import webapp2
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
import email.utils
import models
import main

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


	def reply_error(self, mail_message, error_message):
		logging.info("Error: " + error_message)




application = webapp2.WSGIApplication([
	MailHandler.mapping(),
], debug=True)