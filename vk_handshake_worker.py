"""
Created on 25.03.2020 15:23

Description: опрос сервера, весисление цепочек

Author: YJ
"""

import configparser
import os
import time
import requests
import networkx as nx
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import json
from vk_token import VKToken


class VkException(Exception):
    # TODO: избавиться от этого класса
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class VkWorker:
    def __init__(self, graph_name='test', debug=False):
        self.graph_name = graph_name
        self._debug = debug
        self.api_v = '5.103'
        self.delay = 0.35
        self._result = {}
        self._database = {}
        self._download_queue = []
        self._max_in_set = 25
        self.t = VKToken(debug=True)
        self._graphs_dir = os.path.join(os.path.dirname(__file__), 'Graphs')
        self._graph_path = os.path.join(self._graphs_dir, self.graph_name)
        if os.path.exists(self._graph_path):
            self.g = nx.read_adjlist(self._graph_path)
        else:
            self.g = nx.Graph(directed=False)

    def get_chains(self, id1, id2):
        # TODO: цпочки заданной длины (меньше или больше и тд)
        user1_name, user1_last_name, user1_photo, user1_id = self.base_info(id1)
        user2_name, user2_last_name, user2_photo, user2_id = self.base_info(id2)
        self._debug_print('id1:', user1_name, user1_last_name, user1_photo, user1_id)
        self._debug_print('id2:', user2_name, user2_last_name, user2_photo, user2_id)
        while True:
            if self._is_paths_from_id1_to_id2(user1_id, user2_id):
                return self.make_output_json(list(nx.all_shortest_paths(self.g, user1_id, user2_id)))
            self._download_queue_builder(user1_id, user2_id)
            self._database_builder()
            self._graph_builder()

    def _graph_builder(self):
        for i in self._database:
            self.g.add_node(i, a='1')  # для этого узла все друзья известны
            for j in self._database[i]:
                self.g.add_edge(i, j)
        self._save_graph()
        return self.g

    def _database_builder(self):
        self.t.update()
        broken_token_num_lst = []
        not_downloaded_set = []
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

    def _worker(self, set):
        token_i = int(threading.current_thread().getName()[2:])
        r = requests.get(
            self._request_url('execute.deepFriends', 'targets=%s' % self._make_targets(set), token_i)).json()
        if 'error' in r.keys():
            self._debug_print('Error message: %s Error code: %s' % (r['error']['error_msg'], r['error']['error_code']))
        if 'execute_errors' in r.keys():
            if 'Rate limit reached' in [r['execute_errors'][i]['error_msg'] for i in range(len(r['execute_errors']))]:
                return [set, token_i]
            self._debug_print('Execute errors: %s ' % (r['execute_errors']))
        r = r['response']
        for x, id in enumerate(set):
            if r[x]:
                self._database[id] = tuple(r[x]["items"])
        self._debug_print('ids_counter = ' + str(len(self._database)))
        time.sleep(self.delay)

    def _download_queue_builder(self, id1, id2):
        temp_download_queue = []
        id1_in_g = self.g.has_node(id1)
        id2_in_g = self.g.has_node(id2)
        if id1_in_g and id2_in_g:
            # without a label
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

    def _request_url(self, method_name, parameters, token_i):  # with token
        token = self.t.token_list[token_i]
        req_url = 'https://api.vk.com/method/{method_name}?{parameters}&v={api_v}&access_token={token}'.format(
            method_name=method_name, api_v=self.api_v, parameters=parameters, token=token)
        return req_url

    def _is_paths_from_id1_to_id2(self, id1, id2):
        is_paths = False
        try:
            lst = list(nx.all_shortest_paths(self.g, id1, id2))
            is_paths = True
        except nx.exception.NetworkXNoPath:
            is_paths = False
        except nx.exception.NodeNotFound:
            is_paths = False
        return is_paths

    def _save_graph(self):
        nx.write_adjlist(self.g, self._graph_path)

    def base_info(self, ids):
        self.t.update()
        self.t.save()
        r = requests.get(
            self._request_url('users.get', 'user_ids=%s&fields=photo' % ids, 0)).json()
        if 'error' in r.keys():
            raise VkException('Error message: %s Error code: %s' % (r['error']['error_msg'], r['error']['error_code']))
        r = r['response'][0]
        if 'deactivated' in r.keys():
            raise VkException("User deactivated")
        return r['first_name'], r['last_name'], r['photo'], r['id']  # r['id'] - int

    def _debug_print(self, *arg):
        if self._debug:
            print(*arg)

    def _id_set(self, lst):
        return (lst[i:i + self._max_in_set] for i in iter(range(0, len(lst), self._max_in_set)))

    def make_output_json(self, output_chains_list, result_code=None, result_description=None):
        output = {}
        all_chains_list = []
        for chain in output_chains_list:
            chain_dict = {}
            chain_list = []
            for id in chain:
                user_dict = {}
                user_param = {}
                if isinstance(id, str):
                    id = int(id)
                user_name, user_last_name, user_photo, user_id = self.base_info(id)
                user_url = 'https://vk.com/id{}'.format(id)
                user_param.update({"name": user_name})
                user_param.update({"last_name": user_last_name})
                user_param.update({"url": user_url})
                user_param.update({"photo": user_photo})
                user_dict.update({"user": user_param})
                chain_list.append(user_dict)
            chain_dict.update({"chain": chain_list})
            all_chains_list.append(chain_dict)
        output.update({"result": all_chains_list})
        output.update({"resultCode": "1"})
        output.update({"resultDescription": 'Success'})
        return json.dumps(output, sort_keys=True, indent=4, ensure_ascii=False, separators=(',', ': ')).encode()

    @staticmethod
    def _make_targets(lst):
        return ",".join(str(id) for id in lst)


if __name__ == '__main__':
    w = VkWorker(graph_name='test', debug=True)
    print(w.get_chains('221436497', 'sasha_gt'))

# TODO: Traceback (most recent call last):
#   File "D:/Desktop/1/!!!projects/vk_kandshake/VKHandShakes-Server/API Files/vk_handshake_worker.py", line 280, in <module>
#     print(w.get_chains('221436497', 'sashaspilberg'))
#   File "D:/Desktop/1/!!!projects/vk_kandshake/VKHandShakes-Server/API Files/vk_handshake_worker.py", line 55, in get_chains
#     return self.make_output_json(list(nx.all_shortest_paths(self.g, user1_id, user2_id)))
#   File "D:/Desktop/1/!!!projects/vk_kandshake/VKHandShakes-Server/API Files/vk_handshake_worker.py", line 171, in make_output_json
#     user_name, user_last_name, user_photo, user_id = self.base_info(id)
#   File "D:/Desktop/1/!!!projects/vk_kandshake/VKHandShakes-Server/API Files/vk_handshake_worker.py", line 147, in base_info
#     raise VkException('Error message: %s Error code: %s' % (r['error']['error_msg'], r['error']['error_code']))
# __main__.VkException: Error message: Too many requests per second Error code: 6
