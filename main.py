import os
import urllib
import jinja2
import webapp2
import sys
import re
from datetime import datetime
from unicodedata import normalize
import logging

from google.appengine.ext import db
from google.appengine.api import memcache, users

import models

sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
import pygments

import pprint


JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
	extensions=['jinja2.ext.autoescape'])


class BaseHandler(webapp2.RequestHandler):
	pass
	# def handle_exception(self, exception, debug):
	# 	if isinstance(exception, webapp2.HTTPException):
	# 		self.response.set_status(exception.code)
	# 	else:
	# 		self.response.set_status(500)


class Page:
	def __init__(self, template='base', url='/', user=None):
		self.template = template
		self.values = {
			'loginurl': users.create_login_url(url),
			'logouturl': users.create_logout_url(url)
		}

		if user is None:
			_user = users.get_current_user()

			if _user:
				user_q = models.Author.all()
				user_q.filter('user =', _user)

				user = user_q.get()

				if not user:
					k = models.Author.register(_user)
					user = models.Author.get(k)

				self.values['user'] = user
				self.values['logged_in'] = True

			else:
				self.values['logged_in'] = False
		else:
			self.values['user'] = user
			self.values['logged_in'] = True

	def render(self):
		template = JINJA_ENVIRONMENT.get_template(self.template + '.html')
		return template.render(self.values)

class List:
	def __init__(self, req, query, itemsperpage, cols):
		self.cols = cols
		self.total_pages = ((query.count() - 1) / itemsperpage) + 1

		self.page = int(req.get('page', 1))

		if self.page > self.total_pages or self.page < 1:
			webapp2.abort(404)

		self.offset = (self.page-1)*itemsperpage
		self.items = itemsperpage
		self.query = query

		self.req = req

	def pagelink(self, i):
		args = self.req.arguments()

		return '?page=%s' % i

	def paginate(self):
		current = self.page

		start = current - 2
		if start < 1:
			start = 1

		end = current + 2
		if end > self.total_pages:
			end = self.total_pages

		items = []

		if start > 1:
			items.append('<a href="%s">&lt;&lt; First</a>' % self.pagelink(1))

		if current > 1:
			items.append('<a href="%s">&lt; Prev</a>' % self.pagelink(current-1))

		for n in range(start, end + 1):
			if n == current:
				items.append('<a href="%s" class="current">%i</a>' % (self.pagelink(n), n))
			else:
				items.append('<a href="%s">%i</a>' % (self.pagelink(n), n))

		if current < end:
			items.append('<a href="%s">Next &gt;</a>' % self.pagelink(current+1))

		if end < self.total_pages:
			items.append('<a href="%s">Last &gt;&gt;</a>' % self.pagelink(self.total_pages))

		ret = '<ol class="pagination"><li>%s</li></ol>' % '</li><li>'.join(items)

		return ret


	def run(self):
		return self.query.run(offset=self.offset,limit=self.items,projection=self.cols)

# misc

def slugify(text, delim=u'-'):
	_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

	result = []
	for word in _punct_re.split(text.lower()):
		word = normalize('NFKD', word).encode('ascii', 'ignore')
		if word:
			result.append(word.lower())

	return unicode(delim.join(result))

class AdminInit(BaseHandler):
	def get(self):
		if (not users.is_current_user_admin()):
			webapp2.abort(403)

		deflang = []

		self.response.write('Creating language database...')

		for fullname, names, exts, mimeType in pygments.lexers.get_all_lexers():
			slug = ""
			if names is not None:
				slug = names[0]
			else:
				slug = slugify(fullname)

			ext = ".txt"
			if len(exts) > 0:
				ext = exts[0].lstrip('*')

			mtype = "text/plain"
			if len(mimeType) > 0:
				mtype = mimeType[0]

			l = models.Language(key_name=slug,title=fullname,fileExt=ext,mimeType=mtype)
			l.put()

			if slug == 'text':
				deflang = l

		self.response.write('Creating first user...')

		k = models.Author.register(users.get_current_user(), True)
		user = models.Author.get(k)

		self.response.write('Creating the first snippet...')

		sn = models.Snippet(key_name='hello',
			title='Your First Snippet',
			filename='hello.txt',
			description='This is a demo snippet. It\'s always important to start with the traditional greeting.',
			language=deflang,
			createdBy=user,
			content='Hello, World!')
		sn.put()


		self.redirect('/')

