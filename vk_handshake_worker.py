"""
Created on 25.03.2020 15:23

Description: опрос сервера, вычисление цепочек

Author: YJ
"""

import os
import time
import json
import random
import requests
import threading
import configparser
import networkx as nx
from concurrent.futures import ThreadPoolExecutor, as_completed


class VkException(Exception):
    """
    Base class for exceptions in vk_handshake_worker.
    """

    def __init__(self, message, error_code):
        self.message = message
        self.error_code = error_code


class VkWorker:
    def __init__(self, graph_name='test', debug=False):
        self.graph_name = graph_name
        self._debug = debug
        self.api_v = '5.103'
        self.delay = 0.36
        self._result = {}
        self._database = {}
        self._download_queue = []
        self._max_in_set = 25
        self.max_nodes_in_graph_for_save = 1000000
        try:
            self.t = Token()
        except Exception:
            pass
        self._graphs_dir = os.path.join(os.path.dirname(__file__), 'Graphs')
        self._graph_path = os.path.join(self._graphs_dir, self.graph_name)
        if os.path.exists(self._graph_path):
            self.g = nx.read_adjlist(self._graph_path)
        else:
            self.g = nx.Graph(directed=False)

    def get_chains(self, id1='1', id2='1', max_chain_length=10):
        try:
            is_link1_valid, user1_name, user1_last_name, user1_photo, user1_id = self._check_vk_link(id1)
            is_link2_valid, user2_name, user2_last_name, user2_photo, user2_id = self._check_vk_link(id2)
            if not is_link1_valid or not is_link2_valid:
                return self._response(result_code=-2, result_description='Cannot resolve request with this parameters')
            self._debug_print('id1:', user1_name, user1_last_name, user1_photo, user1_id)
            self._debug_print('id2:', user2_name, user2_last_name, user2_photo, user2_id)
            self._debug_print('{} tokens work'.format(self.t.number_of_token))
            if user1_id == user2_id:
                return self._response(output_chains_list=[[user1_id]])
            while True:
                if self._is_paths_from_id1_to_id2(user1_id, user2_id, max_chain_length=max_chain_length):
                    self._save_graph()
                    return self._response(
                        output_chains_list=list(nx.all_shortest_paths(self.g, str(user1_id), str(user2_id))))
                self._download_queue_builder(user1_id, user2_id)
                self._database_builder()
                self._graph_builder()
                self._debug_print('{} tokens work'.format(self.t.number_of_token))
        except VkException as error:
            return self._response(result_code=error.args[1], result_description=error.args[0])
        except Exception:
            return self._response(result_code=-2)

    def _graph_builder(self):
        try:
            for i in self._database:
                self.g.add_node(str(i), a='1')  # для этого узла все друзья известны
                for j in self._database[i]:
                    self.g.add_edge(str(i), str(j))
            self._database = {}
            if self._debug:
                print('{} nodes in graph'.format(self.g.order()))
            return self.g
        except Exception as e:
            raise VkException('Graph error', -2)

    def _database_builder(self):
        try:
            broken_token_num_lst = []
            not_downloaded_set = []
            self.t.update()
            with ThreadPoolExecutor(max_workers=self.t.number_of_token, thread_name_prefix='.') as pool:
                future_list = [pool.submit(self._worker, i) for i in self._id_set(self._download_queue)]
            for f in as_completed(future_list):
                if f.result() is not None:
                    not_downloaded_set + f.result()[0]
                    broken_token_num_lst.append(f.result()[1])
            self._download_queue = not_downloaded_set
            self.t.update(broken_token_num_lst)
            self.t.save()
            return self._database
        except VkException as error:
            raise VkException(error.args[0], error.args[1])
        except Exception:
            raise VkException('_database_builder error', -2)

    def _worker(self, set):
        try:
            token_i = int(threading.current_thread().getName()[2:])
            r = requests.get(
                self._request_url('execute.deepFriends', 'targets=%s' % self._make_targets(set), token_i)).json()
            if 'error' in r.keys():
                if self._debug:
                    print('Error message: %s Error code: %s' % (r['error']['error_msg'], r['error']['error_code']))
            if 'execute_errors' in r.keys():
                if 'Rate limit reached' in [r['execute_errors'][i]['error_msg'] for i in
                                            range(len(r['execute_errors']))]:
                    return [set, token_i]
                if self._debug:
                    print('Execute errors: %s ' % (r['execute_errors']))
            r = r['response']
            for x, id in enumerate(set):
                if r[x]:
                    self._database[id] = tuple(r[x]["items"])
            time.sleep(self.delay)
        except VkException as error:
            raise VkException(error.args[0], error.args[1])
        except Exception:
            raise VkException('_worker error', -2)

    def _download_queue_builder(self, id1, id2):
        try:
            temp_download_queue = []
            id1_in_g = self.g.has_node(str(id1))
            id2_in_g = self.g.has_node(str(id2))
            if id1_in_g and id2_in_g:
                # without 'a' label
                temp_download_queue = list({k: v for k, v in dict(self.g.nodes(data='a')).items() if v is None}.keys())
            if not id1_in_g and not id2_in_g:
                temp_download_queue.append(id1)
                temp_download_queue.append(id2)
            else:
                if not id1_in_g:
                    temp_download_queue.append(id1)
                if not id2_in_g:
                    temp_download_queue.append(id2)
            random.shuffle(temp_download_queue)
            self._download_queue += temp_download_queue[:self._max_in_set * self.t.number_of_token]
            self._download_queue = list(set(self._download_queue))
            random.shuffle(self._download_queue)
            return self._download_queue
        except VkException as error:
            raise VkException(error.args[0], error.args[1])
        except Exception:
            raise VkException('_download_queue_builder error', -2)

    def _request_url(self, method_name, parameters, token_i):  # with token
        token = self.t.token_list[token_i]
        req_url = 'https://api.vk.com/method/{method_name}?{parameters}&v={api_v}&access_token={token}'.format(
            method_name=method_name, api_v=self.api_v, parameters=parameters, token=token)
        return req_url

    def _is_paths_from_id1_to_id2(self, id1, id2, max_chain_length=10):
        is_paths = False
        try:
            shortest_path_length = nx.shortest_path_length(self.g, str(id1), str(id2))
            if shortest_path_length <= max_chain_length:
                is_paths = True
        except nx.exception.NetworkXNoPath:
            is_paths = False
        except nx.exception.NodeNotFound:
            is_paths = False
        return is_paths

    def _save_graph(self):
        if self.g.order() > self.max_nodes_in_graph_for_save:
            os.remove(self._graph_path)
        else:
            nx.write_adjlist(self.g, self._graph_path)

    def _check_vk_link(self, link='1'):
        """
        Args:
            link: строка - ссылка на вк

        Returns: is_link_valid, r['first_name'], r['last_name'], r['photo'], r['id']

        """
        self._debug_print(link)
        try:
            link = link.split('/')[-1]
            self._debug_print(link)
            self.t.update()
            self.t.save()
            r = requests.get(self._request_url('users.get', 'user_ids=%s&fields=photo' % link, 0)).json()
            self._debug_print(r)
            time.sleep(self.delay)
            if 'error' in r.keys():
                return False, [], [], [], []
            r = r['response'][0]
            return True, r['first_name'], r['last_name'], r['photo'], r['id']
        except VkException as error:
            raise VkException(error.args[0], error.args[1])
        except Exception:
            raise VkException('_check_vk_link error', -2)

    def _base_info(self, ids, one_id=False):
        """
        Args:
            ids: список id
        Returns:    если нексолько id: слловарь {id1: {"first_name":"","last_name":"","photo":""}, id2: ...}
                    если один id: 'first_name', 'last_name', 'photo', 'id'  // 'id' - int
        """
        try:
            base_info_dict = {}
            ids = list(set(ids))
            ids_str = self._make_targets(ids)
            self.t.update()
            self.t.save()
            r = requests.get(self._request_url('users.get', 'user_ids=%s&fields=photo' % ids_str, 0)).json()
            self._debug_print(r)
            time.sleep(self.delay)
            if 'error' in r.keys():
                raise VkException('_base_info error', -2)
            r = r['response']
            for r_dict in r:
                base_info_dict.update(
                    {r_dict['id']: dict(first_name=r_dict['first_name'], last_name=r_dict['last_name'],
                                        photo=r_dict['photo'])})
            if len(base_info_dict.keys()) == 1 and one_id:
                id = list(base_info_dict.keys())[0]
                v = base_info_dict[id]
                return v['first_name'], v['last_name'], v['photo'], id
            return base_info_dict
        except VkException as error:
            raise VkException(error.args[0], error.args[1])
        except Exception:
            raise VkException('_base_info error', -2)

    def _base_info_collections(self, output_chains_list):
        id_in_output_chains = list(set([id for chain in output_chains_list for id in chain]))
        id_in_output_chains = [int(id) for id in id_in_output_chains]
        return self._base_info(id_in_output_chains)

    def _response(self, output_chains_list=[], result_code=1, result_description='Unknown error'):
        output = {}
        if result_code == 1:
            result_description = 'Success'
            try:
                all_chains_list = []
                max_num_of_chains = 20
                output_chains_list = output_chains_list[:max_num_of_chains]
                base_info_collections = self._base_info_collections(output_chains_list)
                for chain_num, chain in enumerate(output_chains_list):
                    chain_dict = {}
                    chain_list = []
                    for id in chain:
                        user_dict = {}
                        user_param = {}
                        if isinstance(id, str):
                            id = int(id)
                        user_name = base_info_collections[id]['first_name']
                        user_last_name = base_info_collections[id]['last_name']
                        user_photo = base_info_collections[id]['photo']
                        user_url = 'https://vk.com/id{}'.format(id)
                        user_param.update({"name": user_name})
                        user_param.update({"lastName": user_last_name})
                        user_param.update({"url": user_url})
                        user_param.update({"photo": user_photo})
                        user_dict.update({"user": user_param})
                        chain_list.append(user_dict)
                    chain_dict.update({"chain": chain_list})
                    all_chains_list.append(chain_dict)
                output.update({"result": all_chains_list})
                output.update({"resultCode": "{}".format(result_code)})
                output.update({"resultDescription": '{}'.format(result_description)})
            except VkException as error:
                return self._response(result_code=error.args[1], result_description=error.args[0])
            except Exception:
                VkException('_response error', -2)
        else:
            output.update({"result": ''})
            output.update({"resultCode": "{}".format(result_code)})
            output.update({"resultDescription": '{}'.format(result_description)})
        return json.dumps(output, sort_keys=True, indent=4, ensure_ascii=False, separators=(',', ': ')).encode()

    def _debug_print(self, *arg):
        if self._debug:
            print(*arg)

    def _id_set(self, lst):
        return (lst[i:i + self._max_in_set] for i in iter(range(0, len(lst), self._max_in_set)))

    @staticmethod
    def _make_targets(lst):
        return ",".join(str(id) for id in lst)


