#!/usr/bin/env python

# This application is released under the GNU General Public License
# v3 (or, at your option, any later version). You can find the full
# text of the license under http://www.gnu.org/licenses/gpl.txt.
# By using, editing and/or distributing this software you agree to
# the terms and conditions of this license.
# Thank you for using free software!

#ClearWeatherScreenlet (c) Whise <helder.fraga@hotmail.com>

import datetime
import json
import urllib2
import re
from urllib import urlopen
import socket # for socket.error
import screenlets
from screenlets.options import StringOption, BoolOption, ColorOption, FontOption
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

class ClearWeatherScreenlet(screenlets.Screenlet):
    """A Weather Screenlet modified from the original to look more clear and to enable the use of icon pack , you can use any icon pack compatible with weather.com , you can find many packs on deviantart.com or http://liquidweather.net/icons.php#iconsets."""

    # default meta-info for Screenlets
    __name__ = 'ClearWeatherScreenlet'
    __version__ = '0.5'
    __author__ = 'by Helder Fraga aka Whise'
    __desc__ = 'A Weather Screenlet modified from the original to look more clear and to enable the use of icon pack , you can use any icon pack compatible with weather.com , you can find many packs on deviantart.com or http://liquidweather.net/icons.php#iconsets.Weather information provided by www.weather.com'

    # internals
    __timeout = None

    update_interval = 300
    show_error_message = 1

    lasty = 0
    lastx = 0   ## the cursor position inside the window (is there a better way to do this??)
    over_button = 1

    ZIP = "POXX0079"
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
        # set theme
        self.theme_name = "default"
        # add zip code menu item
        self.add_menuitem("zipcode", "Zip Code...")
        self.add_menuitem("mini", "Toggle mini-view")
        # init the timeout function
        self.update_interval = self.update_interval
        self.add_options_group('Weather',
            'The weather widget settings')
        self.add_option(StringOption('Weather', 'ZIP',
            str(self.ZIP), 'ZIP', 'The ZIP code to be monitored taken from Weather.com'), realtime=False)
        self.add_option(BoolOption('Weather', 'show_error_message',
            bool(self.show_error_message), 'Show error messages',
            'Show an error message on invalid location code'))
        self.add_option(BoolOption('Weather', 'use_metric',
            bool(self.use_metric), 'Use celsius temperature ',
            'Use the metric system for measuring values'))
        self.add_option(BoolOption('Weather', 'mini',
            bool(self.mini), 'Use mini-mode',
            'Switch to the mini-mode'))
        self.add_option(BoolOption('Weather', 'show_daytemp',
            bool(self.show_daytemp), 'Show 6 day temperature',
            'Show 6 day temperature high/low'))
        self.add_option(FontOption('Weather','font',
            self.font, 'Font',
            'font'))
        self.add_option(ColorOption('Weather','font_color',
            self.font_color, 'Text color', 'font_color'))
        self.add_option(ColorOption('Weather','background_color',
            self.background_color, 'Back color(only with default theme)', 'only works with default theme'))

    # attribute-"setter", handles setting of attributes
    def __setattr__(self, name, value):
        # call Screenlet.__setattr__ in baseclass (ESSENTIAL!!!!)
        screenlets.Screenlet.__setattr__(self, name, value)
        # check for this Screenlet's attributes, we are interested in:
        if name == "ZIP":
            self.__dict__[name] = value
            gobject.idle_add(self.update_weather_data)
        if name == "update_interval":
            if value > 0:
                self.__dict__['update_interval'] = value
                if self.__timeout:
                    gobject.source_remove(self.__timeout)
                self.__timeout = gobject.timeout_add(value * 1000, self.update)
            else:
                # TODO: raise exception!!!
                pass

    def on_init (self):
        print "Screenlet has been initialized."
        # add default menuitems
        self.add_default_menuitems()

    def update(self):
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
            #    temp[0]["where"] = temp[0]["where"][:temp[0]["where"].find(',')]
            self.latest = temp
            self.latestHourly = temp2
            self.updated_recently = 1
            self.redraw_canvas()

    def printCity(self, jsonWeatherDataCityDict) :
        print jsonWeatherDataCityDict["country"], jsonWeatherDataCityDict["name"], jsonWeatherDataCityDict["id"]

    def printWeather(self, weatherDict):
        print "%s: t: %d - %d, p: %d, h: %d%%" % (
            self.getWeatherDate(weatherDict),
            self.getMinTemp(weatherDict),
            self.getMaxTemp(weatherDict),
            self.getPressure(weatherDict),
            self.getHumidity(weatherDict))

    def getWeatherDate(self, weatherDict):
        return datetime.datetime.fromtimestamp(int(weatherDict["dt"])).strftime('%Y-%m-%d')

    def getMinTemp(self, weatherDict):
        return int(round(self.tempToCelsius(weatherDict["temp"]["min"])))

    def getMaxTemp(self, weatherDict):
        return int(round(self.tempToCelsius(weatherDict["temp"]["max"])))

    def getDayTemp(self, weatherDict):
        return int(round(self.tempToCelsius(weatherDict["temp"]["day"])))

    def getPressure(self, weatherDict):
        return int(round(self.pressure_hPa_to_mmHg(weatherDict["pressure"])))

    def getHumidity(self, weatherDict):
        return weatherDict["humidity"]

    def tempToCelsius(self, temp):
        return temp - 273.15

    def pressure_hPa_to_mmHg(self, hPa):
        return hPa * 0.750061561303

    def getJsonWeather(self) :
        proxies = proxy.Proxy().get_proxy()
        jsonWeatherData = {}
        try:
            baseUrl = 'http://api.openweathermap.org/data/2.5/forecast/daily?lat=%f&lon=%f&cnt=%d'
            latitude = 55.755833
            longitude = 37.617777
            dayCount  =10
            url = baseUrl % (latitude, longitude, dayCount)
            jsonWeatherData = json.loads(urllib2.urlopen(url).read())
            print jsonWeatherData
            print ""
            self.printCity(jsonWeatherData["city"])

            for i in range(len(jsonWeatherData["list"])):
                self.printWeather(jsonWeatherData["list"][i])

        except (IOError, socket.error), e:
            print "Error retrieving weather data", e
            self.show_error(("Error retrieving weather data", e))
        return jsonWeatherData

    def parseWeatherData(self):
        if self.use_metric:
            unit = 'm'
        else:
            unit = 's'

        return self.getJsonWeather()


    def parseWeatherDataHourly(self):
        if self.use_metric:
            unit = 'm'
        else:
            unit = 's'

        return self.getJsonWeather()


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

        tokenized = {
        'where': self.getBetween(data, '<dnam>','</dnam>'),
        'time' : self.getBetween(data, '<tm>','</tm>'),
        'sunr': self.getBetween(data, '<sunr>','</sunr>'),
        'suns' : self.getBetween(data, '<suns>','</suns>'),
        'date' : self.getBetween(data, '<lsup>','</lsup>'),
        'temp' : self.getBetween(data, '<tmp>','</tmp>'),
        'flik' : self.getBetween(data, '<flik>','</flik>'),
        'state' : self.getBetween(data, '<t>','</t>'),
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
        weather = self.getJsonWeather()
        hourly = self.getJsonWeather();

        # set size
        ctx.scale(self.scale, self.scale)
        # draw bg (if theme available)
        ctx.set_operator(cairo.OPERATOR_OVER)
        ctx.set_source_rgba(*self.background_color)
        if self.theme:
            s = self.theme.path
            if (self.mini == False and weather != {}):
                self.theme.render(ctx,'weather-bg')

                if self.theme_name == 'default':self.draw_rounded_rectangle(ctx,11.5,18.5,8,120,80)
                self.theme.render(ctx,'weather-bg')
            else:
                if self.theme_name == 'default':self.draw_rounded_rectangle(ctx,11.5,18.5,8,120,41.8)
                self.theme.render(ctx,'weather-bg-mini')

        ctx.set_source_rgba(*self.font_color)
        # draw memory-graph
        if self.theme:
            if weather == {}:

                self.draw_text(ctx,'<b>No weather information available</b>', 15, 35, self.font.split(' ')[0], 4,  self.width,pango.ALIGN_LEFT)

            else:
                ctx.save()
                ctx.translate(-2, 0)
                ctx.scale(.6,.6)
                iconTranslate = {
                    '01d' : '32',
                    '01n' : '31',
                    '02d' : '30',
                    '02n' : '29',
                    '03d' : '28',
                    '03n' : '27',
                    '04d' : '26',
                    '04n' : '26',
                    '09d' : '12',
                    '09n' : '40',
                    '10d' : '39',
                    '10n' : '45',
                    '11d' : '17',
                    '11n' : '35',
                    '13d' : '41',
                    '13n' : '42',
                    '50d' : '20',
                    '50n' : '20',
                }
                try:
                    icon = iconTranslate.get(weather["list"][0]["weather"][0]["icon"], "48")
                    self.theme.render(ctx,icon)
                except:
                    pass

                ctx.restore()

            #    for x in range(4):
            #        ctx.save()
            #        ctx.translate(28+x*10,3);
            #        icon = str(self.get_icon(int(hourly[x+1]["icon"])) )
            #        ctx.scale(.25,.25)
            #        self.theme.render(ctx,icon)
            #        ctx.restore()

                degree = unichr(176)
                #if len(str(weather[0]["temp"])) == 3:
                ctx.translate(-7, 0)
                self.draw_text(ctx,'<b>' + str(self.getDayTemp(weather["list"][0])) + degree +'</b>', 90,25, self.font.split(' ')[0], 14,  self.width,pango.ALIGN_LEFT)

                #self.draw_text(ctx,'<b>' + weather[0]["where"][:weather[0]["where"].find(',')][:10] +'</b>', -5,50, self.font.split(' ')[0], 6, self.width,pango.ALIGN_RIGHT)

            #    ctx.translate(0, 6)
            #    p_layout = ctx.create_layout()
            #    p_fdesc.set_size(3 * pango.SCALE)
            #    p_layout.set_font_description(p_fdesc)
            #    p_layout.set_markup('<b>'+weather[0]["where"][weather[0]["where"].find(',') + 2:]+'</b>')
            #    ctx.show_layout(p_layout)

            #    ctx.translate(0, 8)
            #    p_layout = ctx.create_layout()
            #    p_fdesc = pango.FontDescription()
            #    p_fdesc.set_family_static("Sans")
            #    p_fdesc.set_size(5 * pango.SCALE)
            #    p_fdesc.set_weight(300)
            #    p_fdesc.set_style(pango.STYLE_NORMAL)   ####render today's highs and lows
            #    p_layout.set_font_description(p_fdesc)
            #    p_layout.set_markup('<b>' + "High: "+weather[1]["high"] + degree + "   Low: " +weather[1]["low"] + degree +'</b>')
            #    ctx.show_layout(p_layout)



#other stuff text


    #            for x in range(4):
    #                ctx.save();
    #                ctx.translate(x*10,0);
    #                p_layout.set_markup('<i>' + ""+hourly[x+1]["hour"] + "h</i>")
    #                ctx.show_layout(p_layout)
    #                ctx.restore();
    #            ctx.translate(0,5);
    #            for x in range(4):
    #                ctx.save();
    #                ctx.translate(x*10,0);
    #                p_layout.set_markup('<b>' + ""+hourly[x+1]["tmp"] + degree + "</b>")
    #                ctx.show_layout(p_layout)
    #                ctx.restore();


        #        ctx.translate(0, 5)
        #        p_layout.set_markup("p:<b>"+weather[0]["pressure"]+"</b>  h:<b>"+weather[0]["humid"] + "%</b>  w:<b>" +weather[0]["windspeed"] + " m/s</b>")
        #        ctx.show_layout(p_layout)

                if (self.mini == False):

                    ctx.save()
                    ctx.translate(14, 60)
                    self.theme.render(ctx,'day-bg')
                    #self.theme['day-bg.svg'].render_cairo(ctx)   ###render the days background
                    #print self.theme.path
                    self.draw_text(ctx,'<b>' + str(self.getMinTemp(weather["list"][1])) + '</b>', 0,0, self.font.split(' ')[0], 6, self.width,pango.ALIGN_LEFT)

                #    p_layout.set_markup('<b>' +weather[1]["day"][:3] + '</b>')
                #    ctx.show_layout(p_layout)
                    ctx.translate(24, 0)
                    self.draw_text(ctx,'<b>' +str(self.getMinTemp(weather["list"][2])) + '</b>', 0,0, self.font.split(' ')[0], 6, self.width,pango.ALIGN_LEFT)

                    ctx.translate(24, 0)
                    self.draw_text(ctx,'<b>' +str(self.getMinTemp(weather["list"][3])) + '</b>', 0,0, self.font.split(' ')[0], 6, self.width,pango.ALIGN_LEFT)

                    ctx.translate(24, 0)
                    self.draw_text(ctx,'<b>' +str(self.getMinTemp(weather["list"][4])) + '</b>', 0,0, self.font.split(' ')[0], 6, self.width,pango.ALIGN_LEFT)

                    ctx.translate(24, 0)
                    self.draw_text(ctx,'<b>' +str(self.getMinTemp(weather["list"][5])) + '</b>', 0,0, self.font.split(' ')[0], 6, self.width,pango.ALIGN_LEFT)

                    ctx.translate(24, 0)
                    self.draw_text(ctx,'<b>' +str(self.getMinTemp(weather["list"][6])) + '</b>', 0,0, self.font.split(' ')[0], 6, self.width,pango.ALIGN_LEFT)


                    ctx.restore()

                #    ctx.save()
                #    ctx.translate(0, 50)   ###render the days background
                #    self.theme['day-bg.svg'].render_cairo(ctx)
                #    p_layout = ctx.create_layout()
                #    p_fdesc = pango.FontDescription()
                #    p_fdesc.set_family_static("Monospace")
                #    p_fdesc.set_size(3 * pango.SCALE)
                #    p_fdesc.set_weight(300)    ###render the days of the week (second row)
                #    p_fdesc.set_style(pango.STYLE_NORMAL)
                #    p_layout.set_font_description(p_fdesc)
                #    p_layout.set_markup('<b>' + "  "+weather[4]["day"].center(14)+weather[5]["day"].center(14)+weather[6]["day"].center(12)+'</b>')
                #    ctx.show_layout(p_layout)
                #    ctx.restore()

                    #ctx.save()
                    #ctx.translate(36, 28)
                    #self.theme['divider.svg'].render_cairo(ctx)
                    #ctx.translate(31,0)     ######render the dividers
                    #self.theme['divider.svg'].render_cairo(ctx)
                    #ctx.restore()


                    #ctx.save()
                    #ctx.translate(14, 68)
                    #self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[1]["nighticon"]))+ '.png',22,22)
                    #ctx.translate(24,0)
                    #self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[2]["dayicon"]))+ '.png',22,22)
                    #ctx.translate(24,0)
                    #self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[3]["dayicon"]))+ '.png',22,22)
                    #ctx.translate(24, 0)
                    #self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[4]["dayicon"]))+ '.png',22,22)
                    #ctx.translate(24,0)
                    #self.draw_scaled_image(ctx,0,0,self.theme.path + '/' +self.get_icon(int(weather[5]["dayicon"]))+ '.png',22,22)
                    #ctx.restore()

                    if self.show_daytemp == True:
                        ctx.save()

                        ctx.translate(16,90)
                        self.draw_text(ctx,'<b>' + str(self.getMaxTemp(weather["list"][1])) +degree+'</b>'+ str(self.getMinTemp(weather["list"][1])) +degree, 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
                        ctx.translate(24, 0)
                        self.draw_text(ctx,'<b>' + str(self.getMaxTemp(weather["list"][2])) +degree+'</b>'+ str(self.getMinTemp(weather["list"][2])) +degree, 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
                        ctx.translate(24,0)
                        self.draw_text(ctx,'<b>' + str(self.getMaxTemp(weather["list"][3])) +degree+'</b>'+ str(self.getMinTemp(weather["list"][3])) +degree, 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
                        ctx.translate(24,0)
                        self.draw_text(ctx,'<b>' + str(self.getMaxTemp(weather["list"][4])) +degree+'</b>'+ str(self.getMinTemp(weather["list"][4])) +degree, 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)
                        ctx.translate(24,0)
                        self.draw_text(ctx,'<b>' + str(self.getMaxTemp(weather["list"][5])) +degree+'</b>'+ str(self.getMinTemp(weather["list"][5])) +degree, 0,0, self.font.split(' ')[0], 4, self.width,pango.ALIGN_LEFT)


                        ctx.restore()



                self.draw_text(ctx,'<b>' + str(self.getMaxTemp(weather["list"][1]))+degree+'</b>', 68, 28, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)


                self.draw_text(ctx,'<b>' + str(self.getMinTemp(weather["list"][1]))+degree+'</b>', 68, 34, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)

                #if weather[1]["dayppcp"] <> '0':
                    #self.draw_text(ctx,'<i>' + weather[1]["dayppcp"]+'%</i>', 68, 40, self.font.split(' ')[0], 5, self.width,pango.ALIGN_LEFT)





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
        if id=="zipcode":
            self.show_edit_dialog()
            self.update()
        if id == "mini":
            self.mini = not self.mini
            self.update()



    def show_edit_dialog(self):
        # create dialog
        dialog = gtk.Dialog("Zip Code", self.window)
        dialog.resize(300, 100)
        dialog.add_buttons(gtk.STOCK_OK, gtk.RESPONSE_OK,
            gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        entrybox = gtk.Entry()
        entrybox.set_text(str(self.ZIP))
        dialog.vbox.add(entrybox)
        entrybox.show()
        # run dialog
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.ZIP = entrybox.get_text()
            self.updated_recently = 1
        dialog.hide()
        self.update()





    def show_error(self, reason=None):

        dialog = gtk.Dialog("Zip Code", self.window)
        dialog.resize(300, 100)
        dialog.add_buttons(gtk.STOCK_OK, gtk.RESPONSE_OK)

        reasonstr = "\nReason: %s" % reason if reason is not None else ""

        label = gtk.Label("Could not reach weather.com.  Check your internet connection and location and try again."+reasonstr)
        dialog.vbox.add(label)
        check = gtk.CheckButton("Do not show this again")
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
