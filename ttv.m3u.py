# -*- coding: utf-8 -*-
# The code is modification of official Torrent-TV Kodi AddOn:
# Copyright (c) 2013 Torrent-TV.RU
# Writer (c) 2013, Welicobratov K.A., E-mail: 07pov23@gmail.com
# Edited (c) 2015, Vorotilin D.V., E-mail: dvor85@mail.ru

# imports
import xbmcgui, xbmc, xbmcaddon, xbmcplugin
import sys, os
import json
import urllib, urllib2
import uuid
import threading, Queue



ADDON = xbmcaddon.Addon('')
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_ICON = ADDON.getAddonInfo('icon')
ADDON_PATH = ADDON.getAddonInfo('path')
ADDON_ICON = ADDON.getAddonInfo('icon')
PTR_FILE = ADDON.getSetting('port_path')
API_MIRROR = ADDON.getSetting('api_mirror')
ACE_IP = ADDON.getSetting('ip_addr')
ACE_PORT = ADDON.getSetting('outport')
SITE_MIRROR = '1ttv.org' if API_MIRROR == '1ttvxbmc.top' else 'torrent-tv.ru'

DATA_PATH = xbmc.translatePath(os.path.join("special://profile/addon_data", ADDON_ID))
TTV_VERSION = '1.5.3'
chGroups = ['0', 'Детские', 'Музыка', 'Фильмы', 'Спортивные', 'Общие', 'Познавательные', 'Новостные', 'Развлекательные', '9', 'Мужские',
            'Региональные', 'Религиозные', '13', '14', '15']

ch_buffer = [None] * 2000    # MAX num of channels
NUM_OF_PARALLEL_REQ = 10     # MAX num of parallel serv request

def showNotification(msg, icon=ADDON_ICON):
    try:
        if isinstance(msg, unicode):
            msg = msg.encode('utf-8', 'ignore')
        xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), msg, icon)
    except Exception as e:
        log.e('showNotification error: "{0}"'.format(e))


def tryStringToInt(str_val):
    try:
        return int(str_val)
    except:
        return 0


def GET(target, post=None, cookie=None, headers=None, tries=1):
    if not target:
        return 0
    t = 0
    if not headers:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.99 Safari/537.36'}
    req = urllib2.Request(url=target, data=post, headers=headers)

    if post:
        req.add_header("Content-type", "application/x-www-form-urlencoded")
    if cookie:
        for coo in cookie:
            req.add_header('Cookie', coo)
            #         req.add_header('Cookie', 'PHPSESSID=%s' % cookie)
    while True: #not isCancel():
        t += 1
        if 0 < tries < t:
            return#raise Exception('Attempts are over')
        try:
            resp = urllib2.urlopen(req, timeout=6)
            try:
                http = resp.read()
                return http
            finally:
                resp.close()
        except Exception, e:
            if t % 10 == 0:
                #log.e('GET EXCEPT [{0}]'.format(e))
                #if not isCancel():
                xbmc.sleep(3000)

def get_chan_url (ch, i=0):
    global ch_buffer
    ch_buffer[i] = None
    if not (ch.get('name') or ch.get('id')):
        queue.get(True, None)
        queue.task_done()
        return 0
    chID = str(ch['id']).encode('utf8')
    data = GET(
        "http://{0}/v3/translation_stream.php?session={1}&channel_id={2}&typeresult=json".format(API_MIRROR, session, chID), tries=3)
    try:
        jdata2 = json.loads(data)
    except Exception as e:
        queue.get(True, None)
        queue.task_done()
        return 0
    if not jdata2 or tryStringToInt(jdata2.get("success")) == 0 or not jdata2.get("source"):
        queue.get(True, None)
        queue.task_done()
        return 0
    chURL = jdata2["source"].encode('utf8')
    if not chURL:
        queue.get(True, None)
        queue.task_done()
        return 0
    ch_buffer[i] = {'channel': ch, 'url': chURL}
    queue.get(True, None)
    queue.task_done()
    return 1