class Token:
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
            raise VkException('settings.ini is not exist', -2)
        else:
            self.config = configparser.ConfigParser()
            self.config.read(self._settings_path)
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
        try:
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
                    r = requests.get(
                        self._request_url('execute.deepFriends', 'targets=%s' % test_targets, token_i)).json()
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
                                self.config.set('token_{}'.format(self._returned_token_num_list[token_num]),
                                                'stop_time',
                                                '')
                                self.config.set('token_{}'.format(self._returned_token_num_list[token_num]), 'state',
                                                '1')
                                self.token_list.append(token_i)
                                self._returned_token_num_list.append(token_num)
                    else:
                        self._debug_print('ini \'state\' error')
                        raise VkException("ini \'state\' error", -2)
                self.number_of_token = len(self.token_list)
                if self.number_of_token == 0:
                    raise VkException("All token are broken", -2)
            return self.token_list
        except VkException as error:
            raise VkException(error.args[0], error.args[1])
        except Exception:
            raise VkException('Token.update error', -2)

    def _debug_print(self, *arg):
        if self.debug:
            print(*arg)


if __name__ == '__main__':
    w = VkWorker(graph_name='graph1', debug=True)
    print(w.get_chains(id1='й35и4уем', id2='100', max_chain_length=10).decode())
