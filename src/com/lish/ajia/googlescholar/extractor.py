# -*- coding: utf-8 -*-
'''
Runner Platform Module: Extractor
KEG • elivoa[AT]gmail.com
Time-stamp: "root 2010/10/28 13:04:13"
'''

#from runner.proxy import proxy
from com.lish.ajia.googlescholar import models
from com.lish.ajia.util.web import HtmlRetriever
from settings import Settings
import os
import re
from com.lish.ajia.googlescholar.pdfsaver import PDFLinkSaver
from com.lish.pyutil.DataUtil import GoogleDataCleaner, URLCleaner

class Extractor:
	'''
	Extract google scholar information (now citation number).
	'''
	__instance = None

	@staticmethod
	def getInstance():
		if Extractor.__instance is None:
			Extractor.__instance = Extractor()
		return Extractor.__instance


	def __init__(self):
		self.settings = Settings.getInstance()
		self.debug = self.settings.debug
		self.htmlRetriever = HtmlRetriever.getInstance(self.settings.use_proxy)
		if self.settings.save_pdflink:
			self.pdfcache = PDFLinkSaver.getInstance()
			
		self.debug = True
		self.str_blocks_spliter = '<div class=gs_r>'
		self.title_url_block = re.compile('<h3 class="?gs_rt"?>.*?</h3>', re.I)

	def extract_from_source(self, page_html):
		'''
		Extract information from html, return ExtractedModel
		@return: 
			models - [models.ExtractedCitationModel]
		@param: 
			page_html - str:html source of google scholar search result.
		'''
		blocks_html = self.__split_into_blocks(page_html)
		
		if(blocks_html is None):
			print ">"*10 + "(block html is none)" + "<"*10

		models = []
		for block in blocks_html:
			model = self.__extract_googlescholar_result(block)
			if model is not None:
				models.append(model)
		return models


	def getNodesByPersonName(self, names):
		'''
		Get all models by searching use names, multipage
		@return: 
			all_models - {key_title:[ExtractedModel,...]}
		@param: 
			names - person name
		'''
		if names is None or len(names) == 0:
			return None
		
		if self.debug: 
			print 'Extract by person ' , names

		all_models = {}  # {key_title:[ExtractedModel,...]}
		max_pages = 15	#int($total_size * 3 / 100 + 0.5);
		page = 0
		
		for page in range(0, max_pages):
			url, html = self.__getNodesByPersonAndPage(names, page)