# Languages

class LanguageList(BaseHandler):
	def get(self):
		p = Page('lang_list', '/lang')

		lang_q = models.Language.all()

		l = List(self.request, lang_q, 20, ['title', 'description'])

		p.values['languages'] = l

		self.response.write(p.render())

class LanguageAdd(BaseHandler):
	def get(self):
		user = self.checkPerm()

		p = Page('lang_edit', '/lang/add', user)

		p.values['adding'] = True
		p.values['actionpath'] = '/lang/add'
		p.values['language'] = []

		self.response.write(p.render())

	def checkPerm(self):
		user = models.Author.getUser()

		if user is None or not user.is_current_user_admin():
			webapp2.abort(403)

		return user

class LanguageEdit(BaseHandler):
	def get(self, path):
		user = self.checkPerm()
		lang = models.Language.get_by_key_name(path)

		if (lang == None):
			webapp2.abort(404)

		p = Page('lang_edit', self.request.path, user)

		p.values['adding'] = False
		p.values['actionpath'] = self.request.path
		p.values['language'] = lang

		self.response.write(p.render())

	def checkPerm(self):
		user = models.Author.getUser()

		if user is None or not users.is_current_user_admin():
			webapp2.abort(403)

		return user

class LanguageDelete(BaseHandler):
	def get(self, path):
		user = self.checkPerm()
		lang = models.Language.get_by_key_name(path)

		if (lang == None):
			webapp2.abort(404)

		lang.delete()

		self.redirect('/lang')

	def checkPerm(self):
		user = models.Author.getUser()

		if user is None or not user.is_current_user_admin():
			webapp2.abort(403)

		return user

class LanguageShow(BaseHandler):
	def get(self, path):
		lang = models.Language.get_by_key_name(path)

		if (lang == None):
			webapp2.abort(404)

		p = Page('snippet_list', self.request.path)

		query = models.Snippet.all()
		query.filter('language =', lang)

		if not query.count():
			p.values['snippets'] = List(self.request, query, 20, None)
			p.values['title_extra'] = lang.title + ' '
		else:
			p.values['snippets'] = List(self.request, query, 20, None)
			p.values['title_extra'] = lang.title + ' '

		self.response.write(p.render())

# Authors

class AuthorList(BaseHandler):
	def get(self):
		au_q = models.Author.all()

		p = Page('author_list', self.request.path)

		p.values['authors'] = List(self.request, au_q, 20, None)

		self.response.write(p.render())

class AuthorAdd(BaseHandler):
	def get(self):
		self.response.write("Adding author")

class AuthorEdit(BaseHandler):
	def get(self, path):
		author = models.Author.get_by_key_name(path)

		if (author == None):
			webapp2.abort(404)

		self.response.write("Editing author: " + author.nickname)

class AuthorDelete(BaseHandler):
	def get(self, path):
		author = models.Author.get_by_key_name(path)

		if author is None:
			webapp2.abort(404)

		if not users.is_current_user_admin():
			webapp2.abort(403)

		user = models.Author.getUser()

		if user is None:
			webapp2.abort(403)

		if author.key() == user.key():
			webapp2.abort(403) # Todo: Better error message explaining that deleting yourself is just silly.

		# Actually, deleting any user acccount is a bit silly.

		self.redirect(self.request.get('continue', '/'))

class AuthorShow(BaseHandler):
	def get(self, path):
		author = models.Author.get_by_key_name(path)

		if (author == None):
			webapp2.abort(404)

		p = Page('snippet_list', self.request.path)

		snip_q = models.Snippet.all()
		snip_q.filter('createdBy =', author)

		p.values['snippets'] = List(self.request, snip_q, 20, None)
		p.values['title_extra'] = author.nickname + '\'s '

		self.response.write(p.render())

# Snippets:

class SnippetList(BaseHandler):
	def get(self):
		sn_q = models.Snippet.all()

		if sn_q.count() == 0:
			return self.redirect(users.create_login_url('/_init'))

		p = Page('snippet_list', self.request.path)

		p.values['snippets'] = List(self.request, sn_q, 20, None)
		p.values['title_extra'] = 'All '

		self.response.write(p.render())

class SnippetDownload(BaseHandler):
	def get(self, path, fname):
		snippet = models.Snippet.get_by_key_name(path)

		if (snippet == None):
			webapp2.abort(404)

		snippet.incViews()

		self.response.headers.add_header('Content-Disposition', 'attachment', filename=fname)
		self.response.headers.add_header('Content-Type', snippet.language.mimeType)
		self.response.write(snippet.content)

