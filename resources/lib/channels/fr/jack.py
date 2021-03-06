# -*- coding: utf-8 -*-
"""
    Catch-up TV & More
    Copyright (C) 2018  SylvainCecchetto

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
from resources.lib import resolver_proxy

import re
import json
import urlquick

# TO DO
# ....


URL_ROOT = 'https://jack.canal.fr'
# ChannelName

URL_VIDEOS = URL_ROOT + '/video'
# PageId


def replay_entry(plugin, item_id):
    """
    First executed function after replay_bridge
    """
    return list_programs(plugin, item_id)


@Route.register
def list_programs(plugin, item_id):
    """
    Build categories listing
    - Tous les programmes
    - Séries
    - Informations
    - ...
    """
    resp = urlquick.get(URL_VIDEOS)
    json_value = re.compile(
        r'window.APP_STATE\=(.*?)\}\;').findall(resp.text)[0]
    json_parser = json.loads(json_value + '}')

    for program_datas in json_parser["page"]["data"]["blocks"]:
        if program_datas["container"] == 'content':
            if 'template' in program_datas["content"]:
                program_title = program_datas["content"]["title"]

                item = Listitem()
                item.label = program_title
                item.set_callback(
                    list_videos,
                    item_id=item_id,
                    program_title=program_title)
                yield item

@Route.register
def list_videos(plugin, item_id, program_title):

    resp = urlquick.get(URL_VIDEOS)
    json_value = re.compile(
        r'window.APP_STATE\=(.*?)\}\;').findall(resp.text)[0]
    json_parser = json.loads(json_value + '}')

    for program_datas in json_parser["page"]["data"]["blocks"]:
        if program_datas["container"] == 'content':
            if 'template' in program_datas["content"]:
                if program_title == program_datas["content"]["title"]:

                    for video_datas in program_datas["content"]["articles"]:
                        if 'video' in video_datas:
                            video_title = video_datas["title"]
                            video_image = video_datas["mainMedia"]["links"][0]["href"]
                            video_image = video_image.replace('{width}', '800').replace('{height}', '450')
                            video_plot = video_datas["abstract"]
                            video_id = video_datas["video"]["id"]
                            video_source = video_datas["video"]["source"]
                            date_value = video_datas["publishedAt"].split('T')[0]

                            item = Listitem()
                            item.label = video_title
                            item.art['thumb'] = video_image
                            item.info['plot'] = video_plot
                            item.info.date(date_value, '%Y-%m-%d')

                            item.context.script(
                                get_video_url,
                                plugin.localize(LABELS['Download']),
                                item_id=item_id,
                                video_id=video_id,
                                video_source=video_source,
                                video_label=LABELS[item_id] + ' - ' + item.label,
                                download_mode=True)

                            item.set_callback(
                                get_video_url,
                                item_id=item_id,
                                video_id=video_id,
                                video_source=video_source)
                            yield item


@Resolver.register
def get_video_url(
        plugin, item_id, video_id, video_source, download_mode=False, video_label=None):

    if 'youtube' in video_source:
        return resolver_proxy.get_stream_youtube(
            plugin, video_id, download_mode, video_label)
    elif 'dailymotion' in video_source: 
        return resolver_proxy.get_stream_dailymotion(
            plugin, video_id, download_mode, video_label)