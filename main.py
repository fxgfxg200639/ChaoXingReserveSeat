import json
import time
import argparse
import os
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


from utils import reserve, get_user_credentials

get_current_time = lambda action: (
    time.strftime("%H:%M:%S", time.localtime(time.time() + 8 * 3600))
    if action
    else time.strftime("%H:%M:%S", time.localtime(time.time()))
)
get_current_dayofweek = lambda action: (
    time.strftime("%A", time.localtime(time.time() + 8 * 3600))
    if action
    else time.strftime("%A", time.localtime(time.time()))
)


SLEEPTIME = 0.5  # 每次抢座的间隔
ENDTIME = "22:10:00"  # 学校晚上22:00放号，抢到22:10即停

ENABLE_SLIDER = True  # 是否有滑块验证
MAX_ATTEMPT = 20  # 最大尝试次数
RESERVE_NEXT_DAY = True  # 晚上22:00放的是第二天的座位，预约明天


def login_and_reserve(users, usernames, passwords, action, success_list=None):
    logging.info(
        f"Global settings: \nSLEEPTIME: {SLEEPTIME}\nENDTIME: {ENDTIME}\nENABLE_SLIDER: {ENABLE_SLIDER}\nRESERVE_NEXT_DAY: {RESERVE_NEXT_DAY}"
    )
    if success_list is None:
        success_list = [False] * len(users)
    current_dayofweek = get_current_dayofweek(action)
    for index, user in enumerate(users):
        username, password, times, roomid, seatid, daysofweek = user.values()
        # 直接用config.json里的账号密码，不强制用secrets覆盖
        if current_dayofweek not in daysofweek:
            logging.info("Today not set to reserve")
            continue
        if not success_list[index]:
            logging.info(
                f"----------- {username} -- {times} -- {seatid} try -----------"
            )
            s = reserve(
                sleep_time=SLEEPTIME,
                max_attempt=MAX_ATTEMPT,
                enable_slider=ENABLE_SLIDER,
                reserve_next_day=RESERVE_NEXT_DAY,
            )
            s.get_login_status()
            s.login(username, password)
            s.requests.headers.update({"Host": "office.chaoxing.com"})
            suc = s.submit(times, roomid, seatid, action)
            success_list[index] = suc
    return success_list


def main(users, action=False):
    current_time = get_current_time(action)
    logging.info(f"start time {current_time}, action {'on' if action else 'off'}")
    attempt_times = 0
    usernames, passwords = None, None
    if action:
        usernames, passwords = get_user_credentials(action)
    success_list = None
    current_dayofweek = get_current_dayofweek(action)
    today_reservation_num = sum(
        1 for d in users if current_dayofweek in d.get("daysofweek")
    )
    # 手动触发（workflow_dispatch）时只抢一次，不受ENDTIME限制
    is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    if is_manual:
        logging.info("Manual trigger: reserve once regardless of time")
    while current_time < ENDTIME or is_manual:
        attempt_times += 1
        # try:
        success_list = login_and_reserve(
            users, usernames, passwords, action, success_list
        )
        # except Exception as e:
        #     print(f"An error occurred: {e}")
        print(
            f"attempt time {attempt_times}, time now {current_time}, success list {success_list}"
        )
        current_time = get_current_time(action)
        if sum(success_list) == today_reservation_num:
            print(f"reserved successfully!")
            return
        if is_manual:
            logging.info("Manual trigger done, exit")
            break


