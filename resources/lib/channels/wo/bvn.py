# -*- coding: utf-8 -*-
"""
    Catch-up TV & More
    Copyright (C) 2017  SylvainCecchetto

    This file is part of Catch-up TV & More.

    Catch-up TV & More is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    Catch-up TV & More is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with Catch-up TV & More; if not, write to the Free Software Foundation,
    Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""


# The unicode_literals import only has
# an effect on Python 2.
# It makes string literals as unicode like in Python 3
from __future__ import unicode_literals

from codequick import Route, Resolver, Listitem, utils, Script

from resources.lib.labels import LABELS
from resources.lib import web_utils
import resources.lib.cq_utils as cqu

import inputstreamhelper
import json
import re
import urlquick
import xbmc
import xbmcgui


URL_ROOT = 'https://www.bvn.tv'

# LIVE :
URL_LIVE_DATAS = URL_ROOT + '/wp-content/themes/bvn/assets/js/app.js'
# Get Id
JSON_LIVE = 'https://json.dacast.com/b/%s/%s/%s'
# Id in 3 part
JSON_LIVE_TOKEN = 'https://services.dacast.com/token/i/b/%s/%s/%s'
# Id in 3 part

# REPLAY :
URL_DAYS = URL_ROOT + '/uitzendinggemist/'
URL_REPLAY_STREAM = 'https://start-player.npo.nl/video/%s/streams?profile=dash-widevine&quality=npo&tokenId=%s&streamType=broadcast&mobile=0&ios=0&isChromecast=0'
# Id video, tokenId
URL_SUBTITLE = 'https://rs.poms.omroep.nl/v1/api/subtitles/%s'
# Id Video

def replay_entry(plugin, item_id):
    """
    First executed function after replay_bridge
    """
    return list_days(plugin, item_id)


@Route.register
def list_days(plugin, item_id):
    """
    Build categories listing
    - day 1
    - day 2
    - ...
    """
    
    resp = urlquick.get(URL_DAYS)
    root = resp.parse("div", attrs={"id": "missed"})
    
    day_id = 0
    for title in root.iterfind(".//h3[@class='m-section__title']"):
        day_title = title.text
        day_id = day_id + 1

        item = Listitem()
        item.label = day_title
        item.set_callback(
            list_videos,
            item_id=item_id,
            day_id=day_id)
        yield item


@Route.register
def list_videos(plugin, item_id, day_id):
    resp = urlquick.get(URL_DAYS)
    root = resp.parse("ul", attrs={"id": "slick-missed-day-%s" % (day_id)})
    
    for broadcast in root.iterfind(".//li"):
        video_time = broadcast.find(".//time[@class='m-section__scroll__item__bottom__time']").text.replace('.', ':')
        video_title = video_time + " - " + broadcast.find(".//span[@class='m-section__scroll__item__bottom__title']").text
        
        subtitle = broadcast.find("span[@class='m-section__scroll__item__bottom__title--sub']")
        if subtitle is not None and subtitle.text is not None:
            video_title += ": " + subtitle
            
        video_image = URL_ROOT + broadcast.find('.//img').get('data-src')
        video_url = URL_ROOT + broadcast.find('.//a').get('href')
        
        item = Listitem()
        item.label = video_title
        item.art['thumb'] = video_image

        item.set_callback(
            get_video_url,
            item_id=item_id,
            video_url=video_url,
            item_dict=cqu.item2dict(item))
        yield item


@Resolver.register
def get_video_url(
        plugin, item_id, video_url, item_dict, download_mode=False, video_label=None):

    xbmc_version = int(xbmc.getInfoLabel("System.BuildVersion").split('-')[0].split('.')[0])

    if xbmc_version < 18:
        xbmcgui.Dialog().ok(
            'Info',
            plugin.localize(30602))
        return False

    is_helper = inputstreamhelper.Helper('mpd', drm='widevine')
    if not is_helper.check_inputstream():
        return False

    resp = urlquick.get(video_url, max_age = -1)

    token_id = re.compile(
        r'start\-player\.npo\.nl\/embed\/(.*?)\"').findall(resp.text)[0]
    video_id = re.compile(
        r'\"iframe\-(.*?)\"').findall(resp.text)[0]

    resp2 = urlquick.get(URL_REPLAY_STREAM % (video_id, token_id), max_age = -1)
    json_parser = json.loads(resp2.text)
    
    if "html" in json_parser and "Deze video mag niet bekeken worden vanaf jouw locatie" in json_parser["html"]:
        plugin.notify('ERROR', plugin.localize(30713))
        return False
        
    if "html" in json_parser and "Deze video is niet beschikbaar" in json_parser["html"]:
        plugin.notify('ERROR', plugin.localize(30716))
        return False
    
    licence_url = json_parser["stream"]["keySystemOptions"][0]["options"]["licenseUrl"]
    licence_url_header = json_parser["stream"]["keySystemOptions"][0]["options"]["httpRequestHeaders"]
    xcdata_value = licence_url_header["x-custom-data"]


    item = Listitem()
    item.path = json_parser["stream"]["src"]
    item.label = item_dict['label']
    item.info.update(item_dict['info'])
    item.art.update(item_dict['art'])
    
    if plugin.setting.get_boolean('active_subtitle'):
        item.subtitles.append(URL_SUBTITLE % video_id)
    
    item.property['inputstreamaddon'] = 'inputstream.adaptive'
    item.property['inputstream.adaptive.manifest_type'] = 'mpd'
    item.property['inputstream.adaptive.license_type'] = 'com.widevine.alpha'
    item.property['inputstream.adaptive.license_key'] = licence_url + '|Content-Type=&User-Agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3041.0 Safari/537.36&x-custom-data=%s|R{SSM}|' % xcdata_value

    return item


def live_entry(plugin, item_id, item_dict):
    return get_live_url(plugin, item_id, item_id.upper(), item_dict)


@Resolver.register
def get_live_url(plugin, item_id, video_id, item_dict):

    resp = urlquick.get(URL_LIVE_DATAS)
    list_id_values = re.compile(
        r'dacast\(\'(.*?)\'\,').findall(resp.text)[0].split('_')

    resp2 = urlquick.get(JSON_LIVE % (list_id_values[0], list_id_values[1], list_id_values[2]))
    live_json_parser = json.loads(resp2.text)

    # json with token
    resp3 = urlquick.get(JSON_LIVE_TOKEN % (list_id_values[0], list_id_values[1], list_id_values[2]))
    token_json_parser = json.loads(resp3.text)

    return live_json_parser["hls"] + \
        token_json_parser["token"]