try:

    data = GET('http://{0}/v3/version.php?application=xbmc&version={1}'.format(API_MIRROR, TTV_VERSION))
    try:
        jdata = json.loads(data)
        if tryStringToInt(jdata.get('success')) == 0:
            raise Exception(jdata.get('error'))
            #             raise Exception('Test')
    except Exception as e:
        # log.e('onInit error: {0}'.format(e))
        msg = 'Ошибка Torrent-TV.RU'
        showNotification(msg, xbmcgui.NOTIFICATION_ERROR)
        sys.exit(0)
    if tryStringToInt(jdata['support']) == 0:
        msg = "Текущая версия приложения (%s) не поддерживается. Последняя версия %s " % (
        TTV_VERSION, jdata['last_version'].encode('utf-8'))
        showNotification(msg, xbmcgui.NOTIFICATION_ERROR)
        sys.exit(0)

    pDialog = xbmcgui.DialogProgressBG()
    pDialog.create('TTV.M3U Generator', 'Авторизация ...')

    guid = ADDON.getSetting("")
    if guid == '':
        guid = str(uuid.uuid1())
        ADDON.setSetting("uuid", guid)
    guid = guid.replace('-', '')
    data = GET('http://{0}/v3/auth.php?username={1}&password={2}&typeresult=json&application=xbmc&guid={3}'.format(
        API_MIRROR, ADDON.getSetting('login'), ADDON.getSetting('password'), guid))
    try:
        jdata = json.loads(data)
        if tryStringToInt(jdata.get('success')) == 0:
            raise Exception(jdata.get('error'))
    except Exception as e:
        msg = 'Ошибка Авторизации'
        showNotification(msg, xbmcgui.NOTIFICATION_ERROR)

    user = {"login": ADDON.getSetting('login'), "balance": jdata["balance"], "vip": jdata["balance"] > 1}

    session = jdata['session']

    '''msg = "Получение списка каналов"
    showNotification(msg, xbmcgui.NOTIFICATION_INFO)'''
    pDialog.update(0, 'TTV.M3U Generator', 'Получение списка каналов ...')

    # GET channels list with channels IDs
    param = 'all'  # list of all channels
    data = GET(
        'http://{0}/v3/translation_list.php?session={1}&type={2}&typeresult=json'.format(API_MIRROR, session, param),
        cookie=['PHPSESSID=%s' % session], tries=10)
    try:
        jdata = json.loads(data)
    except:
        msg = 'Ошибка Torrent-TV.RU'
        showNotification(msg, xbmcgui.NOTIFICATION_ERROR)

    queue = Queue.Queue(NUM_OF_PARALLEL_REQ)

    num_of_channels = len(jdata['channels'])
    i = 0
    for ch in jdata['channels']:
        queue.put(1, True, None)
        t = threading.Thread(target=get_chan_url, args=(ch, i))
        t.daemon = True
        t.start()
        i += 1
        pDialog.update(i * 100 / num_of_channels, 'TTV.M3U Generator', 'Получение списка каналов ...')

    queue.join()  # block until all tasks are done

    # Write ch_buffer to m3u file
    PLUGIN_DATA_PATH = ADDON.getSetting('m3upath')
    if PLUGIN_DATA_PATH == 'default':
        PLUGIN_DATA_PATH = xbmc.translatePath(os.path.join("special://profile/addon_data", 'script.module.ttv.m3u'))

    if (sys.platform == 'win32') or (sys.platform == 'win64'):
        PLUGIN_DATA_PATH = PLUGIN_DATA_PATH.decode('utf-8')
    m3ufile = os.path.join(PLUGIN_DATA_PATH, 'ttv.m3u')
    if not os.path.exists(PLUGIN_DATA_PATH):
        os.makedirs(PLUGIN_DATA_PATH)
        # if os.path.exists(m3ufile):
        #    os.remove(m3ufile)
    try:
        out = open(m3ufile, 'w')
    except:
        msg = "Ошибка открытия файла"
        showNotification(msg, xbmcgui.NOTIFICATION_ERROR)

    num_of_channels = 0
    if ADDON.getSetting('sortbycategories') == 'false':
        for i in range(0, len(ch_buffer)):
            if ch_buffer[i] is None:
                continue
            chNAME = ch_buffer[i]['channel']['name'].encode('utf8')
            chGROUP = (chGroups[ch_buffer[i]['channel']['group']])
            chURL = ch_buffer[i]['url']
            out.write(
                '#EXTINF:0 group-title="' + chGROUP + '",' + chNAME + '\nhttp://' + ACE_IP + ':' + ACE_PORT + '/ace/getstream?url=' + chURL + '\n')
            num_of_channels += 1
    else:
        for group_num in range(0, len(chGroups)):
            for i in range(0, len(ch_buffer)):
                if ch_buffer[i] is None:
                    continue
                chGROUP = ch_buffer[i]['channel']['group']
                if chGROUP != group_num:
                    continue
                chGROUP = chGroups[chGROUP]
                chNAME = ch_buffer[i]['channel']['name'].encode('utf8')
                chURL = ch_buffer[i]['url']
                out.write(
                    '#EXTINF:0 group-title="' + chGROUP + '",' + chNAME + '\nhttp://' + ACE_IP + ':' + ACE_PORT + '/ace/getstream?url=' + chURL + '\n')
                num_of_channels += 1

    out.close()
    msg = 'Плейлист обновлен (каналов-' + str(num_of_channels) + ')'
    showNotification(msg, xbmcgui.NOTIFICATION_INFO)
except:
    msg = 'Ошибка'
    showNotification(msg, xbmcgui.NOTIFICATION_ERROR)
finally:
    pDialog.close()