def debug(users, action=False):
    logging.info(
        f"Global settings: \nSLEEPTIME: {SLEEPTIME}\nENDTIME: {ENDTIME}\nENABLE_SLIDER: {ENABLE_SLIDER}\nRESERVE_NEXT_DAY: {RESERVE_NEXT_DAY}"
    )
    suc = False
    logging.info(f" Debug Mode start! , action {'on' if action else 'off'}")
    if action:
        usernames, passwords = get_user_credentials(action)
    current_dayofweek = get_current_dayofweek(action)
    for index, user in enumerate(users):
        username, password, times, roomid, seatid, daysofweek = user.values()
        if type(seatid) == str:
            seatid = [seatid]
        if action:
            username, password = (
                usernames.split(",")[index],
                passwords.split(",")[index],
            )
        if current_dayofweek not in daysofweek:
            logging.info("Today not set to reserve")
            continue
        logging.info(f"----------- {username} -- {times} -- {seatid} try -----------")
        s = reserve(
            sleep_time=SLEEPTIME,
            max_attempt=MAX_ATTEMPT,
            enable_slider=ENABLE_SLIDER,
            reserve_next_day=RESERVE_NEXT_DAY,
        )
        s.get_login_status()
        s.login(username, password)
        s.requests.headers.update({"Host": "office.chaoxing.com"})
        suc = s.submit(times, roomid, seatid, action)
        if suc:
            return


def get_roomid(args1, args2):
    username = input("请输入用户名：")
    password = input("请输入密码：")
    s = reserve(
        sleep_time=SLEEPTIME,
        max_attempt=MAX_ATTEMPT,
        enable_slider=ENABLE_SLIDER,
        reserve_next_day=RESERVE_NEXT_DAY,
    )
    s.get_login_status()
    s.login(username=username, password=password)
    s.requests.headers.update({"Host": "office.chaoxing.com"})
    encode = input("请输入deptldEnc：")
    s.roomid(encode)


# ==================== 签到功能 ====================

MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'


def do_checkin_one(username, password, roomid, seatnum):
    """对单个账号单个座位执行签到，返回(bool, str)"""
    from utils.reserve import reserve
    import json as _json
    try:
        logging.info(f"  登录 {username}...")
        s = reserve(sleep_time=0.2, max_attempt=3, enable_slider=True)
        s.get_login_status()
        ok, msg = s.login(username, password)
        if not ok:
            logging.error(f"  登录失败: {msg}")
            return False, f"登录失败: {msg}"
        logging.info(f"  登录成功")

        # 换手机UA
        old = dict(s.requests.headers)
        s.requests.headers = {k: v for k, v in old.items() if k not in ('User-Agent', 'Host', 'Content-Type')}
        s.requests.headers['User-Agent'] = MOBILE_UA
        s.requests.headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
        s.requests.headers['X-Requested-With'] = 'XMLHttpRequest'
        s.requests.headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'

        # 获取座位信息
        info_r = s.requests.post('https://office.chaoxing.com/data/apps/seat/reserve/info',
                                 data={'id': roomid, 'seatNum': seatnum}, verify=False, timeout=20)
        info = info_r.json()
        cfg = info.get('data', {}).get('seatConfig', {})
        seatReserve = info.get('data', {}).get('seatReserve', {})
        dept_id = str(cfg.get('deptId', '146550'))
        app_id = str(cfg.get('id', '3703'))

        if seatReserve:
            logging.info(f"  检测到预约: {seatReserve.get('firstLevelName','')} {seatReserve.get('seatNum','')}号")
        else:
            logging.warning(f"  未检测到该座位预约")
            return False, "未检测到该座位预约"

        # 获取图书馆位置
        addr_r = s.requests.post('https://office.chaoxing.com/data/apps/seat/address',
                                 data={'deptId': dept_id, 'roomId': roomid}, verify=False, timeout=20)
        addr = addr_r.json()
        address_arr = addr.get('data', {}).get('addressArr', [])

        # 上报位置
        if address_arr:
            first = address_arr[0]
            use_lng, use_lat = first['location'].split(',')[0], first['location'].split(',')[1]
            loc = {'location': f'{use_lng},{use_lat}', 'locationTemp': f'{use_lng},{use_lat}',
                   'offset': first.get('offset', 100), 'offsetReal': first.get('offsetReal', 1000),
                   'distance': 0, 'appType': 0, 'deptId': dept_id, 'appId': app_id, 'source': 1}
            loc_r = s.requests.get('https://office.chaoxing.com/data/apps/seat/add/location/log',
                                   params={'locationLogs': _json.dumps([loc])}, verify=False, timeout=20)
            logging.info(f"  位置上报: {use_lng},{use_lat}")

        # 提交签到
        reserve_id = seatReserve.get("id")
        if not reserve_id:
            return False, "未获取到预约记录id"
        logging.info(f"  提交签到(预约id={reserve_id})...")
        sign_r = s.requests.post('https://office.chaoxing.com/data/apps/seat/sign',
                                 data={'id': reserve_id}, verify=False, timeout=20)
        try:
            sign_json = sign_r.json()
        except Exception:
            sign_json = None
        logging.info(f"  签到接口返回: {sign_r.status_code} {sign_r.text[:120]}")

        if sign_json and sign_json.get("success"):
            return True, "签到成功"
        elif sign_json and not sign_json.get("success"):
            m = str(sign_json.get("msg", ""))
            if any(k in m for k in ("已签到", "已在使用", "正在使用", "已确认", "使用中", "重复签到")):
                return True, f"已签到/使用中({m})"
            if "不在签到时间" in m or "签到时间" in m or "无法签到" in m:
                # 查status确认
                try:
                    _re = s.requests.post('https://office.chaoxing.com/data/apps/seat/reserve/info',
                                          data={'id': roomid, 'seatNum': seatnum}, verify=False, timeout=15)
                    _status = _re.json().get('data', {}).get('seatReserve', {}).get('status')
                    if _status == 1:
                        return True, f"已签到/使用中(status=1)"
                    else:
                        return False, f"不在签到时间(status={_status})"
                except Exception:
                    return False, f"不在签到时间"
            return False, f"签到失败: {m}"
        return False, "签到接口无响应"
    except Exception as e:
        logging.exception("签到异常")
        return False, f"签到异常: {e}"