class SnippetAdd(BaseHandler):
	def get(self):
		user = self.checkPerm()

		p = Page('snippet_edit', self.request.path, user)

		p.values['adding'] = True
		p.values['snippet'] = []
		p.values['actionpath'] = self.request.path
		p.values['language_menu'] = models.Language.menu(sel="text")

		self.response.write(p.render())

	def post(self):
		user = self.checkPerm()

		if self.request.get("adding"):
			sn = models.Snippet(key_name=self.request.get("slug"),
				title=self.request.get("title"),
				fileName=self.request.get("filename"),
				description=self.request.get("description"),
				language=models.Language.get_by_key_name(self.request.get("language")),
				createdBy=user,
				content=self.request.get("content"))
			sn.put()

			self.redirect(sn.url())

	def checkPerm(self):
		user = models.Author.getUser()

		if user is None or not user.canCreate:
			webapp2.abort(403)

		return user


class SnippetDelete(BaseHandler):
	def get(self, path):
		user = models.Author.getUser()
		snippet = models.Snippet.get_by_key_name(path)

		if snippet == None:
			webapp2.abort(404)

		if user is None or not user.canDeleteSnippet(snippet):
			webapp2.abort(403)

		models.Snippet.delete(snippet)

		self.redirect('/')


class SnippetEdit(BaseHandler):
	def get(self, path):
		snippet = models.Snippet.get_by_key_name(path)

		if snippet == None:
			webapp2.abort(404)

		usr = self.checkPerm(snippet)

		p = Page('snippet_edit', self.request.path, usr)

		p.values['adding'] = False
		p.values['snippet'] = snippet
		p.values['actionpath'] = self.request.path
		p.values['language_menu'] = models.Language.menu(sel=snippet.language.key().name())

		self.response.write(p.render())

	def post(self, path):
		snippet = models.Snippet.get_by_key_name(path)

		if snippet == None:
			webapp2.abort(404)

		usr = self.checkPerm(snippet)

		snippet.title = self.request.get("title")
		snippet.fileName = self.request.get("filename")
		snippet.description = self.request.get("description")
		snippet.language = models.Language.get_by_key_name(self.request.get("language"))
		snippet.modifiedBy = usr
		snippet.modified = datetime.now()
		snippet.content = self.request.get("content")

		snippet.put()

		memcache.delete('snippet_' + snippet.key().name())

		self.redirect(snippet.url())



	def checkPerm(self, sn, u=None):
		user = models.Author.getUser()

		if user is None:
			webapp2.abort(403)

		if not user.canEdit:
			if not user.canEditOwn or user.key() != sn.createdBy.key():
				webapp2.abort(403)

		return user

class SnippetShowRaw(BaseHandler):
	def get(self, path):
		snippet = models.Snippet.get_by_key_name(path)

		if (snippet == None):
			webapp2.abort(404)

		snippet.incViews()
		values = {'snippet': snippet}

		template = JINJA_ENVIRONMENT.get_template('snippet_raw.html')
		self.response.write(template.render(values))


class SnippetShow(BaseHandler):
	def get(self, path):

		snippet = models.Snippet.get_by_key_name(path)

		if (snippet == None):
			webapp2.abort(404)

		p = Page('snippet', self.request.path)

		p.values['snippet'] = snippet

		self.response.write(p.render())


application = webapp2.WSGIApplication([
	('/', SnippetList),
	('/_init', AdminInit),
	('/lang/?', LanguageList),
	('/lang/add/?', LanguageAdd),
	('/lang/(.+)/edit/?', LanguageEdit),
	('/lang/(.+)/delete/?', LanguageDelete),
	('/lang/(.+)/?', LanguageShow),
	('/author/?', AuthorList),
	('/author/(.+)/edit/?', AuthorEdit),
	('/author/(.+)/delete/?', AuthorDelete),
	('/author/(.+)/?', AuthorShow),
	('/dl/(.+)/(.+)', SnippetDownload),
	('/add/?', SnippetAdd),
	('/(.+)/delete/?', SnippetDelete),
	('/(.+)/edit/?', SnippetEdit),
	('/(.+)/raw/?', SnippetShowRaw),
	('/(.+)/?', SnippetShow),
], debug=True)
