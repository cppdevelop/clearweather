#!/usr/bin/env python

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

#ClearWeatherScreenlet (c) Whise <helder.fraga@hotmail.com>
#ClearWeatherScreenlet (c) Aditya Kher  - http://www.kher.org
#ClearWeatherScreenlet (c) Rastko Karadzic <rastkokaradzic@gmail.com>
import re
from urllib import urlopen
import httplib
import socket # for socket.error
import screenlets
from screenlets.options import StringOption, BoolOption, ColorOption, FontOption, IntOption
from screenlets import Notify
import pygtk
pygtk.require('2.0')
import cairo
import pango
import sys
import gobject
import time
import datetime
import math
import gtk
from gtk import gdk
import os
from screenlets import Plugins
proxy = Plugins.importAPI('Proxy')

#use gettext for translation
import gettext

_ = screenlets.utils.get_translator(__file__)

def tdoc(obj):
	obj.__doc__ = _(obj.__doc__)
	return obj

@tdoc

class ClearWeatherScreenlet(screenlets.Screenlet):
	"""A Weather Screenlet modified from the original to look more clear and to enable the use of icon pack , you can use any icon pack compatible with weather.com , you can find many packs on deviantart.com or http://liquidweather.net/icons.php#iconsets."""

	# default meta-info for Screenlets
	__name__ = 'ClearWeatherScreenlet'
	__version__ = '0.7.41+++'
	__author__ = 'Aditya Kher <http://www.kher.org>, Whise <helder.fraga@hotmail.com>, Rastko Karadzic <rastkokaradzic@gmail.com>'
	__desc__ = __doc__

	# internals
	__timeout = None

        # Default update interval is 5 mins (300 Sec)
	update_interval = 5
	show_error_message = 1

	lasty = 0
	lastx = 0   ## the cursor position inside the window (is there a better way to do this??)
	over_button = 1

	ZIP = "KSXX0025"
	CITY = "Suwon"
	use_metric = True
	show_daytemp = True
	mini = False
	font = 'Sans'
	font_color = (1,1,1, 0.8)
	background_color = (0,0,0, 0.8)
	latest = []          ## the most recent settings we could get...
	latestHourly = []

	updated_recently = 0 ## don't keep showing the error messages until a connection has been established
			     ## and then lost again.
	
	# constructor
	def __init__(self, text="", **keyword_args):
		#call super (and not show window yet)
		screenlets.Screenlet.__init__(self, width=int(132 * self.scale), height=int(100 * self.scale),uses_theme=True, **keyword_args) 
		self.__tooltip = gtk.Tooltip()
		#self.__widget = self.get
		# set theme
		self.theme_name = "default"
		# add zip code menu item 
		self.add_menuitem("city", _("Enter city name"))
		self.add_menuitem("mini", _("Toggle mini-view"))
		# init the timeout function
		#self.update_interval = self.update_interval
		#self.add_menuitem("update_interval", _("Update Interval"))

                self.add_options_group(_('Weather'),
                        _('The weather widget settings'))
                self.add_option(StringOption(_('Weather'), 'ZIP',
                        str(self.ZIP), 'ZIP', _('The ZIP code to be monitored taken from Weather.com')), realtime=False)
		self.add_option(BoolOption(_('Weather'), 'show_error_message', 
			bool(self.show_error_message), _('Show error messages'), 
			_('Show an error message on invalid location code')))
		self.add_option(BoolOption(_('Weather'), 'use_metric', 
			bool(self.use_metric), _('Use celsius temperature '), 
			_('Use the metric system for measuring values')))
		self.add_option(BoolOption(_('Weather'), 'mini',
			bool(self.mini), _('Use mini-mode'),
			_('Switch to the mini-mode')))
		self.add_option(BoolOption(_('Weather'), 'show_daytemp',
			bool(self.show_daytemp), _('Show 6 day temperature'),
			_('Show 6 day temperature high/low')))
                # minimum update interval is 1 mins (60 Sec)
		self.add_option(IntOption(_('Weather'), 'update_interval',
                        int(self.update_interval), _('Update Interval(In minutes)'), _('The update interval for weather forecast'),min=1,max=1440), realtime=False)
		self.add_option(FontOption(_('Weather'),'font', 
			self.font, _('Font'), 
			'font'))
		self.add_option(ColorOption(_('Weather'),'font_color', 
			self.font_color, _('Text color'), 'font_color'))
		self.add_option(ColorOption(_('Weather'),'background_color', 
			self.background_color, _('Back color'), _('Only works with the default theme')))

                # Update the weather data as soon as initialized.
                #uncomment following if debugging
                #print "updating now"
		gobject.idle_add(self.update_weather_data)
                # Add timer function in constructor call
		self.__timeout = gobject.timeout_add((self.update_interval*1000*60), self.update)
	
	# attribute-"setter", handles setting of attributes
	def __setattr__(self, name, value):
		# call Screenlet.__setattr__ in baseclass (ESSENTIAL!!!!)
		screenlets.Screenlet.__setattr__(self, name, value)
		# check for this Screenlet's attributes, we are interested in:
		if name == "ZIP":
			self.__dict__[name] = value
			gobject.idle_add(self.update_weather_data)
		if name == "use_metric":
			self.__dict__[name] = value
			gobject.idle_add(self.update_weather_data)
		if name == "update_interval":
			#if value > 0:
				self.__dict__['update_interval'] = value
			#	if self.__timeout:
			#		gobject.source_remove(self.__timeout)
			#	self.__timeout = gobject.timeout_add(value * 1000 * 60, self.update)
			#else:
			# The minimum value accepted is 1 	
			#	pass

	def on_init (self):
		print "Screenlet has been initialized."
		# add default menuitems
		self.add_default_menuitems()	

	def update(self):
                # Uncomment following for debugging
                #print " Inside update: update_interval at ", time.localtime()
		gobject.idle_add(self.update_weather_data)
		
		return True


	def update_weather_data(self):
		temp = self.parseWeatherData()
		temp2 = self.parseWeatherDataHourly()
		

		if len(temp) == 0 or temp[0]["where"]  == '':    ##did we get any data?  if not...
			if self.show_error_message==1 and self.updated_recently == 1:
				self.show_error()
			self.updated_recently = 0
		else:
			#if temp[0]["where"].find(',') > -1:
			#	temp[0]["where"] = temp[0]["where"][:temp[0]["where"].find(',')]
			self.latest = temp
			self.latestHourly = temp2
			self.updated_recently = 1
			self.redraw_canvas()


	def parseWeatherData(self):
		if self.use_metric:
			unit = 'm'
		else:
			unit = 's'

		forecast = []

		
		proxies = proxy.Proxy().get_proxy()
		try:
			data = urlopen('http://xoap.weather.com/weather/local/'+self.ZIP+'?cc=*&dayf=10&prod=xoap&par=1003666583&key=4128909340a9b2fc&unit='+unit + '&link=xoap',proxies=proxies).read()

			dcstart = data.find('<loc ')
			dcstop = data.find('</cc>')     ###### current conditions
			data_current = data[dcstart:dcstop]
			forecast.append(self.tokenizeCurrent(data_current))

			for x in range(10):
				dcstart = data.find('<day d=\"'+str(x))
				dcstop = data.find('</day>',dcstart)   #####10-day forecast
				day = data[dcstart:dcstop]
				forecast.append(self.tokenizeForecast(day))
		except (IOError, socket.error), e:
			print "Error retrieving weather data", e
			self.show_error((_("Error retrieving weather data"), e))

		return forecast


	def parseWeatherDataHourly(self):
		if self.use_metric:
			unit = 'm'
		else:
			unit = 's'

		hforecast = []
		try:
			
			proxies = proxy.Proxy().get_proxy()
			data = urlopen('http://xoap.weather.com/weather/local/'+self.ZIP+'?cc=*&dayf=10&prod=xoap&par=1003666583&key=4128909340a9b2fc&unit='+unit+'&hbhf=12&link=xoap',proxies=proxies).read()
			for x in range(8):
				dcstart = data.find('<hour h=\"'+str(x))
				dcstop = data.find('</hour>',dcstart)   ####hourly forecast
				hour = data[dcstart:dcstop]
				hforecast.append(self.tokenizeForecastHourly(hour))
		except (IOError, socket.error), e:
			print "Error retrieving weather data", e
			self.show_error((_("Error retrieving weather data"), e))

		return hforecast


	def tokenizeForecast(self, data):
	
		day = self.getBetween(data, '<part p="d">', '</part>')
		daywind = self.getBetween(day, '<wind>', '</wind>')
	
		night = self.getBetween(data, '<part p="n">', '</part>')
		nightwind = self.getBetween(night, '<wind>', '</wind>')

		tokenized = {
		'date': self.getBetween(data, 'dt=\"','\"'),
		'day' : self.getBetween(data, 't=\"','\"'),
		'high': self.getBetween(data, '<hi>','</hi>'),
		'low': self.getBetween(data, '<low>','</low>'),	
		'sunr': self.getBetween(data, '<sunr>','</sunr>'),
		'suns' : self.getBetween(data, '<suns>','</suns>'),		
		'dayicon' : self.getBetween(day, '<icon>','</icon>'), 
		'daystate' : self.getBetween(day, '<t>','</t>'), 
		'daywindspeed' : self.getBetween(daywind, '<s>','</s>'), 
		'daywinddir' : self.getBetween(daywind, '<t>','</t>'), 
		'dayppcp' : self.getBetween(day, '<ppcp>','</ppcp>'), 
		'dayhumid' : self.getBetween(day, '<hmid>','</hmid>'),
		'nighticon' : self.getBetween(night, '<icon>','</icon>'), 
		'nightstate' : self.getBetween(night, '<t>','</t>'), 
		'nightwindspeed' : self.getBetween(nightwind, '<s>','</s>'), 
		'nightwinddir' : self.getBetween(nightwind, '<t>','</t>'), 
		'nightppcp' : self.getBetween(night, '<ppcp>','</ppcp>'), 
		'nighthumid' : self.getBetween(night, '<hmid>','</hmid>'),
		}
		return tokenized

	def tokenizeForecastHourly(self, data):
		tokenized = {
		'hour' : self.getBetween(data, 'c=\"','\"'),
		'tmp': self.getBetween(data, '<tmp>','</tmp>'),
		'flik': self.getBetween(data, '<flik>','</flik>'),
		'icon': self.getBetween(data, '<icon>','</icon>')
		}
		return tokenized
	
	def tokenizeCurrent(self, data):
		wind = self.getBetween(data, '<wind>', '</wind>')
		bar = self.getBetween(data, '<bar>', '</bar>')
		uv = self.getBetween(data, '<uv>', '</uv>')
		state = self.getBetween(data, '</flik>', '<t> ')

		tokenized = {
		'where': self.getBetween(data, '<dnam>','</dnam>'),
		'time' : self.getBetween(data, '<tm>','</tm>'),
		'sunr': self.getBetween(data, '<sunr>','</sunr>'),
		'suns' : self.getBetween(data, '<suns>','</suns>'),	
		'date' : self.getBetween(data, '<lsup>','</lsup>'),
		'temp' : self.getBetween(data, '<tmp>','</tmp>'),	
		'flik' : self.getBetween(data, '<flik>','</flik>'), 
		'state' : self.getBetween(state, '<t>','</t>'), 
		'icon' : self.getBetween(data, '<icon>','</icon'),
		'pressure' : self.getBetween(data, '<r>','</r>'),
		'windspeed' : self.getBetween(wind, '<s>','</s>'), 
		'winddir' : self.getBetween(wind, '<t>','</t>'), 
		'humid' : self.getBetween(data, '<hmid>','</hmid>'),
		'vis' : self.getBetween(data, '<vis>','</vis>'),
		'dew' : self.getBetween(data, '<dewp>','</dewp>')
		}
		return tokenized		


	def getBetween(self, data, first, last):
		x = len(first)
		begin = data.find(first) +x
		end = data.find(last, begin)
		return data[begin:end]


	def get_icon(self, code):
		if code < 3200:
			weather = str(code)
		
		elif code == 3200:
			weather = "na"
		return weather


	def get_day_or_night(self, weather):
		time = weather[0]["time"].split()[0]
		ampm = weather[0]["time"].split()[1]
		sunset = weather[0]["suns"].split()[0]
		sunrise = weather[0]["sunr"].split()[0]

		hour = time.split(':')[0]
		min = time.split(':')[1]
		risehr = sunrise.split(':')[0]
		risemin = sunrise.split(':')[1]
		sethr = sunset.split(':')[0]
		setmin = sunset.split(':')[1]

		if int(hour) == 12:
			hour = 0
		if ampm == "AM" :
		        if int(risehr) > int(hour) :
		                dark = 1
		        elif int(risehr) < int(hour) :
				dark = 0
		        else :
		                if int(risemin) > int(min) :
        	                	dark = 1
      		          	elif int(risemin) < int(min) :
       	 	                	dark = 0
         		        else :
           				dark = -1

		elif ampm == "PM" :
		        if int(sethr) > int(hour) :
		                dark = 0
		        elif int(sethr) < int(hour) :
		                dark = 1
		        else :
		                if int(setmin) > int(min) :
		                        dark = 0
		                elif int(setmin) < int(min) :
		                        dark = 1
		                else :
		                        dark = -1
		if dark == 1:
			return "moon"
		else:
			return "sun"


	def on_draw(self, ctx):
		weather = self.latest
		hourly = self.latestHourly


		# set size
		ctx.scale(self.scale, self.scale)
		# draw bg (if theme available)
		ctx.set_operator(cairo.OPERATOR_OVER)
		ctx.set_source_rgba(*self.background_color)
		if self.theme:
			s = self.theme.path
			if (self.mini == False and weather != []):
				self.theme.render(ctx,'weather-bg')
				
				if self.theme_name == 'default':self.draw_rounded_rectangle(ctx,11.5,18.5,8,120,80)
				self.theme.render(ctx,'weather-bg')
			else:
				if self.theme_name == 'default':self.draw_rounded_rectangle(ctx,11.5,18.5,8,120,41.8)
				self.theme.render(ctx,'weather-bg-mini')
				
		ctx.set_source_rgba(*self.font_color)
		# draw memory-graph
		if self.theme:
			if weather == []:
				
				self.draw_text(ctx,'<b>No weather information available</b>', 15, 35, self.font.split(' ')[0], 4,  self.width,pango.ALIGN_LEFT)

			else:
				ctx.save()
				ctx.translate(-2, 0)
				ctx.scale(.6,.6)
				if weather[0]["icon"]=="-": weather[0]["icon"]="48"
				icon = str(self.get_icon(int(weather[0]["icon"])) )
				self.theme.render(ctx,icon)
				ctx.restore()
				
			#	for x in range(4):
			#		ctx.save()
			#		ctx.translate(28+x*10,3);
			#		icon = str(self.get_icon(int(hourly[x+1]["icon"])) )
			#		ctx.scale(.25,.25)
			#		self.theme.render(ctx,icon)
			#		ctx.restore()

				degree = unichr(176) 
				if self.use_metric:
					suffix =  'C'
					speed_suffix = 'Kph'
				else:
					suffix = 'F' 
					speed_suffix = 'Mph'

				if len(str(weather[0]["temp"])) == 3:
					ctx.translate(-7, 0)
				self.draw_text(ctx,'<b>' + weather[0]["temp"] + degree + suffix + '</b>' , 95,25, self.font.split(' ')[0], 10,  self.width,pango.ALIGN_LEFT)
				self.draw_text(ctx,'<b>' + weather[0]["where"][:weather[0]["where"].find(',')][:12] +'</b>', -5,45, self.font.split(' ')[0], 7, self.width,pango.ALIGN_RIGHT)

			#	ctx.translate(0, 6)
			#	p_layout = ctx.create_layout()
			#	p_fdesc.set_size(3 * pango.SCALE)
			#	p_layout.set_font_description(p_fdesc)
			#	p_layout.set_markup('<b>'+weather[0]["where"][weather[0]["where"].find(',') + 2:]+'</b>')
			#	ctx.show_layout(p_layout)

			#	ctx.translate(0, 8)
			#	p_layout = ctx.create_layout()
			#	p_fdesc = pango.FontDescription()
			#	p_fdesc.set_family_static("Sans")
			#	p_fdesc.set_size(5 * pango.SCALE)
			#	p_fdesc.set_weight(300)
			#	p_fdesc.set_style(pango.STYLE_NORMAL)   ####render today's highs and lows
			#	p_layout.set_font_description(p_fdesc)
			#	p_layout.set_markup('<b>' + "High: "+weather[1]["high"] + degree + "   Low: " +weather[1]["low"] + degree +'</b>')						
			#	ctx.show_layout(p_layout)
					