#			print page, url, html
			print url
			
			if html is None: continue
			
			models = self.extract_from_source(html)
			
			if models is None: continue
			
			self.__merge_into_extractedmap(all_models, models)

			# save source?
			if self.settings.save_source:
				filename = "".join((','.join(names), '_page_', str(page), '.html'))
				f = file(os.path.join(self.settings.source_dir, filename), 'w')
				f.write(url)
				f.write("\n")
				f.write(html)
				f.close()

			itemsPerPage = len(models)
			print "{+A}[Download Page %s, got %s items.] '%s'" % (page, itemsPerPage, names)
			if itemsPerPage < 60:
				break

		if self.debug : print "{+A}[Total found %s items] '%s'" % (len(all_models), names)
		return all_models

	def getNodesByPubs(self, pubs):
		'''Get by pubs.
		Return: 
			all_models, {key_title:[ExtractedModel,...]}, can be None, or []
		Param: 
			pubs, [models.Publication], query generated by this pubs must less than 256.
		'''
		query, used_pubs, nouse_pubs = Extractor.pinMaxQuery(pubs)  #@UnusedVariable
		if False:
			print "||- ", query
		url = self.settings.urltemplate_by_pubs % URLCleaner.encodeUrlForDownload(query)
		# url = URLCleaner.encodeUrlForDownload(url)
		
		html = self.htmlRetriever.getHtmlRetry(url)
		if html is None:
			return None
		
		models = self.extract_from_source(html)
		if models is None or len(models) == 0: return None

		# save models
		all_models = self.__merge_into_extractedmap(None, models)  # {key_title:[ExtractedModel,...]}
		return all_models


	def __update_user_profile(self, authors):
		"""
		<a href="/citations?hl=en&amp;user=n1zDCkQAAAAJ&amp;oi=sra">J Tang</a>, J Li, B Liang, X Huang, Y Li
		"""
		pat = re.compile("<.+?>")
		return ','.join([pat.sub('', author.strip()) for author in authors.split(',')])
	
	def __split_into_blocks(self, html):
		'''
		Split google scholar result page html into blocks of each search result.
		'''
		if html is not None and len(html) > 0:
			return html.split(self.settings.str_blocks_spliter)

	def __extract_googlescholar_result(self, block_html):
		'''
		parse html_block into google scholar result model.
		'''
		test_debug = False
		
		if block_html is None or block_html == '': 
			return None

		test_re_gs_title = re.compile('<h3 class="?gs_rt"?>(<span.*</span>)?<a href="?([^\s"]+)?"?[^>]+?>([^<>]+)(</a>)?</h3>', re.I)
		test_re_citedby = re.compile('<div class="?gs_fl"?>(<a[^>]+?>)?Cited by (\d+)(</a>)?', re.I)
		test_re_pdflink = re.compile('<div class="?gs_ggs gs_fl"?><a href="?([^\s"]+)?"?[^>]+?><span class="?gs_ctg2"?>\[PDF\]</span>', re.I)
		test_re_author = re.compile("<div class=gs_a>([^\\x00]+?) - ", re.I)
		
		title_url_block = re.findall(self.title_url_block, block_html)
		if title_url_block is not None and len(title_url_block) == 0:
			return None
		(title, url) = self.get_title_and_url(title_url_block[0])
		if not all((title, url)):
			return

		(readable_title, title_cleaned, has_dot) = GoogleDataCleaner.cleanGoogleTitle(title)

		gs_result = models.ExtractedGoogleScholarResult()
		gs_result.title = title
		gs_result.readable_title = readable_title
		gs_result.shunked_title = title_cleaned
		gs_result.title_has_dot = has_dot
		gs_result.web_url = str(url)

		#citation
		citation_match = re.findall(test_re_citedby, block_html)
		if test_debug:
			print 'citation match:', citation_match
			
		if len(citation_match) == 0:
			gs_result.ncitation = 0
		else:
			gs_result.ncitation = int(citation_match[0][1])
			
		# author
		authors = re.findall(test_re_author, block_html)
		if authors is not None and len(authors) > 0:
				gs_result.authors = self.__update_user_profile(authors[0].replace("&hellip;",''))
				
		if test_debug:
			print 'block : ', block_html
			print gs_result.authors
			raw_input()
		
		# pdf link
		if self.settings.save_pdflink:
			link = re.findall(test_re_pdflink, block_html)
			if link is not None and len(link) > 0:
				gs_result.pdfLink = link
				self.pdfcache.add(gs_result.readable_title, link)
		return gs_result

	def __extract_googlescholar_result_back(self, block_html):
		'''parse html_block into google scholar result model.'''
		if block_html is None or block_html == '': return None
		print '\n', block_html, '\n'
		# match title
		matchs = re.findall(self.settings.re_gs_title, block_html)
		print 'matches', len(matchs)
		if len(matchs) == 0:
			return None
		type = matchs[0][1]
		url = matchs[0][3]
		title = matchs[0][4]

		(readable_title, title_cleaned, has_dot) = GoogleDataCleaner.cleanGoogleTitle(title)

		if self.debug and False:
			print '>get:\t', (type, title, url)
			print '>3titles: %s <to> %s <to> %s' % (title, readable_title, title_cleaned)

		gs_result = models.ExtractedGoogleScholarResult()
		gs_result.title = title
		gs_result.readable_title = readable_title
		gs_result.shunked_title = title_cleaned
		gs_result.title_has_dot = has_dot
		gs_result.web_url = str(url)

		# match #citation
		citation_match = re.findall(self.settings.re_citedby, block_html)
		if len(citation_match) == 0:
			gs_result.ncitation = 0;
		else:
			gs_result.ncitation = int(citation_match[0][1])
		# author
		authors = re.findall(self.settings.re_author, block_html)
		if authors is not None and len(authors) > 0:
			gs_result.authors = authors[0]

		# pdf link
		if self.settings.save_pdflink:
			link = re.findall(self.settings.re_pdflink, block_html)
			if link is not None and len(link) > 0:
				gs_result.pdfLink = link
				self.pdfcache.add(gs_result.readable_title, link)

		return gs_result

	# extract citations.
	
	def __getNodesByPersonAndPage(self, names, page):
		'''get page# of person, put pubs who found citation into self.found
		Return url, html
		'''
		assert names is not None
		assert page >= 0 and page < 20
		namesInUrl = []
		for name in names:
			namesInUrl.append(("author:%%22%s%%22" % ("+".join(name.strip().split(" ")))));
		
		start = 100 * page
		url = self.settings.urltemplate_by_person_page % (start, '%20OR%20'.join(namesInUrl))
		
		#print '---- ' + url
		
		html = self.htmlRetriever.getHtmlRetry(url)
		return url, html

	def __merge_into_extractedmap(self, out_all_models, models):
		'''Add all in list models into out_all_models'''
		if out_all_models is None : out_all_models = {}
		for model in models:
			keytitle = model.shunked_title
			if keytitle not in out_all_models:
				out_all_models[keytitle] = [model]
			else:
				models = out_all_models[keytitle]
				models.append(model)
		return out_all_models

	@staticmethod
	def pinMaxQuery(pubs):
		'''Query google scholar use: "xxx a" OR "xxx b" OR ..., max 256 chars. 
		return: query, used_pubs, nouse_pubs(write citation to -10 back to db)
		'''
		printout = False
		maxchars = 256
		query = ""
		total_pubs_used = 0
		used_pubs = []
		nouse_pubs = []
		total_title_length = 0
		for pub in pubs:
			# clean title
			cleaned_titles = GoogleDataCleaner.cleanGoogleTitle(pub.title)
			cleaned_title = cleaned_titles[0]
			
			# Add by gb Nov 05, 2011, filter out nouse titles.
			if cleaned_title is None or len(re.split('[\W+]', cleaned_title)) < 3:
				print "**** no-use-title: ", cleaned_title
				pub.ncitation = -1;
				nouse_pubs.append(pub)
				continue
			
			
			# calc new length
			new_length = Extractor.__calc_control_char_length(total_pubs_used + 1) + total_title_length + len(cleaned_title)

			# 
			splits = cleaned_title.split("\\s+")
			if splits is not None and len(splits) > 1:
				if total_pubs_used == 0:  # if the first one-word paper, only get this.
					new_length += 255
				else:  # skip this one.
					continue

			if printout:# DEBUG PRINT
				print str(len(query)), " new length:" , str(new_length)

			# first pub must be here, to avoid first pub title length > 255
			if total_pubs_used > 0 and new_length > maxchars:
				break # overflow
			# real pin
			if total_pubs_used > 0:
				query += 'OR'
			query += ''.join(('"', cleaned_title, '"'))
			used_pubs.append(pub)
			total_pubs_used += 1
			total_title_length += len(cleaned_title)
		if printout:# DEBUG PRINT
			print 'pin done'
			print 'query(%s): %s' % (len(query), query)
			print 'use %s pubs' % total_pubs_used
		return query, used_pubs, nouse_pubs


	@staticmethod
	def __calc_control_char_length(numpubs):
		'''Return how many chars used in control character such as '"' 'OR'
		allintitle: 
		'''
		if numpubs <= 0:
			return 0
		return numpubs * 4 - 2

	def get_title_and_url(self, head_block):
		try:
			soup = BeautifulSoup(head_block)
			if soup.a is not None:
				url = soup.a['href'].strip()
				title = soup.a.string.strip()
				return title, url
			else:
				title = re.sub('\[[a-zA-Z]*\]', '', soup.h3.get_text()).strip()
				return title, ''
		except:
			print '[ERROR]Can not parse it using BeautifulSoup'
			return (None, None)

if __name__ == '__main__':
	#test = Extractor()
	#test.test_pin_characters()
	cleaned_title = "email lerning"
	if cleaned_title is None or len(cleaned_title.split(' ')) < 3:
		print "**** no-use-title: ", cleaned_title
	

