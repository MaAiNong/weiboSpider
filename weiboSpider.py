#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import codecs
import csv
import os
import random
import re
import sys
import traceback
from collections import OrderedDict
from datetime import datetime, timedelta
from time import sleep

import requests
from lxml import etree
from requests.adapters import HTTPAdapter
from tqdm import tqdm


class Weibo(object):
    cookie = {'_T_WM':'34853770235',
    'XSRF-TOKEN':'eeb57a',
    'WEIBOCN_FROM':'1110006030',
    'SUB':'_2A25wvEaRDeRhGeNG71cX9S7OzzyIHXVQX2rZrDV6PUJbkdAKLWnzkW1NS0RzOJFapHs5ZWhMaIdPtn7mrJEMCCEe',
    'SUHB':'0ebtEDMZlObOAx',
    'SCF':'ApnmkP9Haov-qJVG5j7Pcm40-Fu0xOUsFTits8kij32_spSbR3645CVlWOei_x-r_4b1f_IsizfkTk5wi469u1k.',
    'SSOLoginState':'1572353729',
    'MLOGIN':'1',
    'M_WEIBOCN_PARAMS':'luicode%3D10000011%26lfid%3D102803%26uicode%3D20000174'}

    def __init__(self,
                 filter=0,
                 since_date='1900-01-01',
                 mongodb_write=0,
                 mysql_write=0,
                 pic_download=0,
                 video_download=0):
        """Weibo类初始化"""
        if filter != 0 and filter != 1:
            sys.exit(u'filter值应为0或1,请重新输入')
        if not self.is_date(since_date):
            sys.exit(u'since_date值应为yyyy-mm-dd形式,请重新输入')
        if mongodb_write != 0 and mongodb_write != 1:
            sys.exit(u'mongodb_write值应为0或1,请重新输入')
        if mysql_write != 0 and mysql_write != 1:
            sys.exit(u'mysql_write值应为0或1,请重新输入')
        if pic_download != 0 and pic_download != 1:
            sys.exit(u'pic_download值应为0或1,请重新输入')
        if video_download != 0 and video_download != 1:
            sys.exit(u'video_download值应为0或1,请重新输入')
        self.user_id = ''  # 用户id,如昵称为"Dear-迪丽热巴"的id为'1669879400'
        self.filter = filter  # 取值范围为0、1,程序默认值为0,代表要爬取用户的全部微博,1代表只爬取用户的原创微博
        self.since_date = since_date  # 起始时间，即爬取发布日期从该值到现在的微博，形式为yyyy-mm-dd
        self.mongodb_write = mongodb_write  # 值为0代表不将结果写入MongoDB数据库,1代表写入
        self.mysql_write = mysql_write  # 值为0代表不将结果写入MySQL数据库,1代表写入
        self.pic_download = pic_download  # 取值范围为0、1,程序默认值为0,代表不下载微博原始图片,1代表下载
        self.video_download = video_download  # 取值范围为0、1,程序默认为0,代表不下载微博视频,1代表下载
        self.got_num = 0  # 爬取到的微博数
        self.weibo = []  # 存储爬取到的所有微博信息
        self.user = {}  # 存储爬取到的用户信息
        self.weibo_id_list = []  # 存储爬取到的所有微博id
        self.mysql_config = {
        }  # MySQL数据库连接配置，可以不填，当使用者的mysql用户名、密码等与本程序默认值不同时，需要通过mysql_config来自定义

    def is_date(self, since_date):
        """判断日期格式是否正确"""
        try:
            datetime.strptime(since_date, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def deal_html(self, url):
        """处理html"""
        try:
            html = requests.get(url, cookies=self.cookie).content
            selector = etree.HTML(html)
            return selector
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def deal_garbled(self, info):
        """处理乱码"""
        try:
            info = (info.xpath('string(.)').replace(u'\u200b', '').encode(
                sys.stdout.encoding, 'ignore').decode(sys.stdout.encoding))
            return info
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_nickname(self):
        """获取用户昵称"""
        try:
            url = 'https://weibo.cn/%s/info' % (self.user_id)
            selector = self.deal_html(url)
            nickname = selector.xpath('//title/text()')[0]
            nickname = nickname[:-3]
            if nickname == u'登录 - 新' or nickname == u'新浪':
                sys.exit(u'cookie错误或已过期,请按照README中方法重新获取')
            self.user['nickname'] = nickname
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def user_to_mongodb(self):
        """将爬取的用户信息写入MongoDB数据库"""
        user_list = [self.user]
        self.info_to_mongodb('user', user_list)
        print(u'%s信息写入MongoDB数据库完毕' % self.user['nickname'])

    def user_to_mysql(self):
        """将爬取的用户信息写入MySQL数据库"""
        mysql_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'password': '123456',
            'charset': 'utf8mb4'
        }
        # 创建'weibo'数据库
        create_database = """CREATE DATABASE IF NOT EXISTS weibo DEFAULT
                         CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"""
        self.mysql_create_database(mysql_config, create_database)
        # 创建'user'表
        create_table = """
                CREATE TABLE IF NOT EXISTS user (
                id varchar(12) NOT NULL,
                nickname varchar(30),
                weibo_num INT,
                following INT,
                followers INT,
                PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
        self.mysql_create_table(mysql_config, create_table)
        self.mysql_insert(mysql_config, 'user', [self.user])
        print(u'%s信息写入MySQL数据库完毕' % self.user['nickname'])

    def user_to_database(self):
        """将用户信息写入数据库"""
        if self.mysql_write:
            self.user_to_mysql()
        if self.mongodb_write:
            self.user_to_mongodb()

    def print_user_info(self):
        """打印微博用户信息"""
        print(u'用户昵称: %s' % self.user['nickname'])
        print(u'用户id: %s' % self.user['id'])
        print(u'微博数: %d' % self.user['weibo_num'])
        print(u'关注数: %d' % self.user['following'])
        print(u'粉丝数: %d' % self.user['followers'])

    def get_user_info(self, selector):
        """获取用户昵称、微博数、关注数、粉丝数"""
        try:
            self.get_nickname()  # 获取用户昵称
            user_info = selector.xpath("//div[@class='tip2']/*/text()")
            weibo_num = int(user_info[0][3:-1])
            following = int(user_info[1][3:-1])
            followers = int(user_info[2][3:-1])
            self.user['weibo_num'] = weibo_num
            self.user['following'] = following
            self.user['followers'] = followers
            self.user['id'] = self.user_id
            self.print_user_info()
            self.user_to_database()
            print('*' * 100)
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_page_num(self, selector):
        """获取微博总页数"""
        try:
            if selector.xpath("//input[@name='mp']") == []:
                page_num = 1
            else:
                page_num = (int)(
                    selector.xpath("//input[@name='mp']")[0].attrib['value'])
            return page_num
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_long_weibo(self, weibo_link):
        """获取长原创微博"""
        try:
            selector = self.deal_html(weibo_link)
            info = selector.xpath("//div[@class='c']")[1]
            wb_content = self.deal_garbled(info)
            wb_time = info.xpath("//span[@class='ct']/text()")[0]
            weibo_content = wb_content[wb_content.find(':') +
                                       1:wb_content.rfind(wb_time)]
            return weibo_content
        except Exception as e:
            return u'网络出错'
            print('Error: ', e)
            traceback.print_exc()

    def get_original_weibo(self, info, weibo_id):
        """获取原创微博"""
        try:
            weibo_content = self.deal_garbled(info)
            weibo_content = weibo_content[:weibo_content.rfind(u'赞')]
            a_text = info.xpath('div//a/text()')
            if u'全文' in a_text:
                weibo_link = 'https://weibo.cn/comment/' + weibo_id
                wb_content = self.get_long_weibo(weibo_link)
                if wb_content:
                    weibo_content = wb_content
            return weibo_content
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_long_retweet(self, weibo_link):
        """获取长转发微博"""
        try:
            wb_content = self.get_long_weibo(weibo_link)
            weibo_content = wb_content[:wb_content.rfind(u'原文转发')]
            return weibo_content
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_retweet(self, info, weibo_id):
        """获取转发微博"""
        try:
            original_user = info.xpath("div/span[@class='cmt']/a/text()")
            if not original_user:
                wb_content = u'转发微博已被删除'
                return wb_content
            else:
                original_user = original_user[0]
            wb_content = self.deal_garbled(info)
            wb_content = wb_content[wb_content.find(':') +
                                    1:wb_content.rfind(u'赞')]
            wb_content = wb_content[:wb_content.rfind(u'赞')]
            a_text = info.xpath('div//a/text()')
            if u'全文' in a_text:
                weibo_link = 'https://weibo.cn/comment/' + weibo_id
                weibo_content = self.get_long_retweet(weibo_link)
                if weibo_content:
                    wb_content = weibo_content
            retweet_reason = self.deal_garbled(info.xpath('div')[-1])
            retweet_reason = retweet_reason[:retweet_reason.rindex(u'赞')]
            wb_content = (retweet_reason + '\n' + u'原始用户: ' + original_user +
                          '\n' + u'转发内容: ' + wb_content)
            return wb_content
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def is_original(self, info):
        """判断微博是否为原创微博"""
        is_original = info.xpath("div/span[@class='cmt']")
        if len(is_original) > 3:
            return False
        else:
            return True

    def get_weibo_content(self, info, is_original):
        """获取微博内容"""
        try:
            weibo_id = info.xpath('@id')[0][2:]
            if is_original:
                weibo_content = self.get_original_weibo(info, weibo_id)
            else:
                weibo_content = self.get_retweet(info, weibo_id)
            return weibo_content
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_publish_place(self, info):
        """获取微博发布位置"""
        try:
            div_first = info.xpath('div')[0]
            a_list = div_first.xpath('a')
            publish_place = u'无'
            for a in a_list:
                if ('place.weibo.com' in a.xpath('@href')[0]
                        and a.xpath('text()')[0] == u'显示地图'):
                    weibo_a = div_first.xpath("span[@class='ctt']/a")
                    if len(weibo_a) >= 1:
                        publish_place = weibo_a[-1]
                        if (u'视频' == div_first.xpath(
                                "span[@class='ctt']/a/text()")[-1][-2:]):
                            if len(weibo_a) >= 2:
                                publish_place = weibo_a[-2]
                            else:
                                publish_place = u'无'
                        publish_place = self.deal_garbled(publish_place)
                        break
            return publish_place
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_publish_time(self, info):
        """获取微博发布时间"""
        try:
            str_time = info.xpath("div/span[@class='ct']")
            str_time = self.deal_garbled(str_time[0])
            publish_time = str_time.split(u'来自')[0]
            if u'刚刚' in publish_time:
                publish_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            elif u'分钟' in publish_time:
                minute = publish_time[:publish_time.find(u'分钟')]
                minute = timedelta(minutes=int(minute))
                publish_time = (datetime.now() -
                                minute).strftime('%Y-%m-%d %H:%M')
            elif u'今天' in publish_time:
                today = datetime.now().strftime('%Y-%m-%d')
                time = publish_time[3:]
                publish_time = today + ' ' + time
                if len(publish_time) > 16:
                    publish_time = publish_time[:16]
            elif u'月' in publish_time:
                year = datetime.now().strftime('%Y')
                month = publish_time[0:2]
                day = publish_time[3:5]
                time = publish_time[7:12]
                publish_time = year + '-' + month + '-' + day + ' ' + time
            else:
                publish_time = publish_time[:16]
            return publish_time
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_publish_tool(self, info):
        """获取微博发布工具"""
        try:
            str_time = info.xpath("div/span[@class='ct']")
            str_time = self.deal_garbled(str_time[0])
            if len(str_time.split(u'来自')) > 1:
                publish_tool = str_time.split(u'来自')[1]
            else:
                publish_tool = u'无'
            return publish_tool
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_weibo_footer(self, info):
        """获取微博点赞数、转发数、评论数"""
        try:
            footer = {}
            pattern = r'\d+'
            str_footer = info.xpath('div')[-1]
            str_footer = self.deal_garbled(str_footer)
            str_footer = str_footer[str_footer.rfind(u'赞'):]
            weibo_footer = re.findall(pattern, str_footer, re.M)

            up_num = int(weibo_footer[0])
            footer['up_num'] = up_num

            retweet_num = int(weibo_footer[1])
            footer['retweet_num'] = retweet_num

            comment_num = int(weibo_footer[2])
            footer['comment_num'] = comment_num
            return footer
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def extract_picture_urls(self, info, weibo_id):
        """提取微博原始图片url"""
        try:
            a_list = info.xpath('div/a/@href')
            first_pic = 'https://weibo.cn/mblog/pic/' + weibo_id + '?rl=0'
            all_pic = 'https://weibo.cn/mblog/picAll/' + weibo_id + '?rl=1'
            if first_pic in a_list:
                if all_pic in a_list:
                    selector = self.deal_html(all_pic)
                    preview_picture_list = selector.xpath('//img/@src')
                    picture_list = [
                        p.replace('/thumb180/', '/large/')
                        for p in preview_picture_list
                    ]
                    picture_urls = ','.join(picture_list)
                else:
                    if info.xpath('.//img/@src'):
                        preview_picture = info.xpath('.//img/@src')[-1]
                        picture_urls = preview_picture.replace(
                            '/wap180/', '/large/')
                    else:
                        sys.exit(
                            u"爬虫微博可能被设置成了'不显示图片'，请前往"
                            u"'https://weibo.cn/account/customize/pic'，修改为'显示'"
                        )
            else:
                picture_urls = u'无'
            return picture_urls
        except Exception as e:
            return u'无'
            print('Error: ', e)
            traceback.print_exc()

    def get_picture_urls(self, info, is_original):
        """获取微博原始图片url"""
        try:
            weibo_id = info.xpath('@id')[0][2:]
            picture_urls = {}
            if is_original:
                original_pictures = self.extract_picture_urls(info, weibo_id)
                picture_urls['original_pictures'] = original_pictures
                if not self.filter:
                    picture_urls['retweet_pictures'] = u'无'
            else:
                retweet_url = info.xpath("div/a[@class='cc']/@href")[0]
                retweet_id = retweet_url.split('/')[-1].split('?')[0]
                retweet_pictures = self.extract_picture_urls(info, retweet_id)
                picture_urls['retweet_pictures'] = retweet_pictures
                a_list = info.xpath('div[last()]/a/@href')
                original_picture = u'无'
                for a in a_list:
                    if a.endswith(('.gif', '.jpeg', '.jpg', '.png')):
                        original_picture = a
                        break
                picture_urls['original_pictures'] = original_picture
            return picture_urls
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_video_url(self, info, is_original):
        """获取微博视频url"""
        try:
            if is_original:
                div_first = info.xpath('div')[0]
                a_list = div_first.xpath('.//a')
                video_link = u'无'
                for a in a_list:
                    if 'm.weibo.cn/s/video/show?object_id=' in a.xpath(
                            '@href')[0]:
                        video_link = a.xpath('@href')[0]
                        break
                if video_link != u'无':
                    video_link = video_link.replace(
                        'm.weibo.cn/s/video/show', 'm.weibo.cn/s/video/object')
                    wb_info = requests.get(video_link,
                                           cookies=self.cookie).json()
                    video_url = wb_info['data']['object']['stream'].get(
                        'hd_url')
                    if not video_url:
                        video_url = wb_info['data']['object']['stream']['url']
                        if not video_url:  # 说明该视频为直播
                            video_url = u'无'
            else:
                video_url = u'无'
            return video_url
        except Exception as e:
            return u'无'
            print('Error: ', e)
            traceback.print_exc()

    def download_one_file(self, url, file_path, type, weibo_id):
        """下载单个文件(图片/视频)"""
        try:
            if not os.path.isfile(file_path):
                s = requests.Session()
                s.mount(url, HTTPAdapter(max_retries=5))
                downloaded = s.get(url, timeout=(5, 10))
                with open(file_path, 'wb') as f:
                    f.write(downloaded.content)
        except Exception as e:
            error_file = self.get_filepath(
                type) + os.sep + 'not_downloaded.txt'
            with open(error_file, 'ab') as f:
                url = weibo_id + ':' + url + '\n'
                f.write(url.encode(sys.stdout.encoding))
            print('Error: ', e)
            traceback.print_exc()

    def download_files(self, type):
        """下载文件(图片/视频)"""
        try:
            if type == 'img':
                describe = u'图片'
                key = 'original_pictures'
            else:
                describe = u'视频'
                key = 'video_url'
            print(u'即将进行%s下载' % describe)
            file_dir = self.get_filepath(type)
            for w in tqdm(self.weibo, desc=u'%s下载进度' % describe):
                if w[key] != u'无':
                    file_prefix = w['publish_time'][:11].replace(
                        '-', '') + '_' + w['id']
                    if type == 'img' and ',' in w[key]:
                        w[key] = w[key].split(',')
                        for j, url in enumerate(w[key]):
                            file_suffix = url[url.rfind('.'):]
                            file_name = file_prefix + '_' + str(
                                j + 1) + file_suffix
                            file_path = file_dir + os.sep + file_name
                            self.download_one_file(url, file_path, type,
                                                   w['id'])
                    else:
                        if type == 'video':
                            file_suffix = '.mp4'
                        else:
                            file_suffix = w[key][w[key].rfind('.'):]
                        file_name = file_prefix + file_suffix
                        file_path = file_dir + os.sep + file_name
                        self.download_one_file(w[key], file_path, type,
                                               w['id'])
            print(u'%s下载完毕,保存路径:' % describe)
            print(file_dir)
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_one_weibo(self, info):
        """获取一条微博的全部信息"""
        try:
            weibo = OrderedDict()
            is_original = self.is_original(info)
            if (not self.filter) or is_original:
                weibo['id'] = info.xpath('@id')[0][2:]
                weibo['content'] = self.get_weibo_content(info,
                                                          is_original)  # 微博内容
                picture_urls = self.get_picture_urls(info, is_original)
                weibo['original_pictures'] = picture_urls[
                    'original_pictures']  # 原创图片url
                if not self.filter:
                    weibo['retweet_pictures'] = picture_urls[
                        'retweet_pictures']  # 转发图片url
                    weibo['original'] = is_original  # 是否原创微博
                weibo['video_url'] = self.get_video_url(info,
                                                        is_original)  # 微博视频url
                weibo['publish_place'] = self.get_publish_place(info)  # 微博发布位置
                weibo['publish_time'] = self.get_publish_time(info)  # 微博发布时间
                weibo['publish_tool'] = self.get_publish_tool(info)  # 微博发布工具
                footer = self.get_weibo_footer(info)
                weibo['up_num'] = footer['up_num']  # 微博点赞数
                weibo['retweet_num'] = footer['retweet_num']  # 转发数
                weibo['comment_num'] = footer['comment_num']  # 评论数
            else:
                weibo = None
            return weibo
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def print_one_weibo(self, weibo):
        """打印一条微博"""
        print(weibo['content'])
        print(u'微博发布位置：%s' % weibo['publish_place'])
        print(u'发布发布时间：%s' % weibo['publish_time'])
        print(u'发布发布工具：%s' % weibo['publish_tool'])
        print(u'点赞数：%d' % weibo['up_num'])
        print(u'转发数：%d' % weibo['retweet_num'])
        print(u'评论数：%d' % weibo['comment_num'])

    def is_pinned_weibo(self, info):
        """判断微博是否为置顶微博"""
        kt = info.xpath(".//span[@class='kt']/text()")
        if kt and kt[0] == u'置顶':
            return True
        else:
            return False

    def get_one_page(self, page):
        """获取第page页的全部微博"""
        try:
            url = 'https://weibo.cn/u/%s?page=%d' % (self.user_id, page)
            selector = self.deal_html(url)
            info = selector.xpath("//div[@class='c']")
            is_exist = info[0].xpath("div/span[@class='ctt']")
            if is_exist:
                for i in range(0, len(info) - 2):
                    weibo = self.get_one_weibo(info[i])
                    if weibo:
                        if weibo['id'] in self.weibo_id_list:
                            continue
                        publish_time = datetime.strptime(
                            weibo['publish_time'][:10], "%Y-%m-%d")
                        since_date = datetime.strptime(self.since_date,
                                                       "%Y-%m-%d")
                        if publish_time < since_date:
                            if self.is_pinned_weibo(info[i]):
                                continue
                            else:
                                return True
                        self.print_one_weibo(weibo)
                        self.weibo.append(weibo)
                        self.weibo_id_list.append(weibo['id'])
                        self.got_num += 1
                        print('-' * 100)
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_filepath(self, type):
        """获取结果文件路径"""
        try:
            file_dir = os.path.split(
                os.path.realpath(__file__)
            )[0] + os.sep + 'weibo' + os.sep + self.user['nickname']
            if type == 'img' or type == 'video':
                file_dir = file_dir + os.sep + type
            if not os.path.isdir(file_dir):
                os.makedirs(file_dir)
            if type == 'img' or type == 'video':
                return file_dir
            file_path = file_dir + os.sep + self.user_id + '.' + type
            return file_path
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def write_csv(self, wrote_num):
        """将爬取的信息写入csv文件"""
        try:
            result_headers = [
                '微博id',
                '微博正文',
                '原始图片url',
                '微博视频url',
                '发布位置',
                '发布时间',
                '发布工具',
                '点赞数',
                '转发数',
                '评论数',
            ]
            if not self.filter:
                result_headers.insert(3, '被转发微博原始图片url')
                result_headers.insert(4, '是否为原创微博')
            result_data = [w.values() for w in self.weibo][wrote_num:]
            if sys.version < '3':  # python2.x
                reload(sys)
                sys.setdefaultencoding('utf-8')
                with open(self.get_filepath('csv'), 'ab') as f:
                    f.write(codecs.BOM_UTF8)
                    writer = csv.writer(f)
                    if wrote_num == 0:
                        writer.writerows([result_headers])
                    writer.writerows(result_data)
            else:  # python3.x
                with open(self.get_filepath('csv'),
                          'a',
                          encoding='utf-8-sig',
                          newline='') as f:
                    writer = csv.writer(f)
                    if wrote_num == 0:
                        writer.writerows([result_headers])
                    writer.writerows(result_data)
            print(u'%d条微博写入csv文件完毕,保存路径:' % self.got_num)
            print(self.get_filepath('csv'))
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def write_txt(self, wrote_num):
        """将爬取的信息写入txt文件"""
        try:
            temp_result = []
            if wrote_num == 0:
                if self.filter:
                    result_header = u'\n\n原创微博内容: \n'
                else:
                    result_header = u'\n\n微博内容: \n'
                result_header = (u'用户信息\n用户昵称：' + self.user['nickname'] +
                                 u'\n用户id: ' + str(self.user_id) + u'\n微博数: ' +
                                 str(self.user['weibo_num']) + u'\n关注数: ' +
                                 str(self.user['following']) + u'\n粉丝数: ' +
                                 str(self.user['followers']) + result_header)
                temp_result.append(result_header)
            for i, w in enumerate(self.weibo[wrote_num:]):
                temp_result.append(
                    str(wrote_num + i + 1) + ':' + w['content'] + '\n' +
                    u'微博位置: ' + w['publish_place'] + '\n' + u'发布时间: ' +
                    w['publish_time'] + '\n' + u'点赞数: ' + str(w['up_num']) +
                    u'   转发数: ' + str(w['retweet_num']) + u'   评论数: ' +
                    str(w['comment_num']) + '\n' + u'发布工具: ' +
                    w['publish_tool'] + '\n\n')
            result = ''.join(temp_result)
            with open(self.get_filepath('txt'), 'ab') as f:
                f.write(result.encode(sys.stdout.encoding))
            print(u'%d条微博写入txt文件完毕,保存路径:' % self.got_num)
            print(self.get_filepath('txt'))
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def info_to_mongodb(self, collection, info_list):
        """将爬取的信息写入MongoDB数据库"""
        from pymongo import MongoClient

        client = MongoClient()
        db = client['weibo']
        collection = db[collection]
        for info in info_list:
            if not collection.find_one({'id': info['id']}):
                collection.insert_one(info)
            else:
                collection.update_one({'id': info['id']}, {'$set': info})

    def weibo_to_mongodb(self, wrote_num):
        """将爬取的微博信息写入MongoDB数据库"""
        weibo_list = []
        for w in self.weibo[wrote_num:]:
            w['user_id'] = self.user_id
            weibo_list.append(w)
        self.info_to_mongodb('weibo', weibo_list)
        print(u'%d条微博写入MongoDB数据库完毕' % self.got_num)

    def change_mysql_config(self, mysql_config):
        """修改MySQL数据库连接配置"""
        self.mysql_config = mysql_config

    def mysql_create(self, connection, sql):
        """创建MySQL数据库或表"""
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
        finally:
            connection.close()

    def mysql_create_database(self, mysql_config, sql):
        """创建MySQL数据库"""
        import pymysql

        if self.mysql_config:
            mysql_config = self.mysql_config
        connection = pymysql.connect(**mysql_config)
        self.mysql_create(connection, sql)

    def mysql_create_table(self, mysql_config, sql):
        """创建MySQL表"""
        import pymysql

        if self.mysql_config:
            mysql_config = self.mysql_config
        mysql_config['db'] = 'weibo'
        connection = pymysql.connect(**mysql_config)
        self.mysql_create(connection, sql)

    def mysql_insert(self, mysql_config, table, data_list):
        """向MySQL表插入或更新数据"""
        import pymysql

        if len(data_list) > 0:
            keys = ', '.join(data_list[0].keys())
            values = ', '.join(['%s'] * len(data_list[0]))
            if self.mysql_config:
                mysql_config = self.mysql_config
            mysql_config['db'] = 'weibo'
            connection = pymysql.connect(**mysql_config)
            cursor = connection.cursor()
            sql = """INSERT INTO {table}({keys}) VALUES ({values}) ON
                     DUPLICATE KEY UPDATE""".format(table=table,
                                                    keys=keys,
                                                    values=values)
            update = ','.join([
                " {key} = values({key})".format(key=key)
                for key in data_list[0]
            ])
            sql += update
            try:
                cursor.executemany(
                    sql, [tuple(data.values()) for data in data_list])
                connection.commit()
            except Exception as e:
                connection.rollback()
                print('Error: ', e)
                traceback.print_exc()
            finally:
                connection.close()

    def weibo_to_mysql(self, wrote_num):
        """将爬取的微博信息写入MySQL数据库"""
        mysql_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'password': '123456',
            'charset': 'utf8mb4'
        }
        # 创建'weibo'表
        create_table = """
                CREATE TABLE IF NOT EXISTS weibo (
                id varchar(10) NOT NULL,
                user_id varchar(12),
                content varchar(2000),
                original_pictures varchar(1000),
                retweet_pictures varchar(1000),
                original BOOLEAN NOT NULL DEFAULT 1,
                video_url varchar(300),
                publish_place varchar(100),
                publish_time DATETIME NOT NULL,
                publish_tool varchar(30),
                up_num INT NOT NULL,
                retweet_num INT NOT NULL,
                comment_num INT NOT NULL,
                PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
        self.mysql_create_table(mysql_config, create_table)
        # 在'weibo'表中插入或更新微博数据
        weibo_list = []
        for weibo in self.weibo[wrote_num:]:
            weibo['user_id'] = self.user_id
            weibo_list.append(weibo)
        self.mysql_insert(mysql_config, 'weibo', weibo_list)
        print(u'%d条微博写入MySQL数据库完毕' % self.got_num)

    def write_data(self, wrote_num):
        """将爬取到的信息写入文件或数据库"""
        if self.got_num > wrote_num:
            self.write_csv(wrote_num)
            self.write_txt(wrote_num)
            if self.mysql_write:
                self.weibo_to_mysql(wrote_num)
            if self.mongodb_write:
                self.weibo_to_mongodb(wrote_num)

    def get_weibo_info(self):
        """获取微博信息"""
        try:
            url = 'https://weibo.cn/u/%s' % (self.user_id)
            print("get weibo info "+url)
            selector = self.deal_html(url)
            self.get_user_info(selector)  # 获取用户昵称、微博数、关注数、粉丝数
            page_num = self.get_page_num(selector)  # 获取微博总页数
            wrote_num = 0
            page1 = 0
            random_pages = random.randint(1, 5)
            for page in tqdm(range(1, page_num + 1), desc=u'进度'):
                is_end = self.get_one_page(page)  # 获取第page页的全部微博
                if is_end:
                    break

                if page % 20 == 0:  # 每爬20页写入一次文件
                    self.write_data(wrote_num)
                    wrote_num = self.got_num

                # 通过加入随机等待避免被限制。爬虫速度过快容易被系统限制(一段时间后限
                # 制会自动解除)，加入随机等待模拟人的操作，可降低被系统限制的风险。默
                # 认是每爬取1到5页随机等待6到10秒，如果仍然被限，可适当增加sleep时间
                if page - page1 == random_pages and page < page_num:
                    sleep(random.randint(6, 10))
                    page1 = page
                    random_pages = random.randint(1, 5)

            self.write_data(wrote_num)  # 将剩余不足20页的微博写入文件
            if not self.filter:
                print(u'共爬取' + str(self.got_num) + u'条微博')
            else:
                print(u'共爬取' + str(self.got_num) + u'条原创微博')
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()

    def get_user_list(self, file_name):
        """获取文件中的微博id信息"""
        with open(file_name, 'rb') as f:
            lines = f.read().splitlines()
            lines = [line.decode('utf-8') for line in lines]
            user_id_list = [
                line.split(' ')[0] for line in lines
                if len(line.split(' ')) > 0 and line.split(' ')[0].isdigit()
            ]
        return user_id_list

    def initialize_info(self, user_id):
        """初始化爬虫信息"""
        self.got_num = 0
        self.weibo = []
        self.user = {}
        self.user_id = user_id
        self.weibo_id_list = []

    def start(self, user_id_list):
        """运行爬虫"""
        try:
            for user_id in user_id_list:
                self.initialize_info(user_id)
                print('*' * 100)
                self.get_weibo_info()
                print(u'信息抓取完毕')
                print('*' * 100)
                if self.pic_download == 1:
                    self.download_files('img')
                if self.video_download == 1:
                    self.download_files('video')
        except Exception as e:
            print('Error: ', e)
            traceback.print_exc()


def main():
    try:
        # 以下是程序配置信息，可以根据自己需求修改
        filter = 1  # 值为0表示爬取全部微博（原创微博+转发微博），值为1表示只爬取原创微博
        since_date = '2018-01-01'  # 起始时间，即爬取发布日期从该值到现在的微博，形式为yyyy-mm-dd
        """值为0代表不将结果写入MongoDB数据库,1代表写入；若要写入MongoDB数据库，
        请先安装MongoDB数据库和pymongo，pymongo安装方法为命令行运行:pip install pymongo"""
        mongodb_write = 0
        """值为0代表不将结果写入MySQL数据库,1代表写入;若要写入MySQL数据库，
        请先安装MySQL数据库和pymysql，pymysql安装方法为命令行运行:pip install pymysql"""
        mysql_write = 0
        pic_download = 0  # 值为0代表不下载微博原始图片,1代表下载微博原始图片
        video_download = 0  # 值为0代表不下载微博视频,1代表下载微博视频

        wb = Weibo(filter, since_date, mongodb_write, mysql_write,
                   pic_download, video_download)

        # 下面是自定义MySQL数据库连接配置(可选)
        """因为操作MySQL数据库需要用户名、密码等参数，本程序默认为:
        mysql_config = {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'password': '123456',
            'charset': 'utf8mb4'
        }
        大家的参数配置如果和默认值不同，可以将上面的参数值替换成自己的，
        然后添加如下代码，使修改生效，如果你的参数和默认值相同则不需要下面的代码:
        wb.change_mysql_config(mysql_config)"""

        # 下面是配置user_id_list
        """user_id_list包含了要爬的目标微博id，可以是一个，也可以是多个，也可以从文件中读取
        爬单个微博，user_id_list如下所示，可以改成任意合法的用户id
        user_id_list = ['1669879400']
        爬多个微博，user_id_list如下所示，可以改成任意合法的用户id
        user_id_list = ['1669879400', '1729370543']
        也可以在文件中读取user_id_list，文件中可以包含很多user_id，
        每个user_id占一行，也可以在user_id后面加注释，如用户昵称，user_id和注释之间必需要有空格，
        文件名任意，类型为txt，位置位于本程序的同目录下，文件内容可以为如下形式：
        1223178222 胡歌
        1669879400 迪丽热巴
        1729370543 郭碧婷
        比如文件可以叫user_id_list.txt，读取文件中的user_id_list如下所示:
        user_id_list = wb.get_user_list('user_id_list.txt')"""
        user_id_list = ['2186152883']

        wb.start(user_id_list)  # 爬取微博信息
    except Exception as e:
        print('Error: ', e)
        traceback.print_exc()


if __name__ == '__main__':
    main()