def checkin(users, action=False):
    """签到模式：检查当前时间是否在某账号预约开始时间±10分钟内，是则签到"""
    now = datetime.now()
    if action:
        now = datetime.utcnow() + timedelta(hours=8)
    now_hm = now.strftime("%H:%M")
    logging.info(f"签到检查，当前北京时间: {now_hm}")

    checked_any = False
    for user in users:
        username = user.get("username", "")
        password = user.get("password", "")
        times = user.get("time", ["08:30", "12:00"])
        roomid = str(user.get("roomid", ""))
        seatid = user.get("seatid", ["082"])
        if isinstance(seatid, str):
            seatid = [seatid]

        start_hm = times[0]  # 开始时间
        try:
            sh, sm = map(int, start_hm.split(":"))
        except Exception:
            continue
        # 签到窗口：开始时间前10分钟 ~ 后10分钟
        target = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        early = target - timedelta(minutes=10)
        late = target + timedelta(minutes=10)

        if not (early <= now <= late):
            logging.info(f"  {username} {start_hm} 不在签到窗口({early.strftime('%H:%M')}~{late.strftime('%H:%M')})，跳过")
            continue

        seatnum = seatid[0].zfill(3)
        logging.info(f"⏰ 到签到窗口: {username} 座位{roomid}/{seatnum} 开始{start_hm}")
        ok, msg = do_checkin_one(username, password, roomid, seatnum)
        if ok:
            logging.info(f"✅ 签到成功: {username} {seatnum}号 - {msg}")
        else:
            logging.error(f"❌ 签到失败: {username} {seatnum}号 - {msg}")
        checked_any = True

    if not checked_any:
        logging.info("当前没有需要签到的预约")
    logging.info("签到检查结束")


if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    parser = argparse.ArgumentParser(prog="Chao Xing seat auto reserve")
    parser.add_argument("-u", "--user", default=config_path, help="user config file")
    parser.add_argument(
        "-m",
        "--method",
        default="reserve",
        choices=["reserve", "debug", "room", "checkin"],
        help="for debug",
    )
    parser.add_argument(
        "-a",
        "--action",
        action="store_true",
        help="use --action to enable in github action",
    )
    args = parser.parse_args()
    func_dict = {"reserve": main, "debug": debug, "room": get_roomid, "checkin": checkin}
    with open(args.user, "r+") as data:
        usersdata = json.load(data)["reserve"]
    func_dict[args.method](usersdata, args.action)


