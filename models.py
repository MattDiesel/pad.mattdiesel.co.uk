
import sys
import os

from google.appengine.ext import db
from google.appengine.api import memcache, users

sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
import pygments
import pygments.lexers
import pygments.formatters

class Language(db.Model):
	title = db.StringProperty(verbose_name='Name', required=True)
	description = db.TextProperty(verbose_name='Description', default='')
	fileExt = db.StringProperty(verbose_name='Default File Extension', default='.txt')
	mimeType = db.StringProperty(verbose_name='MIME type', default='text/plain')

	def put(self, *args, **kwargs):
		memcache.delete('language_menu')
		return super(Language, self).put(*args, **kwargs)

	def delete(self, **kwargs):
		memcache.delete('language_menu')
		return super(Language, self).delete(**kwargs)

	def url(self):
		return '/lang/' + self.key().name() + '/'

	def editUrl(self):
		return self.url() + 'edit'

	def deleteUrl(self):
		return self.url() + 'delete'

	@staticmethod
	def menu(name='language',sel=None):
		ret = memcache.get('language_menu')

		if ret is None:
			lang_q = Language.all()

			rows = []

			for v in lang_q.run(projection=['title']):
				rows.append('<option value="%s">%s</option>'
					% (v.key().name(), v.title))

			ret = '<select name="%%s">%s</select>' % ('\n'.join(rows))

			memcache.add('language_menu', ret)

		if sel is not None:
			ret = ret.replace('value="%s">' % sel, 'value="%s" selected>' % sel)

		return ret % name

	@staticmethod
	def lookup(name):
		lang = Language.get_by_key_name(name.lower())

		if lang is not None:
			return lang
		return None

class Author(db.Model):
	user_email = db.StringProperty(verbose_name='User Email', required=True)
	user_id = db.StringProperty(verbose_name='User ID', required=True)
	nickname = db.StringProperty(verbose_name='Display name', required=True)
	canCreate = db.BooleanProperty(verbose_name='Can create snippets', default=True)
	canEditOwn = db.BooleanProperty(verbose_name='Can edit own snippets', default=True)
	canEdit = db.BooleanProperty(verbose_name='Can edit snippets', default=False)
	canDeleteOwn = db.BooleanProperty(verbose_name='Can delete own snippets', default=False)
	canDelete = db.BooleanProperty(verbose_name='Can delete snippets', default=False)

	def url(self):
		return '/author/' + self.key().name() + '/'

	def editUrl(self):
		return self.url() + 'edit'

	def deleteUrl(self):
		return self.url() + 'delete'

	@staticmethod
	def register(u, creator=False):
		keyname = u.nickname()

		if '@' in keyname:
			keyname = keyname.split('@')[0]

		nickname = keyname

		if Author.get_by_key_name(keyname) != None:
			i = 1
			while Author.get_by_key_name(keyname + str(i)) != None:
				i += 1

			keyname = keyname + str(i)

		a = Author(user_email=u.email(), user_id=u.user_id(), nickname=nickname, key_name=keyname, canCreate=creator)
		return a.put()

	def canEditSnippet(self, snippet):
		return users.is_current_user_admin() or self.canEdit or \
			(self.canEditOwn and snippet.createdBy.key() == self.key())

	def canDeleteSnippet(self, snippet):
		return users.is_current_user_admin() or self.canDelete or \
			(self.canDeleteOwn and snippet.createdBy.key() == self.key())

	def isAdmin(self):
		return users.is_current_user_admin() # TODO: Do it properly.

	@staticmethod
	def getUser(u=None):
		if (u == None):
			u = users.get_current_user()

		if not u:
			return None

		user_q = Author.all()
		user_q.filter('user_id =', u.user_id())

		user = user_q.get()

		if not user:
			return None

		return user

	@staticmethod
	def getByEmail(email):
		user_q = Author.all()
		user_q.filter('user_email =', email)

		user = user_q.get()

		if not user:
			return None

		return user


class Snippet(db.Model):
	title = db.StringProperty(verbose_name='Title', required=True)
	fileName = db.StringProperty(verbose_name='File Name', default='')

	description = db.TextProperty(verbose_name='Description', default='')
	language = db.ReferenceProperty(Language, verbose_name='Language')

	createdBy = db.ReferenceProperty(Author, verbose_name='Created By', collection_name="snippet_created_set")
	modifiedBy = db.ReferenceProperty(Author, verbose_name='Modified By', collection_name="snippet_modified_set")
	created = db.DateTimeProperty(verbose_name='Creation Date',auto_now_add=True)
	modified = db.DateTimeProperty(verbose_name='Modified Date')

	content = db.TextProperty(verbose_name='Content')


	def get_content(self):
		ret = memcache.get('snippet_' + self.key().name())

		if ret is None:
			ret = pygments.highlight(
				self.content,
				pygments.lexers.get_lexer_by_name(self.language.key().name()),
				pygments.formatters.HtmlFormatter(linenos='table'))

			memcache.add('snippet_' + self.key().name(), ret)

		return ret

	def delete(self, **kwargs):
		memcache.delete('snippet_' + self.key().name())

		return super(Snippet, self).delete(**kwargs)

	def url(self):
		return '/' + self.key().name()

	def editUrl(self):
		return self.url() + '/edit'

	def deleteUrl(self):
		return self.url() + '/delete'

	def rawUrl(self):
		return self.url() + '/raw'

	def downloadUrl(self):
		if self.fileName == None or self.fileName == "":
			return '/dl' + self.url() + '/' + self.key().name() + \
				self.language.fileExt

		return '/dl' + self.url() + '/' + self.fileName