#other stuff text

			
	#			for x in range(4):
	#				ctx.save();
	#				ctx.translate(x*10,0);
	#				p_layout.set_markup('<i>' + ""+hourly[x+1]["hour"] + "h</i>")						
	#				ctx.show_layout(p_layout)
	#				ctx.restore();
	#			ctx.translate(0,5);
	#			for x in range(4):
	#				ctx.save();
	#				ctx.translate(x*10,0);
	#				p_layout.set_markup('<b>' + ""+hourly[x+1]["tmp"] + degree + "</b>")						
	#				ctx.show_layout(p_layout)
	#				ctx.restore();

				
		#		ctx.translate(0, 5)
		#		p_layout.set_markup("p:<b>"+weather[0]["pressure"]+"</b>  h:<b>"+weather[0]["humid"] + "%</b>  w:<b>" +weather[0]["windspeed"] + " m/s</b>")	
		#		ctx.show_layout(p_layout)

				if (self.mini == False):
			
					ctx.save() 
					ctx.translate(14, 60)
					self.theme.render(ctx,'day-bg')					
					#self.theme['day-bg.svg'].render_cairo(ctx)   ###render the days background
					#print self.theme.path
					self.draw_text(ctx,weather[1]["day"][:3], 0,0, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)

				#	p_layout.set_markup('<b>' +weather[1]["day"][:3] + '</b>')		
				#	ctx.show_layout(p_layout)
					ctx.translate(24, 0)
					self.draw_text(ctx,weather[2]["day"][:3], 0,0, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)

					ctx.translate(24, 0)
					self.draw_text(ctx,weather[3]["day"][:3], 0,0, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)

					ctx.translate(24, 0)
					self.draw_text(ctx,weather[4]["day"][:3], 0,0, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)

					ctx.translate(24, 0)
					self.draw_text(ctx,weather[5]["day"][:3], 0,0, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)

					ctx.translate(24, 0)
					self.draw_text(ctx,weather[6]["day"][:3], 0,0, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)


					ctx.restore()	

				#	ctx.save()	
				#	ctx.translate(0, 50)   ###render the days background
				#	self.theme['day-bg.svg'].render_cairo(ctx)
				#	p_layout = ctx.create_layout()
				#	p_fdesc = pango.FontDescription()
				#	p_fdesc.set_family_static("Monospace")
				#	p_fdesc.set_size(3 * pango.SCALE)
				#	p_fdesc.set_weight(300)    ###render the days of the week (second row)
				#	p_fdesc.set_style(pango.STYLE_NORMAL)
				#	p_layout.set_font_description(p_fdesc)
				#	p_layout.set_markup('<b>' + "  "+weather[4]["day"].center(14)+weather[5]["day"].center(14)+weather[6]["day"].center(12)+'</b>')						
				#	ctx.show_layout(p_layout)
				#	ctx.restore()

					#ctx.save()
					#ctx.translate(36, 28)
					#self.theme['divider.svg'].render_cairo(ctx)
					#ctx.translate(31,0)     ######render the dividers
					#self.theme['divider.svg'].render_cairo(ctx)
					#ctx.restore()
		

					ctx.save()
					ctx.translate(14, 68)
					self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[1]["nighticon"]))+ '.png',22,22)
					ctx.translate(24,0)
					self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[2]["dayicon"]))+ '.png',22,22)
					ctx.translate(24,0)
					self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[3]["dayicon"]))+ '.png',22,22)
					ctx.translate(24, 0)
					self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[4]["dayicon"]))+ '.png',22,22)
					ctx.translate(24,0)
					self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[5]["dayicon"]))+ '.png',22,22)
					ctx.restore()						
	
					if self.show_daytemp == True:
						ctx.save()	
						
						ctx.translate(16,90)
						if(weather[1]["high"] == "N/A"):
							self.draw_text(ctx,'<b> </b>'+'|'+'<b>' + weather[1]["low"]+degree+'</b>', 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
						else:
							self.draw_text(ctx,'<b>' + weather[1]["high"]+degree+'</b>'+'|'+'<b>' + weather[1]["low"]+degree+'</b>', 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
						ctx.translate(24, 0)
						self.draw_text(ctx,'<b>' + weather[2]["high"]+degree+'</b>'+'|'+'<b>' + weather[2]["low"]+degree+'</b>', 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
						ctx.translate(24,0)
						self.draw_text(ctx,'<b>' + weather[3]["high"]+degree+'</b>'+'|'+'<b>' + weather[3]["low"]+degree+'</b>', 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
						ctx.translate(24,0)
						self.draw_text(ctx,'<b>' + weather[4]["high"]+degree+'</b>'+'|'+'<b>' + weather[4]["low"]+degree+'</b>', 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)	
						ctx.translate(24,0)
						self.draw_text(ctx,'<b>' + weather[5]["high"]+degree+'</b>'+'|'+'<b>' + weather[5]["low"]+degree+'</b>', 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)

					
						ctx.restore()
			
				#self.draw_text(ctx,'<b>' + weather[1]["high"]+degree+'</b>', 68, 28, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)
				#self.draw_text(ctx,'<b>' + weather[1]["low"]+degree+'</b>', 68, 34, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)

				self.draw_text(ctx,'H:' + weather[0]["humid"]+'%', 68, 28, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)

				if(weather[0]["windspeed"] != "calm"):
					self.draw_text(ctx,'W:'+weather[0]["windspeed"] + speed_suffix, 68, 34, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
				else:
					self.draw_text(ctx,'W:'+weather[0]["windspeed"] , 68, 34, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)

				self.draw_text(ctx,'W Ch:'+ weather[0]["flik"] + degree + suffix , 68, 40, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
                		#self.display_details()
					

	def display_details(self):
		weather = self.latest
		
		if len(weather)<=0:return
		
		if self.use_metric:
			degree = unichr(176) + 'C'
			speed_suffix = _('Kph')
			distance_suffix = _('Km')
			pr_suffix = 'hPa'
		else:
			degree = unichr(176) + 'F' 
			speed_suffix = _('Mph')
			distance_suffix = _('Mi')
			pr_suffix = 'in'

		if(weather[0]["windspeed"] != "calm"):
			wind_direction = speed_suffix + ' From ' + weather[0]["winddir"][:2] 
		else:
			wind_direction = ''



		details = 'Location    : ' + weather[0]["where"] + '  \n' \
			  'Now         : ' + weather[0]["state"] +'\n'\
			  'Temperature : ' + weather[0]["temp"] + degree +'\n'\
			  'Feels Like  : ' + weather[0]["flik"] + degree +' \n'\
			  'Humidity   : ' + weather[0]["humid"] + '% \n' \
			  'Wind  : ' + weather[0]["windspeed"]  + wind_direction + '\n'\
			  'Pressure    : ' + weather[0]["pressure"] + pr_suffix + '\n' \
			  'Visibility    : ' + weather[0]["vis"] + distance_suffix + '\n' \
			  'Sunrise      : ' + weather[0]["sunr"] + '\n' \
			  'Sunset       : ' + weather[0]["suns"] + '\n' 

		self.window.set_tooltip_text(details)
		#print details
		

	def on_mouse_leave (self, event):
		"""Called when the mouse leaves the Screenlet's window."""
		#self.redraw_canvas()
		pass
					
	def on_mouse_move(self, event):
		"""Called when the mouse moves in the Screenlet's window."""
		self.display_details()
		self.redraw_canvas()	

	def on_mouse_down(self,event):
		if event.button == 1:
			x = event.x / self.scale
			y = event.y / self.scale

		
			if y >= 75 and x <= 132 and x >= 110:
				os.system('xdg-open http://weather.com')

	def on_draw_shape(self,ctx):
		if self.theme:
			# set size rel to width/height
			self.on_draw(ctx)

	def menuitem_callback(self, widget, id):
		screenlets.Screenlet.menuitem_callback(self, widget, id)
		if id=="city":
			self.show_edit_dialog()
			self.update()
		if id == "mini":
			self.mini = not self.mini
			self.update()
			


	def show_edit_dialog(self):
		# create dialog
		dialog = gtk.Dialog(_("City"), self.window)
		dialog.resize(300, 100)
		dialog.add_buttons(gtk.STOCK_OK, gtk.RESPONSE_OK, 
			gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
		entrybox = gtk.Entry()
		entrybox.set_text(self.CITY)
		dialog.vbox.add(entrybox)
		entrybox.show()	
		# run dialog
		response = dialog.run()
		if response == gtk.RESPONSE_OK:
                    city = entrybox.get_text()
                    dialog.hide()
                    zip = self.get_zip_code(city)
                    if zip != -1:
                        self.ZIP = zip
                        self.CITY=city
                        self.updated_recently = 1
		


	def get_zip_code(self,city):
            """Getting ZIP from www.weather.com"""
            city_name = city
            req_string = "/search/enhancedlocalsearch?where="
            req_string = req_string + '+'.join(city_name.split())
            try:
                connection1 = httplib.HTTPConnection("www.weather.com")
                connection1.request("GET",req_string)
                resp = connection1.getresponse()
                response = resp.read()
                rg_zip = re.compile("[+]\D\D\D\D\d\d\d\d\"")
                rg_city = re.compile(city_name+",(.+)")
                list_zip_codes = rg_zip.findall(response)
                list_cities = rg_city.findall(response)
                if len(list_zip_codes)==1:
                    zip = list_zip_codes[0]
                    return zip[1:9]
                elif len(list_zip_codes)==0 or len(list_cities)==0:
                    self.show_error()
                    return -1
                else:
                    return self.show_choose_city_dialog(city_name, list_cities,list_zip_codes)
            except (IOError, socket.error, Exception), e:
                self.show_error()
                return -1

        def show_choose_city_dialog(self, city_name, list_of_cities, list_of_zips):
            """Dialog to choose if multiple cities from multiple countries with same name available"""
            self.city_select_dialog = gtk.Dialog("Choose city")
            self.city_select_dialog.resize(200,50) 
            cnt = 0
            for city in list_of_cities:
                button = gtk.Button(city_name+" - "+ city)
                button.connect("button_press_event", self.city_selected_callback, list_of_zips[cnt])
                button.show()
                self.city_select_dialog.vbox.add(button)
                cnt = cnt + 1
            self.city_select_dialog.run()
            return self.czip

        def city_selected_callback(self,widget, event, data):
            self.czip = data[1:9]
            self.city_select_dialog.destroy()



	def show_error(self, reason=None):

		dialog = gtk.Dialog(_("Zip Code"), self.window)
		dialog.resize(300, 100)
		dialog.add_buttons(gtk.STOCK_OK, gtk.RESPONSE_OK)

		reasonstr = "\nReason: %s" % reason if reason is not None else ""

		label = gtk.Label(_("Could not reach weather.com.  Check your internet connection and location and try again.")+reasonstr)
		dialog.vbox.add(label)
		check = gtk.CheckButton(_("Do not show this again"))
		dialog.vbox.add(check)
		dialog.show_all()
		response = dialog.run()
		if response == gtk.RESPONSE_OK:
			if check.get_active() == True:
				self.show_error_message = 0			
			dialog.hide()


if __name__ == "__main__":
	import screenlets.session
	screenlets.session.create_session(ClearWeatherScreenlet)
