# VK-Handshakes(NetStalking)
Клиент-серверное приложение для Нет-сталкинга ВК, с оновной фичей - построение цепочек рукопожатий между пользователями

## Autors 
- Pavlov Max
- Julikov Yaroslav

# Server

## Server response without params
- IP:8088

## List of availible API methods

- `/?method=handshake&users=id100,id200`
- `...`

## Result Codes - Result Description
- `0` - Success with nothing (API is alive)
- `1` - Success

- `-2` - Cannot resolve request with this parameters
- `-2` - Unknown error
- `-2` - All token are broken
- `-2` - settings.ini is not exist
- `-2` - ini \'state\' error
- `-2` - Graph error
- `-2` - _base_info error
- `-2` - _response error
- `-2` - _database_builder error
- `-2` - _worker error
- `-2` - _download_queue_builder error
- `-2` - _check_vk_link error
- `-2` - Token.update error

## Future Features

- Выбрать минимальную глубину цепочки
- Смежные друзья для n-ного количества пользователей
- Смежные лайки на нескольких постах
- Вычисление возраста по друзьям
- Вычисление города по друзьям
- Вычисление инстаграма
- Дата создания страницы

## Response Example
```
{
"resultCode": "1",
"resultDescription": "Success",
"result": "..."
}
```


## Run Script On VDS
### Update
- `ssh root@<SSH IP>` - Connect to SSH
- `<enter password to SSH>` - Password to SSH
- `cd /home/h/VKHandShakes-Server/` - Open server-project directory
- `git pull origin master` - pull changes from master
- `<enter username>` - enter GIT username (used 1 time for SSH session)
- `<enter password>` - enter GIT password (used 1 time for SSH session)

### Run
- `python3.8 /home/h/VKHandShakes-Server/server.py` - run server python script
- `nohup` - for unlimitless script
# Front IOS-App
...
