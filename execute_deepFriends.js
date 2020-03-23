var targets = Args.targets;
var all_friends = {};
var req;
var parametr = "";
var start = 0;
// из строки с целями вынимаем каждую цель
while(start<=targets.length){
    if (targets.substr(start, 1) != "," && start != targets.length){
        parametr = parametr + targets.substr(start, 1);
    }
    else {
        // сразу делаем запросы, как только вытащили id
        req = API.friends.get({"user_id":parametr});
        if (req) {
            all_friends = all_friends + [req];
        }
        else {
            all_friends = all_friends + [0];
        }
        parametr = "";
    }
    start = start + 1;
}
return all_friends;


deepFriends

var targets = Args.targets;
var targets_arr = targets.split(",");
var all_friends = {};
var req;
var parametr = "";
var i = 0;
while(i<targets_arr.length){
    req = API.friends.get({"user_id":targets_arr[i]});
    if (req) {
        all_friends = all_friends + [req];
    }
    else {
        all_friends = all_friends + [0];
    }
    i = i + 1;
}
return all_friends;