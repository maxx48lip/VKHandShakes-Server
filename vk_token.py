"""
Created on 02.04.2020 1:01

Description: класс Token

Author: YJ
"""
import os
import configparser
import time
import requests

class VKToken:
    """
    Метод update возвращает список рабочих токенов
    Метод save сохраняет settings.ini
    """

    def __init__(self, debug=False):
        self.debug = debug
        self._settings_path = os.path.join(os.path.dirname(__file__), 'settings.ini')
        self._returned_token_num_list = []
        self.token_list = []
        self.number_of_token = 0
        self._api_v = '5.103'
        if not os.path.exists(self._settings_path):
            self._debug_print('settings.ini is not exist')
            return
        else:
            self.config = configparser.ConfigParser()
            self.config.read(self._settings_path)
            print(self.config)
            self.token_list = self.update(update=True)

    def _request_url(self, method_name, parameters, token_i):  # with token
        req_url = 'https://api.vk.com/method/{method_name}?{parameters}&v={api_v}&access_token={token}'.format(
            method_name=method_name, api_v=self._api_v, parameters=parameters, token=token_i)
        return req_url

    def save(self):
        with open(self._settings_path, 'w') as configfile:
            self.config.write(configfile)

    def update(self, broken_token_num_lst=[], update=False):
        """
        broken_token_num_lst не уазывается при первом вызове
        broken_token_num_lst = [0, 1, ...]
        _returned_token_num_list = [0, 1, ...]
        Returns: возвращает список рабочих токенов
        """
        self.token_list = []
        self._returned_token_num_list = []
        test_targets = '10'
        stop_period = 3600  # время, на протяжении которого токен недоступен после превышения количества запросов

        if len(broken_token_num_lst) != 0:
            for token_num in broken_token_num_lst:
                self.config.set('token_{}'.format(self._returned_token_num_list[token_num]), 'stop_time',
                                str(time.time()))
                self.config.set('token_{}'.format(self._returned_token_num_list[token_num]), 'state', '0')

        number_of_tokens = int(self.config.get('settings', 'number_of_tokens'))
        for token_num in range(number_of_tokens):
            token_i = self.config.get('token_{}'.format(token_num + 1), 'value')
            if update:
                r = requests.get(self._request_url('execute.deepFriends', 'targets=%s' % test_targets, token_i)).json()
                if 'error' not in r.keys() and 'execute_errors' not in r.keys():
                    self.config.set('token_{}'.format(token_num + 1), 'stop_time', '')
                    self.config.set('token_{}'.format(token_num + 1), 'state', '1')
                    self.token_list.append(token_i)
                    self._returned_token_num_list.append(token_num)
                else:
                    self.config.set('token_{}'.format(token_num + 1), 'stop_time', str(time.time()))
                    self.config.set('token_{}'.format(token_num + 1), 'state', '0')
            else:
                if self.config.get('token_{}'.format(token_num + 1), 'state') == '1':
                    self.token_list.append(token_i)
                elif self.config.get('token_{}'.format(token_num + 1), 'state') == '0':
                    stop_time = self.config.get('token_{}'.format(token_num + 1), 'stop_time')
                    if stop_time == '':
                        stop_time = '0'
                    if time.time() - float(stop_time) > stop_period:
                        r = requests.get(
                            self._request_url('execute.deepFriends', 'targets=%s' % test_targets, token_i)).json()
                        if 'error' not in r.keys() and 'execute_errors' not in r.keys():
                            self.config.set('token_{}'.format(self._returned_token_num_list[token_num]), 'stop_time',
                                            '')
                            self.config.set('token_{}'.format(self._returned_token_num_list[token_num]), 'state', '1')
                            self.token_list.append(token_i)
                            self._returned_token_num_list.append(token_num)
                else:
                    self._debug_print('ini \'state\' error')
                    return
            self.number_of_token = len(self.token_list)
        return self.token_list

    def _debug_print(self, *arg):
        if self.debug:
            print(*arg)
